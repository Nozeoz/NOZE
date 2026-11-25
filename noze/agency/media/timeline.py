"""The edit timeline: source ranges laid end to end, and the maths that maps
source time ↔ output time (captions, SFX cues and review timecodes all depend on it).

Transitions never overlap clips (flash / dip / whip / zoom / glitch are applied *at*
the cut, rewind is drawn over the head of the incoming segment), so output time is a
plain running sum — simple, exact, testable. A segment may end with a ``hold`` (its
last frame frozen for up to HOLD_MAX seconds): it lengthens the segment's slot and
carries no words.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .transcribe import is_filler

MIN_SEGMENT_S = 0.25
HOLD_MAX = 1.2
BOUND_SLACK_S = 1.5


def clamp_hold(v: Any) -> float:
    try:
        return round(min(HOLD_MAX, max(0.0, float(v or 0.0))), 3)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class Placed:
    index: int
    src_start: float
    src_end: float
    speed: float
    out_start: float
    out_end: float
    hold: float = 0.0  # frozen last frame, seconds, included in out_end

    @property
    def out_duration(self) -> float:
        return self.out_end - self.out_start

    @property
    def play_end(self) -> float:
        """Output time where the moving picture ends (the hold, if any, follows)."""
        return self.out_end - self.hold


class Timeline:
    def __init__(self, segments: list[dict[str, Any]]):
        self.segments = segments
        self.placed: list[Placed] = []
        t = 0.0
        for i, seg in enumerate(segments):
            speed = float(seg.get("speed") or 1.0)
            hold = clamp_hold(seg.get("hold"))
            d = (float(seg["src_end"]) - float(seg["src_start"])) / speed + hold
            self.placed.append(Placed(i, float(seg["src_start"]), float(seg["src_end"]), speed, t, t + d, hold))
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
            if p.out_start - 1e-6 <= out_t <= p.out_end + 1e-6:  # inside a hold = the frozen last frame
                return round(min(p.src_end, p.src_start + (out_t - p.out_start) * p.speed), 3)
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
                    # a word never spills into the hold: the picture is frozen and silent there
                    out.append({**w, "start": round(p.out_start + (s - p.src_start) / p.speed, 3),
                                "end": round(min(p.out_start + (max(e, s + 0.05) - p.src_start) / p.speed,
                                                 p.play_end), 3)})
        out.sort(key=lambda w: w["start"])
        return out

    def cut_points(self) -> list[float]:
        return [round(p.out_start, 3) for p in self.placed[1:]]


def remove_output_range(segments: list[dict[str, Any]], out_a: float, out_b: float) -> list[dict[str, Any]]:
    """Cut [out_a, out_b] (output seconds, e.g. measured dead air) out of the edit,
    splitting the segment(s) it falls in. The piece after a split keeps a plain cut
    (and the hold, which belongs to the end of the segment); the head loses it."""
    tl = Timeline(segments)
    out: list[dict[str, Any]] = []
    for p in tl.placed:
        seg = segments[p.index]
        a, b = max(out_a, p.out_start), min(out_b, p.play_end)
        if b - a <= 0.02:
            out.append(seg)
            continue
        src_a = p.src_start + (a - p.out_start) * p.speed
        src_b = p.src_start + (b - p.out_start) * p.speed
        keep_head = src_a - p.src_start >= MIN_SEGMENT_S
        keep_tail = p.src_end - src_b >= MIN_SEGMENT_S
        if keep_head:  # the hold belongs to the END of the segment: the head only gives it up if a tail carries it
            out.append({**seg, "src_end": round(src_a, 3), **({"hold": 0.0} if keep_tail and "hold" in seg else {})})
        if keep_tail:
            out.append({**seg, "src_start": round(src_b, 3),
                        "transition_in": seg.get("transition_in", "cut") if not keep_head else "cut"})
    return out


def _bounds_list(bounds: Any, source_duration: float) -> list[tuple[float, float]]:
    """``None`` | ``(a, b)`` | ``[(a, b), ...]`` → allowed source ranges, each widened by the slack."""
    if bounds is None:
        return [(0.0, source_duration)]
    pairs = [bounds] if len(bounds) == 2 and not isinstance(bounds[0], (list, tuple)) else list(bounds)
    if not pairs:
        return [(0.0, source_duration)]
    return [(max(0.0, float(a) - BOUND_SLACK_S), min(source_duration, float(b) + BOUND_SLACK_S)) for a, b in pairs]


def sanitize_segments(segments: list[dict[str, Any]], source_duration: float,
                      bounds: tuple[float, float] | list[tuple[float, float]] | None = None,
                      max_total: float | None = None) -> list[dict[str, Any]]:
    """Clamp an editor's segment list into something renderable: inside the source and inside the moment's
    part(s) (with a little slack), no slivers, sane speed and hold, capped length. ``bounds`` is one range or a
    list (a moment built from several periods of the stream): each segment is clamped into the range it overlaps
    most and dropped if it overlaps none. The editor's ORDER is kept — a story may jump back in the source."""
    ranges = _bounds_list(bounds, source_duration)
    out: list[dict[str, Any]] = []
    for seg in segments:
        try:
            a, b = float(seg.get("src_start", 0)), float(seg.get("src_end", 0))
        except (TypeError, ValueError):
            continue
        lo, hi = max(ranges, key=lambda r: min(b, r[1]) - max(a, r[0]))
        a, b = max(lo, a), min(hi, b)
        if b - a < MIN_SEGMENT_S:  # also covers "overlaps no bound": the clamp inverts the range
            continue
        s = dict(seg)
        s["src_start"], s["src_end"] = round(a, 3), round(b, 3)
        s["speed"] = min(1.5, max(0.5, float(seg.get("speed") or 1.0)))
        if "hold" in seg:
            s["hold"] = clamp_hold(seg.get("hold"))
        out.append(s)
    return _cap_total(out, max_total) if max_total else out


CAP_ORDER = (("setup", "build", "context"), ("hook", "foreshadow", "turn", "callback", "button", ""),
             ("payoff", "reaction", "cold_open"))  # what gives up time first, last


def _slot(s: dict[str, Any]) -> float:
    return (s["src_end"] - s["src_start"]) / s["speed"] + clamp_hold(s.get("hold"))


def _cap_total(segs: list[dict[str, Any]], max_total: float) -> list[dict[str, Any]]:
    """Fit the edit into ``max_total``: holds shrink first (last to first), then segments give up playing time —
    setup/build/context first (longest first), then the rest, the payoff / reaction / cold open last. Order kept.
    Still too long after every segment is down to the minimum → the tail is dropped."""
    segs = [dict(s) for s in segs]
    excess = sum(_slot(s) for s in segs) - max_total
    for s in reversed(segs):
        if excess <= 1e-6:
            break
        cut = min(clamp_hold(s.get("hold")), excess)
        if cut > 0:
            s["hold"] = round(clamp_hold(s.get("hold")) - cut, 3)
            excess -= cut
    for roles in CAP_ORDER:
        while excess > 1e-6:
            pool = [s for s in segs if (s.get("role") or "") in roles
                    and (s["src_end"] - s["src_start"]) / s["speed"] - MIN_SEGMENT_S > 1e-6]
            if not pool:
                break
            s = max(pool, key=lambda x: x["src_end"] - x["src_start"])
            cut = min(excess, (s["src_end"] - s["src_start"]) / s["speed"] - MIN_SEGMENT_S)
            s["src_end"] = round(s["src_end"] - cut * s["speed"], 3)
            excess -= cut
    out: list[dict[str, Any]] = []
    total = 0.0
    for s in segs:  # anything still over (all at the minimum): drop from the tail
        if total + _slot(s) > max_total + 1e-6:
            break
        out.append(s)
        total += _slot(s)
    return out


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
