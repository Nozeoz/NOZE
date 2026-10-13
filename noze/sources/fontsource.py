"""Fontsource — 1,500+ open-source font families (all of Google Fonts and more)."""

from __future__ import annotations

import time
from typing import Any

from ..licenses import LicenseInfo, known
from ..models import Asset, Kind, Usage
from .base import DownloadPart, SearchResult, Source, words

API = "https://api.fontsource.org/v1/fonts"
CDN = "https://cdn.jsdelivr.net/fontsource/fonts"

# vibe words -> font categories, so "retro poster" still finds display faces
FONT_VIBES = {
    "retro": ["display"], "vintage": ["serif", "display"], "elegant": ["serif"], "luxury": ["serif"],
    "classic": ["serif"], "editorial": ["serif"], "handwriting": ["handwriting"], "handwritten": ["handwriting"],
    "script": ["handwriting"], "signature": ["handwriting"], "calligraphy": ["handwriting"], "cute": ["handwriting", "display"],
    "fun": ["display", "handwriting"], "playful": ["display", "handwriting"], "code": ["monospace"], "mono": ["monospace"],
    "monospace": ["monospace"], "tech": ["monospace", "sans-serif"], "cyberpunk": ["monospace", "display"],
    "futuristic": ["display", "sans-serif"], "minimal": ["sans-serif"], "minimalist": ["sans-serif"],
    "modern": ["sans-serif"], "clean": ["sans-serif"], "bold": ["display"], "poster": ["display"],
    "headline": ["display"], "title": ["display"], "horror": ["display"], "pixel": ["display"], "serif": ["serif"],
    "sans": ["sans-serif"], "display": ["display"], "brutalist": ["display", "sans-serif"], "swiss": ["sans-serif"],
}

OPEN_FONT = LicenseInfo("ofl-1.1", "Open font license (OFL/Apache, via Google Fonts)", Usage.FREE, "https://fonts.google.com/knowledge/glossary/open_font_license")


class Fontsource(Source):
    name = "fontsource"
    label = "Fontsource"
    homepage = "https://fontsource.org"
    description = "Open-source fonts (all Google Fonts + more): searchable by name and vibe."
    kinds = (Kind.FONT,)

    def __init__(self, settings, http):
        super().__init__(settings, http)
        self._fonts: list[dict[str, Any]] = []
        self._ts = 0.0

    async def fonts(self) -> list[dict[str, Any]]:
        if not self._fonts or time.time() - self._ts > 24 * 3600:
            data = await self.get(API)
            self._fonts = data if isinstance(data, list) else []
            self._ts = time.time()
        return self._fonts

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        fonts = await self.fonts()
        terms = words(query)
        cats: set[str] = set()
        for t in terms:
            cats.update(FONT_VIBES.get(t, []))
        scored: list[tuple[float, dict]] = []
        for f in fonts:
            family = (f.get("family") or "").lower()
            fid = (f.get("id") or "").lower()
            score = 0.0
            for t in terms:
                if t in family.split() or t == fid:
                    score += 5
                elif t in family or t in fid:
                    score += 3
            if f.get("category") in cats:
                score += 2
            if f.get("category") and f["category"] in terms:
                score += 2
            if terms and score == 0:
                continue
            score += 0.3 if f.get("variable") else 0.0
            score += min(len(f.get("weights") or []), 9) * 0.05
            scored.append((score, f))
        scored.sort(key=lambda s: (-s[0], s[1].get("family") or ""))
        if kinds and Kind.FONT not in kinds:
            return SearchResult([], exhausted=True)
        if not kinds and len(terms) > 1:
            # mixed "All" searches: only fonts that really match the words, not every
            # family that happens to contain "night" or "city"
            need = 5 * (len(terms) + 1) // 2
            scored = [x for x in scored if x[0] >= need][:6]
        start = (page - 1) * limit
        return SearchResult([self.parse(f) for _, f in scored[start:start + limit]], exhausted=start + limit >= len(scored))

    def parse(self, f: dict[str, Any]) -> Asset:
        fid = f.get("id") or ""
        subset = f.get("defSubset") or "latin"
        weights = f.get("weights") or [400]
        weight = 400 if 400 in weights else weights[0]
        styles = f.get("styles") or ["normal"]
        style = "normal" if "normal" in styles else styles[0]
        tags = [f.get("category"), f.get("type")] + (["variable"] if f.get("variable") else []) + list(f.get("subsets") or [])[:4]
        return self.make(
            source_id=fid,
            kind=Kind.FONT,
            title=f.get("family") or fid,
            description=f"{f.get('category', '')} font · weights {', '.join(str(w) for w in weights)}",
            tags=tags,
            author="Fontsource",
            page_url=f"https://fontsource.org/fonts/{fid}",
            preview_url=f"{CDN}/{fid}@latest/{subset}-{weight}-{style}.woff2",
            download_url=f"{CDN}/{fid}@latest/{subset}-{weight}-{style}.ttf",
            width=3,
            height=2,
            license=OPEN_FONT if f.get("type") == "google" else known("unknown"),
            created_at=f.get("lastModified") or "",
            extra={"family": f.get("family"), "weights": weights, "styles": styles, "subset": subset,
                   "category": f.get("category"), "variable": bool(f.get("variable"))},
        )

    async def resolve_download(self, asset: dict[str, Any]) -> list[DownloadPart]:
        ex = asset.get("extra") or {}
        fid, subset = asset["source_id"], ex.get("subset") or "latin"
        parts = []
        for w in ex.get("weights") or [400]:
            for style in ex.get("styles") or ["normal"]:
                parts.append(DownloadPart(f"{CDN}/{fid}@latest/{subset}-{w}-{style}.ttf", f"{fid}-{w}-{style}.ttf"))
        return parts
