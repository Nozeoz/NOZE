"""Pinterest-like, people-uploaded image communities with official APIs:
Wallhaven (keyless), Tumblr, Flickr, DeviantArt.

Uploads there belong to their creators → reference-only, except Flickr photos
whose owners chose a CC/public-domain license (labelled per photo)."""

from __future__ import annotations

import time
from typing import Any

from ..http import SourceError
from ..licenses import known, normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source, strip_html, words


class Wallhaven(Source):
    name = "wallhaven"
    label = "Wallhaven"
    homepage = "https://wallhaven.cc"
    description = "Huge tag-searchable library of aesthetic wallpapers & art (SFW) — reference only."
    kinds = (Kind.IMAGE,)
    optional_keys = ("WALLHAVEN_API_KEY",)
    signup_url = "https://wallhaven.cc/settings/account"
    trust_match = True  # matches on tags we don't get back in search results
    min_interval = 1.4  # 45 requests / minute

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        params: dict[str, Any] = {"q": query, "purity": "100", "categories": "111", "sorting": "relevance",
                                  "page": page}
        key = self.settings.key("WALLHAVEN_API_KEY")
        if key:
            params["apikey"] = key
        data = await self.get("https://wallhaven.cc/api/v1/search", params=params)
        meta = data.get("meta") or {}
        terms = words(query)
        out = [a for a in (self.parse(w, terms) for w in data.get("data") or []) if a]
        return SearchResult(out, exhausted=page >= int(meta.get("last_page") or 0))

    def parse(self, w: dict[str, Any], terms: list[str]) -> Asset | None:
        if w.get("purity") != "sfw" or not w.get("path"):
            return None
        thumbs = w.get("thumbs") or {}
        return self.make(
            source_id=w["id"],
            kind=Kind.IMAGE,
            title=f"{' '.join(terms).title() or 'Wallpaper'} · {w.get('category', '')}".strip(" ·"),
            # search results carry no tags; the query matched Wallhaven's tags, so keep it as context
            tags=terms + [w.get("category") or "", "wallpaper"],
            page_url=w.get("url") or "",
            thumb_url=thumbs.get("large") or thumbs.get("small") or "",
            preview_url=thumbs.get("original") or w["path"],
            download_url=w["path"],
            width=w.get("dimension_x"),
            height=w.get("dimension_y"),
            license=known("reference"),
            popularity=float(w.get("favorites") or 0) * 10 + float(w.get("views") or 0) / 100,
            colors=[[c, round(1 / len(w["colors"]), 3)] for c in w.get("colors") or []] or None,
            created_at=(w.get("created_at") or "")[:10],
            extra={"source_url": w.get("source") or ""},
        )


class Tumblr(Source):
    name = "tumblr"
    label = "Tumblr"
    homepage = "https://www.tumblr.com"
    description = "Aesthetic/moodboard culture — where lots of Pinterest content comes from (reference only)."
    kinds = (Kind.IMAGE, Kind.GIF, Kind.VIDEO)
    key_names = ("TUMBLR_API_KEY",)
    signup_url = "https://www.tumblr.com/oauth/apps"
    trust_match = True  # tag search
    min_interval = 0.5

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        if page > 1 and not cursor:
            return SearchResult([], exhausted=True)
        params: dict[str, Any] = {"tag": query.strip().lower(), "api_key": self.settings.key("TUMBLR_API_KEY"),
                                  "limit": 20, "npf": "true", "filter": "text"}
        if cursor:
            params["before"] = cursor
        data = await self.get("https://api.tumblr.com/v2/tagged", params=params)
        posts = data.get("response") or []
        out: list[Asset] = []
        for p in posts:
            out.extend(a for a in self.parse(p) if not kinds or a.kind in kinds)
        last = posts[-1] if posts else {}
        nxt = last.get("featured_timestamp") or last.get("timestamp")
        return SearchResult(out, cursor=str(nxt) if nxt else None, exhausted=not posts)

    def parse(self, p: dict[str, Any]) -> list[Asset]:
        blocks = list(p.get("content") or [])
        for t in p.get("trail") or []:  # reblogs keep the media in the trail
            blocks.extend(t.get("content") or [])
        out: list[Asset] = []
        common = {
            "tags": list(p.get("tags") or [])[:20],
            "author": p.get("blog_name") or (p.get("blog") or {}).get("name") or "",
            "page_url": p.get("post_url") or "",
            "license": known("reference"),
            "popularity": float(p.get("note_count") or 0),
            "created_at": time.strftime("%Y-%m-%d", time.gmtime(p["timestamp"])) if p.get("timestamp") else "",
        }
        summary = strip_html(p.get("summary") or "")[:200]
        common["author_url"] = f"https://www.tumblr.com/{common['author']}" if common["author"] else ""
        for i, b in enumerate(blocks):
            if b.get("type") == "image":
                media = sorted(b.get("media") or [], key=lambda m: -(m.get("width") or 0))
                if not media:
                    continue
                big = media[0]
                small = next((m for m in reversed(media) if (m.get("width") or 0) >= 400), big)
                gif = "gif" in (big.get("type") or "") or big.get("url", "").lower().endswith(".gif")
                out.append(self.make(
                    source_id=f"{p.get('id_string') or p.get('id')}-{i}", kind=Kind.GIF if gif else Kind.IMAGE,
                    title=b.get("alt_text") or summary or common["author"], thumb_url=small.get("url") or "",
                    preview_url=big.get("url") or "", download_url=big.get("url") or "",
                    width=big.get("width"), height=big.get("height"), **common))
            elif b.get("type") == "video":
                media = b.get("media") or {}
                url = media.get("url") if isinstance(media, dict) else b.get("url")
                poster = (b.get("poster") or [{}])[0]
                if not url or not poster.get("url"):
                    continue
                out.append(self.make(
                    source_id=f"{p.get('id_string') or p.get('id')}-{i}", kind=Kind.VIDEO,
                    title=summary or common["author"], thumb_url=poster.get("url"), preview_url=url,
                    download_url=url if (media.get("type") or "").startswith("video/") else "",
                    width=poster.get("width"), height=poster.get("height"), **common))
        return out[:4]


FLICKR_LICENSES = {
    0: ("reference", None), 1: ("cc", "https://creativecommons.org/licenses/by-nc-sa/2.0/"),
    2: ("cc", "https://creativecommons.org/licenses/by-nc/2.0/"), 3: ("cc", "https://creativecommons.org/licenses/by-nc-nd/2.0/"),
    4: ("cc", "https://creativecommons.org/licenses/by/2.0/"), 5: ("cc", "https://creativecommons.org/licenses/by-sa/2.0/"),
    6: ("cc", "https://creativecommons.org/licenses/by-nd/2.0/"), 7: ("public-domain", None),
    8: ("public-domain", None), 9: ("cc", "https://creativecommons.org/publicdomain/zero/1.0/"),
    10: ("cc", "https://creativecommons.org/publicdomain/mark/1.0/"), 11: ("cc", "https://creativecommons.org/licenses/by/4.0/"),
    12: ("cc", "https://creativecommons.org/licenses/by-sa/4.0/"), 13: ("cc", "https://creativecommons.org/licenses/by-nd/4.0/"),
    14: ("cc", "https://creativecommons.org/licenses/by-nc/4.0/"), 15: ("cc", "https://creativecommons.org/licenses/by-nc-sa/4.0/"),
    16: ("cc", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
}


def flickr_license(lid: Any):
    try:
        kind, url = FLICKR_LICENSES.get(int(lid), ("unknown", None))
    except (TypeError, ValueError):
        kind, url = "unknown", None
    if kind == "cc":
        return normalize_license(None, url)
    return known(kind)


class Flickr(Source):
    name = "flickr"
    label = "Flickr"
    homepage = "https://www.flickr.com"
    description = "Billions of photos by real people; licenses per photo (CC/public domain are usable)."
    kinds = (Kind.IMAGE,)
    key_names = ("FLICKR_API_KEY",)
    signup_url = "https://www.flickr.com/services/apps/create/apply/"
    min_interval = 0.4
    EXTRAS = "description,license,owner_name,tags,views,url_q,url_z,url_l,url_o,o_dims,date_upload"

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        data = await self.get("https://api.flickr.com/services/rest/", params={
            "method": "flickr.photos.search", "api_key": self.settings.key("FLICKR_API_KEY"), "format": "json",
            "nojsoncallback": 1, "text": query, "sort": "relevance", "safe_search": 1, "content_types": 0,
            "media": "photos", "extras": self.EXTRAS, "per_page": min(limit, 100), "page": page,
        })
        if data.get("stat") != "ok":
            raise SourceError(f"Flickr: {data.get('message', 'error')}")
        photos = data.get("photos") or {}
        out = [a for a in (self.parse(p) for p in photos.get("photo") or []) if a]
        return SearchResult(out, exhausted=page >= int(photos.get("pages") or 0))

    def parse(self, p: dict[str, Any]) -> Asset | None:
        thumb = p.get("url_z") or p.get("url_q")
        if not thumb:
            return None
        big = p.get("url_l") or p.get("url_z")
        owner = p.get("owner") or ""
        desc = p.get("description")
        desc = desc.get("_content") if isinstance(desc, dict) else desc
        lic = flickr_license(p.get("license"))
        return self.make(
            source_id=p["id"],
            kind=Kind.IMAGE,
            title=p.get("title") or "Untitled",
            description=strip_html(desc or "")[:1500],
            tags=(p.get("tags") or "").split()[:25],
            author=p.get("ownername") or owner,
            author_url=f"https://www.flickr.com/photos/{owner}/" if owner else "",
            page_url=f"https://www.flickr.com/photos/{owner}/{p['id']}",
            thumb_url=thumb,
            preview_url=big,
            # originals of all-rights-reserved photos stay on Flickr; CC ones can be banked
            download_url=(p.get("url_o") or big) if lic.usage != "reference" else big,
            width=p.get("width_l") or p.get("width_z") or p.get("o_width"),
            height=p.get("height_l") or p.get("height_z") or p.get("o_height"),
            license=lic,
            popularity=float(p.get("views") or 0) / 10,
        )


class DeviantArt(Source):
    name = "deviantart"
    label = "DeviantArt"
    homepage = "https://www.deviantart.com"
    description = "Massive art community: illustration, concept art, photomanip, 3D (reference only)."
    kinds = (Kind.IMAGE,)
    key_names = ("DEVIANTART_CLIENT_ID", "DEVIANTART_CLIENT_SECRET")
    signup_url = "https://www.deviantart.com/developers/apps"
    supports_related = True
    min_interval = 0.5
    API = "https://www.deviantart.com/api/v1/oauth2"

    def __init__(self, settings, http):
        super().__init__(settings, http)
        self._token: str | None = None
        self._exp = 0.0

    async def _auth(self) -> dict[str, str]:
        if not self._token or time.time() > self._exp - 60:
            resp = await self.http.request("POST", "https://www.deviantart.com/oauth2/token", data={
                "grant_type": "client_credentials", "client_id": self.settings.key("DEVIANTART_CLIENT_ID"),
                "client_secret": self.settings.key("DEVIANTART_CLIENT_SECRET")})
            body = resp.json()
            self._token = body.get("access_token")
            self._exp = time.time() + float(body.get("expires_in") or 3600)
        return {"Authorization": f"Bearer {self._token}"}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        per = min(limit, 24)
        data = await self.get(f"{self.API}/browse/home", headers=await self._auth(), params={
            "q": query, "limit": per, "offset": (page - 1) * per, "mature_content": "false"})
        out = [a for a in (self.parse(d) for d in data.get("results") or []) if a]
        return SearchResult(out, exhausted=not data.get("has_more"))

    async def related(self, asset: dict[str, Any], limit: int = 30) -> list[Asset]:
        data = await self.get(f"{self.API}/browse/morelikethis/preview", headers=await self._auth(),
                              params={"seed": asset["source_id"], "mature_content": "false"})
        items = list(data.get("more_from_da") or []) + list(data.get("more_from_artist") or [])
        return [a for a in (self.parse(d) for d in items[:limit]) if a]

    def parse(self, d: dict[str, Any]) -> Asset | None:
        if d.get("is_mature") or d.get("is_deleted"):
            return None
        preview = d.get("preview") or {}
        content = d.get("content") or {}
        thumbs = sorted(d.get("thumbs") or [], key=lambda t: t.get("width") or 0)
        thumb = next((t for t in thumbs if (t.get("width") or 0) >= 300), thumbs[-1] if thumbs else preview)
        if not (thumb or {}).get("src"):
            return None
        author = (d.get("author") or {}).get("username") or ""
        return self.make(
            source_id=d.get("deviationid"),
            kind=Kind.GIF if (content.get("src") or "").lower().endswith(".gif") else Kind.IMAGE,
            title=d.get("title") or "Untitled",
            tags=[d.get("category") or ""],
            author=author,
            author_url=f"https://www.deviantart.com/{author}" if author else "",
            page_url=d.get("url") or "",
            thumb_url=thumb["src"],
            preview_url=preview.get("src") or content.get("src") or thumb["src"],
            download_url=content.get("src") or "",
            width=content.get("width") or preview.get("width"),
            height=content.get("height") or preview.get("height"),
            license=known("reference"),
            popularity=float((d.get("stats") or {}).get("favourites") or 0),
        )
