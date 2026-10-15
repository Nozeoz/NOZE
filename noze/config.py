"""Settings, read from environment variables and optional .env files.

Every knob has a sane default so `noze serve` works with zero configuration;
API keys only unlock extra sources.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Every API key / credential NOZE understands. Sources look them up by name.
KEY_NAMES = (
    "PEXELS_API_KEY",
    "PIXABAY_API_KEY",
    "UNSPLASH_ACCESS_KEY",
    "FREESOUND_API_KEY",
    "GIPHY_API_KEY",
    "SMITHSONIAN_API_KEY",
    "EUROPEANA_API_KEY",
    "GITHUB_TOKEN",
    "OPENVERSE_CLIENT_ID",
    "OPENVERSE_CLIENT_SECRET",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "ARENA_TOKEN",
    "WALLHAVEN_API_KEY",
    "TUMBLR_API_KEY",
    "FLICKR_API_KEY",
    "DEVIANTART_CLIENT_ID",
    "DEVIANTART_CLIENT_SECRET",
    "VIMEO_ACCESS_TOKEN",
    "YOUTUBE_API_KEY",
    "WIKIMEDIA_TOKEN",
    "PINTEREST_ACCESS_TOKEN",
    "PINTEREST_APP_ID",
    "PINTEREST_APP_SECRET",
    "REPLICATE_API_TOKEN",
)

# Public demo keys that work (slowly) out of the box.
DEFAULT_KEYS = {
    "SMITHSONIAN_API_KEY": "DEMO_KEY",
    "EUROPEANA_API_KEY": "api2demo",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {v.strip().lower() for v in value.split(",") if v.strip()}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path("noze-data"))
    host: str = "127.0.0.1"
    port: int = 8787
    password: str = ""
    contact: str = ""
    embedder: str = "auto"
    storage: str = "local"
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "auto"
    s3_prefix: str = "noze/"
    thumb_size: int = 360
    cache_ttl_hours: float = 168.0
    live_timeout: float = 12.0
    per_source: int = 30
    auto_download_on_save: bool = True
    max_download_mb: int = 500
    video_max_width: int = 1920
    safe_search: bool = True
    worker: bool = True
    autopilot: bool = True
    pinterest_sync_hours: float = 6.0
    allow_private_fetch: bool = False
    disabled_sources: set[str] = field(default_factory=set)
    only_sources: set[str] = field(default_factory=set)
    gen_image_model: str = "black-forest-labs/flux-schnell"
    gen_video_model: str = "bytedance/seedance-1-lite"
    keys: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, data_dir: str | Path | None = None, env: dict[str, str] | None = None,
             dotenv: bool = True) -> "Settings":
        merged: dict[str, str] = {}
        # .env files first; real environment variables win.
        if dotenv:
            merged.update(_parse_env_file(Path.cwd() / ".env"))
        base_env = dict(os.environ) if env is None else dict(env)
        dd = Path(data_dir or base_env.get("NOZE_DATA_DIR") or merged.get("NOZE_DATA_DIR") or "noze-data")
        if dotenv:
            merged.update(_parse_env_file(dd / ".env"))
        merged.update(base_env)

        def get(name: str, default: str = "") -> str:
            return merged.get(name, default)

        keys = {k: v for k, v in DEFAULT_KEYS.items()}
        for name in KEY_NAMES:
            if merged.get(name):
                keys[name] = merged[name]

        return cls(
            data_dir=dd.expanduser().resolve(),
            host=get("NOZE_HOST", "127.0.0.1"),
            port=int(get("NOZE_PORT", "8787") or 8787),
            password=get("NOZE_PASSWORD"),
            contact=get("NOZE_CONTACT"),
            embedder=(get("NOZE_EMBEDDER", "auto") or "auto").lower(),
            storage=(get("NOZE_STORAGE", "local") or "local").lower(),
            s3_endpoint=get("NOZE_S3_ENDPOINT"),
            s3_bucket=get("NOZE_S3_BUCKET"),
            s3_access_key=get("NOZE_S3_ACCESS_KEY"),
            s3_secret_key=get("NOZE_S3_SECRET_KEY"),
            s3_region=get("NOZE_S3_REGION", "auto") or "auto",
            s3_prefix=get("NOZE_S3_PREFIX", "noze/"),
            thumb_size=int(get("NOZE_THUMB_SIZE", "360") or 360),
            cache_ttl_hours=float(get("NOZE_CACHE_TTL_HOURS", "168") or 168),
            live_timeout=float(get("NOZE_LIVE_TIMEOUT", "12") or 12),
            per_source=int(get("NOZE_PER_SOURCE", "30") or 30),
            auto_download_on_save=_bool(get("NOZE_AUTO_DOWNLOAD_ON_SAVE"), True),
            max_download_mb=int(get("NOZE_MAX_DOWNLOAD_MB", "500") or 500),
            video_max_width=int(get("NOZE_VIDEO_MAX_WIDTH", "1920") or 1920),
            safe_search=_bool(get("NOZE_SAFE_SEARCH"), True),
            worker=_bool(get("NOZE_WORKER"), True),
            autopilot=_bool(get("NOZE_AUTOPILOT"), True),
            pinterest_sync_hours=float(get("NOZE_PINTEREST_SYNC_HOURS", "6") or 6),
            allow_private_fetch=_bool(get("NOZE_ALLOW_PRIVATE_FETCH"), False),
            disabled_sources=_csv(get("NOZE_DISABLED_SOURCES")),
            only_sources=_csv(get("NOZE_SOURCES")),
            gen_image_model=get("NOZE_GEN_IMAGE_MODEL", "black-forest-labs/flux-schnell"),
            gen_video_model=get("NOZE_GEN_VIDEO_MODEL", "bytedance/seedance-1-lite"),
            keys=keys,
        )

    def key(self, name: str) -> str:
        return self.keys.get(name, "")

    @property
    def user_agent(self) -> str:
        # format recommended by Wikimedia's User-Agent policy: name/version (contact)
        contact = f"; {self.contact}" if self.contact else ""
        return f"NOZE/0.1 (https://github.com/nozeoz/noze{contact})"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "noze.db"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.thumbs_dir, self.tmp_dir):
            d.mkdir(parents=True, exist_ok=True)
