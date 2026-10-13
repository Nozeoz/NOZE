"""Civitai — AI-generated images & clips people publish with their prompts.

The public images API has no text search, so NOZE pulls the SFW feed and keeps
posts whose prompt/tags match your query. Only "None" (PG) content is kept.
"""

from __future__ import annotations

import re
from typing import Any

from ..licenses import known
from ..models import Asset, Kind
from .base import SearchResult, Source, words

API = "https://civitai.com/api/v1/images"


class Civitai(Source):
    name = "civitai"
    label = "Civitai (AI-generated)"
    homepage = "https://civitai.com/images"
    description = "Public AI generations (images & short clips) with prompts — SFW only, matched on prompt text."
    kinds = (Kind.IMAGE, Kind.VIDEO)
    min_interval = 1.0

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        terms = words(query)
        params: dict[str, Any] = {
            "limit": 100, "nsfw": "None", "sort": "Most Reactions", "period": "Month",
            "withMeta": "true", "flatMeta": "true", "withTags": "true",
        }
        if kinds and Kind.VIDEO in kinds and Kind.IMAGE not in kinds:
            params["type"] = "video"
        elif kinds and Kind.IMAGE in kinds and Kind.VIDEO not in kinds:
            params["type"] = "image"
        matched: list[tuple[int, Asset]] = []
        next_cursor = cursor
        for _ in range(2):  # scan up to 200 feed items per page request
            if next_cursor:
                params["cursor"] = next_cursor
            data = await self.get(API, params=params)
            for item in data.get("items") or []:
                a = self.parse(item)
                if not a or (kinds and a.kind not in kinds):
                    continue
                score = self._match(terms, a)
                if score > 0:
                    matched.append((score, a))
            next_cursor = (data.get("metadata") or {}).get("nextCursor")
            if not next_cursor or len(matched) >= limit:
                break
        matched.sort(key=lambda m: (-m[0], -m[1].popularity))
        return SearchResult([a for _, a in matched[:limit]], cursor=str(next_cursor) if next_cursor else None,
                            exhausted=not next_cursor)

    @staticmethod
    def _match(terms: list[str], a: Asset) -> int:
        if not terms:
            return 1
        hay = f"{a.description} {' '.join(a.tags)}".lower()
        hits = sum(1 for t in terms if re.search(rf"\b{re.escape(t)}", hay))
        return hits if hits >= max(1, (len(terms) + 1) // 2) else 0

    def parse(self, it: dict[str, Any]) -> Asset | None:
        if it.get("nsfw") or (it.get("nsfwLevel") not in (None, "None")):
            return None
        level = it.get("browsingLevel")
        if isinstance(level, int) and level > 1:
            return None
        url = it.get("url") or ""
        if not url:
            return None
        meta = it.get("meta") or {}
        if isinstance(meta, dict) and "meta" in meta and isinstance(meta.get("meta"), dict):
            meta = meta["meta"]
        prompt = (meta or {}).get("prompt") or ""
        kind = Kind.VIDEO if it.get("type") == "video" else Kind.IMAGE
        stats = it.get("stats") or {}
        tags = [t.get("name") for t in it.get("tags") or [] if isinstance(t, dict)]
        thumb = url.replace("original=true", "anim=false,width=450") if "original=true" in url else url
        title = re.sub(r"[<>()\[\]{}:]+", " ", prompt)
        title = " ".join(title.split())[:90] or f"AI {kind} #{it.get('id')}"
        username = it.get("username") or ""
        return self.make(
            source_id=it.get("id"),
            kind=kind,
            title=title,
            description=prompt[:2500],
            tags=tags + ["ai-generated", it.get("baseModel") or ""],
            author=username,
            author_url=f"https://civitai.com/user/{username}" if username else "",
            page_url=f"https://civitai.com/images/{it.get('id')}",
            thumb_url=thumb,
            preview_url=url,
            download_url=url,
            width=it.get("width"),
            height=it.get("height"),
            license=known("ai-generated"),
            popularity=float(stats.get("likeCount") or 0) + 2 * float(stats.get("heartCount") or 0),
            created_at=(it.get("createdAt") or "")[:10],
            extra={"prompt": prompt[:4000], "negative_prompt": ((meta or {}).get("negativePrompt") or "")[:1000],
                   "model": (meta or {}).get("Model"), "base_model": it.get("baseModel")},
        )
