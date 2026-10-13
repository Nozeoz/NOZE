"""Fan a query out to every relevant source, normalize, and bank the results.

Everything a source returns is stored (metadata + later a cached thumbnail),
so the next time you search the same vibe it's answered locally — "ga crawl
lagi". Each (query, source, page) is cached for NOZE_CACHE_TTL_HOURS.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any

from .context import Context
from .db import now
from .http import Http, RateLimited, SourceError
from .lexicon import ParsedQuery, normalize_key, parse_query
from .models import Asset, Kind
from .sources import DownloadPart, Source, build_sources
from .storage import guess_ext

log = logging.getLogger("noze.harvest")

# what "more like this" may mix with, per kind
RELATED_KINDS = {
    Kind.IMAGE: {Kind.IMAGE, Kind.GIF, Kind.LINK, Kind.VIDEO, Kind.MOTION, Kind.TEXTURE, Kind.HDRI},
    Kind.GIF: {Kind.GIF, Kind.VIDEO, Kind.MOTION, Kind.IMAGE},
    Kind.VIDEO: {Kind.VIDEO, Kind.GIF, Kind.MOTION, Kind.IMAGE},
    Kind.MOTION: {Kind.MOTION, Kind.GIF, Kind.VIDEO, Kind.ICON},
    Kind.LINK: {Kind.LINK, Kind.IMAGE, Kind.GIF, Kind.VIDEO},
    Kind.AUDIO: {Kind.AUDIO},
    Kind.FONT: {Kind.FONT},
    Kind.ICON: {Kind.ICON, Kind.MOTION},
    Kind.CODE: {Kind.CODE, Kind.TEMPLATE},
    Kind.TEMPLATE: {Kind.TEMPLATE, Kind.CODE},
    Kind.MODEL3D: {Kind.MODEL3D, Kind.TEXTURE, Kind.HDRI},
    Kind.TEXTURE: {Kind.TEXTURE, Kind.IMAGE, Kind.HDRI, Kind.MODEL3D},
    Kind.HDRI: {Kind.HDRI, Kind.TEXTURE, Kind.IMAGE},
}


def group_edges(assets: list[Asset], ids: list[str], fanout: int = 8) -> list[tuple[str, str, str, float]]:
    """Items a source says belong together (an Are.na channel, a board…) become graph edges:
    that co-curation signal is what makes Pinterest's "more like this" feel human."""
    groups: dict[str, list[str]] = {}
    sizes: dict[str, int] = {}
    for a, aid in zip(assets, ids):
        g = a.extra.get("group")
        if g:
            groups.setdefault(g, []).append(aid)
            sizes[g] = int(a.extra.get("group_size") or 0)
    edges: list[tuple[str, str, str, float]] = []
    for g, members in groups.items():
        weight = 1.0 / math.log(2.0 + max(sizes.get(g) or 0, len(members)))
        for i, a in enumerate(members):
            for b in members[i + 1:i + 1 + fanout]:
                edges.append((a, b, "group", weight))
    return edges


@dataclass
class HarvestReport:
    query: str
    page: int
    sources: dict[str, str] = field(default_factory=dict)
    new_items: int = 0
    pending: list[str] = field(default_factory=list)
    exhausted: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"query": self.query, "page": self.page, "sources": self.sources, "new_items": self.new_items,
                "pending": self.pending, "exhausted": self.exhausted}


class Harvester:
    def __init__(self, ctx: Context, http: Http):
        self.ctx = ctx
        self.db = ctx.db
        self.http = http
        self.sources: dict[str, Source] = build_sources(ctx.settings, http)
        self._background: set[asyncio.Task] = set()

    def active_sources(self, kinds: set[str] | None = None, only: set[str] | None = None) -> list[Source]:
        out = []
        for s in self.sources.values():
            if not s.enabled or not s.supports(kinds):
                continue
            if only and s.name not in only:
                continue
            out.append(s)
        return out

    async def search(self, pq: ParsedQuery | str, kinds: set[str] | None = None, only: set[str] | None = None,
                     page: int = 1, timeout: float | None = None, force: bool = False) -> HarvestReport:
        if isinstance(pq, str):
            pq = parse_query(pq)
        text = pq.text or pq.raw.strip()
        report = HarvestReport(query=text, page=page)
        if not text:
            return report
        qkey = normalize_key(text)
        kinds_key = ",".join(sorted(kinds)) if kinds else "*"
        ttl = self.ctx.settings.cache_ttl_hours * 3600
        tasks: dict[asyncio.Task, str] = {}
        for src in self.active_sources(kinds, only):
            cached = self.db.cache_get(qkey, src.name, kinds_key, page)
            if cached is not None and not cached["error"] and not force and cached["fetched_at"] > now() - ttl:
                report.sources[src.name] = "cached"
                report.exhausted = report.exhausted and bool(cached["exhausted"])
                continue
            cursor = None
            if page > 1:
                prev = self.db.cache_get(qkey, src.name, kinds_key, page - 1)
                if prev is not None and prev["exhausted"]:
                    report.sources[src.name] = "no more results"
                    continue
                cursor = prev["next_cursor"] if prev is not None else None
            if not self.db.take_budget(src.name, src.hourly_budget()):
                report.sources[src.name] = "resting (rate limit)"
                continue
            task = asyncio.create_task(self._run(src, text, kinds, page, cursor, qkey, kinds_key))
            tasks[task] = src.name
        if tasks:
            done, pending = await asyncio.wait(tasks.keys(), timeout=timeout)
            for t in done:
                name, status, n, exhausted = t.result()
                report.sources[name] = status
                report.new_items += n
                report.exhausted = report.exhausted and exhausted
            for t in pending:  # let slow sources finish in the background; results still get banked
                report.sources[tasks[t]] = "still loading"
                report.pending.append(tasks[t])
                report.exhausted = False
                self._background.add(t)
                t.add_done_callback(self._background.discard)
        return report

    async def _run(self, src: Source, text: str, kinds: set[str] | None, page: int, cursor: str | None,
                   qkey: str, kinds_key: str) -> tuple[str, str, int, bool]:
        started = time.monotonic()
        try:
            res = await src.search(text, set(kinds or ()), page, self.ctx.settings.per_source, cursor)
            assets = [a for a in res.assets if isinstance(a, Asset) and a.source_id]
            ids = self.db.upsert_assets(assets)
            self.db.add_edges(group_edges(assets, ids))
            self.db.cache_put(qkey, src.name, kinds_key, page, ids, res.cursor, res.exhausted)
            self.db.source_ok(src.name, len(ids))
            log.info("%s p%d %r → %d items (%.1fs)", src.name, page, text, len(ids), time.monotonic() - started)
            return src.name, f"ok · {len(ids)}", len(ids), res.exhausted
        except RateLimited as exc:
            self.db.source_error(src.name, str(exc), cooldown_s=min(exc.retry_after, 6 * 3600))
            self.db.cache_put(qkey, src.name, kinds_key, page, [], cursor, False, error=str(exc))
            return src.name, f"resting ({exc})", 0, False
        except (SourceError, ValueError, KeyError, TypeError, AttributeError) as exc:
            msg = f"{type(exc).__name__}: {exc}" if not isinstance(exc, SourceError) else str(exc)
            self.db.source_error(src.name, msg)
            self.db.cache_put(qkey, src.name, kinds_key, page, [], cursor, False, error=msg[:300])
            log.warning("%s failed for %r: %s", src.name, text, msg)
            return src.name, f"error: {msg[:120]}", 0, True
        except Exception as exc:  # never let one source break a search
            self.db.source_error(src.name, repr(exc))
            log.exception("%s crashed", src.name)
            return src.name, f"error: {type(exc).__name__}", 0, True

    # -- related ("more like this") from the source's own graph --------------------
    async def related(self, asset_id: str, force: bool = False) -> int:
        a = self.db.get_asset(asset_id)
        if not a:
            return 0
        src = self.sources.get(a["source"])
        qkey = f"related:{asset_id}"
        cached = self.db.cache_get(qkey, a["source"], "*", 1)
        if cached is not None and not force and not cached["error"]:
            return 0
        found: list[Asset] = []
        if src and src.enabled and src.supports_related and self.db.take_budget(src.name, src.hourly_budget()):
            try:
                found = await src.related(a)
            except Exception as exc:
                self.db.source_error(src.name, f"related: {exc}")
        ids = self.db.upsert_assets(found)
        edges = [(asset_id, aid, "source", float(x.extra.get("edge_weight", 1.0)) / (1 + i * 0.02))
                 for i, (aid, x) in enumerate(zip(ids, found))]
        self.db.add_edges(edges)
        self.db.cache_put(qkey, a["source"], "*", 1, ids, None, True)
        # sources without a graph: widen by the asset's own tags
        if len(ids) < 10 and (a.get("tags") or a.get("title")):
            terms = (a.get("tags") or [])[:3] or (a.get("title") or "").split()[:4]
            query = " ".join(terms)
            kinds = RELATED_KINDS.get(a["kind"], {a["kind"]})
            await self.search(parse_query(query), kinds=kinds, page=1, timeout=20)
        return len(ids)

    async def hydrate(self, asset_id: str) -> dict[str, Any] | None:
        a = self.db.get_asset(asset_id)
        if not a or (a.get("extra") or {}).get("hydrated"):
            return a
        src = self.sources.get(a["source"])
        if not src:
            return a
        try:
            fields = await src.hydrate(a)
        except Exception as exc:
            log.info("hydrate %s failed: %s", asset_id, exc)
            fields = None
        if fields:
            self.db.update_asset(asset_id, **fields)
        self.db.merge_extra(asset_id, {"hydrated": True})
        return self.db.get_asset(asset_id)

    # -- downloading into the bank ---------------------------------------------------
    async def download(self, asset_id: str) -> dict[str, Any]:
        a = self.db.get_asset(asset_id)
        if not a:
            raise SourceError("asset not found")
        storage = self.ctx.storage
        if a.get("blob_key") and storage.has(a["blob_key"]):
            return a
        src = self.sources.get(a["source"])
        if src is not None:
            parts = await src.resolve_download(a)
        else:
            url = a.get("download_url") or a.get("preview_url")
            parts = [DownloadPart(url)] if url else []
        parts = [p for p in parts if p.url]
        if not parts:
            raise SourceError("this asset has no downloadable file — open it on the source page")
        settings = self.ctx.settings
        max_bytes = settings.max_download_mb * 1024 * 1024
        check = src is None  # user-supplied URLs get SSRF checks
        if src is not None:
            for part in parts:
                part.headers = part.headers or src.fetch_headers() or None
        if len(parts) == 1:
            d = await self.http.download(parts[0].url, settings.tmp_dir, max_bytes, headers=parts[0].headers,
                                         check_public=check)
            mime = d.mime.split(";")[0].strip() if d.mime else ""
            ext = guess_ext(mime, parts[0].name or d.final_url)
            try:
                key = storage.put_file(d.path, d.sha256, ext, mime)
            finally:
                d.path.unlink(missing_ok=True)
            size = d.size
        else:
            key, size, mime = await self._download_bundle(a, parts, max_bytes, check)
        self.db.update_asset(asset_id, blob_key=key, blob_size=size, blob_mime=mime)
        if src is not None:
            await src.on_download(a)
        return self.db.get_asset(asset_id)

    async def _download_bundle(self, a: dict[str, Any], parts: list[DownloadPart], max_bytes: int,
                               check: bool) -> tuple[str, int, str]:
        """Multi-file assets (PBR texture sets, glTF + textures, font families) → one zip."""
        import hashlib

        tmp_dir = self.ctx.settings.tmp_dir
        buf = io.BytesIO()
        total = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, part in enumerate(parts):
                d = await self.http.download(part.url, tmp_dir, max_bytes - total, headers=part.headers,
                                             check_public=check)
                try:
                    total += d.size
                    name = part.name or d.final_url.rsplit("/", 1)[-1].split("?")[0] or f"file{i}"
                    zf.write(d.path, arcname=name.lstrip("/").replace("..", "_"))
                finally:
                    d.path.unlink(missing_ok=True)
        data = buf.getvalue()
        sha = hashlib.sha256(data).hexdigest()
        tmp = tmp_dir / f"bundle-{sha[:16]}.zip"
        tmp.write_bytes(data)
        try:
            key = self.ctx.storage.put_file(tmp, sha, ".zip", "application/zip")
        finally:
            tmp.unlink(missing_ok=True)
        return key, len(data), "application/zip"
