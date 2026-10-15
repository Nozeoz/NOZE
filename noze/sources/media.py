"""Sound effects, GIFs/stickers and community posts: Freesound, GIPHY, Reddit."""

from __future__ import annotations

import os
import time
from typing import Any

from ..licenses import known, normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source, strip_html


class Freesound(Source):
    name = "freesound"
    label = "Freesound"
    homepage = "https://freesound.org"
    description = "600k+ sound effects & field recordings (whooshes, impacts, ambience) under CC licenses."
    kinds = (Kind.AUDIO,)
    key_names = ("FREESOUND_API_KEY",)
    signup_url = "https://freesound.org/apiv2/apply/"
    min_interval = 1.0
    FIELDS = "id,name,tags,description,license,username,previews,duration,url,images,num_downloads,avg_rating"

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        params = {"query": query, "token": self.settings.key("FREESOUND_API_KEY"), "page": page,
                  "page_size": min(limit, 150), "fields": self.FIELDS}
        try:
            data = await self.get("https://freesound.org/apiv2/search/text/", params=params)
        except Exception as exc:
            if "404" not in str(exc):
                raise
            data = await self.get("https://freesound.org/apiv2/search/", params=params)
        out = [self.parse(r) for r in data.get("results") or []]
        return SearchResult(out, exhausted=not data.get("next"))

    def parse(self, r: dict[str, Any]) -> Asset:
        previews = r.get("previews") or {}
        images = r.get("images") or {}
        user = r.get("username") or ""
        mp3 = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3") or ""
        return self.make(
            source_id=r.get("id"),
            kind=Kind.AUDIO,
            title=r.get("name") or "",
            description=strip_html(r.get("description") or "")[:1500],
            tags=r.get("tags") or [],
            author=user,
            author_url=f"https://freesound.org/people/{user}/" if user else "",
            page_url=r.get("url") or "",
            thumb_url=images.get("waveform_m") or images.get("waveform_l") or "",
            preview_url=mp3,
            download_url=mp3,
            width=2,
            height=1,
            duration=r.get("duration"),
            license=normalize_license(None, r.get("license") or ""),
            popularity=float(r.get("num_downloads") or 0),
            extra={"note": "Stored file is Freesound's HQ MP3 preview; the original needs a Freesound login."},
        )


class Giphy(Source):
    name = "giphy"
    label = "GIPHY"
    homepage = "https://giphy.com"
    description = "GIFs and transparent stickers — reference/social use (rights stay with creators)."
    kinds = (Kind.GIF,)
    key_names = ("GIPHY_API_KEY",)
    signup_url = "https://developers.giphy.com/dashboard/"
    credit = "Powered by GIPHY"
    budget_per_hour = 90

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        per = max(1, min(limit, 50) // 2)
        rating = "g" if self.settings.safe_search else "pg-13"
        out: list[Asset] = []
        exhausted = True
        for endpoint, sticker in (("gifs", False), ("stickers", True)):
            data = await self.get(f"https://api.giphy.com/v1/{endpoint}/search", params={
                "api_key": self.settings.key("GIPHY_API_KEY"), "q": query, "limit": per,
                "offset": (page - 1) * per, "rating": rating, "lang": "en",
            })
            out += [a for a in (self.parse(g, sticker) for g in data.get("data") or []) if a]
            pag = data.get("pagination") or {}
            if (pag.get("offset", 0) or 0) + per < int(pag.get("total_count") or 0):
                exhausted = False
        return SearchResult(out, exhausted=exhausted)

    def parse(self, g: dict[str, Any], sticker: bool) -> Asset | None:
        images = g.get("images") or {}
        still = (images.get("fixed_width_still") or images.get("original_still") or {}).get("url")
        fixed = images.get("fixed_width") or {}
        orig = images.get("original") or {}
        if not still:
            return None
        user = g.get("user") or {}
        return self.make(
            source_id=g.get("id"),
            kind=Kind.GIF,
            title=g.get("title") or "GIF",
            tags=(["sticker", "transparent"] if sticker else ["gif"]) + list(g.get("tags") or []),
            author=g.get("username") or user.get("display_name") or "",
            author_url=user.get("profile_url") or "",
            page_url=g.get("url") or "",
            thumb_url=still,
            preview_url=fixed.get("mp4") or fixed.get("url") or orig.get("url") or "",
            download_url=orig.get("url") or "",
            width=orig.get("width") or fixed.get("width"),
            height=orig.get("height") or fixed.get("height"),
            license=known("giphy"),
            extra={"mp4": orig.get("mp4"), "sticker": sticker, "webp": fixed.get("webp")},
        )


DEFAULT_SUBS = ("motiondesign+AfterEffects+Cinema4D+blender+generative+graphic_design+Design+Illustration+"
                "PixelArt+vfx+Filmmakers+typography+creativecoding+VaporwaveAesthetics+Cyberpunk+Moodboards")


class Reddit(Source):
    name = "reddit"
    label = "Reddit"
    homepage = "https://www.reddit.com"
    description = "Motion/design/art subreddits (r/motiondesign, r/AfterEffects, r/generative…) — reference only."
    kinds = (Kind.IMAGE, Kind.VIDEO, Kind.GIF, Kind.LINK)
    key_names = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")
    signup_url = "https://www.reddit.com/prefs/apps"
    min_interval = 1.0

    def __init__(self, settings, http):
        super().__init__(settings, http)
        self._token: str | None = None
        self._exp = 0.0

    async def _auth(self) -> dict[str, str]:
        if not self._token or time.time() > self._exp - 60:
            resp = await self.http.request(
                "POST", "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                auth=(self.settings.key("REDDIT_CLIENT_ID"), self.settings.key("REDDIT_CLIENT_SECRET")),
            )
            body = resp.json()
            self._token = body.get("access_token")
            self._exp = time.time() + float(body.get("expires_in") or 3600)
        return {"Authorization": f"Bearer {self._token}"}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        if page > 1 and not cursor:
            return SearchResult([], exhausted=True)
        subs = os.environ.get("NOZE_REDDIT_SUBS") or DEFAULT_SUBS
        params = {"q": query, "restrict_sr": 1, "sort": "relevance", "t": "all", "limit": min(limit, 100),
                  "type": "link", "raw_json": 1}
        if cursor:
            params["after"] = cursor
        data = await self.get(f"https://oauth.reddit.com/r/{subs}/search", params=params, headers=await self._auth())
        listing = data.get("data") or {}
        out = [a for a in (self.parse(c.get("data") or {}) for c in listing.get("children") or []) if a]
        out = [a for a in out if not kinds or a.kind in kinds]
        after = listing.get("after")
        return SearchResult(out, cursor=after, exhausted=not after)

    def parse(self, d: dict[str, Any]) -> Asset | None:
        if d.get("over_18") or not d.get("id"):
            return None
        preview = (d.get("preview") or {}).get("images") or []
        img = preview[0] if preview else {}
        source = img.get("source") or {}
        resolutions = img.get("resolutions") or []
        thumb = next((r.get("url") for r in resolutions if (r.get("width") or 0) >= 320), None) or source.get("url")
        video = ((d.get("media") or {}).get("reddit_video") or {}) if isinstance(d.get("media"), dict) else {}
        url = d.get("url") or ""
        if d.get("is_video") and video.get("fallback_url"):
            kind, preview_url, download = Kind.VIDEO, video["fallback_url"], video["fallback_url"]
        elif url.lower().endswith((".gif", ".gifv")) or (img.get("variants") or {}).get("mp4"):
            mp4 = ((img.get("variants") or {}).get("mp4") or {}).get("source") or {}
            kind, preview_url, download = Kind.GIF, mp4.get("url") or url, mp4.get("url") or url
        elif d.get("post_hint") == "image":
            kind, preview_url, download = Kind.IMAGE, source.get("url") or url, url
        elif thumb:
            kind, preview_url, download = Kind.LINK, source.get("url") or "", ""
        else:
            return None
        if not thumb:
            return None
        return self.make(
            source_id=d["id"],
            kind=kind,
            title=d.get("title") or "",
            tags=[d.get("subreddit"), d.get("link_flair_text")],
            author=f"u/{d.get('author')}" if d.get("author") else "",
            author_url=f"https://www.reddit.com/user/{d.get('author')}" if d.get("author") else "",
            page_url=f"https://www.reddit.com{d.get('permalink', '')}",
            thumb_url=thumb,
            preview_url=preview_url,
            download_url=download,
            width=video.get("width") or source.get("width"),
            height=video.get("height") or source.get("height"),
            duration=video.get("duration"),
            license=known("reference"),
            popularity=float(d.get("score") or 0),
            extra={"subreddit": d.get("subreddit"), "external_url": url},
        )
