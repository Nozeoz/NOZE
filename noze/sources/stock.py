"""Free stock libraries with free API keys: Pexels, Pixabay, Unsplash.
All three licenses allow commercial use without attribution (credit is nice)."""

from __future__ import annotations

from typing import Any

from ..licenses import known
from ..models import Asset, Kind
from .base import DownloadPart, SearchResult, Source, slug_title

UTM = "utm_source=noze&utm_medium=referral"


class Pexels(Source):
    name = "pexels"
    label = "Pexels"
    homepage = "https://www.pexels.com"
    description = "Free stock photos & 4K stock footage — great for B-roll."
    kinds = (Kind.IMAGE, Kind.VIDEO)
    key_names = ("PEXELS_API_KEY",)
    signup_url = "https://www.pexels.com/api/new/"
    budget_per_hour = 180

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        headers = {"Authorization": self.settings.key("PEXELS_API_KEY")}
        per_page = min(limit, 80)
        out: list[Asset] = []
        exhausted = True
        if not kinds or Kind.IMAGE in kinds:
            data = await self.get("https://api.pexels.com/v1/search", headers=headers,
                                  params={"query": query, "per_page": per_page, "page": page})
            out += [self.parse_photo(p) for p in data.get("photos") or []]
            exhausted = exhausted and not data.get("next_page")
        if not kinds or Kind.VIDEO in kinds:
            data = await self.get("https://api.pexels.com/videos/search", headers=headers,
                                  params={"query": query, "per_page": per_page, "page": page})
            out += [a for a in (self.parse_video(v) for v in data.get("videos") or []) if a]
            exhausted = exhausted and not data.get("next_page")
        return SearchResult(out, exhausted=exhausted)

    def parse_photo(self, p: dict[str, Any]) -> Asset:
        src = p.get("src") or {}
        name = p.get("photographer") or ""
        return self.make(
            source_id=f"p{p.get('id')}",
            kind=Kind.IMAGE,
            title=p.get("alt") or slug_title(p.get("url") or "") or f"Photo by {name}",
            author=name,
            author_url=p.get("photographer_url") or "",
            page_url=p.get("url") or "",
            thumb_url=src.get("medium") or src.get("small") or "",
            preview_url=src.get("large2x") or src.get("large") or "",
            download_url=src.get("original") or "",
            width=p.get("width"),
            height=p.get("height"),
            license=known("pexels"),
            attribution=f"Photo by {name} on Pexels — {p.get('url') or ''}",
            colors=[[p["avg_color"], 0.5]] if p.get("avg_color") else None,
        )

    def parse_video(self, v: dict[str, Any]) -> Asset | None:
        files = [f for f in v.get("video_files") or [] if (f.get("file_type") or "").endswith("mp4") and f.get("link")]
        if not files:
            return None
        files.sort(key=lambda f: f.get("width") or 0)
        small = next((f for f in files if (f.get("width") or 0) >= 480), files[0])
        cap = self.settings.video_max_width
        big = [f for f in files if (f.get("width") or 0) <= cap] or files[:1]
        user = v.get("user") or {}
        return self.make(
            source_id=f"v{v.get('id')}",
            kind=Kind.VIDEO,
            title=slug_title(v.get("url") or "") or f"Video by {user.get('name', '')}",
            tags=[t for t in v.get("tags") or [] if isinstance(t, str)],
            author=user.get("name") or "",
            author_url=user.get("url") or "",
            page_url=v.get("url") or "",
            thumb_url=v.get("image") or "",
            preview_url=small.get("link"),
            download_url=big[-1].get("link"),
            width=v.get("width"),
            height=v.get("height"),
            duration=v.get("duration"),
            license=known("pexels"),
            attribution=f"Video by {user.get('name', '')} on Pexels — {v.get('url') or ''}",
        )


class Pixabay(Source):
    name = "pixabay"
    label = "Pixabay"
    homepage = "https://pixabay.com"
    description = "Free photos, illustrations, vectors and videos (incl. motion backgrounds)."
    kinds = (Kind.IMAGE, Kind.VIDEO)
    key_names = ("PIXABAY_API_KEY",)
    signup_url = "https://pixabay.com/api/docs/"
    min_interval = 0.7  # 100 requests / minute

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        base = {"key": self.settings.key("PIXABAY_API_KEY"), "q": query[:100], "page": page,
                "per_page": max(3, min(limit, 200)), "safesearch": "true" if self.settings.safe_search else "false"}
        out: list[Asset] = []
        exhausted = True
        if not kinds or Kind.IMAGE in kinds:
            data = await self.get("https://pixabay.com/api/", params={**base, "image_type": "all"})
            hits = data.get("hits") or []
            out += [self.parse_image(h) for h in hits]
            exhausted = exhausted and page * base["per_page"] >= int(data.get("totalHits") or 0)
        if not kinds or Kind.VIDEO in kinds:
            data = await self.get("https://pixabay.com/api/videos/", params=base)
            out += [a for a in (self.parse_video(h) for h in data.get("hits") or []) if a]
            exhausted = exhausted and page * base["per_page"] >= int(data.get("totalHits") or 0)
        return SearchResult(out, exhausted=exhausted)

    def _common(self, h: dict[str, Any]) -> dict[str, Any]:
        tags = [t.strip() for t in (h.get("tags") or "").split(",") if t.strip()]
        user = h.get("user") or ""
        return {
            "tags": tags + ([h.get("type")] if h.get("type") else []),
            "title": ", ".join(tags[:4]).title() or f"Pixabay {h.get('type', '')}",
            "author": user,
            "author_url": f"https://pixabay.com/users/{user}-{h.get('user_id')}/" if user else "",
            "page_url": h.get("pageURL") or "",
            "license": known("pixabay"),
            "popularity": float(h.get("likes") or 0) * 5 + float(h.get("downloads") or 0) / 10,
        }

    def parse_image(self, h: dict[str, Any]) -> Asset:
        return self.make(
            source_id=f"i{h.get('id')}",
            kind=Kind.IMAGE,
            thumb_url=h.get("webformatURL") or h.get("previewURL") or "",
            preview_url=h.get("largeImageURL") or h.get("webformatURL") or "",
            download_url=h.get("largeImageURL") or "",
            width=h.get("imageWidth"),
            height=h.get("imageHeight"),
            **self._common(h),
        )

    def parse_video(self, h: dict[str, Any]) -> Asset | None:
        vids = h.get("videos") or {}
        tiny, small, medium, large = (vids.get(k) or {} for k in ("tiny", "small", "medium", "large"))
        preview = tiny.get("url") or small.get("url")
        if not preview:
            return None
        thumb = medium.get("thumbnail") or small.get("thumbnail") or tiny.get("thumbnail") or ""
        if not thumb and h.get("picture_id"):
            thumb = f"https://i.vimeocdn.com/video/{h['picture_id']}_640x360.jpg"
        best = large if large.get("url") and (large.get("width") or 0) <= self.settings.video_max_width else medium
        return self.make(
            source_id=f"v{h.get('id')}",
            kind=Kind.VIDEO,
            thumb_url=thumb,
            preview_url=preview,
            download_url=best.get("url") or medium.get("url") or preview,
            width=(best.get("width") or medium.get("width")),
            height=(best.get("height") or medium.get("height")),
            duration=h.get("duration"),
            **self._common(h),
        )


class Unsplash(Source):
    name = "unsplash"
    label = "Unsplash"
    homepage = "https://unsplash.com"
    description = "High-quality free photos (hotlinked as Unsplash's API guidelines require)."
    kinds = (Kind.IMAGE,)
    key_names = ("UNSPLASH_ACCESS_KEY",)
    signup_url = "https://unsplash.com/oauth/applications"
    hotlink = True
    budget_per_hour = 45  # demo apps get 50/hour

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Client-ID {self.settings.key('UNSPLASH_ACCESS_KEY')}", "Accept-Version": "v1"}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        data = await self.get("https://api.unsplash.com/search/photos", headers=self._headers(), params={
            "query": query, "page": page, "per_page": min(limit, 30),
            "content_filter": "high" if self.settings.safe_search else "low",
        })
        out = [self.parse(r) for r in data.get("results") or []]
        return SearchResult(out, exhausted=page >= int(data.get("total_pages") or 0))

    def parse(self, r: dict[str, Any]) -> Asset:
        urls = r.get("urls") or {}
        links = r.get("links") or {}
        user = r.get("user") or {}
        name = user.get("name") or user.get("username") or ""
        page = links.get("html") or ""
        profile = (user.get("links") or {}).get("html") or ""
        return self.make(
            source_id=r.get("id"),
            kind=Kind.IMAGE,
            title=r.get("description") or r.get("alt_description") or f"Photo by {name}",
            description=r.get("alt_description") or "",
            tags=[t.get("title") for t in r.get("tags") or [] if isinstance(t, dict)],
            author=name,
            author_url=f"{profile}?{UTM}" if profile else "",
            page_url=f"{page}?{UTM}" if page else "",
            thumb_url=urls.get("small") or urls.get("thumb") or "",
            preview_url=urls.get("regular") or "",
            download_url=urls.get("full") or urls.get("raw") or "",
            width=r.get("width"),
            height=r.get("height"),
            license=known("unsplash"),
            attribution=f"Photo by {name} on Unsplash — {page}",
            popularity=float(r.get("likes") or 0),
            colors=[[r["color"], 0.5]] if r.get("color") else None,
            extra={"download_location": links.get("download_location"), "blur_hash": r.get("blur_hash")},
        )

    async def on_download(self, asset: dict[str, Any]) -> None:
        loc = (asset.get("extra") or {}).get("download_location")
        if loc:
            try:
                await self.get(loc, headers=self._headers())
            except Exception:
                pass

    async def resolve_download(self, asset: dict[str, Any]) -> list[DownloadPart]:
        url = asset.get("download_url") or asset.get("preview_url")
        return [DownloadPart(url, f"unsplash-{asset['source_id']}.jpg")] if url else []
