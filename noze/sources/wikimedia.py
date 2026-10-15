"""Wikimedia Commons — 100M+ free media files (photos, SVG, video, audio, 3D)."""

from __future__ import annotations

import re
from typing import Any

from ..licenses import normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source, strip_html

API = "https://commons.wikimedia.org/w/api.php"
FILETYPE = {Kind.IMAGE: "filetype:bitmap", Kind.VIDEO: "filetype:video", Kind.AUDIO: "filetype:audio",
            Kind.MODEL3D: "filetype:3d", Kind.GIF: "filemime:image/gif"}


def _kind_for_mime(mime: str) -> str | None:
    mime = (mime or "").lower()
    if mime == "image/gif":
        return Kind.GIF
    if mime.startswith("image/"):
        return Kind.IMAGE
    if mime.startswith("video/") or mime in ("application/ogg",):
        return Kind.VIDEO
    if mime.startswith("audio/"):
        return Kind.AUDIO
    if mime in ("application/sla", "model/stl", "application/vnd.ms-pki.stl") or "stl" in mime:
        return Kind.MODEL3D
    return None


class Wikimedia(Source):
    name = "wikimedia"
    label = "Wikimedia Commons"
    homepage = "https://commons.wikimedia.org"
    description = "100M+ freely licensed photos, illustrations, SVGs, videos, sounds and 3D files."
    kinds = (Kind.IMAGE, Kind.GIF, Kind.VIDEO, Kind.AUDIO, Kind.MODEL3D)
    optional_keys = ("WIKIMEDIA_TOKEN",)
    signup_url = "https://api.wikimedia.org/wiki/Special:AppManagement"
    min_interval = 1.0  # Wikimedia rate-limits bursty anonymous API clients

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        limit = min(limit, 50)
        flt = FILETYPE.get(next(iter(kinds))) if kinds and len(kinds) == 1 else ""
        params = {
            "action": "query", "format": "json", "formatversion": "2", "generator": "search",
            "gsrsearch": f"{query} {flt}".strip(), "gsrnamespace": "6", "gsrlimit": str(limit),
            "gsroffset": str((page - 1) * limit), "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": "500",  # Wikimedia only serves standard thumbnail steps (250/330/500/960/1280/1920…)
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist|ImageDescription|Categories|DateTimeOriginal",
            "iiextmetadatalanguage": "en",
        }
        token = self.settings.key("WIKIMEDIA_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        data = await self.get(API, params=params, headers=headers)
        pages = (data.get("query") or {}).get("pages") or []
        if isinstance(pages, dict):  # formatversion=1 fallback
            pages = list(pages.values())
        pages.sort(key=lambda p: p.get("index", 0))
        out: list[Asset] = []
        for p in pages:
            a = self.parse(p)
            if a and (not kinds or a.kind in kinds):
                out.append(a)
        return SearchResult(out, exhausted="continue" not in data)

    def parse(self, p: dict[str, Any]) -> Asset | None:
        infos = p.get("imageinfo") or []
        if not infos:
            return None
        ii = infos[0]
        kind = _kind_for_mime(ii.get("mime", ""))
        if kind is None:
            return None
        meta = ii.get("extmetadata") or {}

        def mv(key: str) -> str:
            v = meta.get(key) or {}
            return strip_html(v.get("value") if isinstance(v, dict) else v)

        lic = normalize_license(mv("LicenseShortName"), (meta.get("LicenseUrl") or {}).get("value", ""))
        title = (p.get("title") or "").removeprefix("File:")
        name = title.rsplit(".", 1)[0].replace("_", " ")
        cats = [c.strip() for c in mv("Categories").split("|") if c.strip()]
        url = ii.get("url") or ""
        thumb = ii.get("thumburl") or ""
        width = ii.get("width") or 0
        preview = url
        if kind == Kind.IMAGE and thumb and width and width > 1920:
            preview = re.sub(r"/\d+px-", "/1280px-", thumb, count=1)
        return self.make(
            source_id=p.get("pageid") or title,
            kind=kind,
            title=name,
            description=mv("ImageDescription")[:1500],
            tags=cats[:15],
            author=re.sub(r"\(\s*talk\s*\)|^New work\s+", "", mv("Artist")).strip()[:120],
            page_url=ii.get("descriptionurl") or "",
            thumb_url=thumb,
            preview_url=preview,
            download_url=url,
            width=ii.get("width"),
            height=ii.get("height"),
            duration=ii.get("duration"),
            license=lic,
            created_at=mv("DateTimeOriginal")[:32],
            extra={"mime": ii.get("mime"), "size": ii.get("size")},
        )
