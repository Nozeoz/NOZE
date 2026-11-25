"""Story helpers shared by every role: a moment is one or more source ranges played in order
(``parts``), possibly jumping back or forward in the stream. Time-jump labels are always
computed here from the real gap, never trusted from a model (a card saying "40 MIN LATER"
over a 3-minute gap is a lie the viewer can't check but the creator can)."""

from __future__ import annotations

from typing import Any

MIN_LABEL_GAP_S = 60.0  # parts closer than this read as one scene: no card


def moment_parts(moment: dict[str, Any]) -> list[dict[str, Any]]:
    """The moment's parts in play order; a plain moment is one part covering start_s-end_s."""
    parts = [p for p in (moment.get("parts") or [])
             if isinstance(p, dict) and float(p.get("end_s") or 0) - float(p.get("start_s") or 0) > 0.25]
    if parts:
        out = [{"start_s": float(p["start_s"]), "end_s": float(p["end_s"]), "role": p.get("role") or "build",
                "label": p.get("label") or ""} for p in parts]
    else:
        out = [{"start_s": float(moment["start_s"]), "end_s": float(moment["end_s"]), "role": "build", "label": ""}]
    return split_at_seams(out, moment.get("vod_map"))


def split_at_seams(parts: list[dict[str, Any]], vod_map: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """A story pack glues VOD ranges hours apart: a part must never run across a glue point as if the footage
    were continuous (review 24 Nov). Cut every part at each seam inside it; slivers < 0.25 s (snap padding that
    spilled over a seam) are dropped. Without a map the parts come back unchanged."""
    if not vod_map:
        return parts
    seams = sorted({float(p["file_end"]) for p in vod_map} | {float(p["file_start"]) for p in vod_map})
    out = []
    for p in parts:
        cuts = [p["start_s"]] + [s for s in seams if p["start_s"] + 1e-6 < s < p["end_s"] - 1e-6] + [p["end_s"]]
        for a, b in zip(cuts, cuts[1:]):
            if b - a >= 0.25:
                out.append({**p, "start_s": round(a, 3), "end_s": round(b, 3)})
    return out or parts


def envelope(parts: list[dict[str, Any]]) -> tuple[float, float]:
    return min(p["start_s"] for p in parts), max(p["end_s"] for p in parts)


def parts_duration(parts: list[dict[str, Any]]) -> float:
    return sum(p["end_s"] - p["start_s"] for p in parts)


def _span(seconds: float) -> str:
    m = int(round(seconds / 60.0))
    if m < 60:
        return f"{max(1, m)} MIN"
    h = seconds / 3600.0
    hours = round(h * 2) / 2  # nearest half hour
    txt = f"{hours:g}"
    return f"{txt} HOUR" if hours == 1 else f"{txt} HOURS"


def to_vod(t: float, vod_map: list[dict[str, Any]] | None) -> float:
    """File second → stream (VOD) second. A story pack is several VOD ranges glued into one file:
    ``vod_map`` = [{"file_start", "file_end", "vod_start"}]; without one, file time IS stream time."""
    for piece in vod_map or []:
        if float(piece["file_start"]) - 1e-6 <= t <= float(piece["file_end"]) + 1e-6:
            return float(piece["vod_start"]) + (t - float(piece["file_start"]))
    return t


def to_file(t_vod: float, vod_map: list[dict[str, Any]] | None) -> float | None:
    """Stream (VOD) second -> second in the story-pack file; None when that stream second is not in the pack."""
    if not vod_map:
        return t_vod
    for piece in vod_map:
        a = float(piece["vod_start"])
        b = a + float(piece["file_end"]) - float(piece["file_start"])
        if a - 1e-6 <= t_vod <= b + 1e-6:
            return float(piece["file_start"]) + (t_vod - a)
    return None


def _on_vod(part: dict[str, Any], vod_map: list[dict[str, Any]] | None) -> dict[str, Any]:
    """A whole part maps through ONE piece — the one holding its midpoint — so an edge that sits a few
    hundredths past a seam can't land it in the neighbouring piece (review 24 Nov: '' instead of 2 HOURS)."""
    if not vod_map:
        return part
    mid = (part["start_s"] + part["end_s"]) / 2
    piece = next((p for p in vod_map if float(p["file_start"]) - 1e-6 <= mid <= float(p["file_end"]) + 1e-6), None)
    if piece is None:
        return {**part, "start_s": to_vod(part["start_s"], vod_map), "end_s": to_vod(part["end_s"], vod_map)}
    off = float(piece["vod_start"]) - float(piece["file_start"])
    return {**part, "start_s": part["start_s"] + off, "end_s": part["end_s"] + off}


def time_jump_label(prev: dict[str, Any] | None, part: dict[str, Any],
                    vod_map: list[dict[str, Any]] | None = None) -> str:
    """'40 MIN LATER' / '2 HOURS EARLIER' for a part that starts far from where the previous one
    ended — measured in STREAM time (``vod_map``), never the glued file's time; '' when the jump is
    too small to need a card (or for the first part)."""
    if prev is None:
        return ""
    prev, part = _on_vod(prev, vod_map), _on_vod(part, vod_map)
    if part["start_s"] >= prev["end_s"]:
        gap = part["start_s"] - prev["end_s"]
        word = "LATER"
    else:
        gap = prev["start_s"] - part["start_s"] if part["end_s"] <= prev["start_s"] else 0.0
        word = "EARLIER"
    if gap < MIN_LABEL_GAP_S:
        return ""
    return f"{_span(gap)} {word}"


def label_parts(parts: list[dict[str, Any]], vod_map: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Overwrite every part's label with the true time-jump label (stream time when ``vod_map``); parts that
    cross a story-pack seam are split there first, so the jump gets its card."""
    out, prev = [], None
    for p in split_at_seams(parts, vod_map):
        out.append({**p, "label": time_jump_label(prev, p, vod_map)})
        prev = p
    return out


def label_matches(label: str, prev: dict[str, Any] | None, part: dict[str, Any],
                  vod_map: list[dict[str, Any]] | None = None) -> bool:
    """Is an on-screen label consistent with the real gap? (QC: C3 rewind_label_delta)."""
    return (label or "").strip().upper() == time_jump_label(prev, part, vod_map)


if __name__ == "__main__":
    a = {"start_s": 100.0, "end_s": 130.0}
    b = {"start_s": 2500.0, "end_s": 2520.0}
    assert time_jump_label(None, a) == ""
    assert time_jump_label(a, b) == "40 MIN LATER", time_jump_label(a, b)
    assert time_jump_label(b, a) == "40 MIN EARLIER", time_jump_label(b, a)
    assert time_jump_label(a, {"start_s": 140.0, "end_s": 150.0}) == ""
    assert time_jump_label(a, {"start_s": 130 + 7400, "end_s": 7600}) == "2 HOURS LATER"
    assert moment_parts({"start_s": 1, "end_s": 9})[0]["end_s"] == 9.0
    assert label_matches("40 min later", a, b) and not label_matches("10 MIN LATER", a, b)
    # a story pack: two VOD ranges 2 h apart glued back to back in one file (file gap 0 s)
    vm = [{"file_start": 0, "file_end": 60, "vod_start": 3600}, {"file_start": 60, "file_end": 120, "vod_start": 10800}]
    x, y = {"start_s": 10.0, "end_s": 50.0}, {"start_s": 70.0, "end_s": 110.0}
    assert time_jump_label(x, y) == "" and time_jump_label(x, y, vm) == "2 HOURS LATER"
    assert to_vod(70, vm) == 10810 and to_vod(500, vm) == 500
    # review 24 Nov: an edge 0.07 s before the seam must not drag the part into the first piece
    assert time_jump_label({"start_s": 10.0, "end_s": 50.0}, {"start_s": 59.93, "end_s": 110.0}, vm) == "2 HOURS LATER"
    # a single part running across the seam is split there and the second half gets the card
    lp = label_parts([{"start_s": 30.0, "end_s": 90.0, "role": "build", "label": ""}], vm)
    assert [(p["start_s"], p["end_s"], p["label"]) for p in lp] == [(30.0, 60.0, ""), (60.0, 90.0, "2 HOURS LATER")], lp
    assert len(moment_parts({"start_s": 30, "end_s": 90, "vod_map": vm})) == 2
    assert split_at_seams([{"start_s": 59.9, "end_s": 80.0}], vm) == [{"start_s": 60.0, "end_s": 80.0}]
    print("story ok")
