"""Measured "where was it loud / funny / hyped" signals for a long source video.

The analyst used to guess which moments mattered from the transcript alone. This collects *evidence*:
chat replay spikes (Twitch / YouTube), viewer-made Twitch clips, YouTube "most replayed", audio events
(laughter / cheering / screaming / music via YAMNet-ONNX) and plain loudness, bins them every ``bin_s``
seconds and fuses them into a 0-10 ``heat`` per bin plus a list of ``peaks`` with the evidence spelled out.

All network / model work happens only inside :func:`collect_signals`; any failure becomes a ``notes`` line,
never an exception. Every time in the result is seconds of the SOURCE FILE (VOD time - ``offset_s``).
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import httpx
import numpy as np

from .ffmpeg import MediaError, probe, run

log = logging.getLogger("noze.agency.signals")

VERSION = 1
BIN_S = 2.0
GQL_URL = "https://gql.twitch.tv/gql"
GQL_HEADERS = {"Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json"}
CHAT_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"
YAMNET_URL = "https://huggingface.co/jafet21/yamnetonnx/resolve/main/"
CLIP_PERIODS = ("LAST_DAY", "LAST_WEEK", "LAST_MONTH", "ALL_TIME")

# fusion weights (share of the weighted mean) and "hot" thresholds (how many sources agree on a bin)
WEIGHTS = {"chat": 0.30, "clip": 0.30, "event": 0.25, "loud": 0.10, "replay": 0.20}
HOT = {"chat": 0.5, "clip": 0.5, "event": 0.4, "loud": 0.7, "replay": 0.6}

# chat lexicon — Twitch emotes arrive as plain text fragments, so word match is enough
_LEX: dict[str, re.Pattern] = {
    "funny": re.compile(r"(?<!\w)(kekw+|lulw?|omegalul|lmf?ao|icant|lo{2,}l|lol|(?:ha){2,}h?|(?:wk){2,}|"
                        r"hahaha+|😂|🤣|💀)(?!\w)", re.I),
    "hype": re.compile(r"(?<!\w)(pog(?:gers|champ|u)?|w{1,3}|let'?s ?go+|letsgo+|clap|goat|hype|🔥)(?!\w)", re.I),
    "shock": re.compile(r"(?<!\w)(what|wtf|monkas|no ?way|noway|wait|omg|😳)(?!\w)", re.I),
    "sad": re.compile(r"(?<!\w)(sadge|f|rip|pepehands|😭)(?!\w)", re.I),
}
_QMARKS = re.compile(r"^[\s?!]*\?[\s?!]*$")  # a message that is only "???" counts as shock

_TAG_FOR_CHAT = {"funny": "funny", "hype": "hype", "shock": "shock", "sad": "sad"}


# -- small numeric helpers -----------------------------------------------------------------------------------
def _norm(values: np.ndarray, lo_pct: float = 50, hi_pct: float = 98) -> np.ndarray:
    """Per-stream 0-1 scale: ``lo_pct`` percentile -> 0, ``hi_pct`` percentile -> 1 (falls back to max)."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return v
    lo, hi = float(np.percentile(v, lo_pct)), float(np.percentile(v, hi_pct))
    if hi <= lo:
        hi = float(v.max())
    if hi <= lo:
        return np.zeros_like(v)
    return np.clip((v - lo) / (hi - lo), 0.0, 1.0)


def _hms(t: float) -> str:
    t = int(max(0, t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


# -- chat lexicon -----------------------------------------------------------------------------------------
def classify_message(text: str) -> tuple[dict[str, int], list[str]]:
    """-> ({category: 1 if hit}, [matched lexicon tokens]). A message counts once per category."""
    cats: dict[str, int] = {}
    toks: list[str] = []
    if _QMARKS.match(text or ""):
        return {"shock": 1}, ["?"]
    for cat, pat in _LEX.items():
        hits = [m.group(0) for m in pat.finditer(text or "")]
        if hits:
            cats[cat] = 1
            toks += [h.upper() for h in hits]
    return cats, toks


# -- source: YouTube ---------------------------------------------------------------------------------------
def _ytdlp() -> list[str] | None:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # type: ignore  # noqa: F401

        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def _yt_args() -> list[str]:
    return ["--js-runtimes", "node"] if shutil.which("node") else []


def parse_vod_url(url: str) -> tuple[str, str] | None:
    """-> ("twitch", video id) | ("youtube", video id) | None."""
    u = urlparse(url or "")
    host = (u.hostname or "").lower()
    if host.endswith("twitch.tv"):
        m = re.search(r"/videos/(\d+)", u.path)
        return ("twitch", m.group(1)) if m else None
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
        return ("youtube", vid) if vid else None
    if host.endswith("youtube.com"):
        vid = (parse_qs(u.query).get("v") or [""])[0]
        if not vid:
            m = re.search(r"/(?:live|shorts|embed)/([\w-]{6,})", u.path)
            vid = m.group(1) if m else ""
        return ("youtube", vid) if vid else None
    return None


def yt_info(url: str) -> dict[str, Any]:
    cmd = _ytdlp()
    if not cmd:
        raise MediaError("yt-dlp not installed")
    proc = subprocess.run(cmd + ["--dump-json", "--skip-download", "--no-playlist", *_yt_args(), "--", url],
                          capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise MediaError(f"yt-dlp info failed: {proc.stderr.strip()[-300:]}")
    return json.loads(proc.stdout.splitlines()[0])


def parse_heatmap(info: dict[str, Any]) -> list[tuple[float, float, float]]:
    """YouTube "most replayed": [(start, end, value 0-1)] in video time; [] when the video has none (new videos)."""
    return [(float(h["start_time"]), float(h["end_time"]), float(h["value"]))
            for h in (info.get("heatmap") or []) if isinstance(h, dict) and "value" in h]


def yt_live_chat(url: str, work: Path) -> list[tuple[float, str]]:
    cmd = _ytdlp()
    if not cmd:
        raise MediaError("yt-dlp not installed")
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd + ["--skip-download", "--no-playlist", "--write-subs", "--sub-langs", "live_chat",
                          *_yt_args(), "-o", str(work / "%(id)s"), "--", url],
                   capture_output=True, text=True, timeout=600)
    files = sorted(work.glob("*.live_chat.json"))
    if not files:
        raise MediaError("no live chat replay for this video")
    return parse_yt_chat(files[0])


def parse_yt_chat(path: Path) -> list[tuple[float, str]]:
    """One JSON object per line (yt-dlp ``live_chat``) -> [(video seconds, text)]; non-text items dropped."""
    out: list[tuple[float, str]] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        rep = row.get("replayChatItemAction") or {}
        off = rep.get("videoOffsetTimeMsec", row.get("videoOffsetTimeMsec"))
        try:
            t = float(off) / 1000.0
        except (TypeError, ValueError):
            continue
        for act in rep.get("actions") or []:
            item = ((act.get("addChatItemAction") or {}).get("item") or {}).get("liveChatTextMessageRenderer")
            if not item:
                continue
            parts = []
            for r in (item.get("message") or {}).get("runs") or []:
                emo = r.get("emoji") or {}
                parts.append(r.get("text") or emo.get("emojiId") or (emo.get("shortcuts") or [""])[0])
            text = "".join(parts).strip()
            if text:
                out.append((t, text))
    return out


# -- source: Twitch ----------------------------------------------------------------------------------------
def _gql(client: httpx.Client, payload: Any) -> Any:
    r = client.post(GQL_URL, json=payload, headers=GQL_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _chat_page(client: httpx.Client, vod_id: str, *, offset: float | None = None, cursor: str | None = None) -> dict:
    var: dict[str, Any] = {"videoID": vod_id}
    if cursor:
        var["cursor"] = cursor
    else:
        var["contentOffsetSeconds"] = int(offset or 0)
    data = _gql(client, [{"operationName": "VideoCommentsByOffsetOrCursor", "variables": var,
                          "extensions": {"persistedQuery": {"version": 1, "sha256Hash": CHAT_HASH}}}])
    row = data[0] if isinstance(data, list) else data
    if row.get("errors"):
        raise MediaError(f"twitch chat query refused: {str(row['errors'])[:200]}")
    comments = ((row.get("data") or {}).get("video") or {}).get("comments")
    if comments is None:
        raise MediaError("twitch chat: video has no comments object (deleted / expired VOD?)")
    return comments


def twitch_chat(vod_id: str, start_s: float, end_s: float, *, client: httpx.Client | None = None,
                max_pages: int | None = None, pause: float = 0.22, max_seconds: float = 2400.0,
                info: dict | None = None) -> list[tuple[float, str]]:
    """Chat of a Twitch VOD within [start_s, end_s] (VOD seconds). Uses the cursor to page; if the cursor
    stops advancing it falls back to re-asking from the last offset. ~4 requests/second. The page budget scales
    with the range; if the budget / ``max_seconds`` / a mid-way error stops it early, ``info["truncated_at"]`` is the
    VOD second reached (and what was read is still returned) so the caller can mark the rest unread."""
    if max_pages is None:
        max_pages = max(800, int((end_s - start_s) / 0.5) + 50)
    deadline = time.monotonic() + max_seconds
    finished = False
    own = client is None
    client = client or httpx.Client()
    seen: set[str] = set()
    out: list[tuple[float, str]] = []
    cursor: str | None = None
    offset = float(start_s)
    try:
        for _ in range(max_pages):
            if time.monotonic() > deadline:
                break
            try:
                page = _chat_page(client, vod_id, offset=offset, cursor=cursor)
            except (httpx.HTTPError, MediaError):
                if cursor:  # cursor mode broke -> retry once in offset mode
                    cursor = None
                    continue
                if out and info is not None:  # keep what we have, report where it stops
                    break
                raise
            edges = page.get("edges") or []
            fresh = 0
            for e in edges:
                n = e.get("node") or {}
                nid = n.get("id") or f"{n.get('contentOffsetSeconds')}:{(n.get('message') or {}).get('fragments')}"
                if nid in seen:
                    continue
                seen.add(nid)
                fresh += 1
                t = float(n.get("contentOffsetSeconds") or 0)
                if start_s <= t <= end_s:
                    text = "".join((f or {}).get("text") or "" for f in (n.get("message") or {}).get("fragments") or [])
                    if text.strip():
                        out.append((t, text.strip()))
            last_t = float((edges[-1].get("node") or {}).get("contentOffsetSeconds") or offset) if edges else offset
            offset = max(offset, last_t)
            if last_t >= end_s:
                finished = True
                break
            nxt = (edges[-1].get("cursor") if edges else None)
            if (page.get("pageInfo") or {}).get("hasNextPage") and nxt and fresh:
                cursor = nxt
            else:  # no usable cursor: move the clock forward ourselves
                cursor = None
                if not edges or not fresh:
                    if edges:
                        offset = max(offset + 1, last_t + 1)
                    else:
                        offset += 5  # empty stretch (chat paused) — hop, but stop at the end
                else:
                    offset = max(offset + 1, last_t)
                if offset > end_s:
                    finished = True
                    break
            time.sleep(pause)
        if not finished and info is not None:
            info["truncated_at"] = offset
    finally:
        if own:
            client.close()
    return out


def twitch_video_meta(vod_id: str, client: httpx.Client | None = None) -> dict[str, Any]:
    own = client is None
    client = client or httpx.Client()
    try:
        d = _gql(client, {"query": "query($id:ID!){video(id:$id){title lengthSeconds owner{login}}}",
                          "variables": {"id": vod_id}})
        v = (d.get("data") or {}).get("video")
        if not v:
            raise MediaError("twitch VOD not found (expired or private)")
        return {"title": v.get("title") or "", "length_s": float(v.get("lengthSeconds") or 0),
                "login": ((v.get("owner") or {}).get("login") or "")}
    finally:
        if own:
            client.close()


def twitch_clips(login: str, period: str = "LAST_WEEK", client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Viewer-made clips of a channel, most viewed first -> [{vod_id, start_s, end_s, title, views, slug}]
    (only clips that point into a VOD; ``start_s`` is VOD seconds)."""
    if not re.fullmatch(r"[A-Za-z0-9_]{1,25}", login or ""):
        raise MediaError(f"bad twitch login: {login!r}")
    if period not in CLIP_PERIODS:
        raise MediaError(f"bad clip period: {period!r}")
    own = client is None
    client = client or httpx.Client()
    q = ('query($login:String!){user(login:$login){clips(first:100,criteria:{period:%s,sort:VIEWS_DESC})'
         '{edges{node{slug title viewCount durationSeconds videoOffsetSeconds video{id}}}}}}' % period)
    try:
        d = _gql(client, {"query": q, "variables": {"login": login}})
    finally:
        if own:
            client.close()
    edges = (((d.get("data") or {}).get("user") or {}).get("clips") or {}).get("edges") or []
    out = []
    for e in edges:
        n = e.get("node") or {}
        vid, off = (n.get("video") or {}).get("id"), n.get("videoOffsetSeconds")
        if not vid or off is None:
            continue
        dur = float(n.get("durationSeconds") or 30)
        out.append({"vod_id": str(vid), "start_s": float(off), "end_s": float(off) + dur,
                    "title": n.get("title") or "", "views": int(n.get("viewCount") or 0), "slug": n.get("slug") or ""})
    return out


def twitch_vods(login: str, limit: int = 30, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Latest past broadcasts -> [{id, title, length_s, created_at (ISO), views}]."""
    if not re.fullmatch(r"[A-Za-z0-9_]{1,25}", login or ""):
        raise MediaError(f"bad twitch login: {login!r}")
    own = client is None
    client = client or httpx.Client()
    q = ('query($login:String!,$n:Int!){user(login:$login){videos(first:$n,type:ARCHIVE,sort:TIME)'
         '{edges{node{id title lengthSeconds createdAt viewCount}}}}}')
    try:
        d = _gql(client, {"query": q, "variables": {"login": login, "n": int(limit)}})
    finally:
        if own:
            client.close()
    user = (d.get("data") or {}).get("user")
    if not user:
        raise MediaError(f"twitch channel {login!r} not found")
    return [{"id": str(n["id"]), "title": n.get("title") or "", "length_s": float(n.get("lengthSeconds") or 0),
             "created_at": n.get("createdAt") or "", "views": int(n.get("viewCount") or 0)}
            for n in ((e.get("node") or {}) for e in (user.get("videos") or {}).get("edges") or []) if n.get("id")]


# -- source: audio ---------------------------------------------------------------------------------------
def _pcm(video: Path, start: float, end: float) -> np.ndarray:
    proc = run(["-nostats", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video), "-vn", "-sn",
                "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], timeout=1800, check=False)
    return np.frombuffer(proc.stdout or b"", dtype=np.int16).astype(np.float32) / 32768.0


def _loudness_bins(video: Path, duration: float, n_bins: int, chunk_s: float = 600.0) -> np.ndarray:
    """Max level (dBFS) per bin, decoded in chunks so a 6-hour VOD does not sit in RAM."""
    from .analyze import audio_envelope

    hop = 0.5
    env = np.full(int(math.ceil(duration / hop)) + 1, -90.0, dtype=np.float32)
    t = 0.0
    while t < duration:
        seg = audio_envelope(video, hop=hop, start=t, end=min(duration, t + chunk_s))
        i0 = int(round(t / hop))
        env[i0:i0 + seg.size] = seg[: max(0, env.size - i0)]
        t += chunk_s
    per = int(BIN_S / hop)
    pad = np.full(n_bins * per - min(env.size, n_bins * per), -90.0, dtype=np.float32)
    return np.concatenate([env[: n_bins * per], pad]).reshape(n_bins, per).max(axis=1)


class _Yamnet:
    GROUPS = {"laugh": ("Laughter", "Belly laugh", "Chuckle, chortle", "Giggle"),
              "cheer": ("Cheering", "Applause"),
              "scream": ("Screaming", "Yell", "Shout"),
              "music": ("Music",)}

    def __init__(self, model: Path, class_map: Path):
        import onnxruntime as ort

        self.sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
        self.inp = self.sess.get_inputs()[0].name
        with class_map.open(encoding="utf-8", newline="") as fh:
            names = [r[2] for r in list(csv.reader(fh))[1:]]
        self.idx = {g: [names.index(n) for n in ns if n in names] for g, ns in self.GROUPS.items()}

    def scores(self, pcm: np.ndarray) -> dict[str, np.ndarray]:
        """One value per 0.48 s window, per group (max over the group's classes)."""
        if pcm.size < 16000:
            return {g: np.zeros(0, dtype=np.float32) for g in self.idx}
        s = self.sess.run(None, {self.inp: pcm.astype(np.float32)})[0]
        return {g: (s[:, ix].max(axis=1) if ix else np.zeros(s.shape[0], dtype=np.float32)) for g, ix in self.idx.items()}


def _load_yamnet(models_dir: Path, allow_network: bool) -> tuple[Any | None, str]:
    """-> (model | None, note). Downloads the 16 MB ONNX once into ``models_dir``."""
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return None, "onnxruntime not installed — audio events skipped (pip install onnxruntime)"
    model, cmap = models_dir / "yamnet.onnx", models_dir / "yamnet_class_map.csv"
    if not (model.exists() and cmap.exists()):
        if not allow_network:
            return None, "YAMNet model not on disk and network is off — audio events skipped"
        models_dir.mkdir(parents=True, exist_ok=True)
        try:
            for f in (model, cmap):
                tmp = f.with_suffix(f.suffix + ".part")
                with httpx.stream("GET", YAMNET_URL + f.name, follow_redirects=True, timeout=120) as r:
                    r.raise_for_status()
                    with tmp.open("wb") as fh:
                        for chunk in r.iter_bytes(1 << 20):
                            fh.write(chunk)
                tmp.replace(f)
        except (httpx.HTTPError, OSError) as exc:
            return None, f"YAMNet download failed ({exc}) — audio events skipped"
    try:
        return _Yamnet(model, cmap), ""
    except Exception as exc:  # corrupt model / ort failure: degrade, never raise
        return None, f"YAMNet failed to load ({exc}) — audio events skipped"


def _audio_events(video: Path, duration: float, n_bins: int, yam: Any, chunk_s: float = 600.0) -> dict[str, np.ndarray]:
    out = {g: np.zeros(n_bins, dtype=np.float32) for g in _Yamnet.GROUPS}
    t = 0.0
    while t < duration:
        sc = yam.scores(_pcm(video, t, min(duration, t + chunk_s)))
        for g, arr in sc.items():
            for i, v in enumerate(arr):
                b = int((t + 0.48 * i + 0.48) / BIN_S)
                if 0 <= b < n_bins:
                    out[g][b] = max(out[g][b], v)
        t += chunk_s
    return out


# -- fusion ----------------------------------------------------------------------------------------------
def _pieces(vod_map: list[dict] | None) -> list[tuple[float, float, float]]:
    """``[{file_start,file_end,vod_start}]`` -> sorted ``[(file_start, file_end, vod_start)]`` (story pack)."""
    return sorted((float(p["file_start"]), float(p["file_end"]), float(p["vod_start"])) for p in vod_map or [])


def _vod_to_file(t: float, pieces: list[tuple[float, float, float]]) -> float | None:
    """Stream second -> second inside the glued file; None when no piece covers it."""
    for fs, fe, vs in pieces:
        if vs <= t < vs + (fe - fs):
            return fs + (t - vs)
    return None


def _file_to_vod(t: float, pieces: list[tuple[float, float, float]]) -> float | None:
    for fs, fe, vs in pieces:
        if fs <= t < fe:
            return vs + (t - fs)
    return None


def _chat_bins(msgs: list[tuple[float, str]], offset_s: float, duration: float, n_bins: int,
               pieces: list[tuple[float, float, float]] | None = None) -> dict[str, Any]:
    n = np.zeros(n_bins, dtype=np.int64)
    tags = [Counter() for _ in range(n_bins)]
    toks = [Counter() for _ in range(n_bins)]
    for t_vod, text in msgs:
        t = _vod_to_file(t_vod, pieces) if pieces else t_vod - offset_s
        if t is None or not (0 <= t < duration):
            continue
        b = min(n_bins - 1, int(t / BIN_S))
        n[b] += 1
        cats, tk = classify_message(text)
        tags[b].update(cats)
        toks[b].update(tk)
    return {"n": n, "tags": tags, "toks": toks}


def _clip_bins(clips: list[dict], n_bins: int) -> np.ndarray:
    x = np.zeros(n_bins, dtype=np.float64)
    top = max((c["views"] for c in clips), default=0) or 1
    for c in clips:
        w = 0.7 + 0.3 * min(1.0, c["views"] / top)
        for b in range(max(0, int(c["start_s"] / BIN_S)), min(n_bins, int(c["end_s"] / BIN_S) + 1)):
            x[b] = max(x[b], w)
    return x


def _replay_bins(heat: list[tuple[float, float, float]], offset_s: float, n_bins: int,
                 pieces: list[tuple[float, float, float]] | None = None) -> np.ndarray:
    x = np.zeros(n_bins, dtype=np.float64)
    for b in range(n_bins):
        c = b * BIN_S + BIN_S / 2 + offset_s
        if pieces:
            c = _file_to_vod(b * BIN_S + BIN_S / 2, pieces)
            if c is None:  # outside every piece: not measured
                x[b] = np.nan
                continue
        for a, z, v in heat:
            if a <= c < z:
                x[b] = v
                break
    return x


def _fuse(parts: dict[str, np.ndarray | None]) -> np.ndarray:
    """0-1 per bin. Half = the strongest source (a viewer clip alone is already a signal), half = weighted mean
    of the sources that exist; each extra source that agrees (>= its HOT level) lifts the bin 30%."""
    avail = {k: np.asarray(v, dtype=np.float64) for k, v in parts.items() if v is not None}
    n = len(next(iter(avail.values()))) if avail else 0
    if not n:
        return np.zeros(0)
    ok = {k: ~np.isnan(v) for k, v in avail.items()}  # NaN = this source could not be read for that bin
    avail = {k: np.nan_to_num(v) for k, v in avail.items()}
    wsum = sum(WEIGHTS[k] * ok[k] for k in avail)
    mean = sum(WEIGHTS[k] * ok[k] * v for k, v in avail.items()) / np.maximum(wsum, 1e-9)
    top = np.max([v * min(1.0, WEIGHTS[k] / 0.30) for k, v in avail.items()], axis=0)
    hot = sum((v >= HOT[k]).astype(np.int64) for k, v in avail.items())
    base = 0.5 * top + 0.5 * mean
    return np.clip(base * (1.0 + 0.3 * np.maximum(hot - 1, 0)), 0.0, 1.0)


def _evidence(bins: list[dict], clips: list[dict], a: float, b: float) -> str:
    bits: list[str] = []
    n = sum(x["chat_n"] for x in bins)
    if n:
        top = Counter()
        for x in bins:
            if x.get("chat_top"):
                top[x["chat_top"]] += x["chat_n"]
        bits.append(f"chat×{n}" + (f" {top.most_common(1)[0][0]}" if top else ""))
    for c in clips:
        if c["start_s"] < b and c["end_s"] > a:
            bits.append(f"viewer clip “{c['title'][:40]}” ({c['views']} views)")
            break
    for key, label, floor in (("laugh", "laughter", 0.25), ("cheer", "cheering", 0.25), ("scream", "screaming", 0.25)):
        v = max(x[key] for x in bins)
        if v >= floor:
            bits.append(f"{label} {v:.2f}".replace("0.", "."))
    rp = [x["replay"] for x in bins if x["replay"] is not None]
    if rp and max(rp) >= 0.5:
        bits.append(f"most-replayed {max(rp):.2f}".replace("0.", "."))
    if max(x["loud"] for x in bins) >= 0.8:
        bits.append("loud")
    return " · ".join(bits)


def _tags(bins: list[dict], clips: list[dict], a: float, b: float) -> list[str]:
    out: list[str] = []
    n = sum(x["chat_n"] for x in bins)
    for cat in ("funny", "hype", "shock", "sad"):
        c = sum(x["chat_tags"].get(cat, 0) for x in bins)
        if c >= 3 and c >= 0.2 * max(n, 1):
            out.append(cat)
    for key, tag in (("laugh", "funny"), ("cheer", "hype"), ("scream", "shock")):
        if max(x[key] for x in bins) >= 0.3 and tag not in out:
            out.append(tag)
    mus = [x["music"] for x in bins if x["music"] is not None]
    if mus and sum(mus) / len(mus) >= 0.5:
        out.append("music")
    if any(c["start_s"] < b and c["end_s"] > a for c in clips):
        out.append("clip")
    return out


def _peaks(bins: list[dict], clips: list[dict], duration: float, max_peaks: int = 40, min_sep_s: float = 12.0) -> list[dict]:
    if not bins:
        return []
    heat = np.array([b["heat"] for b in bins])
    sm = np.convolve(heat, np.ones(3) / 3, mode="same")
    thr = max(float(np.percentile(sm, 90)), 2.5)
    picks: list[int] = []
    for i in np.argsort(-sm):
        if sm[i] < thr or len(picks) >= max_peaks:
            break
        if all(abs(int(i) - j) * BIN_S >= min_sep_s for j in picks):
            picks.append(int(i))
    out = []
    for i in sorted(picks):
        lo = hi = i
        while lo > 0 and sm[lo - 1] >= 0.6 * sm[i] and i - lo < 6:
            lo -= 1
        while hi < len(bins) - 1 and sm[hi + 1] >= 0.6 * sm[i] and hi - i < 6:
            hi += 1
        a, b = lo * BIN_S, min(duration, (hi + 1) * BIN_S)
        seg = bins[lo:hi + 1]
        out.append({"start_s": round(a, 2), "end_s": round(b, 2), "heat": round(float(max(x["heat"] for x in seg)), 2),
                    "tags": _tags(seg, clips, a, b), "evidence": _evidence(seg, clips, a, b)})
    return out


# -- public API ------------------------------------------------------------------------------------------
def collect_signals(video: Path, work_dir: Path, *, url: str = "", offset_s: float = 0.0, duration: float | None = None,
                    allow_network: bool = True, models_dir: Path | None = None,
                    vod_map: list[dict] | None = None) -> dict[str, Any]:
    """Measure ``video``; cached in ``work_dir/signals.json``. Never raises — failures land in ``notes``.

    ``vod_map`` (story pack: several VOD ranges glued into one file) replaces the single ``offset_s``: chat, viewer
    clips and the heatmap are mapped piece by piece, and chat is only fetched for the pieces' VOD ranges."""
    video, work_dir = Path(video), Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        dur = float(duration) if duration else float(probe(video)["duration"])
    except Exception as exc:
        return {"version": VERSION, "duration": 0.0, "bin_s": BIN_S, "bins": [], "peaks": [], "clips": [], "sources": [],
                "notes": [f"could not probe video: {exc}"]}
    md = Path(models_dir) if models_dir else default_models_dir()
    pcs = _pieces(vod_map)
    key = {"url": url, "offset_s": round(float(offset_s), 2),
           "vod_map": [[round(a, 2), round(b, 2), round(c, 2)] for a, b, c in pcs] or None, "duration": round(dur, 1), "network": bool(allow_network),
           "size": video.stat().st_size if video.exists() else 0,
           "yamnet": (md / "yamnet.onnx").exists() and (md / "yamnet_class_map.csv").exists()}
    cache = work_dir / "signals.json"
    if cache.exists():
        try:
            old = json.loads(cache.read_text(encoding="utf-8"))
            if old.get("version") == VERSION and old.get("key") == key and not old.get("partial"):
                return old
        except (ValueError, OSError):
            pass

    n_bins = max(1, int(math.ceil(dur / BIN_S)))
    sources: list[str] = []
    notes: list[str] = []
    transient = False  # a source failed for a reason that may pass: do not cache this result
    unread: list[tuple[float, float]] = []  # file-second ranges where chat reading stopped early
    clips: list[dict] = []
    chat = None
    replay = None
    kind = parse_vod_url(url) if url else None
    if url and not kind:
        notes.append("signals url is not a Twitch VOD / YouTube video — no chat or clip signals")

    # audio: loudness (always) + YAMNet events (optional)
    loud: np.ndarray | None = None
    music: np.ndarray | None = None
    ev = {g: np.zeros(n_bins, dtype=np.float32) for g in _Yamnet.GROUPS}
    has_events = False
    try:
        loud = _norm(_loudness_bins(video, dur, n_bins), 10, 99)
        sources.append("loudness")
    except Exception as exc:
        notes.append(f"loudness failed: {exc}")
    yam, why = _load_yamnet(md, allow_network)
    if yam:
        try:
            ev = _audio_events(video, dur, n_bins, yam)
            music = ev["music"].astype(np.float64)
            has_events = True
            sources.append("yamnet")
        except Exception as exc:
            notes.append(f"YAMNet run failed: {exc}")
    else:
        notes.append(why)
        transient = transient or "download failed" in why

    # platform signals (only with network)
    if kind and allow_network:
        try:
            if kind[0] == "twitch":
                msgs: list[tuple[float, str]] = []
                try:
                    with httpx.Client() as client:
                        # (file_start, file_end, vod_start) per range to read; one range without a vod_map
                        ranges = pcs or [(0.0, dur, offset_s)]
                        for fs, fe, vs in ranges:
                            cinfo: dict = {}
                            msgs += twitch_chat(kind[1], vs, vs + (fe - fs), client=client, info=cinfo)
                            cut = cinfo.get("truncated_at")
                            if cut is not None:
                                unread.append((fs + max(0.0, cut - vs), fe))
                                notes.append(f"chat truncated at {_hms(fs + cut - vs)} of this file (VOD {_hms(cut)}); "
                                             "later bins have chat=None")
                                transient = True
                        meta = twitch_video_meta(kind[1], client)
                        for c in twitch_clips(meta["login"], "LAST_WEEK", client):
                            if c["vod_id"] != kind[1]:
                                continue
                            for fs, fe, vs in ranges:  # clip ∩ piece, mapped into the file
                                a, z = max(c["start_s"], vs) - vs + fs, min(c["end_s"], vs + (fe - fs)) - vs + fs
                                if z > a and z > 0 and a < dur:
                                    clips.append({"start_s": round(max(0, a), 2), "end_s": round(min(dur, z), 2),
                                                  "title": c["title"], "views": c["views"]})
                except Exception as exc:
                    notes.append(f"twitch signals partly failed: {exc}")
                    transient = True
                if msgs:
                    chat = _chat_bins(msgs, offset_s, dur, n_bins, pcs)
                    sources.append("twitch_chat")
                else:
                    notes.append("twitch chat: no messages in this range")
                if clips:
                    sources.append("twitch_clips")
                else:
                    notes.append("twitch viewer clips: none for this VOD (only last-week clips are searched)")
            else:
                try:
                    hm = parse_heatmap(yt_info(url))
                    if hm:
                        replay = _replay_bins(hm, offset_s, n_bins, pcs)
                        sources.append("yt_heatmap")
                    else:
                        notes.append("youtube: no most-replayed heatmap (new or small video)")
                except Exception as exc:
                    notes.append(f"youtube heatmap failed: {exc}")
                    transient = True
                try:
                    with tempfile.TemporaryDirectory() as tmp:
                        msgs = yt_live_chat(url, Path(tmp))
                    if msgs:
                        chat = _chat_bins(msgs, offset_s, dur, n_bins, pcs)
                        sources.append("yt_chat")
                except Exception as exc:
                    notes.append(f"youtube live chat unavailable: {exc}")
                    transient = transient or "no live chat" not in str(exc)
        except Exception as exc:  # belt and braces: nothing above may escape
            notes.append(f"platform signals failed: {exc}")
            transient = True
    elif kind:
        notes.append("network off — chat / viewer clips / replay skipped")

    chat_x = None
    if chat is not None:
        tag_total = np.array([sum(c.values()) for c in chat["tags"]], dtype=np.float64)
        raw = chat["n"] + tag_total
        read = np.ones(n_bins, dtype=bool)  # False = chat not read there (not "quiet")
        centers = np.arange(n_bins) * BIN_S + BIN_S / 2
        if pcs:
            read &= np.array([_file_to_vod(c, pcs) is not None for c in centers])
        for a, z in unread:
            read &= ~((centers >= a) & (centers < z))
        chat_x = np.full(n_bins, np.nan)
        if read.any():
            chat_x[read] = _norm(raw[read])
    parts = {"chat": chat_x, "clip": _clip_bins(clips, n_bins) if clips else None,
             "event": np.maximum.reduce([ev["laugh"], ev["cheer"], ev["scream"]]).astype(np.float64) if has_events else None,
             "loud": loud, "replay": replay}
    fused = _fuse(parts)

    bins: list[dict] = []
    for i in range(n_bins):
        top = chat["toks"][i].most_common(1)[0][0] if chat is not None and chat["toks"][i] else ""
        bins.append({
            "t": round(i * BIN_S, 2), "heat": round(float(fused[i]) * 10, 2),
            "loud": round(float(loud[i]), 3) if loud is not None else 0.0,
            "laugh": round(float(ev["laugh"][i]), 3), "cheer": round(float(ev["cheer"][i]), 3),
            "scream": round(float(ev["scream"][i]), 3), "music": round(float(music[i]), 3) if music is not None else None,
            "chat": round(float(chat_x[i]), 3) if chat_x is not None and not np.isnan(chat_x[i]) else None,
            "chat_n": int(chat["n"][i]) if chat is not None else 0,
            "chat_tags": {k: int(chat["tags"][i].get(k, 0)) if chat is not None else 0 for k in _TAG_FOR_CHAT},
            "chat_top": top, "replay": round(float(replay[i]), 3) if replay is not None and not np.isnan(replay[i]) else None})
    sig = {"version": VERSION, "duration": round(dur, 2), "bin_s": BIN_S, "bins": bins, "peaks": _peaks(bins, clips, dur),
           "clips": clips, "sources": sources, "notes": notes, "key": key}
    key["yamnet"] = (md / "yamnet.onnx").exists() and (md / "yamnet_class_map.csv").exists()
    # a partial result (a source failed for a reason that may pass) is still what the analyst reads now, but it
    # is never served as a cache hit: the next call retries the failed sources
    sig["partial"] = bool(transient)
    try:
        cache.write_text(json.dumps(sig, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("could not cache signals: %s", exc)
    return sig


def default_models_dir() -> Path:
    env = os.environ.get("AGENCY_MODELS_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "cache" / "models"


def heat_between(sig: dict[str, Any], a: float, b: float) -> dict[str, Any]:
    """Aggregate the measured signals over [a, b] source seconds."""
    bin_s = sig.get("bin_s") or BIN_S
    seg = [x for x in sig.get("bins") or [] if x["t"] < b and x["t"] + bin_s > a]
    empty = {"heat": 0.0, "mean": 0.0, "laugh": 0.0, "chat": None, "music": None, "tags": [], "evidence": ""}
    if not seg:
        return empty
    clips = sig.get("clips") or []
    chats = [x["chat"] for x in seg if x["chat"] is not None]
    mus = [x["music"] for x in seg if x["music"] is not None]
    return {"heat": max(x["heat"] for x in seg), "mean": round(sum(x["heat"] for x in seg) / len(seg), 2),
            "laugh": max(x["laugh"] for x in seg), "chat": max(chats) if chats else None,
            "music": round(sum(mus) / len(mus), 3) if mus else None,
            "tags": _tags(seg, clips, a, b), "evidence": _evidence(seg, clips, a, b)}


def prompt_timeline(sig: dict[str, Any], max_items: int = 60) -> str:
    """Compact text for the analyst prompt: the hottest peaks in time order, with their evidence."""
    peaks = sorted(sig.get("peaks") or [], key=lambda p: -p["heat"])[:max_items]
    head = f"Measured signals ({', '.join(sig.get('sources') or []) or 'none'}); times = seconds of this file."
    if not peaks:
        return head + "\n(no peak stood out)"
    lines = [f"[{p['start_s']:.0f}s–{p['end_s']:.0f}s] heat {p['heat']:.1f}"
             + (f" [{','.join(p['tags'])}]" if p["tags"] else "") + (f" — {p['evidence']}" if p["evidence"] else "")
             for p in sorted(peaks, key=lambda p: p["start_s"])]
    return head + "\n" + "\n".join(lines)
