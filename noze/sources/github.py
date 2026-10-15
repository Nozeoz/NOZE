"""GitHub — repos with motion scripts, shaders, After Effects/Blender tools,
Lottie packs, icon sets, fonts, design systems, awesome-lists… Keyless works
(10 searches/min); a token raises it."""

from __future__ import annotations

from typing import Any

from ..licenses import known, normalize_license
from ..models import Asset, Kind
from .base import SearchResult, Source

API = "https://api.github.com/search/repositories"


class GitHub(Source):
    name = "github"
    label = "GitHub"
    homepage = "https://github.com"
    description = "Open-source creative code: AE/Blender scripts, shaders, Lottie packs, icon/font sets, templates."
    kinds = (Kind.CODE,)
    optional_keys = ("GITHUB_TOKEN",)
    signup_url = "https://github.com/settings/tokens"
    min_interval = 2.0

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.settings.key("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {self.settings.key('GITHUB_TOKEN')}"
        per_page = min(limit, 50)
        if page * per_page > 1000:
            return SearchResult([], exhausted=True)
        data = await self.get(API, headers=headers, params={
            "q": f"{query} fork:false archived:false", "per_page": per_page, "page": page,
        })
        out = [self.parse(r) for r in data.get("items") or []]
        return SearchResult(out, exhausted=page * per_page >= min(int(data.get("total_count") or 0), 1000))

    def parse(self, r: dict[str, Any]) -> Asset:
        full = r.get("full_name") or ""
        lic = r.get("license") or {}
        spdx = (lic.get("spdx_id") or "") if isinstance(lic, dict) else ""
        if not lic:
            info = known("no-license")
        elif spdx in ("", "NOASSERTION"):
            info = normalize_license("NOASSERTION")
        else:
            info = normalize_license(spdx, lic.get("url") or "")
        branch = r.get("default_branch") or "main"
        return self.make(
            source_id=r.get("id") or full,
            kind=Kind.CODE,
            title=full,
            description=r.get("description") or "",
            tags=list(r.get("topics") or []) + ([r["language"]] if r.get("language") else []),
            author=(r.get("owner") or {}).get("login") or "",
            author_url=(r.get("owner") or {}).get("html_url") or "",
            page_url=r.get("html_url") or f"https://github.com/{full}",
            thumb_url=f"https://opengraph.githubassets.com/1/{full}",
            download_url=f"https://github.com/{full}/archive/refs/heads/{branch}.zip",
            width=1200,
            height=600,
            license=info,
            popularity=float(r.get("stargazers_count") or 0),
            created_at=(r.get("pushed_at") or r.get("updated_at") or "")[:10],
            extra={"stars": r.get("stargazers_count"), "language": r.get("language")},
        )
