"""Internet Archive — public-domain films (Prelinger!), old cartoons, footage,
sound recordings and image collections."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..licenses import normalize_license
from ..models import Asset, Kind
from .base import DownloadPart, SearchResult, Source, as_list, first, strip_html

API = "https://archive.org/advancedsearch.php"
MEDIATYPE = {Kind.VIDEO: "movies", Kind.IMAGE: "image", Kind.AUDIO: "audio"}
KIND_OF = {v: k for k, v in MEDIATYPE.items()}
FIELDS = ("identifier", "title", "description", "mediatype", "licenseurl", "creator", "subject", "downloads", "date")
FORMAT_PREFS = {
    Kind.VIDEO: ("h.264", "mpeg4", "512kb mpeg4", "h.264 hd", "ogg video"),
    Kind.AUDIO: ("vbr mp3", "mp3", "128kbps mp3", "ogg vorbis", "flac"),
    Kind.IMAGE: ("jpeg", "png", "jpeg thumb"),
}


class InternetArchive(Source):
    name = "archive"
    label = "Internet Archive"
    homepage = "https://archive.org"
    description = "Public-domain films & footage (Prelinger), cartoons, sound recordings and image scans."
    kinds = (Kind.VIDEO, Kind.IMAGE, Kind.AUDIO)
    min_interval = 0.3

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        mts = [MEDIATYPE[k] for k in self.kinds if not kinds or k in kinds]
        params: list[tuple[str, Any]] = [("q", f"({query}) AND mediatype:({' OR '.join(mts)})")]
        params += [("fl[]", f) for f in FIELDS]
        params += [("sort[]", "downloads desc"), ("rows", min(limit, 100)), ("page", page), ("output", "json")]
        data = await self.get(API, params=params)
        resp = data.get("response") or {}
        out = [a for a in (self.parse(d) for d in resp.get("docs") or []) if a]
        return SearchResult(out, exhausted=page * limit >= int(resp.get("numFound") or 0))

    def parse(self, d: dict[str, Any]) -> Asset | None:
        ident = d.get("identifier")
        kind = KIND_OF.get(first(d.get("mediatype")))
        if not ident or not kind:
            return None
        subjects: list[str] = []
        for s in as_list(d.get("subject")):
            subjects += [x.strip() for x in str(s).split(";") if x.strip()]
        lic_url = first(d.get("licenseurl"))
        return self.make(
            source_id=ident,
            kind=kind,
            title=strip_html(first(d.get("title"))) or ident,
            description=strip_html(d.get("description"))[:1500],
            tags=subjects[:20],
            author=", ".join(str(c) for c in as_list(d.get("creator"))[:2]),
            page_url=f"https://archive.org/details/{quote(ident)}",
            thumb_url=f"https://archive.org/services/img/{quote(ident)}",
            license=normalize_license(None, lic_url) if lic_url else normalize_license("unknown"),
            popularity=float(d.get("downloads") or 0),
            created_at=str(first(d.get("date")))[:10],
        )

    async def _best_file(self, asset: dict[str, Any]) -> tuple[str, str] | None:
        ident = asset["source_id"]
        meta = await self.get(f"https://archive.org/metadata/{quote(ident)}")
        files = meta.get("files") or []
        for pref in FORMAT_PREFS.get(asset["kind"], ()):
            for f in files:
                if (f.get("format") or "").lower() == pref and f.get("name"):
                    return f"https://archive.org/download/{quote(ident)}/{quote(f['name'])}", f["name"]
        return None

    async def hydrate(self, asset: dict[str, Any]) -> dict[str, Any] | None:
        best = await self._best_file(asset)
        if not best:
            return None
        return {"preview_url": best[0], "download_url": best[0]}

    async def resolve_download(self, asset: dict[str, Any]) -> list[DownloadPart]:
        if asset.get("download_url"):
            return [DownloadPart(asset["download_url"])]
        best = await self._best_file(asset)
        return [DownloadPart(best[0], best[1])] if best else []
