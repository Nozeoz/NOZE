"""Base class and helpers shared by every source connector."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..config import Settings
from ..http import Http
from ..licenses import LicenseInfo, attribution_line, known
from ..models import Asset


@dataclass
class SearchResult:
    assets: list[Asset] = field(default_factory=list)
    cursor: str | None = None  # opaque token for the next page (cursor-paginated APIs)
    exhausted: bool = False


@dataclass
class DownloadPart:
    url: str
    name: str = ""
    headers: dict[str, str] | None = None


_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, (list, tuple)):
        text = " ".join(str(t) for t in text if t)
    text = _TAG_RE.sub(" ", str(text))
    return " ".join(html.unescape(text).split())


def first(value: Any, default: Any = "") -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return default if value is None else value


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 1]


def slug_title(url: str) -> str:
    """'…/video/drone-shot-of-a-city-1234/' -> 'drone shot of a city'."""
    part = (url or "").rstrip("/").rsplit("/", 1)[-1]
    part = re.sub(r"[-_]\d+$", "", part)
    return " ".join(part.replace("_", "-").split("-")).strip()


class Source:
    name = ""
    label = ""
    homepage = ""
    description = ""
    kinds: tuple[str, ...] = ()
    key_names: tuple[str, ...] = ()  # all required
    optional_keys: tuple[str, ...] = ()
    signup_url = ""
    credit = ""  # visible credit some APIs ask for ("Powered by …")
    hotlink = False  # show thumbnails from the source's URLs (Unsplash requires this)
    supports_related = False
    min_interval = 0.0  # seconds between calls
    budget_per_hour: int | None = None
    default_enabled = True

    def __init__(self, settings: Settings, http: Http):
        self.settings = settings
        self.http = http

    # -- availability ------------------------------------------------------
    def missing_keys(self) -> list[str]:
        return [k for k in self.key_names if not self.settings.key(k)]

    @property
    def enabled(self) -> bool:
        s = self.settings
        if self.name in s.disabled_sources:
            return False
        if s.only_sources:
            return self.name in s.only_sources and not self.missing_keys()
        return self.default_enabled and not self.missing_keys()

    def supports(self, kinds: set[str] | None) -> bool:
        return not kinds or bool(set(self.kinds) & set(kinds))

    def hourly_budget(self) -> int | None:
        return self.budget_per_hour

    # -- API surface -------------------------------------------------------
    async def search(self, query: str, kinds: set[str], page: int, limit: int, cursor: str | None = None) -> SearchResult:
        raise NotImplementedError

    async def related(self, asset: dict[str, Any], limit: int = 30) -> list[Asset]:
        return []

    async def hydrate(self, asset: dict[str, Any]) -> dict[str, Any] | None:
        """Fill in fields that need an extra call (e.g. playable preview URL). Return changed fields."""
        return None

    async def resolve_download(self, asset: dict[str, Any]) -> list[DownloadPart]:
        url = asset.get("download_url") or asset.get("preview_url") or ""
        return [DownloadPart(url)] if url else []

    async def on_download(self, asset: dict[str, Any]) -> None:
        """Hook for APIs that want to be pinged when a file is downloaded (Unsplash)."""

    def fetch_headers(self) -> dict[str, str]:
        """Extra headers some image hosts need when NOZE fetches thumbnails/files server-side."""
        return {}

    # -- helpers -----------------------------------------------------------
    async def get(self, url: str, **kw: Any) -> Any:
        return await self.http.get_json(url, rate_key=self.name, min_interval=self.min_interval, **kw)

    async def post(self, url: str, payload: Any, **kw: Any) -> Any:
        return await self.http.post_json(url, payload, rate_key=self.name, min_interval=self.min_interval, **kw)

    def make(self, *, source_id: Any, kind: str, license: LicenseInfo | None = None, tags: Iterable[Any] = (),
             **fields: Any) -> Asset:
        lic = license or known("unknown")
        a = Asset(source=self.name, source_id=str(source_id), kind=kind, tags=[str(t) for t in tags if t], **fields)
        a.license, a.license_label, a.usage = lic.code, lic.label, lic.usage
        a.license_url = a.license_url or lic.url
        if not a.attribution:
            a.attribution = attribution_line(a.title, a.author, self.label, lic.label, a.page_url)
        return a

    def info(self) -> dict[str, Any]:
        return {
            "name": self.name, "label": self.label, "homepage": self.homepage, "description": self.description,
            "kinds": list(self.kinds), "enabled": self.enabled, "missing_keys": self.missing_keys(),
            "optional_keys": list(self.optional_keys), "signup_url": self.signup_url, "credit": self.credit,
            "hotlink": self.hotlink, "related": self.supports_related,
        }
