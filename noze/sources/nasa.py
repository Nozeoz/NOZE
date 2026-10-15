"""NASA Image and Video Library — space, earth and science imagery, footage and audio."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..licenses import known
from ..models import Asset, Kind
from .base import DownloadPart, SearchResult, Source, strip_html

API = "https://images-api.nasa.gov/search"
ASSETS = "https://images-assets.nasa.gov"
MEDIA = {Kind.IMAGE: "image", Kind.VIDEO: "video", Kind.AUDIO: "audio"}
KIND_OF = {v: k for k, v in MEDIA.items()}


class NASA(Source):
    name = "nasa"
    label = "NASA Images"
    homepage = "https://images.nasa.gov"
    description = "Space, earth & science photos, footage and audio — generally public domain."
    kinds = (Kind.IMAGE, Kind.VIDEO, Kind.AUDIO)

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        types = [MEDIA[k] for k in self.kinds if not kinds or k in kinds]
        data = await self.get(API, params={"q": query, "media_type": ",".join(types), "page": page,
                                           "page_size": min(limit, 100)})
        coll = data.get("collection") or {}
        out = [a for a in (self.parse(it) for it in coll.get("items") or []) if a]
        has_next = any(link.get("rel") == "next" for link in coll.get("links") or [])
        return SearchResult(out, exhausted=not has_next)

    def parse(self, item: dict[str, Any]) -> Asset | None:
        d = (item.get("data") or [{}])[0]
        nid = d.get("nasa_id")
        kind = KIND_OF.get(d.get("media_type"))
        if not nid or not kind:
            return None
        thumb = next((lk.get("href") for lk in item.get("links") or [] if lk.get("render") == "image"), "") or ""
        q = quote(nid)
        base = f"{ASSETS}/{d.get('media_type')}/{q}/{q}"
        if kind == Kind.IMAGE:
            preview = thumb.replace("~thumb.jpg", "~medium.jpg") if "~thumb" in thumb else thumb
            download = thumb.replace("~thumb.jpg", "~orig.jpg") if "~thumb" in thumb else thumb
        elif kind == Kind.VIDEO:
            preview, download = f"{base}~mobile.mp4", ""
        else:
            preview, download = f"{base}~128k.mp3", ""
        return self.make(
            source_id=nid,
            kind=kind,
            title=d.get("title") or nid,
            description=strip_html(d.get("description") or d.get("description_508") or "")[:2000],
            tags=(d.get("keywords") or [])[:20] + ([d.get("center")] if d.get("center") else []),
            author=d.get("photographer") or d.get("secondary_creator") or d.get("center") or "NASA",
            page_url=f"https://images.nasa.gov/details/{q}",
            thumb_url=thumb,
            preview_url=preview,
            download_url=download,
            license=known("nasa"),
            created_at=(d.get("date_created") or "")[:10],
            extra={"manifest": item.get("href") or ""},
        )

    async def resolve_download(self, asset: dict[str, Any]) -> list[DownloadPart]:
        manifest = (asset.get("extra") or {}).get("manifest")
        if not manifest:
            return await super().resolve_download(asset)
        files = await self.get(manifest)
        files = [f for f in files if isinstance(f, str)]
        prefs = {
            Kind.VIDEO: ("~large.mp4", "~medium.mp4", "~orig.mp4", "~small.mp4", "~mobile.mp4"),
            Kind.AUDIO: ("~orig.wav", "~orig.mp3", "~128k.mp3"),
            Kind.IMAGE: ("~orig.jpg", "~orig.png", "~large.jpg", "~orig.tif", "~medium.jpg"),
        }.get(asset["kind"], ())
        for suffix in prefs:
            for f in files:
                if f.lower().endswith(suffix):
                    return [DownloadPart(f.replace("http://", "https://"))]
        return await super().resolve_download(asset)
