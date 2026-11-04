"""Transcripts with word timings — the backbone of moment picking, jump cuts and captions.

Backends, best first:
- ``faster-whisper`` (``pip install faster-whisper``): large-v3 float16 on a CUDA GPU, small int8 on CPU
- sidecar subtitles next to the video: ``video.srt`` / ``video.en.vtt`` (yt-dlp writes
  these; YouTube auto-captions even carry per-word timings) / whisper-style ``video.json``
- none: the pipeline still runs on scene cuts and audio energy, just without captions

Shape: ``{"language", "source", "segments": [{"start","end","text","words":[{"start","end","word"}]}]}``
"""

from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("noze.agency.transcribe")

FILLERS = {"um", "uh", "uhm", "umm", "erm", "er", "hmm", "mm", "ehm", "eh", "emm", "anu"}

_TS = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{1,3})|(\d{1,2}):(\d{2})[.,](\d{1,3})")
_TAG = re.compile(r"<[^>]+>")
_WORD_TS = re.compile(r"<(\d+:\d{2}:\d{2}\.\d{3})>")


def _ts(text: str) -> float:
    m = _TS.search(text)
    if not m:
        return 0.0
    if m.group(1) is not None:
        h, mi, s, ms = m.group(1), m.group(2), m.group(3), m.group(4)
        return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
    mi, s, ms = m.group(5), m.group(6), m.group(7)
    return int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def spread_words(text: str, start: float, end: float) -> list[dict[str, Any]]:
    """Estimate word timings inside a cue, proportional to word length."""
    words = text.split()
    if not words:
        return []
    weights = [len(w) + 2 for w in words]
    total = sum(weights)
    out, t = [], start
    for w, wt in zip(words, weights):
        d = (end - start) * wt / total
        out.append({"start": round(t, 3), "end": round(t + d, 3), "word": w})
        t += d
    return out


def parse_subtitles(text: str) -> list[dict[str, Any]]:
    """SRT or WebVTT → segments (keeps YouTube's inline per-word timings when present)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text)
    # YouTube auto-captions: each cue repeats the previous line untimed, then adds the new
    # words with inline timings; untimed-only cues are 10 ms "transition" repeats.
    youtube_style = bool(_WORD_TS.search(text))
    segments: list[dict[str, Any]] = []
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip()]
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            continue
        a, _, b = lines[idx].partition("-->")
        start, end = _ts(a), _ts(b)
        body_lines = lines[idx + 1:]
        if youtube_style:
            first_timed = next((i for i, ln in enumerate(body_lines) if _WORD_TS.search(ln)), None)
            if first_timed is None:
                continue
            body_lines = body_lines[first_timed:]
        raw = " ".join(body_lines)
        words: list[dict[str, Any]] = []
        if _WORD_TS.search(raw):  # YouTube auto-captions: word<00:00:01.234><c> next</c>…
            parts = _WORD_TS.split(raw)
            cursor = start
            pending = _TAG.sub("", parts[0]).split()
            for i in range(1, len(parts), 2):
                t = _ts(parts[i])
                for w in pending:
                    words.append({"start": round(cursor, 3), "end": round(t, 3), "word": html.unescape(w)})
                cursor = t
                pending = _TAG.sub("", parts[i + 1]).split() if i + 1 < len(parts) else []
            for w in pending:
                words.append({"start": round(cursor, 3), "end": round(end, 3), "word": html.unescape(w)})
        clean = html.unescape(_TAG.sub("", raw)).strip()
        if not clean:
            continue
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": clean,
                         "words": words or spread_words(clean, start, end)})
    return _dedupe_rolling(segments) if youtube_style else segments


def _dedupe_rolling(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """YouTube auto-subs repeat the previous line in each cue; keep each word once."""
    out: list[dict[str, Any]] = []
    last_word_end = -1.0
    for seg in segments:
        words = [w for w in seg["words"] if w["start"] >= last_word_end - 0.01]
        if not words:
            continue
        last_word_end = words[-1]["end"]
        out.append({"start": words[0]["start"], "end": max(seg["end"], words[-1]["end"]),
                    "text": " ".join(w["word"] for w in words), "words": words})
    return out


def find_sidecar(video: Path) -> Path | None:
    stem = video.with_suffix("")
    candidates = []
    for ext in (".json", ".srt", ".vtt"):
        candidates.append(stem.with_name(stem.name + ext))
    candidates += sorted(video.parent.glob(f"{video.stem}.*.vtt")) + sorted(video.parent.glob(f"{video.stem}.*.srt"))
    return next((c for c in candidates if c.exists() and c != video), None)


def load_sidecar(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        segs = data.get("segments") or []
        for s in segs:
            s.setdefault("words", spread_words(s.get("text", ""), s["start"], s["end"]))
            for w in s["words"]:
                w["word"] = (w.get("word") or w.get("text") or "").strip()
        return {"language": data.get("language", ""), "source": f"sidecar:{path.name}", "segments": segs}
    lang = path.suffixes[-2].lstrip(".") if len(path.suffixes) >= 2 else ""
    return {"language": lang, "source": f"sidecar:{path.name}",
            "segments": parse_subtitles(path.read_text(encoding="utf-8", errors="replace"))}


def transcribe(video: Path, backend: str = "auto", model_size: str = "small", language: str | None = None,
               cache: Path | None = None, hint: str = "") -> dict[str, Any]:
    """``hint``: names Whisper can't guess (creator, handles, game) — fed as its initial prompt."""
    if cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    result: dict[str, Any] | None = None
    if backend in ("auto", "sidecar"):
        side = find_sidecar(video)
        if side:
            result = load_sidecar(side)
    if result is None and backend in ("auto", "faster-whisper"):
        result = _faster_whisper(video, model_size, language, hint)
        if result:
            fix_names(result, hint)
    if result is None:
        result = {"language": language or "", "source": "none", "segments": []}
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def fix_names(transcript: dict[str, Any], hint: str) -> int:
    """Snap near-miss spellings of the hinted names ("skiMaskTimmy") to the real one ("SkiiMaskTimmy").

    Only one-word names of 5+ letters; names of 8+ letters take close matches (difflib ratio ≥ 0.8), shorter
    ones only a case fix, so ordinary words survive.
    """
    from difflib import SequenceMatcher

    names: dict[str, str] = {}  # lower → first spelling given (the brief's "SkiiMaskTimmy" beats the handle)
    for n in re.split(r"[,;]", hint or ""):
        n = n.strip().strip(".")
        if re.fullmatch(r"\w[\w.]{4,}", n):
            names.setdefault(n.lower(), n)
    fixed = 0
    for seg in transcript.get("segments") or []:
        for w in seg.get("words") or []:
            m = re.fullmatch(r"(\W*)([\w.]+?)(\W*)", w["word"])
            if not m:
                continue
            core = m.group(2)
            for low, name in names.items():
                # short names ("Sketch") only get their capitals fixed: fuzzy matching would eat "sketchy"
                close = (core.lower() == low) if len(low) < 8 else SequenceMatcher(None, core.lower(), low).ratio() >= 0.8
                if core != name and close:
                    seg["text"] = re.sub(rf"\b{re.escape(core)}\b", name, seg["text"])
                    w["word"] = m.group(1) + name + m.group(3)
                    fixed += 1
                    break
    return fixed


def cuda_dll_dirs() -> list[Path]:
    """Folders holding cuBLAS/cuDNN for CTranslate2 on Windows: ``AGENCY_CUDA_DLL_DIRS``, pip ``nvidia-*``
    wheels in this environment, or a CUDA build of PyTorch installed in any user Python (it ships them)."""
    import os
    import site
    import sys

    if sys.platform != "win32":
        return []
    found = [Path(p) for p in os.environ.get("AGENCY_CUDA_DLL_DIRS", "").split(os.pathsep) if p]
    for sp in site.getsitepackages():
        found += [Path(sp) / "nvidia" / sub / "bin" for sub in ("cublas", "cudnn")]
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    found += sorted(local.glob("Python3*/Lib/site-packages/torch/lib"), reverse=True)
    return [d for d in found if d.is_dir() and (any(d.glob("cublas*.dll")) or any(d.glob("cudnn*.dll")))]


def _whisper_devices() -> list[str]:
    import os

    want = os.environ.get("AGENCY_WHISPER_DEVICE", "auto").lower()
    if want in ("cpu", "cuda"):
        return [want]
    try:
        import ctranslate2  # type: ignore

        if ctranslate2.get_cuda_device_count() > 0:
            for d in cuda_dll_dirs():  # CTranslate2 finds its DLLs through PATH, not add_dll_directory
                if str(d) not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
            return ["cuda", "cpu"]
    except Exception:  # noqa: BLE001 — no CUDA runtime is the normal case on laptops without a GPU
        pass
    return ["cpu"]


def _faster_whisper(video: Path, model_size: str, language: str | None, hint: str = "") -> dict[str, Any] | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        log.info("faster-whisper not installed; no transcript (pip install faster-whisper)")
        return None
    # decode with ffmpeg ourselves: faster-whisper's PyAV path breaks across PyAV releases
    audio = _pcm16k(video)
    if audio.size == 0:
        return None
    last: Exception | None = None
    for device in _whisper_devices():
        # "auto": the big model on a GPU (names, shouted lines under game audio), small on CPU
        size = model_size if model_size != "auto" else ("large-v3" if device == "cuda" else "small")
        try:
            model = WhisperModel(size, device=device, compute_type="float16" if device == "cuda" else "int8")
            segments, info = model.transcribe(audio, word_timestamps=True, vad_filter=True,
                                              language=language or None,
                                              vad_parameters={"min_silence_duration_ms": 500},
                                              initial_prompt=hint or None)
            out = []
            for s in segments:  # a generator: CUDA library errors surface here, inside the try
                words = [{"start": round(float(w.start), 3), "end": round(float(w.end), 3), "word": w.word.strip()}
                         for w in (s.words or []) if w.word.strip()]
                out.append({"start": round(float(s.start), 3), "end": round(float(s.end), 3), "text": s.text.strip(),
                            "words": words or spread_words(s.text, s.start, s.end)})
        except (RuntimeError, ValueError, OSError) as exc:
            log.warning("faster-whisper on %s failed (%s); trying the next device", device, exc)
            last = exc
            continue
        return {"language": getattr(info, "language", "") or (language or ""),
                "source": f"faster-whisper:{size}:{device}", "segments": out}
    log.warning("faster-whisper unavailable on every device: %s", last)
    return None


def _pcm16k(video: Path):
    import numpy as np

    from .ffmpeg import run

    proc = run(["-nostats", "-v", "error", "-i", str(video), "-vn", "-sn", "-ac", "1", "-ar", "16000",
                "-f", "s16le", "-"], timeout=7200, check=False)
    return np.frombuffer(proc.stdout or b"", dtype=np.int16).astype(np.float32) / 32768.0


# -- helpers used across roles ------------------------------------------------------
def all_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    return [w for s in transcript.get("segments") or [] for w in s.get("words") or []]


def words_between(transcript: dict[str, Any], start: float, end: float) -> list[dict[str, Any]]:
    return [w for w in all_words(transcript) if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]


def text_between(transcript: dict[str, Any], start: float, end: float) -> str:
    return " ".join(w["word"] for w in words_between(transcript, start, end))


def for_prompt(transcript: dict[str, Any], start: float = 0.0, end: float | None = None,
               max_chars: int = 60000) -> str:
    """Timestamped lines for an LLM: ``[12.3-15.8] text``."""
    lines = []
    for s in transcript.get("segments") or []:
        if s["end"] < start or (end is not None and s["start"] > end):
            continue
        lines.append(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}")
    text = "\n".join(lines)
    if len(text) > max_chars:  # keep the shape of the whole talk instead of silently cutting the end
        keep = max_chars // 2
        text = text[:keep] + "\n[… middle of transcript omitted for length …]\n" + text[-keep:]
    return text


def speech_rate(transcript: dict[str, Any], start: float = 0.0, end: float | None = None) -> float:
    words = [w for w in all_words(transcript) if w["start"] >= start and (end is None or w["end"] <= end)]
    if len(words) < 2:
        return 0.0
    span = words[-1]["end"] - words[0]["start"]
    return round(60.0 * len(words) / span, 1) if span > 0 else 0.0


def is_filler(word: str) -> bool:
    return re.sub(r"[^\w]", "", word.lower()) in FILLERS
