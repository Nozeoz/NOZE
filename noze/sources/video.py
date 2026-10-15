"""Motion references: Vimeo (where motion designers post reels) and YouTube.

Both are watch/embed-only references — NOZE keeps the link, poster and an
embeddable player, never the video file (their terms don't allow downloading
unless the creator enables it)."""

from __future__ import annotations

from typing import Any

from ..licenses import known, normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source, strip_html


class Vimeo(Source):
    name = "vimeo"
    label = "Vimeo"
    homepage = "https://vimeo.com"
    description = "Motion design reels, title sequences, short films — the motion designer's Pinterest."
    kinds = (Kind.VIDEO,)
    key_names = ("VIMEO_ACCESS_TOKEN",)
    signup_url = "https://developer.vimeo.com/apps"
    min_interval = 0.5

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        data = await self.get("https://api.vimeo.com/videos", headers={
            "Authorization": f"bearer {self.settings.key('VIMEO_ACCESS_TOKEN')}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4",
        }, params={"query": query, "page": page, "per_page": min(limit, 50), "sort": "relevant",
                   "fields": "uri,name,description,link,duration,width,height,pictures.sizes,user.name,user.link,"
                             "tags.name,stats.plays,license,content_rating"})
        out = [a for a in (self.parse(v) for v in data.get("data") or []) if a]
        return SearchResult(out, exhausted=not (data.get("paging") or {}).get("next"))

    def parse(self, v: dict[str, Any]) -> Asset | None:
        vid = (v.get("uri") or "").rsplit("/", 1)[-1]
        sizes = sorted(((v.get("pictures") or {}).get("sizes") or []), key=lambda s: s.get("width") or 0)
        thumb = next((s for s in sizes if (s.get("width") or 0) >= 400), sizes[-1] if sizes else {})
        if not vid or not thumb.get("link"):
            return None
        rating = v.get("content_rating") or []
        if any(r not in ("safe", "unrated") for r in rating):
            return None
        user = v.get("user") or {}
        lic = v.get("license")
        return self.make(
            source_id=vid,
            kind=Kind.VIDEO,
            title=v.get("name") or "Untitled",
            description=strip_html(v.get("description") or "")[:1500],
            tags=[t.get("name") for t in v.get("tags") or [] if isinstance(t, dict)],
            author=user.get("name") or "",
            author_url=user.get("link") or "",
            page_url=v.get("link") or f"https://vimeo.com/{vid}",
            thumb_url=thumb["link"],
            width=v.get("width"),
            height=v.get("height"),
            duration=v.get("duration"),
            license=normalize_license(f"cc {lic}") if lic else known("reference"),
            popularity=float((v.get("stats") or {}).get("plays") or 0) / 100,
            extra={"embed": f"https://player.vimeo.com/video/{vid}"},
        )


class YouTube(Source):
    name = "youtube"
    label = "YouTube"
    homepage = "https://www.youtube.com"
    description = "Motion references, breakdowns and tutorials (watch/embed only)."
    kinds = (Kind.VIDEO,)
    key_names = ("YOUTUBE_API_KEY",)
    signup_url = "https://console.cloud.google.com/apis/library/youtube.googleapis.com"
    budget_per_hour = 90  # search costs 100 of the 10k daily quota units

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        if page > 1 and not cursor:
            return SearchResult([], exhausted=True)
        params: dict[str, Any] = {"part": "snippet", "q": query, "type": "video", "maxResults": min(limit, 50),
                                  "safeSearch": "strict", "key": self.settings.key("YOUTUBE_API_KEY")}
        if cursor:
            params["pageToken"] = cursor
        data = await self.get("https://www.googleapis.com/youtube/v3/search", params=params)
        out = [a for a in (self.parse(i) for i in data.get("items") or []) if a]
        nxt = data.get("nextPageToken")
        return SearchResult(out, cursor=nxt, exhausted=not nxt)

    def parse(self, item: dict[str, Any]) -> Asset | None:
        vid = (item.get("id") or {}).get("videoId")
        sn = item.get("snippet") or {}
        thumbs = sn.get("thumbnails") or {}
        thumb = thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}
        if not vid or not thumb.get("url"):
            return None
        return self.make(
            source_id=vid,
            kind=Kind.VIDEO,
            title=strip_html(sn.get("title") or ""),
            description=strip_html(sn.get("description") or "")[:1500],
            author=sn.get("channelTitle") or "",
            author_url=f"https://www.youtube.com/channel/{sn['channelId']}" if sn.get("channelId") else "",
            page_url=f"https://www.youtube.com/watch?v={vid}",
            thumb_url=thumb["url"],
            width=16,
            height=9,
            license=known("reference"),
            created_at=(sn.get("publishedAt") or "")[:10],
            extra={"embed": f"https://www.youtube-nocookie.com/embed/{vid}"},
        )
