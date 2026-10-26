"""Get a source video onto disk: local paths, NOZE bank assets, direct file URLs,
or (opt-in) platform links through yt-dlp — only for content the campaign lets you clip."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ...http import check_public_url
from .ffmpeg import MediaError

log = logging.getLogger("noze.agency.fetch")

PLATFORM_HOSTS = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com", "x.com", "twitter.com", "twitch.tv",
                  "kick.com", "vimeo.com", "drive.google.com", "facebook.com", "fb.watch", "rumble.com")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")


def is_platform_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in PLATFORM_HOSTS)


def _ytdlp_cmd() -> list[str] | None:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # type: ignore  # noqa: F401

        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def fetch_source(ref: str, dest_dir: Path, *, allow_download: bool = False, allow_private: bool = False,
                 max_mb: int = 4000, bank_path=None) -> Path:
    """Resolve ``ref`` to a local video file.

    ``bank_path`` is an optional callable ``asset_id -> Path | None`` for NOZE assets (``noze:<id>``)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if ref.startswith("noze:") and bank_path:
        p = bank_path(ref[5:])
        if not p:
            raise MediaError(f"bank asset {ref[5:]} has no stored file — press Download in NOZE first")
        return Path(p)
    if not ref.lower().startswith(("http://", "https://")):
        p = Path(ref).expanduser()
        if not p.exists():
            raise MediaError(f"source file not found: {ref}")
        return p.resolve()
    key = hashlib.sha1(ref.encode()).hexdigest()[:12]
    if is_platform_url(ref):
        if not allow_download:
            raise MediaError("platform links need AGENCY_ALLOW_DOWNLOAD=1 (only for content the campaign lets you "
                             "clip — most campaigns share a Drive/Dropbox folder of raw footage instead)")
        cmd = _ytdlp_cmd()
        if not cmd:
            raise MediaError("install yt-dlp to fetch platform links: pip install yt-dlp")
        out_tpl = str(dest_dir / f"src_{key}.%(ext)s")
        existing = sorted(dest_dir.glob(f"src_{key}.*"))
        video = next((p for p in existing if p.suffix in VIDEO_EXT), None)
        if video:
            return video
        args = cmd + ["--no-playlist", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
                      "--write-auto-subs", "--write-subs", "--sub-langs", "en.*,id.*", "--sub-format", "vtt",
                      "--max-filesize", f"{max_mb}M", "-o", out_tpl, ref]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise MediaError(f"yt-dlp failed: {proc.stderr.strip()[-500:]}")
        video = next((p for p in sorted(dest_dir.glob(f"src_{key}.*")) if p.suffix in VIDEO_EXT), None)
        if not video:
            raise MediaError("yt-dlp finished but no video file was written")
        return video
    # direct file URL (Dropbox ?dl=1, a CDN link, your own server …)
    asyncio.run(check_public_url(ref, allow_private))
    suffix = Path(urlparse(ref).path).suffix.lower()
    dest = dest_dir / f"src_{key}{suffix if suffix in VIDEO_EXT else '.mp4'}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    limit = max_mb * 1024 * 1024
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        with client.stream("GET", ref) as resp:
            if resp.status_code >= 400:
                raise MediaError(f"download failed: HTTP {resp.status_code}")
            for hop in resp.history:
                asyncio.run(check_public_url(str(hop.headers.get("location") or hop.url), allow_private))
            ctype = resp.headers.get("content-type", "")
            if ctype.startswith("text/html"):
                raise MediaError("that link is a web page, not a video file — use the direct download link")
            size = 0
            with tmp.open("wb") as fh:
                for chunk in resp.iter_bytes(1 << 20):
                    size += len(chunk)
                    if size > limit:
                        raise MediaError(f"file is larger than {max_mb} MB")
                    fh.write(chunk)
    tmp.replace(dest)
    return dest
