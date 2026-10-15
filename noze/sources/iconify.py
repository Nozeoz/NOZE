"""Iconify — 200k+ open-source icons from 150+ sets (Material, Phosphor, Tabler…)."""

from __future__ import annotations

from typing import Any

from ..licenses import normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source

API = "https://api.iconify.design"


class Iconify(Source):
    name = "iconify"
    label = "Iconify"
    homepage = "https://icon-sets.iconify.design"
    description = "200k+ open-source SVG icons from 150+ icon sets, each with its own license."
    trust_match = True
    kinds = (Kind.ICON,)

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        want = max(32, min(limit, 999))
        data = await self.get(f"{API}/search", params={"query": query, "limit": want, "start": (page - 1) * want})
        collections = data.get("collections") or {}
        out = [a for a in (self.parse(name, collections) for name in data.get("icons") or []) if a]
        total = int(data.get("total") or 0)
        return SearchResult(out, exhausted=page * want >= total or not out)

    def parse(self, full: str, collections: dict[str, Any]) -> Asset | None:
        if ":" not in full:
            return None
        prefix, name = full.split(":", 1)
        info = collections.get(prefix) or {}
        lic = info.get("license") or {}
        author = info.get("author") or {}
        svg = f"{API}/{prefix}/{name}.svg"
        return self.make(
            source_id=full,
            kind=Kind.ICON,
            title=name.replace("-", " "),
            tags=[prefix, info.get("name"), info.get("category")] + name.split("-"),
            author=author.get("name") or info.get("name") or prefix,
            author_url=author.get("url") or "",
            page_url=f"https://icon-sets.iconify.design/{prefix}/{name}/",
            thumb_url=svg,
            preview_url=svg,
            download_url=svg,
            width=1,
            height=1,
            license=normalize_license(lic.get("spdx") or lic.get("title"), lic.get("url")),
            extra={"set": info.get("name") or prefix, "palette": info.get("palette")},
        )
