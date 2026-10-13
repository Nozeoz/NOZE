"""ambientCG — thousands of CC0 PBR materials, HDRIs, decals and models."""

from __future__ import annotations

from typing import Any

from ..licenses import known
from ..models import Asset, Kind
from .base import SearchResult, Source

API = "https://ambientcg.com/api/v2/full_json"
KIND_BY_TYPE = {"hdri": Kind.HDRI, "3dmodel": Kind.MODEL3D}
TYPE_FOR_KIND = {Kind.HDRI: "HDRI", Kind.MODEL3D: "3DModel", Kind.TEXTURE: "Material,Decal,Atlas,Terrain,PlainTexture"}


def _pick(d: dict[str, Any], prefs: tuple[str, ...]) -> str:
    for p in prefs:
        if d.get(p):
            return d[p]
    for v in d.values():
        if isinstance(v, str) and v.startswith("http"):
            return v
    return ""


class AmbientCG(Source):
    name = "ambientcg"
    label = "ambientCG"
    homepage = "https://ambientcg.com"
    description = "CC0 PBR materials (wood, metal, concrete, fabric…), HDRIs, decals and 3D models."
    kinds = (Kind.TEXTURE, Kind.HDRI, Kind.MODEL3D)

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        params: dict[str, Any] = {
            "q": query, "limit": min(limit, 100), "offset": (page - 1) * limit,
            "include": "displayData,imageData,downloadData,tagData,statisticsData", "sort": "Popular",
        }
        if kinds and len(kinds & set(self.kinds)) == 1:
            params["type"] = TYPE_FOR_KIND[next(iter(kinds & set(self.kinds)))]
        data = await self.get(API, params=params)
        found = data.get("foundAssets") or []
        out = [a for a in (self.parse(x) for x in found) if a and (not kinds or a.kind in kinds)]
        total = int(data.get("numberOfResults") or 0)
        return SearchResult(out, exhausted=(page * limit >= total) or not found)

    def parse(self, x: dict[str, Any]) -> Asset | None:
        aid = x.get("assetId")
        if not aid:
            return None
        kind = KIND_BY_TYPE.get((x.get("dataType") or "").lower(), Kind.TEXTURE)
        previews = x.get("previewImage") or {}
        downloads: list[dict[str, Any]] = []
        folders = x.get("downloadFolders") or {}
        for folder in folders.values() if isinstance(folders, dict) else []:
            cats = (folder or {}).get("downloadFiletypeCategories") or {}
            for cat in cats.values() if isinstance(cats, dict) else []:
                downloads.extend((cat or {}).get("downloads") or [])
        chosen = None
        for pref in ("2K-JPG", "1K-JPG", "2K-PNG", "2K", "1K"):
            chosen = next((d for d in downloads if (d.get("attribute") or "").upper() == pref), None)
            if chosen:
                break
        chosen = chosen or (downloads[0] if downloads else {})
        return self.make(
            source_id=aid,
            kind=kind,
            title=x.get("displayName") or aid,
            tags=[x.get("displayCategory"), x.get("dataType")] + list(x.get("tags") or []),
            author="ambientCG",
            page_url=x.get("shortLink") or f"https://ambientcg.com/view?id={aid}",
            thumb_url=_pick(previews, ("256-PNG", "256-JPG-FFFFFF", "128-PNG", "512-PNG")),
            preview_url=_pick(previews, ("1024-PNG", "512-PNG", "256-PNG")),
            download_url=chosen.get("fullDownloadPath") or chosen.get("downloadLink") or "",
            width=1,
            height=1,
            license=known("cc0"),
            popularity=float(x.get("downloadCount") or 0),
            created_at=x.get("releaseDate") or "",
        )
