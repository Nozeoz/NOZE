"""Openverse — 800M+ openly licensed images and audio (Flickr, Wikimedia,
museums, Jamendo, ccMixter…). Keyless works but is throttled hard; register a
free OAuth app for more: https://api.openverse.org/v1/#tag/auth"""

from __future__ import annotations

import time
from typing import Any

from ..licenses import normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source

API = "https://api.openverse.org/v1"


class Openverse(Source):
    name = "openverse"
    label = "Openverse"
    homepage = "https://openverse.org"
    description = "800M+ CC-licensed images & audio aggregated from Flickr, Wikimedia, museums, Jamendo…"
    kinds = (Kind.IMAGE, Kind.AUDIO)
    optional_keys = ("OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET")
    signup_url = "https://api.openverse.org/v1/#tag/auth/operation/register"
    supports_related = True
    min_interval = 0.5

    def __init__(self, settings, http):
        super().__init__(settings, http)
        self._token: str | None = None
        self._token_exp = 0.0

    @property
    def _has_auth(self) -> bool:
        return bool(self.settings.key("OPENVERSE_CLIENT_ID") and self.settings.key("OPENVERSE_CLIENT_SECRET"))

    def hourly_budget(self) -> int | None:
        return None if self._has_auth else 20

    async def _headers(self) -> dict[str, str]:
        if not self._has_auth:
            return {}
        if not self._token or time.time() > self._token_exp - 60:
            resp = await self.http.request(
                "POST", f"{API}/auth_tokens/token/",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.key("OPENVERSE_CLIENT_ID"),
                    "client_secret": self.settings.key("OPENVERSE_CLIENT_SECRET"),
                },
            )
            body = resp.json()
            self._token = body.get("access_token")
            self._token_exp = time.time() + float(body.get("expires_in") or 3600)
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        headers = await self._headers()
        page_size = min(limit, 50 if self._has_auth else 20)
        out: list[Asset] = []
        exhausted = True
        for media, kind in (("images", Kind.IMAGE), ("audio", Kind.AUDIO)):
            if kinds and kind not in kinds:
                continue
            params: dict[str, Any] = {"q": query, "page": page, "page_size": page_size}
            if self.settings.safe_search:
                params["mature"] = "false"
            data = await self.get(f"{API}/{media}/", params=params, headers=headers)
            out.extend(self.parse(r, kind) for r in data.get("results") or [] if not r.get("mature"))
            if page < int(data.get("page_count") or 0):
                exhausted = False
        return SearchResult(out, exhausted=exhausted)

    async def related(self, asset: dict[str, Any], limit: int = 30) -> list[Asset]:
        kind = Kind.AUDIO if asset["kind"] == Kind.AUDIO else Kind.IMAGE
        media = "audio" if kind == Kind.AUDIO else "images"
        data = await self.get(f"{API}/{media}/{asset['source_id']}/related/", headers=await self._headers())
        results = data.get("results") if isinstance(data, dict) else data
        return [self.parse(r, kind) for r in (results or [])[:limit] if not r.get("mature")]

    def parse(self, r: dict[str, Any], kind: str) -> Asset:
        lic = normalize_license(f"{r.get('license') or ''} {r.get('license_version') or ''}".strip(), r.get("license_url"))
        tags = [t.get("name") for t in r.get("tags") or [] if isinstance(t, dict) and t.get("name")]
        tags += [g for g in r.get("genres") or [] if g]
        if r.get("category"):
            tags.append(r["category"])
        provider = r.get("source") or r.get("provider") or ""
        duration = r.get("duration")
        return self.make(
            source_id=r["id"],
            kind=kind,
            title=r.get("title") or "",
            tags=tags,
            author=r.get("creator") or "",
            author_url=r.get("creator_url") or "",
            page_url=r.get("foreign_landing_url") or "",
            thumb_url=r.get("thumbnail") or (r.get("url") if kind == Kind.IMAGE else "") or "",
            preview_url=r.get("url") or "",
            download_url=r.get("url") or "",
            width=r.get("width"),
            height=r.get("height"),
            duration=(duration / 1000.0) if isinstance(duration, (int, float)) and duration else None,
            license=lic,
            license_url=r.get("license_url") or "",
            attribution=r.get("attribution") or "",
            extra={"provider": provider, "filetype": r.get("filetype")},
        )
