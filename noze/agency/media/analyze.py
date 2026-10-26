"""Measure a video the way an editor would: shot rhythm, loudness, dead air,
black/frozen frames, energy, plus frames and contact sheets for vision models.

Everything here is deterministic ffmpeg/numpy, so the analyst and the reviewer
reason over *measured* numbers instead of guessing them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .ffmpeg import MediaError, probe, run, stderr_text

_PTS = re.compile(r"pts_time:([0-9.]+)")
_NUM = r"(-?[0-9.]+|-?inf)"


def scene_cuts(path: str | Path, threshold: float = 0.3, start: float = 0.0, end: float | None = None,
               sample_fps: float | None = None) -> list[float]:
    """Times (s) where the picture changes a lot — cuts, hard transitions.
    ``sample_fps`` thins the frames first: on long 60 fps streams the scaler, not the decoder, is the cost."""
    args = []
    if start:
        args += ["-ss", f"{start:.3f}"]
    if end is not None:
        args += ["-to", f"{end:.3f}"]
    thin = f"fps={sample_fps:g}," if sample_fps else ""
    args += ["-i", str(path), "-an", "-sn", "-vf", f"{thin}scale=320:-2,select='gt(scene,{threshold})',showinfo",
             "-f", "null", "-"]
    proc = run(["-nostats", *args], timeout=1800)
    return [round(float(m) + start, 3) for m in _PTS.findall(stderr_text(proc))]


def loudness(path: str | Path) -> dict[str, float]:
    """EBU R128: integrated loudness (LUFS), loudness range (LU) and true peak (dBTP)."""
    proc = run(["-nostats", "-i", str(path), "-vn", "-sn", "-af", "ebur128=peak=true", "-f", "null", "-"],
               timeout=1800, check=False)
    text = stderr_text(proc)
    summary = text[text.rfind("Summary:"):] if "Summary:" in text else ""
    out = {"integrated": -70.0, "lra": 0.0, "true_peak": -70.0}
    for key, pat in (("integrated", rf"I:\s*{_NUM} LUFS"), ("lra", rf"LRA:\s*{_NUM} LU"),
                     ("true_peak", rf"Peak:\s*{_NUM} dBFS")):
        m = re.search(pat, summary)
        if m:
            v = m.group(1)
            out[key] = -70.0 if "inf" in v else float(v)
    return out


def silences(path: str | Path, noise_db: float = -38.0, min_s: float = 0.5,
             duration: float | None = None) -> list[tuple[float, float]]:
    proc = run(["-nostats", "-i", str(path), "-vn", "-sn", "-af", f"silencedetect=noise={noise_db}dB:d={min_s}",
                "-f", "null", "-"], timeout=1800, check=False)
    return _pairs(stderr_text(proc), r"silence_start:\s*([0-9.]+)", r"silence_end:\s*([0-9.]+)", duration)


def blacks(path: str | Path, min_s: float = 0.15) -> list[tuple[float, float]]:
    proc = run(["-nostats", "-i", str(path), "-an", "-sn", "-vf", f"blackdetect=d={min_s}:pix_th=0.10",
                "-f", "null", "-"], timeout=1800, check=False)
    return [(float(a), float(b)) for a, b in
            re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", stderr_text(proc))]


def freezes(path: str | Path, min_s: float = 2.0, duration: float | None = None) -> list[tuple[float, float]]:
    proc = run(["-nostats", "-i", str(path), "-an", "-sn", "-vf", f"scale=320:-2,freezedetect=n=-60dB:d={min_s}",
                "-f", "null", "-"], timeout=1800, check=False)
    return _pairs(stderr_text(proc), r"freeze_start:\s*([0-9.]+)", r"freeze_end:\s*([0-9.]+)", duration)


def _pairs(text: str, start_pat: str, end_pat: str, duration: float | None) -> list[tuple[float, float]]:
    events: list[tuple[int, str, float]] = []
    for m in re.finditer(start_pat, text):
        events.append((m.start(), "s", float(m.group(1))))
    for m in re.finditer(end_pat, text):
        events.append((m.start(), "e", float(m.group(1))))
    events.sort()
    out: list[tuple[float, float]] = []
    open_t: float | None = None
    for _, kind, t in events:
        if kind == "s":
            open_t = t
        elif open_t is not None:
            out.append((round(open_t, 3), round(t, 3)))
            open_t = None
    if open_t is not None and duration:  # still silent/frozen when the file ended
        out.append((round(open_t, 3), round(duration, 3)))
    return out


def audio_envelope(path: str | Path, hop: float = 0.1, start: float = 0.0,
                   end: float | None = None) -> np.ndarray:
    """RMS level in dBFS per ``hop`` seconds (mono, 16 kHz)."""
    args = ["-nostats", "-v", "error"]
    if start:
        args += ["-ss", f"{start:.3f}"]
    if end is not None:
        args += ["-to", f"{end:.3f}"]
    args += ["-i", str(path), "-vn", "-sn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    proc = run(args, timeout=1800, check=False)
    pcm = np.frombuffer(proc.stdout or b"", dtype=np.int16).astype(np.float32) / 32768.0
    n = int(16000 * hop)
    if pcm.size < n:
        return np.full(1, -90.0, dtype=np.float32)
    frames = pcm[: pcm.size - pcm.size % n].reshape(-1, n)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    return (20 * np.log10(rms + 1e-9)).astype(np.float32)


def onsets(envelope: np.ndarray, hop: float = 0.1, jump_db: float = 9.0) -> list[float]:
    """Sudden level jumps (hits, SFX, music drops)."""
    if envelope.size < 3:
        return []
    diff = np.diff(envelope)
    idx = np.where((diff > jump_db) & (envelope[1:] > -35))[0] + 1
    out: list[float] = []
    for i in idx:
        t = round(float(i * hop), 2)
        if not out or t - out[-1] > 0.25:
            out.append(t)
    return out


def shot_stats(cuts: list[float], duration: float) -> dict[str, float]:
    bounds = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    shots = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    if not shots or duration <= 0:
        return {"shots": 0, "avg_shot_s": round(duration, 2), "max_shot_s": round(duration, 2), "cuts_per_min": 0.0}
    return {
        "shots": len(shots),
        "avg_shot_s": round(float(np.mean(shots)), 2),
        "median_shot_s": round(float(np.median(shots)), 2),
        "max_shot_s": round(float(np.max(shots)), 2),
        "cuts_per_min": round(60.0 * (len(shots) - 1) / duration, 1),
    }


def measure(path: str | Path, with_frames_dir: Path | None = None) -> dict[str, Any]:
    """Everything the analyst needs about one video, in one dict."""
    info = probe(path)
    dur = info.get("duration") or 0.0
    out: dict[str, Any] = {"probe": info}
    if info.get("has_video"):
        cuts = scene_cuts(path, sample_fps=12 if dur > 180 else None)  # long sources: 12 fps is plenty for cuts
        out["cuts"] = cuts
        out["shots"] = shot_stats(cuts, dur)
    if info.get("has_audio"):
        out["loudness"] = loudness(path)
        sil = silences(path, duration=dur)
        out["silences"] = sil
        speech_free = sum(b - a for a, b in sil)
        out["silence_share"] = round(speech_free / dur, 3) if dur else 0.0
        env = audio_envelope(path)
        out["onsets"] = onsets(env)
        out["energy_db"] = {"mean": round(float(np.mean(env)), 1), "p90": round(float(np.percentile(env, 90)), 1)}
    if with_frames_dir is not None and info.get("has_video"):
        times = sample_times(dur, out.get("cuts") or [], n=12)
        frames = extract_frames(path, times, with_frames_dir)
        out["contact_sheets"] = [str(p) for p in contact_sheets(frames, times, with_frames_dir / "sheet")]
    return out


def sample_times(duration: float, cuts: Iterable[float] = (), n: int = 12, lead: float = 0.35) -> list[float]:
    """Representative timestamps: just after each cut, topped up with an even grid, first 3 s dense."""
    if duration <= 0:
        return [0.0]
    picks = {0.2, min(duration - 0.05, 1.0), min(duration - 0.05, 2.5)}
    for c in cuts:
        if c + lead < duration:
            picks.add(round(c + lead, 2))
    grid = max(1, n - len(picks))
    for i in range(grid):
        picks.add(round((i + 0.5) * duration / grid, 2))
    times = sorted(t for t in picks if 0 <= t < duration)
    if len(times) > n:  # keep the first seconds (the hook) and spread the rest
        head = [t for t in times if t <= 3.0][:3]
        rest = [t for t in times if t not in head]
        step = len(rest) / max(1, n - len(head))
        times = sorted(head + [rest[int(i * step)] for i in range(n - len(head))])
    return times


def extract_frames(path: str | Path, times: list[float], out_dir: Path, width: int = 360) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames: list[Path] = []
    for i, t in enumerate(times):
        dest = out_dir / f"frame_{i:03d}_{t:07.2f}.jpg"
        if not dest.exists():
            run(["-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                 "-vf", f"scale={width}:-2", "-q:v", "4", "-y", str(dest)], timeout=120, check=False)
        if dest.exists():
            frames.append(dest)
    if not frames:
        raise MediaError(f"could not extract frames from {path}")
    return frames


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheets(frames: list[Path], times: list[float], stem: Path, cols: int = 4, rows: int = 2,
                   cell_w: int = 270) -> list[Path]:
    """Tile frames into labelled sheets (8 per sheet keeps them legible for vision models)."""
    per = cols * rows
    out: list[Path] = []
    font = _font(22)
    for s in range(0, len(frames), per):
        chunk = list(zip(frames[s:s + per], times[s:s + per]))
        imgs = []
        for f, t in chunk:
            with Image.open(f) as im:
                im = im.convert("RGB")
                ratio = cell_w / im.width
                imgs.append((im.resize((cell_w, max(1, int(im.height * ratio)))), t))
        cell_h = max(im.height for im, _ in imgs)
        n_rows = (len(imgs) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell_w + (cols - 1) * 6, n_rows * cell_h + (n_rows - 1) * 6), (20, 20, 20))
        draw = ImageDraw.Draw(sheet)
        for i, (im, t) in enumerate(imgs):
            x, y = (i % cols) * (cell_w + 6), (i // cols) * (cell_h + 6)
            sheet.paste(im, (x, y))
            label = f"{t:0.1f}s"
            draw.rectangle([x, y, x + 12 * len(label) + 10, y + 30], fill=(0, 0, 0))
            draw.text((x + 5, y + 3), label, fill=(255, 230, 0), font=font)
        dest = stem.parent / f"{stem.name}_{s // per + 1}.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(dest, "JPEG", quality=82)
        out.append(dest)
    return out


def loudnorm_measure(path: str | Path, target_i: float, target_tp: float, target_lra: float = 11.0) -> dict[str, Any]:
    """First pass of two-pass loudnorm: the measured values ffmpeg wants back in pass two."""
    proc = run(["-nostats", "-i", str(path), "-vn", "-sn", "-af",
                f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json", "-f", "null", "-"],
               timeout=1800, check=False)
    text = stderr_text(proc)
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return {}
