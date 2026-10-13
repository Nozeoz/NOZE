"""Open-access museum collections: public-domain artworks, posters, prints,
textiles, photos… Great for texture, typography and color references.

The Met, Art Institute of Chicago and Cleveland Museum of Art are keyless;
Smithsonian uses an api.data.gov key (DEMO_KEY works, slowly); Europeana has a
public demo key (api2demo).
"""

from __future__ import annotations

import asyncio
import colorsys
from typing import Any

from ..licenses import known, normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source, first, strip_html


class MetMuseum(Source):
    name = "met"
    label = "The Met"
    homepage = "https://www.metmuseum.org/art/collection"
    description = "The Metropolitan Museum of Art — 490k+ public-domain artworks (CC0)."
    kinds = (Kind.IMAGE,)
    API = "https://collectionapi.metmuseum.org/public/collection/v1"

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        per = min(limit, 16)  # one request per object, keep it light
        # v1/search was retired on 2026-10-01; v1.1 is paginated with offset/limit
        data = await self.get(f"{self.API}.1/search", params={"q": query, "hasImages": "true", "limit": per,
                                                             "offset": (page - 1) * per})
        ids = data.get("objectIDs") or []
        sem = asyncio.Semaphore(4)

        async def one(oid: int) -> Asset | None:
            async with sem:
                try:
                    return self.parse(await self.get(f"{self.API}/objects/{oid}"))
                except Exception:
                    return None

        results = await asyncio.gather(*(one(i) for i in ids[:per]))
        total = int(data.get("total") or 0)
        return SearchResult([a for a in results if a], exhausted=not ids or page * per >= total)

    def parse(self, o: dict[str, Any]) -> Asset | None:
        if not o.get("isPublicDomain") or not o.get("primaryImageSmall"):
            return None
        tags = [t.get("term") for t in o.get("tags") or [] if isinstance(t, dict)]
        tags += [o.get("classification"), o.get("department"), o.get("culture"), o.get("medium")]
        return self.make(
            source_id=o.get("objectID"),
            kind=Kind.IMAGE,
            title=o.get("title") or "Untitled",
            description=" · ".join(x for x in (o.get("objectDate"), o.get("medium"), o.get("creditLine")) if x),
            tags=[t for t in tags if t][:20],
            author=o.get("artistDisplayName") or o.get("culture") or "",
            author_url=o.get("artistWikidata_URL") or "",
            page_url=o.get("objectURL") or "",
            thumb_url=o.get("primaryImageSmall") or "",
            preview_url=o.get("primaryImage") or o.get("primaryImageSmall") or "",
            download_url=o.get("primaryImage") or "",
            license=known("cc0"),
            created_at=str(o.get("objectBeginDate") or ""),
            extra={"museum": "The Met"},
        )


def _hsl_hex(c: dict[str, Any]) -> str | None:
    try:
        r, g, b = colorsys.hls_to_rgb(float(c["h"]) / 360.0, float(c["l"]) / 100.0, float(c["s"]) / 100.0)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))
    except (KeyError, TypeError, ValueError):
        return None


class ArtInstituteChicago(Source):
    name = "artic"
    label = "Art Institute of Chicago"
    homepage = "https://www.artic.edu/collection"
    description = "50k+ public-domain artworks via IIIF (CC0), with dominant-color metadata."
    kinds = (Kind.IMAGE,)
    API = "https://api.artic.edu/api/v1/artworks/search"
    FIELDS = ("id,title,image_id,artist_title,artist_display,is_public_domain,thumbnail,term_titles,"
              "style_titles,subject_titles,classification_titles,date_display,color,medium_display")

    def fetch_headers(self) -> dict[str, str]:
        # their IIIF image server lets identified API clients through its bot wall
        return {"AIC-User-Agent": self.settings.user_agent}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        limit = min(limit, 40)
        headers = self.fetch_headers()
        data = await self.get(self.API, headers=headers, params={
            "q": query, "page": page, "limit": limit, "fields": self.FIELDS,
            "query[term][is_public_domain]": "true",
        })
        iiif = ((data.get("config") or {}).get("iiif_url")) or "https://www.artic.edu/iiif/2"
        out = [a for a in (self.parse(r, iiif) for r in data.get("data") or []) if a]
        pag = data.get("pagination") or {}
        return SearchResult(out, exhausted=page >= int(pag.get("total_pages") or 0))

    def parse(self, r: dict[str, Any], iiif: str) -> Asset | None:
        image_id = r.get("image_id")
        if not image_id or r.get("is_public_domain") is False:
            return None
        thumb = r.get("thumbnail") or {}
        hexv = _hsl_hex(r.get("color") or {}) if r.get("color") else None
        tags: list[str] = []
        for key in ("style_titles", "classification_titles", "subject_titles", "term_titles"):
            tags += r.get(key) or []
        return self.make(
            source_id=r.get("id"),
            kind=Kind.IMAGE,
            title=r.get("title") or "Untitled",
            description=" · ".join(x for x in (r.get("date_display"), r.get("medium_display")) if x),
            tags=tags[:20],
            author=r.get("artist_title") or strip_html(r.get("artist_display") or "").split("\n")[0],
            page_url=f"https://www.artic.edu/artworks/{r.get('id')}",
            thumb_url=f"{iiif}/{image_id}/full/400,/0/default.jpg",
            preview_url=f"{iiif}/{image_id}/full/843,/0/default.jpg",
            download_url=f"{iiif}/{image_id}/full/1686,/0/default.jpg",
            width=thumb.get("width"),
            height=thumb.get("height"),
            license=known("cc0"),
            colors=[[hexv, 0.6]] if hexv else None,
            extra={"museum": "Art Institute of Chicago"},
        )


class ClevelandMuseum(Source):
    name = "cleveland"
    label = "Cleveland Museum of Art"
    homepage = "https://www.clevelandart.org/art/collection/search"
    description = "60k+ CC0 artworks with high-res images."
    kinds = (Kind.IMAGE,)
    API = "https://openaccess-api.clevelandart.org/api/artworks/"

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        limit = min(limit, 50)
        data = await self.get(self.API, params={"q": query, "has_image": 1, "cc0": 1, "limit": limit,
                                                "skip": (page - 1) * limit})
        out = [a for a in (self.parse(r) for r in data.get("data") or []) if a]
        total = int((data.get("info") or {}).get("total") or 0)
        return SearchResult(out, exhausted=page * limit >= total)

    def parse(self, r: dict[str, Any]) -> Asset | None:
        images = r.get("images") or {}
        web = images.get("web") or {}
        if not web.get("url"):
            return None
        big = images.get("print") or images.get("full") or web
        creators = r.get("creators") or []
        author = (creators[0].get("description") if creators and isinstance(creators[0], dict) else "") or ""
        return self.make(
            source_id=r.get("id"),
            kind=Kind.IMAGE,
            title=r.get("title") or "Untitled",
            description=strip_html(r.get("wall_description") or r.get("description") or r.get("tombstone") or "")[:1500],
            tags=[r.get("type"), r.get("technique"), r.get("department")] + list(r.get("culture") or []),
            author=author.split("(")[0].strip(),
            page_url=r.get("url") or "",
            thumb_url=web.get("url"),
            preview_url=web.get("url"),
            download_url=big.get("url") or web.get("url"),
            width=web.get("width"),
            height=web.get("height"),
            license=known("cc0") if (r.get("share_license_status") or "").upper() == "CC0" else known("unknown"),
            created_at=str(r.get("creation_date") or ""),
            extra={"museum": "Cleveland Museum of Art"},
        )


class Smithsonian(Source):
    name = "smithsonian"
    label = "Smithsonian Open Access"
    homepage = "https://www.si.edu/openaccess"
    description = "4.5M+ CC0 images across 21 Smithsonian museums (uses DEMO_KEY unless you add a key)."
    kinds = (Kind.IMAGE,)
    optional_keys = ("SMITHSONIAN_API_KEY",)
    signup_url = "https://api.data.gov/signup/"
    API = "https://api.si.edu/openaccess/api/v1.0/search"

    def hourly_budget(self) -> int | None:
        return 25 if self.settings.key("SMITHSONIAN_API_KEY") in ("", "DEMO_KEY") else 900

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        limit = min(limit, 50)
        data = await self.get(self.API, params={
            "q": f"{query} AND online_media_type:Images", "api_key": self.settings.key("SMITHSONIAN_API_KEY") or "DEMO_KEY",
            "rows": limit, "start": (page - 1) * limit,
        })
        resp = data.get("response") or {}
        out = [a for a in (self.parse(r) for r in resp.get("rows") or []) if a]
        return SearchResult(out, exhausted=page * limit >= int(resp.get("rowCount") or 0))

    def parse(self, r: dict[str, Any]) -> Asset | None:
        content = r.get("content") or {}
        dnr = content.get("descriptiveNonRepeating") or {}
        media = ((dnr.get("online_media") or {}).get("media")) or []
        m = next((m for m in media if ((m.get("usage") or {}).get("access") == "CC0") and m.get("thumbnail")), None)
        if not m:
            return None
        idx = content.get("indexedStructured") or {}
        tags: list[str] = []
        for key in ("object_type", "topic", "name", "place", "culture"):
            for v in idx.get(key) or []:
                tags.append(v if isinstance(v, str) else (v.get("content") if isinstance(v, dict) else ""))
        full = m.get("content") or m.get("thumbnail")
        title = dnr.get("title")
        title = title.get("content") if isinstance(title, dict) else (title or r.get("title") or "Untitled")
        return self.make(
            source_id=r.get("id") or dnr.get("record_ID"),
            kind=Kind.IMAGE,
            title=title,
            tags=[t for t in tags if t][:20],
            author=dnr.get("data_source") or r.get("unitCode") or "Smithsonian",
            page_url=dnr.get("record_link") or dnr.get("guid") or "",
            thumb_url=m.get("thumbnail"),
            preview_url=f"{full}&max=1200" if "deliveryService" in (full or "") else full,
            download_url=full,
            license=known("cc0"),
            extra={"museum": dnr.get("data_source") or "Smithsonian"},
        )


class Europeana(Source):
    name = "europeana"
    label = "Europeana"
    homepage = "https://www.europeana.eu"
    description = "50M+ items from European museums, archives & libraries (open-licensed filter)."
    kinds = (Kind.IMAGE, Kind.VIDEO, Kind.AUDIO, Kind.MODEL3D)
    optional_keys = ("EUROPEANA_API_KEY",)
    signup_url = "https://pro.europeana.eu/pages/get-api"
    API = "https://api.europeana.eu/record/v2/search.json"
    TYPES = {"IMAGE": Kind.IMAGE, "VIDEO": Kind.VIDEO, "SOUND": Kind.AUDIO, "3D": Kind.MODEL3D, "TEXT": Kind.IMAGE}
    QF = {Kind.IMAGE: "TYPE:IMAGE", Kind.VIDEO: "TYPE:VIDEO", Kind.AUDIO: "TYPE:SOUND", Kind.MODEL3D: "TYPE:3D"}

    def hourly_budget(self) -> int | None:
        return 60 if self.settings.key("EUROPEANA_API_KEY") in ("", "api2demo") else None

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        limit = min(limit, 50)
        params: list[tuple[str, Any]] = [
            ("wskey", self.settings.key("EUROPEANA_API_KEY") or "api2demo"), ("query", query), ("rows", limit),
            ("start", (page - 1) * limit + 1), ("media", "true"), ("thumbnail", "true"), ("reusability", "open"),
            ("profile", "standard"),
        ]
        wanted = [k for k in self.kinds if kinds and k in kinds]
        if len(wanted) == 1:
            params.append(("qf", self.QF[wanted[0]]))
        data = await self.get(self.API, params=params)
        out = [a for a in (self.parse(it) for it in data.get("items") or []) if a and (not kinds or a.kind in kinds)]
        return SearchResult(out, exhausted=page * limit >= int(data.get("totalResults") or 0))

    def parse(self, it: dict[str, Any]) -> Asset | None:
        thumb = first(it.get("edmPreview"))
        if not thumb:
            return None
        kind = self.TYPES.get(it.get("type") or "", Kind.IMAGE)
        rights = first(it.get("rights"))
        landing = (it.get("guid") or first(it.get("edmIsShownAt")) or "").split("?", 1)[0]
        labels = [c.get("def") for c in it.get("edmConceptLabel") or [] if isinstance(c, dict)]
        return self.make(
            source_id=(it.get("id") or "").strip("/").replace("/", "_"),
            kind=kind,
            title=first(it.get("title")) or "Untitled",
            description=strip_html(first(it.get("dcDescription")))[:1500],
            tags=labels[:15] + [first(it.get("dataProvider"))],
            author=first(it.get("dcCreator")) or first(it.get("dataProvider")),
            page_url=landing,
            thumb_url=thumb,
            preview_url=first(it.get("edmIsShownBy")) or thumb,
            download_url=first(it.get("edmIsShownBy")) or "",
            license=normalize_license(None, rights),
            created_at=str(first(it.get("year"))),
            extra={"provider": first(it.get("dataProvider"))},
        )
