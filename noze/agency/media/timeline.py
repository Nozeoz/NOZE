"""The edit timeline: source ranges laid end to end, and the maths that maps
source time ↔ output time (captions, SFX cues and review timecodes all depend on it).

Transitions never overlap clips (flash / dip / whip / zoom are applied *at*
the cut), so output time is a plain running sum — simple, exact, testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .transcribe import is_filler

MIN_SEGMENT_S = 0.25


@dataclass
class Placed:
    index: int
    src_start: float
    src_end: float
    speed: float
    out_start: float
    out_end: float

    @property
    def out_duration(self) -> float:
        return self.out_end - self.out_start


class Timeline:
    def __init__(self, segments: list[dict[str, Any]]):
        self.segments = segments
        self.placed: list[Placed] = []
        t = 0.0
        for i, seg in enumerate(segments):
            speed = float(seg.get("speed") or 1.0)
            d = (float(seg["src_end"]) - float(seg["src_start"])) / speed
            self.placed.append(Placed(i, float(seg["src_start"]), float(seg["src_end"]), speed, t, t + d))
            t += d
        self.duration = round(t, 3)

    def to_output(self, src_t: float) -> float | None:
        """First output time showing source time ``src_t`` (None if it was cut)."""
        for p in self.placed:
            if p.src_start - 1e-6 <= src_t <= p.src_end + 1e-6:
                return round(p.out_start + (src_t - p.src_start) / p.speed, 3)
        return None

    def to_source(self, out_t: float) -> float | None:
        for p in self.placed:
            if p.out_start - 1e-6 <= out_t <= p.out_end + 1e-6:
                return round(p.src_start + (out_t - p.out_start) * p.speed, 3)
        return None

    def segment_at(self, out_t: float) -> Placed | None:
        for p in self.placed:
            if p.out_start <= out_t < p.out_end:
                return p
        return self.placed[-1] if self.placed and out_t >= self.placed[-1].out_start else None

    def map_words(self, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Words that survive the cut, re-timed to the output (repeated ranges repeat their words)."""
        out: list[dict[str, Any]] = []
        for p in self.placed:
            for w in words:
                mid = (w["start"] + w["end"]) / 2
                if p.src_start - 0.02 <= mid <= p.src_end + 0.02:
                    s = max(w["start"], p.src_start)
                    e = min(w["end"], p.src_end)
                    out.append({**w, "start": round(p.out_start + (s - p.src_start) / p.speed, 3),
                                "end": round(p.out_start + (max(e, s + 0.05) - p.src_start) / p.speed, 3)})
        out.sort(key=lambda w: w["start"])
        return out

    def cut_points(self) -> list[float]:
        return [round(p.out_start, 3) for p in self.placed[1:]]


def remove_output_range(segments: list[dict[str, Any]], out_a: float, out_b: float) -> list[dict[str, Any]]:
    """Cut [out_a, out_b] (output seconds, e.g. measured dead air) out of the edit,
    splitting the segment(s) it falls in. The piece after a split keeps a plain cut."""
    tl = Timeline(segments)
    out: list[dict[str, Any]] = []
    for p in tl.placed:
        seg = segments[p.index]
        a, b = max(out_a, p.out_start), min(out_b, p.out_end)
        if b - a <= 0.02:
            out.append(seg)
            continue
        src_a = p.src_start + (a - p.out_start) * p.speed
        src_b = p.src_start + (b - p.out_start) * p.speed
        if src_a - p.src_start >= MIN_SEGMENT_S:
            out.append({**seg, "src_end": round(src_a, 3)})
        if p.src_end - src_b >= MIN_SEGMENT_S:
            first = src_a - p.src_start < MIN_SEGMENT_S
            out.append({**seg, "src_start": round(src_b, 3),
                        "transition_in": seg.get("transition_in", "cut") if first else "cut"})
    return out


def sanitize_segments(segments: list[dict[str, Any]], source_duration: float, bounds: tuple[float, float] | None = None,
                      max_total: float | None = None) -> list[dict[str, Any]]:
    """Clamp an editor's segment list into something renderable: inside the source
    (and the moment, with a little slack), ordered, no slivers, sane speed, capped length."""
    lo, hi = (0.0, source_duration) if bounds is None else (max(0.0, bounds[0] - 1.5),
                                                            min(source_duration, bounds[1] + 1.5))
    out: list[dict[str, Any]] = []
    for seg in segments:
        try:
            a, b = float(seg.get("src_start", 0)), float(seg.get("src_end", 0))
        except (TypeError, ValueError):
            continue
        a, b = max(lo, a), min(hi, b)
        if b - a < MIN_SEGMENT_S:
            continue
        s = dict(seg)
        s["src_start"], s["src_end"] = round(a, 3), round(b, 3)
        s["speed"] = min(1.5, max(0.5, float(seg.get("speed") or 1.0)))
        out.append(s)
    total = 0.0
    capped: list[dict[str, Any]] = []
    for s in out:
        d = (s["src_end"] - s["src_start"]) / s["speed"]
        if max_total and total + d > max_total:
            room = max_total - total
            if room >= MIN_SEGMENT_S:
                s = dict(s)
                s["src_end"] = round(s["src_start"] + room * s["speed"], 3)
                capped.append(s)
            break
        capped.append(s)
        total += d
    return capped


def jump_cut(words: list[dict[str, Any]], start: float, end: float, max_gap: float = 0.45,
             cut_fillers: bool = True, pad: float = 0.08) -> list[tuple[float, float]]:
    """Split [start, end] into spoken ranges, dropping pauses longer than ``max_gap``
    and filler words — the classic short-form "tight" cut."""
    ws = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.05]
    if cut_fillers:
        ws = [w for w in ws if not is_filler(w["word"])]
    if not ws:
        return [(start, end)]
    ranges: list[list[float]] = [[max(start, ws[0]["start"] - pad), ws[0]["end"]]]
    for w in ws[1:]:
        if w["start"] - ranges[-1][1] > max_gap:
            ranges[-1][1] = min(end, ranges[-1][1] + pad)
            ranges.append([max(start, w["start"] - pad), w["end"]])
        else:
            ranges[-1][1] = w["end"]
    ranges[-1][1] = min(end, ranges[-1][1] + pad + 0.1)
    merged: list[tuple[float, float]] = []
    for a, b in ranges:
        if merged and a - merged[-1][1] < 0.06:
            merged[-1] = (merged[-1][0], b)
        elif b - a >= MIN_SEGMENT_S:
            merged.append((round(a, 3), round(b, 3)))
    return merged or [(start, end)]
