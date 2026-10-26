"""Thin, dependency-free wrappers around the ffmpeg/ffprobe binaries."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

log = logging.getLogger("noze.agency.media")


class MediaError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    return shutil.which("ffmpeg") or ""


def ffprobe_bin() -> str:
    return shutil.which("ffprobe") or ""


def available() -> bool:
    return bool(ffmpeg_bin() and ffprobe_bin())


def run(args: Sequence[str], timeout: float | None = 3600, cwd: str | Path | None = None,
        check: bool = True, binary: str = "ffmpeg", input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    exe = ffmpeg_bin() if binary == "ffmpeg" else ffprobe_bin()
    if not exe:
        raise MediaError(f"{binary} not found — install ffmpeg (https://ffmpeg.org/download.html)")
    cmd = [exe, "-hide_banner", *args] if binary == "ffmpeg" else [exe, *args]
    log.debug("run: %s", " ".join(cmd)[:2000])
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout, input=input_bytes)
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"{binary} timed out after {timeout}s") from exc
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace")
        tail = "\n".join(line for line in err.splitlines()[-25:] if line.strip())
        raise MediaError(f"{binary} failed ({proc.returncode}):\n{tail}")
    return proc


def stderr_text(proc: subprocess.CompletedProcess) -> str:
    return proc.stderr.decode("utf-8", "replace")


def _rate(value: str | None) -> float:
    if not value or value in ("0/0", "N/A"):
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path: str | Path) -> dict[str, Any]:
    """Duration, size, fps, codecs and audio presence of a media file."""
    proc = run(["-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
               binary="ffprobe", timeout=120)
    data = json.loads(proc.stdout or b"{}")
    fmt = data.get("format") or {}
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    out: dict[str, Any] = {
        "path": str(path),
        "duration": float(fmt.get("duration") or 0.0),
        "size": int(fmt.get("size") or 0),
        "bitrate": int(fmt.get("bit_rate") or 0),
        "format": fmt.get("format_name") or "",
        "has_video": video is not None,
        "has_audio": audio is not None,
    }
    if video:
        w, h = int(video.get("width") or 0), int(video.get("height") or 0)
        rotation = 0
        for sd in video.get("side_data_list") or []:
            if "rotation" in sd:
                rotation = int(sd["rotation"])
        rotation = int((video.get("tags") or {}).get("rotate") or rotation)
        if abs(rotation) % 180 == 90:
            w, h = h, w
        out.update({
            "width": w, "height": h, "rotation": rotation,
            "fps": _rate(video.get("avg_frame_rate")) or _rate(video.get("r_frame_rate")),
            "vcodec": video.get("codec_name") or "", "pix_fmt": video.get("pix_fmt") or "",
        })
        if not out["duration"]:
            out["duration"] = float(video.get("duration") or 0.0)
    if audio:
        out.update({
            "acodec": audio.get("codec_name") or "", "sample_rate": int(audio.get("sample_rate") or 0),
            "channels": int(audio.get("channels") or 0),
        })
    return out


def esc_filter_value(text: str) -> str:
    """Escape a value (usually a path) for use inside a filtergraph option."""
    return (text.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
            .replace(",", "\\,").replace("[", "\\[").replace("]", "\\]").replace(";", "\\;"))
