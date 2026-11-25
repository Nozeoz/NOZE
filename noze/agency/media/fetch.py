"""Get a source video onto disk: local paths, NOZE bank assets, direct file URLs,
or (opt-in) platform links through yt-dlp — only for content the campaign lets you clip."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse

import httpx

from ...http import check_public_url
from .ffmpeg import MediaError, probe, run

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
                      "--max-filesize", f"{max_mb}M", "-o", out_tpl, "--", ref]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise MediaError(f"yt-dlp failed: {proc.stderr.strip()[-500:]}")
        video = next((p for p in sorted(dest_dir.glob(f"src_{key}.*")) if p.suffix in VIDEO_EXT), None)
        if not video:
            raise MediaError("yt-dlp finished but no video file was written")
        return video
    # direct file URL (Dropbox ?dl=1, a CDN link, your own server …)
    suffix = Path(urlparse(ref).path).suffix.lower()
    dest = dest_dir / f"src_{key}{suffix if suffix in VIDEO_EXT else '.mp4'}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    limit = max_mb * 1024 * 1024
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        with safe_stream(client, ref, allow_private) as resp:
            if resp.headers.get("content-type", "").startswith("text/html"):
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


@contextmanager
def safe_stream(client: httpx.Client, url: str, allow_private: bool = False, headers: dict[str, str] | None = None,
                max_hops: int = 6) -> Iterator[httpx.Response]:
    """GET with the SSRF check on every hop *before* it is requested (redirects are
    followed by hand, relative Locations resolved), streaming the final response."""
    current = url
    for _ in range(max_hops):
        asyncio.run(check_public_url(current, allow_private))
        with client.stream("GET", current, headers=headers, follow_redirects=False) as resp:
            if resp.is_redirect:
                current = urljoin(current, resp.headers.get("location", ""))
                continue
            if resp.status_code >= 400:
                raise MediaError(f"download failed: HTTP {resp.status_code}")
            yield resp
            return
    raise MediaError("too many redirects")


# -- fast section fetch (a few minutes of a multi-hour VOD) --------------------------------------------------
def parse_hms(text: str | float) -> float:
    """``90``, ``1:30``, ``01:02:03`` or ``1h2m3s`` -> seconds."""
    if isinstance(text, (int, float)):
        return float(text)
    t = text.strip().lower()
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", t)
    if m and any(m.groups()):
        return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3) or 0)
    parts = t.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"bad time {text!r} (use HH:MM:SS, MM:SS or seconds)")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + float(p)
    return secs


def fmt_hms(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _ytdlp_urls(url: str, fmt: str) -> list[str]:
    cmd = _ytdlp_cmd()
    if not cmd:
        raise MediaError("install yt-dlp: pip install yt-dlp")
    extra = ["--js-runtimes", "node"] if shutil.which("node") and "youtu" in url else []
    proc = subprocess.run(cmd + ["-g", "--no-playlist", "-f", fmt, *extra, "--", url], capture_output=True, text=True, timeout=180)
    urls = [u for u in proc.stdout.split() if u.startswith("http")]
    if proc.returncode != 0 or not urls:
        raise MediaError(f"yt-dlp could not resolve a stream URL: {proc.stderr.strip()[-300:]}")
    return urls


def parse_m3u8(text: str, base: str) -> tuple[list[tuple[str, float, str | None]], tuple[str, str | None] | None]:
    """Media playlist -> ([(segment url, seconds, 'Range' header | None)], fMP4 init (url, range) | None)."""
    segs: list[tuple[str, float, str | None]] = []
    init = None
    dur = 0.0
    rng: str | None = None
    pos = 0
    for line in (ln.strip() for ln in text.splitlines()):
        if line.startswith("#EXTINF:"):
            dur = float(line[8:].split(",")[0])
        elif line.startswith("#EXT-X-BYTERANGE:"):
            ln, _, off = line[17:].partition("@")
            pos = int(off) if off else pos
            rng = f"bytes={pos}-{pos + int(ln) - 1}"
            pos += int(ln)
        elif line.startswith("#EXT-X-MAP:"):
            m = re.search(r'URI="([^"]+)"', line)
            r = re.search(r'BYTERANGE="(\d+)@(\d+)"', line)
            if m:
                init = (urljoin(base, m.group(1)), f"bytes={r.group(2)}-{int(r.group(2)) + int(r.group(1)) - 1}" if r else None)
        elif line and not line.startswith("#"):
            segs.append((urljoin(base, line), dur, rng))
            rng = None
    return segs, init


def _get_bytes(client: httpx.Client, url: str, rng: str | None, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            r = client.get(url, headers={"Range": rng} if rng else None)
            r.raise_for_status()
            return r.content
        except httpx.HTTPError:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    return b""


def _fetch_hls(url: str, start: float, end: float, out: Path, workers: int, fmt: str = "best",
               audio: bool = False) -> None:
    master = _ytdlp_urls(url, fmt)[0]
    with httpx.Client(timeout=30, follow_redirects=True, limits=httpx.Limits(max_connections=workers + 2)) as client:
        text = client.get(master).text
        if "#EXT-X-STREAM-INF" in text:  # a master list: take the highest-bandwidth variant
            best, bw, cur = "", -1, 0
            for ln in (x.strip() for x in text.splitlines()):
                if ln.startswith("#EXT-X-STREAM-INF"):
                    m = re.search(r"BANDWIDTH=(\d+)", ln)
                    cur = int(m.group(1)) if m else 0
                elif ln and not ln.startswith("#") and cur > bw:
                    best, bw = urljoin(master, ln), cur
            master = best
            text = client.get(master).text
        segs, init = parse_m3u8(text, master)
        if not segs:
            raise MediaError("playlist has no segments")
        t, picked, first_t = 0.0, [], None
        for s in segs:
            if t + s[1] > start and t < end:
                picked.append(s)
                first_t = t if first_t is None else first_t
            t += s[1]
        if not picked:
            raise MediaError(f"range {fmt_hms(start)}-{fmt_hms(end)} is outside the VOD ({fmt_hms(t)} long, or expired)")
        log.info("fetching %d segments (%.0fs) with %d workers", len(picked), sum(p[1] for p in picked), workers)
        # segments go to disk beside ``out`` (never RAM, never %TEMP% on a full C:)
        parts = out.parent / (out.name + ".parts")
        shutil.rmtree(parts, ignore_errors=True)
        parts.mkdir(parents=True)
        try:
            def grab(i: int) -> Path:
                f = parts / f"{i:06d}.seg"
                f.write_bytes(_get_bytes(client, picked[i][0], picked[i][2]))
                return f

            with ThreadPoolExecutor(workers) as pool:
                files = list(pool.map(grab, range(len(picked))))
            head = None
            if init:
                head = parts / "init.bin"
                head.write_bytes(_get_bytes(client, init[0], init[1]))
            joined = parts / ("joined.mp4" if init else "joined.ts")
            with joined.open("wb") as fh:
                for f in ([head] if head else []) + files:
                    with f.open("rb") as src:
                        shutil.copyfileobj(src, fh, 1 << 20)
                    f.unlink()
            if audio:
                _cut_audio(["-i", str(joined)], start - (first_t or 0.0), end - start, out)
            else:
                _cut(["-i", str(joined)], start - (first_t or 0.0), end - start, out)
        finally:
            shutil.rmtree(parts, ignore_errors=True)


def _cut_audio(inputs: list[str], rel_start: float, length: float, out: Path) -> None:
    """Audio only (m4a/aac, 96 kbps mono-ish speech is plenty for Whisper + loudness)."""
    args = ["-nostats", "-v", "error", "-y"]
    if inputs[0] == "-i":
        args += ["-ss", f"{max(0.0, rel_start):.3f}", *inputs]
    else:
        args += inputs
    run([*args, "-t", f"{length:.3f}", "-vn", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)],
        timeout=max(3600, int(length * 1.5)))  # an 8 h YouTube window can outlast an hour


def _cut(inputs: list[str], rel_start: float, length: float, out: Path, maps: list[str] | None = None) -> None:
    """Re-encode just the wanted window (accurate cut, no keyframe drift)."""
    args = ["-nostats", "-v", "error", "-y"]
    if inputs[0] == "-i":  # one input: seek after open is fine for a local joined file
        args += ["-ss", f"{max(0.0, rel_start):.3f}", *inputs]
    else:
        args += inputs
    args += ["-t", f"{length:.3f}", *(maps or []), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    run(args, timeout=3600)


def _fetch_direct(url: str, start: float, end: float, out: Path) -> None:
    """YouTube & friends: let ffmpeg range-seek the real stream URLs (no ``--download-sections``: it can leave a
    262-byte file with exit 0)."""
    urls = _ytdlp_urls(url, "bv*[height<=1080]+ba/b[height<=1080]/b")
    pre = ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5", "-ss", f"{start:.3f}"]
    inputs: list[str] = []
    for u in urls[:2]:
        inputs += [*pre, "-i", u]
    maps = ["-map", "0:v:0", "-map", "1:a:0"] if len(urls) > 1 else ["-map", "0:v:0", "-map", "0:a:0?"]
    _cut(inputs, 0.0, end - start, out, maps)


def verify_clip(path: Path, want_s: float, tol: float = 2.0) -> float:
    """Fully decode ``path`` and check its length is ``want_s`` +- ``tol`` — an exit code of 0 proves nothing."""
    if not path.exists() or path.stat().st_size < 10_000:
        raise MediaError(f"fetched file is empty or tiny ({path.stat().st_size if path.exists() else 0} bytes)")
    info = probe(path)
    if not info["has_video"]:
        raise MediaError("fetched file has no video stream")
    proc = run(["-nostats", "-v", "error", "-i", str(path), "-f", "null", "-"], timeout=3600, check=False)
    if proc.returncode != 0 or proc.stderr.strip():
        raise MediaError("fetched file does not decode cleanly: " + proc.stderr.decode("utf-8", "replace")[-300:])
    if abs(info["duration"] - want_s) > tol:
        raise MediaError(f"fetched {info['duration']:.1f}s but asked for {want_s:.1f}s (+-{tol:g}s)")
    return float(info["duration"])


def fetch_range(url: str, start_s: float, end_s: float, out: Path, *, workers: int = 8) -> Path:
    """Download only [start_s, end_s] of a VOD to ``out`` (mp4), verified. Twitch: HLS segments in parallel;
    others: ffmpeg range-seek of the direct stream URLs."""
    if end_s <= start_s:
        raise MediaError("--to must be after --from")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    host = (urlparse(url).hostname or "").lower()
    try:
        if host.endswith("twitch.tv"):
            _fetch_hls(url, start_s, end_s, out, workers)
        else:
            _fetch_direct(url, start_s, end_s, out)
        verify_clip(out, end_s - start_s)
    except Exception:
        out.unlink(missing_ok=True)
        raise
    return out


# -- scan without the video: audio-only window, then only the pieces that are used ------------------------------
def verify_audio(path: Path, want_s: float, tol: float = 2.0) -> float:
    """Fully decode an audio file and check it is ``want_s`` +- ``tol`` long."""
    if not path.exists() or path.stat().st_size < 1_000:
        raise MediaError(f"fetched audio is empty or tiny ({path.stat().st_size if path.exists() else 0} bytes)")
    info = probe(path)
    if not info["has_audio"]:
        raise MediaError("fetched file has no audio stream")
    proc = run(["-nostats", "-v", "error", "-i", str(path), "-f", "null", "-"], timeout=3600, check=False)
    if proc.returncode != 0 or proc.stderr.strip():
        raise MediaError("fetched audio does not decode cleanly: " + proc.stderr.decode("utf-8", "replace")[-300:])
    if abs(info["duration"] - want_s) > tol:
        raise MediaError(f"fetched {info['duration']:.1f}s of audio but asked for {want_s:.1f}s (+-{tol:g}s)")
    return float(info["duration"])


def fetch_audio_range(url: str, start_s: float, end_s: float, out: Path, *, workers: int = 8) -> Path:
    """Audio of [start_s, end_s] only (m4a), verified. Twitch: the ``audio_only`` HLS rendition (~160 kbps, so a
    6 h stream is ~430 MB instead of tens of GB), segments in parallel; others: ffmpeg range-seek, video dropped."""
    if end_s <= start_s:
        raise MediaError("--to must be after --from")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    final, out = out, out.with_suffix(".part" + out.suffix)  # a half download never carries the final name
    out.unlink(missing_ok=True)
    host = (urlparse(url).hostname or "").lower()
    try:
        if host.endswith("twitch.tv"):
            try:
                _fetch_hls(url, start_s, end_s, out, workers, fmt="audio_only", audio=True)
            except MediaError as exc:
                if "stream URL" not in str(exc):
                    raise
                _fetch_hls(url, start_s, end_s, out, workers, fmt="worst", audio=True)  # no audio_only rendition
        else:
            u = _ytdlp_urls(url, "ba/b")[-1]
            _cut_audio(["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                        "-ss", f"{start_s:.3f}", "-i", u], 0.0, end_s - start_s, out)
        verify_audio(out, end_s - start_s)
        os.replace(out, final)
    except BaseException:  # incl. Ctrl-C mid-download
        out.unlink(missing_ok=True)
        raise
    return final


def fetch_pack(url: str, ranges: list[tuple[float, float]], out: Path, *, workers: int = 8,
               fade_s: float = 0.02) -> tuple[Path, list[dict]]:
    """Download each VOD range (video), glue them into ONE mp4 (uniform re-encode, ``fade_s`` audio fades at every
    seam so there is no click) and write ``<out>.vodmap.json``. Returns ``(out, vod_map)`` with
    ``vod_map = [{file_start, file_end, vod_start}]`` — file seconds are measured from the pieces actually written."""
    if not ranges:
        raise MediaError("no ranges to fetch")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    vod_map: list[dict] = []
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".pack_") as tmp:
        parts: list[tuple[Path, float]] = []
        cum = 0.0
        for i, (a, b) in enumerate(ranges):
            p = Path(tmp) / f"p{i}.mp4"
            fetch_range(url, a, b, p, workers=workers)
            info = probe(p)
            if not info["has_audio"]:
                raise MediaError(f"range {fmt_hms(a)}-{fmt_hms(b)} has no audio track")
            dur = float(info["duration"])
            parts.append((p, dur))
            vod_map.append({"file_start": round(cum, 3), "file_end": round(cum + dur, 3), "vod_start": float(a)})
            cum += dur
        first = probe(parts[0][0])
        w, h, fps = int(first["width"]) // 2 * 2, int(first["height"]) // 2 * 2, round(first.get("fps") or 30) or 30
        args = ["-nostats", "-v", "error", "-y"]
        chains: list[str] = []
        for i, (p, dur) in enumerate(parts):
            args += ["-i", str(p)]
            chains.append(f"[{i}:v]fps={fps},scale={w}:{h}:force_original_aspect_ratio=decrease,"
                          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p[v{i}]")
            fade = min(fade_s, dur / 4)
            chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d={fade:.3f},"
                          f"afade=t=out:st={max(0.0, dur - fade):.3f}:d={fade:.3f}[a{i}]")
        joined = "".join(f"[v{i}][a{i}]" for i in range(len(parts)))
        graph = ";".join(chains) + f";{joined}concat=n={len(parts)}:v=1:a=1[v][a]"
        run([*args, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)],
            timeout=3600)
    try:
        verify_clip(out, cum, tol=1.0 + 0.1 * len(ranges))
    except Exception:
        out.unlink(missing_ok=True)
        raise
    sidecar = out.with_name(out.name + ".vodmap.json")
    sidecar.write_text(json.dumps(vod_map, indent=1), encoding="utf-8")
    return out, vod_map
