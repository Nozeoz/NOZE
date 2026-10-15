"""Ranking: hybrid search, "more like this", and the personalized home feed.

How a search is ranked (roughly what Pinterest does, at personal scale):

1. candidates from several independent signals
   - what each source's own search engine returned for this query
   - keyword/BM25 over titles, tags, descriptions (SQLite FTS5)
   - vibe vectors (CLIP or the lightweight hash+color vectors)
2. Reciprocal Rank Fusion to merge them
3. boosts: your taste vector, color match, popularity
4. MMR diversification so one look/source doesn't flood the grid
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from .context import Context
from .db import Filters
from .harvest import RELATED_KINDS
from .imaging import color_match, informative_hash, palette_similarity
from .lexicon import ParsedQuery, normalize_key, parse_query
from .models import expand_kinds, expand_usages
from .ranking import mmr, normalize, rrf

# the home feed is a visual mood board first; fonts/icons/sounds/code show up when you ask for them
VISUAL_BOOST = {"image": 0.12, "video": 0.12, "gif": 0.1, "motion": 0.08, "texture": 0.08, "hdri": 0.06,
                "3d": 0.06, "link": 0.04}

MIN_RELEVANCE = 0.5

ACTION_WEIGHTS = {"view": 0.3, "open": 1.0, "copy": 1.0, "save": 3.0, "download": 3.5, "unsave": -1.0, "hide": -4.0}


@dataclass
class SearchRequest:
    q: str = ""
    kinds: list[str] | None = None
    usages: list[str] | None = None
    sources: list[str] | None = None
    color: str | None = None
    page: int = 1
    per_page: int = 40
    live: bool = True
    auto_filters: bool = True
    mode: str = ""  # "inspiration" = visual kinds unless the query asks for something else


# Default "Inspiration" mode: what a mood board is made of. Icons, fonts, Lottie, audio,
# code and 3D only join when you ask for them (chip or words like "font", "sfx", "lottie").
INSPIRATION_KINDS = {"image", "gif", "video", "link", "texture"}

_WORD = re.compile(r"[a-z0-9]+")


def _stem(w: str) -> str:
    for suf in ("ing", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in _WORD.findall((text or "").lower())}


def lexical_coverage(words: list[str], a: dict[str, Any]) -> tuple[float, float]:
    """(share of query words in title/tags, overall share where a description hit counts 0.6)."""
    if not words:
        return 0.0, 0.0
    strong = _tokens((a.get("title") or "") + " " + " ".join(a.get("tags") or []))
    weak = _tokens((a.get("description") or "")[:600])
    hard = soft = 0.0
    for w in words:
        sw = _stem(w)
        if sw in strong or (len(sw) >= 5 and any(t.startswith(sw) for t in strong)):
            hard += 1.0
            soft += 1.0
        elif sw in weak:
            soft += 0.6
    return hard / len(words), soft / len(words)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class Ranker:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.db = ctx.db
        self._taste_cache: tuple[float, np.ndarray | None, list[str]] | None = None

    # -- helpers ---------------------------------------------------------------
    def resolve_filters(self, req: SearchRequest, pq: ParsedQuery) -> tuple[Filters, dict[str, Any]]:
        applied: dict[str, Any] = {}
        kinds = expand_kinds(req.kinds or [])
        if not kinds and req.auto_filters and pq.kinds:
            kinds = set(pq.kinds)
            applied["kinds"] = sorted(kinds)
        if not kinds and req.mode == "inspiration":
            kinds = set(INSPIRATION_KINDS)
        usages = expand_usages(req.usages or [])
        if not usages and req.auto_filters and pq.usage:
            usages = expand_usages([pq.usage])
            applied["usage"] = pq.usage
        sources = {s for s in (req.sources or []) if s}
        return Filters(kinds=kinds or None, usages=usages or None, sources=sources or None), applied

    def _group_of(self, rows: dict[str, dict[str, Any]]):
        # diversify across sources AND kinds
        return lambda aid: "{source}/{kind}".format(**{"source": "", "kind": "", **(rows.get(aid) or {})})

    def _dupe_of(self, rows: dict[str, dict[str, Any]]):
        def dupe(aid: str) -> str | None:
            d = (rows.get(aid) or {}).get("dhash")
            return d if informative_hash(d) else None
        return dupe

    def taste(self) -> tuple[np.ndarray | None, list[str]]:
        """Your taste = decayed, weighted average of vectors of things you opened/saved/downloaded."""
        if self._taste_cache and time.time() - self._taste_cache[0] < 60:
            return self._taste_cache[1], self._taste_cache[2]
        rows = self.db.interactions_since(time.time() - 120 * 86400, limit=3000)
        acc = None
        tag_w: dict[str, float] = {}
        assets = self.db.get_assets(r["asset_id"] for r in rows) if rows else {}
        for r in rows:
            w = ACTION_WEIGHTS.get(r["action"], 0.0) * 0.5 ** ((time.time() - r["ts"]) / (30 * 86400))
            if not w:
                continue
            v = self.ctx.index.get(r["asset_id"])
            if v is not None:
                acc = v * w if acc is None else acc + v * w
            if w > 0:
                for t in (assets.get(r["asset_id"]) or {}).get("tags") or []:
                    tag_w[t] = tag_w.get(t, 0.0) + w
        vec = None
        if acc is not None and float(np.linalg.norm(acc)) > 0:
            vec = acc / float(np.linalg.norm(acc))
        tags = [t for t, _ in sorted(tag_w.items(), key=lambda x: -x[1])[:12]]
        self._taste_cache = (time.time(), vec, tags)
        return vec, tags

    def _finish(self, fused: dict[str, float], filters: Filters, color: str | None = None,
                taste_weight: float = 0.12, extra_boost: dict[str, float] | None = None,
                exclude: set[str] | None = None, candidates: int = 900, saved_penalty: float = 0.0,
                kind_boost: dict[str, float] | None = None, relevance: dict[str, float] | None = None) -> list[str]:
        if exclude:
            fused = {k: v for k, v in fused.items() if k not in exclude}
        ordered = sorted(fused, key=lambda k: -fused[k])[:candidates]
        ordered = self.db.filter_ids(ordered, filters)
        if not ordered:
            return []
        rows = self.db.get_assets(ordered)
        scores = normalize({k: fused[k] for k in ordered})
        taste_vec, _ = self.taste()
        max_pop = max((math.log1p(max(0.0, (rows.get(k) or {}).get("popularity") or 0.0)) for k in ordered), default=0) or 1.0
        for k in ordered:
            r = rows.get(k) or {}
            s = scores[k]
            if relevance is not None:
                s = 0.45 * s + 0.55 * relevance.get(k, 0.0)
            s += 0.04 * math.log1p(max(0.0, r.get("popularity") or 0.0)) / max_pop
            if color:
                s += 0.6 * color_match(r.get("colors"), color)
            if taste_vec is not None and taste_weight:
                v = self.ctx.index.get(k)
                if v is not None:
                    s += taste_weight * max(0.0, float(v @ taste_vec))
            if extra_boost:
                s += extra_boost.get(k, 0.0)
            if saved_penalty and r.get("saved"):
                s += saved_penalty
            if kind_boost:
                s += kind_boost.get(r.get("kind") or "", 0.0)
            scores[k] = s
        ordered.sort(key=lambda k: -scores[k])
        return mmr(ordered, scores, self.ctx.index, group_of=self._group_of(rows), duplicate_of=self._dupe_of(rows))

    # -- search --------------------------------------------------------------------
    def rank_query(self, pq: ParsedQuery, filters: Filters, color: str | None = None) -> list[str]:
        text = pq.text or pq.raw
        lists: list[tuple[list[str], float]] = []
        hits = self.db.query_hits(normalize_key(text)) if text else []
        if hits:
            # interleave sources by their own rank so no single source dominates
            per_source: dict[str, int] = {}
            ranked = []
            for aid, src, rank in hits:
                per_source[src] = per_source.get(src, 0) + 1
                ranked.append((per_source[src], rank, aid))
            ranked.sort()
            lists.append(([aid for _, _, aid in ranked], 1.0))
        terms = pq.terms or text.split()
        fts = self.db.fts_search(terms, filters, limit=600) if terms else []
        lists.append(([aid for aid, _ in fts], 1.0))
        colors = list(pq.colors) + ([color] if color else [])
        qv = self.ctx.query_vector(text, colors)
        if qv is not None:
            vec_hits = self.ctx.index.search(qv, k=500)
            lists.append(([aid for aid, _ in vec_hits], 1.3 if self.ctx.semantic else 0.5))
        fused = rrf(lists)
        target = color or (pq.colors[0] if pq.colors else None)
        relevance = self.relevance(pq, list(fused), qv, hit_ids={h[0] for h in hits})
        fused = {k: v for k, v in fused.items() if relevance.get(k, 0.0) >= MIN_RELEVANCE}
        return self._finish(fused, filters, color=target, relevance=relevance)

    def relevance(self, pq: ParsedQuery, ids: list[str], qv: np.ndarray | None,
                  hit_ids: set[str] | None = None) -> dict[str, float]:
        """0..1: does this asset actually match the query? Words in its title/tags, or (with
        CLIP) a picture that is unusually close to the query. Cuts the long irrelevant tail."""
        words = [w for w in (pq.text or pq.raw).lower().split() if w]
        originals = [w for w in pq.terms if w not in words]
        rows = self.db.get_assets(ids)
        z = self.ctx.index.zscores(qv, ids) if qv is not None else {}
        trusted = {name for name, cls in self.ctx.source_classes.items() if getattr(cls, "trust_match", False)}
        out: dict[str, float] = {}
        for k in ids:
            a = rows.get(k)
            if not a:
                continue
            strong, lex = lexical_coverage(words, a)
            if originals:
                o_strong, o_lex = lexical_coverage(originals, a)
                strong, lex = max(strong, o_strong), max(lex, o_lex)
            zk = z.get(k)
            if zk is None:
                sem = 0.0
            elif self.ctx.semantic:
                sem = _sigmoid(1.8 * (zk - 1.6))  # z≈1.6 → 0.5, z≈2.6 → 0.86
            else:
                sem = 0.5 * _sigmoid(1.5 * (zk - 2.0))  # hash vectors are just words + colors
            lex = lex ** 1.4  # half the words isn't half relevant: "y2k" alone ≠ "y2k chrome"
            rel = max(lex, sem, 0.7 * lex + 0.5 * sem)
            if hit_ids and k in hit_ids:
                if a["source"] in trusted:
                    rel = max(rel, 0.6)  # sources that match on tags/vibes the text doesn't show
                elif strong > 0 or sem > 0.3:
                    rel += 0.1  # the source's own search engine picked it for this query
            out[k] = min(1.0, rel)
        return out

    def browse(self, filters: Filters, seed: int) -> list[str]:
        lists = [
            (self.db.recent_ids(filters, 400), 1.0),
            (self.db.random_ids(filters, 400, seed), 0.8),
        ]
        return self._finish(rrf(lists), filters, taste_weight=0.2,
                            kind_boost=None if filters.kinds else VISUAL_BOOST)

    # -- more like this ----------------------------------------------------------------
    def related(self, asset_id: str, filters: Filters | None = None) -> list[str]:
        a = self.db.get_asset(asset_id)
        if not a:
            return []
        if filters is None or not filters.kinds:
            base = filters or Filters()
            filters = Filters(kinds=RELATED_KINDS.get(a["kind"], {a["kind"]}), usages=base.usages,
                              sources=base.sources)
        lists: list[tuple[list[str], float]] = []
        v = self.ctx.index.get(asset_id)
        if v is not None:
            lists.append(([k for k, _ in self.ctx.index.search(v, k=500, exclude={asset_id})],
                          1.4 if self.ctx.semantic else 0.9))
        co = self.db.co_saved(asset_id)
        if co:
            lists.append(([k for k, _ in co], 1.2))
        nb = self.db.neighbors(asset_id)
        if nb:
            lists.append(([k for k, _ in nb], 1.1))
        terms = list(a.get("tags") or [])[:10] + (a.get("title") or "").split()[:6]
        if terms:
            lists.append(([k for k, _ in self.db.fts_search(terms, filters, limit=400)], 0.8))
        by_author = self.db.ids_by_author(a["source"], a.get("author") or "", filters)
        if by_author:
            lists.append((by_author, 0.3))
        fused = rrf(lists)
        exclude = {asset_id}
        if informative_hash(a.get("dhash")):
            exclude |= set(self.db.dhash_duplicates(a["dhash"]))
        colors = a.get("colors")
        boost = {}
        if colors:
            rows = self.db.get_assets(list(fused)[:900])
            boost = {k: 0.25 * palette_similarity(colors, (rows.get(k) or {}).get("colors")) for k in rows}
        return self._finish(fused, filters, extra_boost=boost, exclude=exclude, taste_weight=0.06)

    # -- home feed --------------------------------------------------------------------------
    def feed(self, filters: Filters, seed: int) -> list[str]:
        taste_vec, taste_tags = self.taste()
        lists: list[tuple[list[str], float]] = []
        if taste_vec is not None:
            lists.append(([k for k, _ in self.ctx.index.search(taste_vec, k=500)], 1.2))
        recent_saves = [r["asset_id"] for r in self.db.interactions_since(time.time() - 60 * 86400, 200)
                        if r["action"] in ("save", "download")][:8]
        if recent_saves:
            interleaved: list[str] = []
            neigh = []
            for aid in recent_saves:
                v = self.ctx.index.get(aid)
                if v is not None:
                    neigh.append([k for k, _ in self.ctx.index.search(v, k=60, exclude={aid})])
            for i in range(60):
                for n in neigh:
                    if i < len(n):
                        interleaved.append(n[i])
            lists.append((interleaved, 1.0))
        if taste_tags:
            lists.append(([k for k, _ in self.db.fts_search(taste_tags, filters, limit=400)], 0.7))
        lists.append((self.db.recent_ids(filters, 400), 0.6 if lists else 1.0))
        lists.append((self.db.random_ids(filters, 400, seed), 0.45 if len(lists) > 1 else 0.9))
        # things you already saved show up less, like Pinterest's home feed
        return self._finish(rrf(lists), filters, taste_weight=0.2, saved_penalty=-0.25,
                            kind_boost=None if filters.kinds else VISUAL_BOOST)


def page_slice(ids: list[str], page: int, per_page: int) -> list[str]:
    start = max(0, (page - 1) * per_page)
    return ids[start:start + per_page]


def describe_query(pq: ParsedQuery, applied: dict[str, Any]) -> dict[str, Any]:
    return {"raw": pq.raw, "text": pq.text, "translated": pq.translated, "kinds": sorted(pq.kinds),
            "usage": pq.usage, "colors": pq.colors, "vibes": pq.vibes, "applied": applied}


__all__ = ["Ranker", "SearchRequest", "page_slice", "describe_query", "parse_query"]
