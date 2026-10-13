"""The single asset shape every source is normalized into."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Kind:
    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"
    MOTION = "motion"  # Lottie / animated vector
    AUDIO = "audio"
    MODEL3D = "3d"
    TEXTURE = "texture"
    HDRI = "hdri"
    ICON = "icon"
    FONT = "font"
    CODE = "code"  # repos: scripts, shaders, plugins, templates-as-code
    TEMPLATE = "template"  # .aep / .mogrt / .psd / LUTs / presets
    LINK = "link"  # bookmarked page without direct media

    ALL = (
        IMAGE, VIDEO, GIF, MOTION, AUDIO, MODEL3D, TEXTURE, HDRI, ICON, FONT, CODE, TEMPLATE, LINK,
    )


# UI shortcuts: one chip can mean several kinds.
KIND_GROUPS: dict[str, tuple[str, ...]] = {
    "moving": (Kind.VIDEO, Kind.GIF, Kind.MOTION),
    "design": (Kind.IMAGE, Kind.ICON, Kind.FONT, Kind.TEXTURE, Kind.TEMPLATE),
    "3d-all": (Kind.MODEL3D, Kind.TEXTURE, Kind.HDRI),
    "sound": (Kind.AUDIO,),
}


def expand_kinds(values) -> set[str]:
    """Accept kinds or group names ("moving", "3d-all") and return concrete kinds."""
    out: set[str] = set()
    for v in values or ():
        v = (v or "").strip().lower()
        if v in Kind.ALL:
            out.add(v)
        elif v in KIND_GROUPS:
            out.update(KIND_GROUPS[v])
    return out


class Usage:
    FREE = "free"  # commercial OK, no credit required
    CREDIT = "credit"  # commercial OK, credit/notice required
    NONCOMMERCIAL = "noncommercial"
    REFERENCE = "reference"  # rights reserved / unknown origin: inspiration only
    CHECK = "check"  # unclear, verify on the source page
    OWN = "own"  # your own files / generations

    ALL = (FREE, CREDIT, NONCOMMERCIAL, REFERENCE, CHECK, OWN)
    USABLE = (FREE, CREDIT, OWN)


USAGE_PRESETS: dict[str, tuple[str, ...]] = {
    "usable": Usage.USABLE,
    "free": (Usage.FREE, Usage.OWN),
    "any": Usage.ALL,
}


def expand_usages(values) -> set[str]:
    out: set[str] = set()
    for v in values or ():
        v = (v or "").strip().lower()
        if v in USAGE_PRESETS:
            out.update(USAGE_PRESETS[v])
        elif v in Usage.ALL:
            out.add(v)
    return out


def make_id(source: str, source_id: str) -> str:
    return f"{source}:{source_id}"


@dataclass
class Asset:
    source: str
    source_id: str
    kind: str
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    author: str = ""
    author_url: str = ""
    page_url: str = ""
    thumb_url: str = ""
    preview_url: str = ""
    download_url: str = ""
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    license: str = "unknown"
    license_label: str = ""
    license_url: str = ""
    usage: str = Usage.CHECK
    attribution: str = ""
    popularity: float = 0.0
    created_at: str = ""
    colors: list[list[Any]] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return make_id(self.source, str(self.source_id))

    def clean(self) -> "Asset":
        """Normalize whitespace, dedupe tags, coerce numbers; returns self."""
        self.source_id = str(self.source_id)
        self.title = _squash(self.title)[:300]
        self.description = _squash(self.description)[:4000]
        self.author = _squash(self.author)[:200]
        seen: set[str] = set()
        tags: list[str] = []
        for t in self.tags or []:
            t = _squash(str(t)).lower().strip("#,;. ")
            if t and len(t) <= 60 and t not in seen:
                seen.add(t)
                tags.append(t)
        self.tags = tags[:40]
        self.width = _int_or_none(self.width)
        self.height = _int_or_none(self.height)
        try:
            self.duration = float(self.duration) if self.duration not in (None, "") else None
        except (TypeError, ValueError):
            self.duration = None
        try:
            self.popularity = float(self.popularity or 0)
        except (TypeError, ValueError):
            self.popularity = 0.0
        for attr in ("thumb_url", "preview_url", "download_url", "page_url", "author_url", "license_url"):
            value = (getattr(self, attr) or "").strip()
            if value.startswith("//"):
                value = "https:" + value
            # only web links or our own API paths; never javascript:/data:/file: URLs
            if value and not value.lower().startswith(("http://", "https://", "/api/")):
                value = ""
            setattr(self, attr, value)
        return self


def _squash(text: Any) -> str:
    if text is None:
        return ""
    return " ".join(str(text).split())


def _int_or_none(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
