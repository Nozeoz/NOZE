"""LottieFiles — free Lottie animations (Lottie Simple License: free for
commercial use, no attribution required)."""

from __future__ import annotations

from typing import Any

from ..http import SourceError
from ..licenses import known
from ..models import Asset, Kind
from .base import SearchResult, Source

API = "https://graphql.lottiefiles.com/2022-08"
FULL = "id name url lottieUrl jsonUrl gifUrl imageUrl videoUrl bgColor downloads likesCount createdBy { username firstName lastName }"
MINIMAL = "id name url lottieUrl jsonUrl gifUrl imageUrl"
QUERY = """query Search($q: String!, $first: Int, $after: String) {
  searchPublicAnimations(query: $q, first: $first, after: $after) {
    edges { node { %s } }
    pageInfo { hasNextPage endCursor }
  }
}"""


class LottieFiles(Source):
    name = "lottiefiles"
    label = "LottieFiles"
    homepage = "https://lottiefiles.com/free-animations"
    description = "Free Lottie animations (UI, icons, loaders, characters) — Lottie Simple License."
    kinds = (Kind.MOTION,)
    min_interval = 0.3

    async def _query(self, fields: str, variables: dict[str, Any]) -> dict[str, Any]:
        body = await self.post(API, {"query": QUERY % fields, "variables": variables})
        if body.get("errors") and not (body.get("data") or {}).get("searchPublicAnimations"):
            raise SourceError("GraphQL: " + str(body["errors"][0].get("message", "error"))[:160])
        return (body.get("data") or {}).get("searchPublicAnimations") or {}

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        if page > 1 and not cursor:
            return SearchResult([], exhausted=True)
        variables = {"q": query, "first": min(limit, 50), "after": cursor}
        try:
            conn = await self._query(FULL, variables)
        except SourceError:
            conn = await self._query(MINIMAL, variables)
        edges = conn.get("edges") or []
        info = conn.get("pageInfo") or {}
        out = [a for a in (self.parse(e.get("node") or {}) for e in edges) if a]
        return SearchResult(out, cursor=info.get("endCursor"), exhausted=not info.get("hasNextPage"))

    def parse(self, n: dict[str, Any]) -> Asset | None:
        if not n.get("id") or not (n.get("jsonUrl") or n.get("lottieUrl")):
            return None
        creator = n.get("createdBy") or {}
        name = n.get("name") or "Lottie animation"
        author = creator.get("username") or " ".join(x for x in (creator.get("firstName"), creator.get("lastName")) if x)
        return self.make(
            source_id=n["id"],
            kind=Kind.MOTION,
            title=name,
            tags=["lottie", "animation"] + name.lower().replace("-", " ").split(),
            author=author or "",
            author_url=f"https://lottiefiles.com/{creator['username']}" if creator.get("username") else "",
            page_url=n.get("url") or "",
            thumb_url=n.get("imageUrl") or n.get("gifUrl") or "",
            preview_url=n.get("jsonUrl") or n.get("lottieUrl") or "",
            download_url=n.get("jsonUrl") or n.get("lottieUrl") or "",
            width=1,
            height=1,
            license=known("lottie-simple"),
            popularity=float(n.get("downloads") or 0) + 5 * float(n.get("likesCount") or 0),
            extra={"video": n.get("videoUrl"), "gif": n.get("gifUrl"), "lottie": n.get("lottieUrl"),
                   "bg": n.get("bgColor")},
        )
