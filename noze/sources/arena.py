"""Are.na — the designers' Pinterest: human-curated channels of references.

Content is reposted from all over the web, so it's marked reference-only.
Its real value is the graph: blocks that people put in the same channels are
related — exactly how Pinterest's pin–board graph finds "more like this".
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from ..licenses import known
from ..models import Asset, Kind
from .base import SearchResult, Source, strip_html

API = "https://api.are.na/v2"


class Arena(Source):
    name = "arena"
    label = "Are.na"
    homepage = "https://www.are.na"
    description = "Curated reference channels by designers & artists (reference-only), with a related-content graph."
    kinds = (Kind.IMAGE, Kind.GIF, Kind.VIDEO, Kind.LINK)
    optional_keys = ("ARENA_TOKEN",)
    signup_url = "https://dev.are.na/oauth/applications"
    supports_related = True
    min_interval = 0.3

    def _headers(self) -> dict[str, str]:
        token = self.settings.key("ARENA_TOKEN")
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        # Are.na's block search sits behind a bot wall for servers, but channel search and
        # channel contents are open. Find the channels (= boards) about the query, then pull
        # what people collected in them — the same board-first idea Pinterest is built on.
        per_channel = max(8, min(24, limit // 2))
        data = await self.get(f"{API}/search", params={"q": query, "per": 6, "page": page}, headers=self._headers())
        out: list[Asset] = []
        seen: set[str] = set()
        for b in data.get("blocks") or []:
            a = self.parse(b)
            if a and a.source_id not in seen:
                seen.add(a.source_id)
                out.append(a)
        channels = [c for c in data.get("channels") or [] if isinstance(c, dict) and c.get("slug")
                    and not c.get("nsfw?") and (c.get("length") or 0) > 0]

        async def contents(ch: dict[str, Any]) -> list[Asset]:
            try:
                body = await self.get(f"{API}/channels/{ch['slug']}/contents", params={"per": per_channel},
                                      headers=self._headers())
            except Exception:
                return []
            found = []
            for b in (body.get("contents") if isinstance(body, dict) else None) or []:
                a = self.parse(b)
                if a:
                    a.tags.append(ch.get("title") or "")
                    a.extra["group"] = f"arena:{ch['slug']}"
                    a.extra["group_size"] = int(ch.get("length") or 0)
                    found.append(a)
            return found

        batches = await asyncio.gather(*(contents(c) for c in channels))
        # interleave channels so one board doesn't fill the whole page
        for i in range(max((len(b) for b in batches), default=0)):
            for batch in batches:
                if i < len(batch) and batch[i].source_id not in seen:
                    seen.add(batch[i].source_id)
                    out.append(batch[i])
        out = [a for a in out if not kinds or a.kind in kinds]
        total_pages = int(data.get("total_pages") or 0)
        return SearchResult(out, exhausted=page >= total_pages or not channels)

    def parse(self, b: dict[str, Any]) -> Asset | None:
        cls = b.get("class") or ""
        if cls not in ("Image", "Link", "Media", "Attachment"):
            return None
        image = b.get("image") or {}

        def img(size: str) -> str:
            return ((image.get(size) or {}).get("url")) or ""

        thumb = img("display") or img("thumb") or img("square")
        attachment = b.get("attachment") or {}
        ctype = (image.get("content_type") or attachment.get("content_type") or "").lower()
        preview = img("large") or img("original") or thumb
        kind = Kind.IMAGE
        if cls == "Image":
            kind = Kind.GIF if "gif" in ctype else Kind.IMAGE
        elif cls == "Attachment":
            if ctype.startswith("video/"):
                kind, preview = Kind.VIDEO, attachment.get("url") or preview
            elif "gif" in ctype:
                kind = Kind.GIF
            elif not ctype.startswith("image/"):
                return None
        elif cls == "Media":
            kind = Kind.VIDEO
        elif cls == "Link":
            kind = Kind.LINK
        if not thumb:
            return None
        user = b.get("user") or {}
        source = b.get("source") or {}
        provider = (source.get("provider") or {}).get("name") if isinstance(source.get("provider"), dict) else ""
        return self.make(
            source_id=b.get("id"),
            kind=kind,
            title=b.get("title") or b.get("generated_title") or "",
            description=strip_html(b.get("description") or b.get("content") or "")[:1500],
            tags=[provider] if provider else [],
            author=user.get("full_name") or user.get("username") or "",
            author_url=f"https://www.are.na/{user['slug']}" if user.get("slug") else "",
            page_url=f"https://www.are.na/block/{b.get('id')}",
            thumb_url=thumb,
            preview_url=preview,
            download_url=img("original") if kind in (Kind.IMAGE, Kind.GIF) else (attachment.get("url") or ""),
            license=known("reference"),
            popularity=float(b.get("connection_count") or 0),
            created_at=(b.get("created_at") or "")[:10],
            extra={"source_url": source.get("url") or "", "class": cls,
                   "embed": (b.get("embed") or {}).get("url") if isinstance(b.get("embed"), dict) else None},
        )

    async def related(self, asset: dict[str, Any], limit: int = 40) -> list[Asset]:
        data = await self.get(f"{API}/blocks/{asset['source_id']}/channels", params={"per": 8}, headers=self._headers())
        channels = data.get("channels") if isinstance(data, dict) else data
        channels = [c for c in channels or [] if isinstance(c, dict) and c.get("slug")]
        # small, focused channels say more than giant catch-alls
        channels.sort(key=lambda c: int(c.get("length") or 0))
        results: list[Asset] = []

        async def contents(ch: dict[str, Any]) -> list[Asset]:
            body = await self.get(f"{API}/channels/{ch['slug']}/contents", params={"per": 40}, headers=self._headers())
            items = body.get("contents") if isinstance(body, dict) else []
            weight = 1.0 / math.log(2.0 + float(ch.get("length") or 1))
            out = []
            for b in items or []:
                a = self.parse(b)
                if a and a.source_id != str(asset["source_id"]):
                    a.extra["edge_weight"] = weight
                    out.append(a)
            return out

        for chunk in await asyncio.gather(*(contents(c) for c in channels[:3]), return_exceptions=True):
            if isinstance(chunk, list):
                results.extend(chunk)
        return results[: limit * 2]
