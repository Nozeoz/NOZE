"""Poly Haven — CC0 HDRIs, PBR textures and 3D models. Keyless; their API ToS
asks apps to show a "Powered by Poly Haven" style credit (NOZE does)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from ..licenses import known
from ..models import Asset, Kind
from .base import DownloadPart, SearchResult, Source, words

API = "https://api.polyhaven.com"
TYPES = {0: Kind.HDRI, 1: Kind.TEXTURE, 2: Kind.MODEL3D}


class PolyHaven(Source):
    name = "polyhaven"
    label = "Poly Haven"
    homepage = "https://polyhaven.com"
    description = "High-quality CC0 HDRIs, PBR textures and 3D models."
    kinds = (Kind.HDRI, Kind.TEXTURE, Kind.MODEL3D)
    credit = "Powered by Poly Haven"

    def __init__(self, settings, http):
        super().__init__(settings, http)
        self._catalog: dict[str, Any] = {}
        self._catalog_ts = 0.0

    async def catalog(self) -> dict[str, Any]:
        if not self._catalog or time.time() - self._catalog_ts > 6 * 3600:
            self._catalog = await self.get(f"{API}/assets", params={"t": "all"})
            self._catalog_ts = time.time()
        return self._catalog

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        catalog = await self.catalog()
        terms = words(query)
        scored: list[tuple[float, str, dict]] = []
        for aid, v in catalog.items():
            kind = TYPES.get(v.get("type"))
            if kind is None or (kinds and kind not in kinds):
                continue
            score = 0.0
            if terms:
                name = (v.get("name") or aid).lower()
                tags = " ".join(v.get("tags") or []).lower()
                cats = " ".join(v.get("categories") or []).lower()
                for t in terms:
                    score += 3.0 if t in name else 0.0
                    score += 2.0 if t in tags else 0.0
                    score += 1.5 if t in cats else 0.0
                if score == 0:
                    continue
            score += min(float(v.get("download_count") or 0), 1e6) / 1e6
            scored.append((score, aid, v))
        scored.sort(key=lambda s: -s[0])
        start = (page - 1) * limit
        chunk = scored[start:start + limit]
        return SearchResult([self.parse(aid, v) for _, aid, v in chunk], exhausted=start + limit >= len(scored))

    def parse(self, aid: str, v: dict[str, Any]) -> Asset:
        kind = TYPES.get(v.get("type"), Kind.TEXTURE)
        authors = v.get("authors") or {}
        published = v.get("date_published")
        created = datetime.fromtimestamp(published, tz=timezone.utc).date().isoformat() if isinstance(published, (int, float)) else ""
        max_res = v.get("max_resolution") or []
        real = len(max_res) == 2 and all(isinstance(x, int) and x > 16 for x in max_res)
        return self.make(
            source_id=aid,
            kind=kind,
            title=v.get("name") or aid,
            description=v.get("description") or "",
            tags=list(v.get("categories") or []) + list(v.get("tags") or []),
            author=", ".join(authors.keys()) if isinstance(authors, dict) else "",
            page_url=f"https://polyhaven.com/a/{aid}",
            thumb_url=v.get("thumbnail_url") or f"https://cdn.polyhaven.com/asset_img/thumbs/{aid}.png?width=256&height=256",
            preview_url=f"https://cdn.polyhaven.com/asset_img/primary/{aid}.png?height=780",
            width=max_res[0] if real else (2 if kind == Kind.HDRI else 1),
            height=max_res[1] if real else 1,
            license=known("cc0"),
            popularity=float(v.get("download_count") or 0),
            created_at=created,
            extra={"max_resolution": max_res},
        )

    async def resolve_download(self, asset: dict[str, Any]) -> list[DownloadPart]:
        files = await self.get(f"{API}/files/{asset['source_id']}")
        kind = asset["kind"]
        if kind == Kind.HDRI:
            hdri = files.get("hdri") or {}
            for res in ("2k", "1k", "4k"):
                f = (hdri.get(res) or {}).get("hdr")
                if f and f.get("url"):
                    return [DownloadPart(f["url"], f"{asset['source_id']}_{res}.hdr")]
            return []
        if kind == Kind.MODEL3D:
            gltf = files.get("gltf") or {}
            for res in ("1k", "2k"):
                g = (gltf.get(res) or {}).get("gltf")
                if g and g.get("url"):
                    parts = [DownloadPart(g["url"], g["url"].rsplit("/", 1)[-1])]
                    for rel, inc in (g.get("include") or {}).items():
                        if isinstance(inc, dict) and inc.get("url"):
                            parts.append(DownloadPart(inc["url"], rel))
                    return parts
            return []
        parts: list[DownloadPart] = []
        for map_name, by_res in files.items():
            if map_name in ("blend", "gltf", "mtlx", "usd") or not isinstance(by_res, dict):
                continue
            for res in ("2k", "1k"):
                formats = by_res.get(res) or {}
                f = formats.get("jpg") or formats.get("png")
                if isinstance(f, dict) and f.get("url"):
                    parts.append(DownloadPart(f["url"], f["url"].rsplit("/", 1)[-1]))
                    break
        return parts
