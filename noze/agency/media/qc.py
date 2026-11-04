"""Technical QC + plan lint: the reviewer's checklist that never needs an LLM.

Every check yields issues with a stable ``id`` (``category:check``) so the same
problem can be tracked across revision rounds and counted by the learning loop.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..standards import DELIVERY, LAYOUT, QC, PLATFORM_LIMITS, safe_zone
from .analyze import blacks, freezes, loudness, scene_cuts, silences
from .captions import (AssDoc, Meter, box_pad, caption_styles, overlay_styles, pick_font, plan_captions, plan_overlays,
                       rides_seam, text_box)
from .ffmpeg import MediaError, probe, run
from . import faces as face_finder
from .render import _valid_cam, stack_layout
from .timeline import Timeline


def issue(check: str, category: str, severity: str, description: str, fix: str,
          timecode: float | None = None, evidence: Any = None) -> dict[str, Any]:
    return {"id": f"{category}:{check}", "category": category, "severity": severity,
            "timecode_s": None if timecode is None else round(float(timecode), 2),
            "description": description, "fix": fix, "source": "qc", "evidence": evidence}


def _near(t: float, points: list[float], tol: float) -> bool:
    return any(abs(t - p) <= tol for p in points)


log = logging.getLogger("noze.agency.qc")


def stack_seams(plan: dict[str, Any], src_size: tuple[int, int] | None, width: int, height: int
                ) -> list[tuple[float, float, int, dict[str, Any]]]:
    """(out_start, out_end, cam band px, segment) of the segments the renderer really stacks (facecam on top)."""
    segs = plan.get("segments") or []
    src_w, src_h = src_size or (1920, 1080)
    if not segs or src_w / max(src_h, 1) <= width / height:
        return []
    return [(p.out_start, p.out_end, stack_layout(segs[p.index]["reframe"]["cam"], src_w, src_h, width, height)[0],
             segs[p.index]) for p in Timeline(segs).placed
            if (segs[p.index].get("reframe") or {}).get("mode") == "stack"
            and _valid_cam(segs[p.index]["reframe"].get("cam"))]


def empty_band_stretches(path: str, seams: list[tuple[float, float, int, Any]], width: int, height: int,
                         duration: float) -> list[tuple[float, float, bool]]:
    """Stretches (start, end, bare) longer than QC['empty_band_max_s'] where the gameplay band of the RENDERED file has
    no action: sample frames; a sample is empty when the share of band pixels whose luma is more than
    QC['empty_band_luma_delta'] levels from the band's median luma is under QC['empty_band_min_share'], or when
    (median over a short window) under QC['empty_band_motion_share'] of the band changed since the last sample.
    The band is everything below the seam on stacked segments, the whole frame elsewhere."""
    import numpy as np

    fps = float(QC["empty_band_sample_fps"])
    sw = max(32, width // 9)
    sh = max(32, round(height * sw / max(width, 1)))
    raw = run(["-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={sw}:{sh}:flags=area", "-pix_fmt", "gray",
               "-f", "rawvideo", "-"], timeout=600, check=False).stdout
    n = len(raw) // (sw * sh)
    if n == 0:  # never "clean" by accident: the caller records the error in the metrics
        raise MediaError("could not sample the render for the empty-band check")
    frames = np.frombuffer(raw[:n * sw * sh], dtype=np.uint8).reshape(n, sh, sw).astype(np.int16)
    share: list[float] = []  # band pixels far from the band's median luma
    moved: list[float] = []  # band pixels that changed by more than the same delta since the previous sample
    for i in range(n):
        seam = next((y for a, b, y, _ in seams if a - 0.01 <= i / fps < b), None)
        row0 = 0 if seam is None else min(sh - 1, int(seam * sh / height) + 1)  # +1: skip the seam line itself
        band = frames[i, row0:]
        share.append(float((np.abs(band - np.median(band)) > QC["empty_band_luma_delta"]).mean()))
        moved.append(float((np.abs(band - frames[i - 1, row0:]) > QC["empty_band_luma_delta"]).mean()) if i else 1.0)
    if n > 1:
        moved[0] = moved[1]
    w = int(QC["empty_band_motion_window"]) // 2
    # empty = a bare stage (little differs from the median) OR a still one: live run 3 Nov, a static letterbox bar
    # alone put 28% of the band "away from the median" for 9 s while only a 70px square moved
    empty = [share[i] < QC["empty_band_min_share"]
             or float(np.median(moved[max(0, i - w):i + w + 1])) < QC["empty_band_motion_share"] for i in range(n)]
    out: list[tuple[float, float]] = []
    i = 0
    while i < n:
        if not empty[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and empty[j + 1]:
            j += 1
        a, b = i / fps, min(duration or (j + 1) / fps, (j + 1) / fps)
        if b - a > QC["empty_band_max_s"] + 1e-6:
            bare = sum(share[k] < QC["empty_band_min_share"] for k in range(i, j + 1)) > (j + 1 - i) / 2
            out.append((round(a, 2), round(b, 2), bare))
        i = j + 1
    return out


def empty_band_issues(empties: list[tuple[float, float, bool]]) -> list[dict[str, Any]]:
    out = []
    for a, b, bare in empties:
        # a bare stage is empty however long; a merely still band (busy but static UI, a board game) only from 2x
        sev = "major" if bare or b - a > 2 * QC["empty_band_max_s"] else "minor"
        out.append(issue("empty_band", "visual", sev,
                         f"The gameplay band is empty (no action) for {b - a:.1f}s, {a:.1f}-{b:.1f}s.",
                         f"Cut {a:.1f}-{b:.1f}s, give that segment a band_src replay or a punch_title "
                         f"(max {QC['empty_band_max_s']:.0f}s of empty stage).", a, evidence={"start": a, "end": b}))
    return out


def measure_cam_faces(path: str, seams: list[tuple[float, float, int, Any]], work: Path, per_seg: int = 5
                      ) -> dict[float, dict[str, Any]] | None:
    """Detect the face on OUTPUT frames, inside the cam band of every stacked segment (not the plan's guess).
    {round(seg out_start, 2): {"box": median head box (x, y, w, h px) | None, "hits", "n"}}; None when OpenCV
    cannot detect (the caller then keeps the plan's box)."""
    if not seams or not face_finder.available():
        return None
    work.mkdir(parents=True, exist_ok=True)
    per = max(2, min(per_seg, 24 // len(seams)))
    jobs: list[tuple[int, Path, int]] = []
    for k, (a, b, band, _) in enumerate(seams):
        for i in range(per):
            dest = work / f"cam_{k}_{i}.jpg"
            t = a + (i + 0.5) * (b - a) / per
            if not dest.exists():
                run(["-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-q:v", "2", "-y", str(dest)],
                    timeout=120, check=False)
            if dest.exists():
                jobs.append((k, dest, band))
    found = face_finder.faces_in_band([(f, band) for _, f, band in jobs])
    if found is None:
        return None
    out: dict[float, dict[str, Any]] = {}
    for k, (a, *_rest) in enumerate(seams):
        mine = [box for (kk, _, _), box in zip(jobs, found) if kk == k]
        # ONE real detection (median area) — a per-coordinate median of different boxes builds a box no frame
        # had (with 2 samples it is the max of each edge, spilling below the seam)
        hits = sorted((b for b in mine if b), key=lambda b: b[2] * b[3])
        box = tuple(hits[len(hits) // 2]) if hits else None
        out[round(a, 2)] = {"box": box, "hits": len(hits), "n": len(mine)}
    return out


def _iou(a: tuple, b: tuple) -> float:
    """IoU of two (x, y, w, h) boxes."""
    ix = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def technical_qc(path: str, *, width: int, height: int, fps: int, target_lufs: float,
                 min_s: float, max_s: float, platform: str, intended_dips: list[float] | None = None,
                 render_info: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Measure the delivered file. Returns (issues, metrics)."""
    issues: list[dict[str, Any]] = []
    info = probe(path)
    dur = float(info.get("duration") or 0.0)
    m: dict[str, Any] = {"duration": round(dur, 2), "width": info.get("width"), "height": info.get("height"),
                         "fps": round(float(info.get("fps") or 0), 2), "size_mb": round(info.get("size", 0) / 1e6, 1)}
    if (info.get("width"), info.get("height")) != (width, height):
        issues.append(issue("resolution", "technical", "blocker",
                            f"Frame is {info.get('width')}x{info.get('height')}, delivery needs {width}x{height}.",
                            f"Render at {width}x{height}."))
    if abs(float(info.get("fps") or 0) - fps) > 0.5:
        issues.append(issue("fps", "technical", "major", f"Frame rate {m['fps']} ≠ {fps}.", f"Render at {fps} fps."))
    if info.get("vcodec") != DELIVERY["vcodec"] or info.get("pix_fmt") != DELIVERY["pix_fmt"]:
        issues.append(issue("codec", "technical", "blocker",
                            f"Video is {info.get('vcodec')}/{info.get('pix_fmt')}.", "Encode H.264 yuv420p."))
    if not info.get("has_audio"):
        issues.append(issue("no_audio", "audio", "blocker", "The clip has no audio track.", "Keep the source audio."))
    if m["size_mb"] > DELIVERY["max_file_mb"]:
        issues.append(issue("file_size", "technical", "major", f"File is {m['size_mb']} MB.",
                            "Lower bitrate or shorten the clip."))
    limit = (PLATFORM_LIMITS.get(platform) or PLATFORM_LIMITS["other"])["max_s"]
    if dur < min_s - 0.5:
        issues.append(issue("too_short", "compliance", "major", f"Clip is {dur:.1f}s; the brief needs ≥ {min_s:.0f}s.",
                            f"Extend to at least {min_s:.0f}s (keep context before the hook or let the payoff land)."))
    if dur > min(max_s, limit) + 0.5:
        issues.append(issue("too_long", "compliance", "major",
                            f"Clip is {dur:.1f}s; the limit is {min(max_s, limit):.0f}s.",
                            f"Trim to ≤ {min(max_s, limit):.0f}s: cut setup, keep hook and payoff."))

    if info.get("has_audio"):
        loud = loudness(path)
        m["loudness"] = loud
        if abs(loud["integrated"] - target_lufs) > DELIVERY["lufs_tolerance"]:
            issues.append(issue("loudness", "audio", "major",
                                f"Integrated loudness {loud['integrated']} LUFS (target {target_lufs}).",
                                f"Normalise to {target_lufs} LUFS (two-pass loudnorm)."))
        if loud["true_peak"] > DELIVERY["true_peak_max"]:
            issues.append(issue("true_peak", "audio", "major", f"True peak {loud['true_peak']} dBTP clips.",
                                f"Limit to ≤ {DELIVERY['true_peak_max']} dBTP."))
        sil = silences(path, noise_db=-42.0, min_s=QC["max_dead_air_s"], duration=dur)
        m["silences"] = sil
        for a, b in sil:
            if a < QC["hook_first_sound_s"]:
                issues.append(issue("silent_open", "hook", "major", f"No sound in the first {b:.1f}s.",
                                    "Start on the first spoken word — trim the lead-in.", a))
            elif b < dur - 0.3:
                issues.append(issue("dead_air", "pacing", "major", f"Dead air {b - a:.1f}s at {a:.1f}s.",
                                    f"Jump-cut the pause between {a:.1f}s and {b:.1f}s.", a,
                                    evidence={"start": a, "end": b}))

    dips = intended_dips or []
    bl = blacks(path, min_s=QC["max_black_s"])
    m["black"] = bl
    for a, b in bl:
        if not _near(a, dips, 0.3):
            issues.append(issue("black_frames", "visual", "major", f"Black frames {a:.2f}-{b:.2f}s.",
                                "Remove the black gap or replace it with footage.", a))
    fr = freezes(path, min_s=QC["max_freeze_s"], duration=dur)
    m["freezes"] = fr
    for a, b in fr:
        sev = "major" if b - a >= 3.0 else "minor"
        issues.append(issue("frozen", "visual", sev, f"Frozen picture {a:.1f}-{b:.1f}s ({b - a:.1f}s).",
                            "Cut away, punch in, or add b-roll/motion on that stretch.", a,
                            evidence={"start": a, "end": b}))

    try:  # measured on the rendered pixels: a plan can look busy while the stage is empty
        empties = empty_band_stretches(path, (render_info or {}).get("seams") or [], width, height, dur)
    except (MediaError, ImportError, ValueError) as exc:
        log.info("empty-band check unavailable: %s", exc)
        empties = []
        m["empty_band_error"] = str(exc)[:200]
    m["empty_band"] = empties
    issues += empty_band_issues(empties)

    cuts = scene_cuts(path, threshold=0.25)
    m["cuts"] = cuts
    changes = sorted(set(cuts) | set((render_info or {}).get("visual_changes") or []))
    m["visual_changes"] = changes
    first_change = next((c for c in changes if c > 0.05), dur)
    if first_change > QC["hook_first_change_s"] and not (render_info or {}).get("hook_overlay"):
        issues.append(issue("slow_open", "hook", "major",
                            f"First visual change at {first_change:.1f}s and no hook text on screen.",
                            "Add a hook title in the first second or punch in on the first key word.", 0.0))
    bounds = [0.0] + [c for c in changes if 0 < c < dur] + [dur]
    longest, at = 0.0, 0.0
    for a, b in zip(bounds, bounds[1:]):
        if b - a > longest:
            longest, at = b - a, a
    m["longest_static_s"] = round(longest, 2)
    if longest > QC["max_static_s"]:
        issues.append(issue("static_stretch", "pacing", "minor" if longest < QC["max_static_s"] * 1.6 else "major",
                            f"{longest:.1f}s without any visual change from {at:.1f}s.",
                            f"Add a punch-in, cut or text beat around {at + longest / 2:.1f}s.", at,
                            evidence={"start": at, "end": at + longest}))
    return issues, m


def caption_lint(words_out: list[dict[str, Any]], captions_enabled: bool, required: bool) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if required and not captions_enabled:
        issues.append(issue("missing", "captions", "blocker", "Captions are required but disabled.",
                            "Enable burned-in captions."))
        return issues
    if not captions_enabled or not words_out:
        return issues
    # reading speed over a sliding 2-second window
    i = 0
    for j, w in enumerate(words_out):
        while words_out[i]["start"] < w["end"] - 2.0:
            i += 1
        chars = sum(len(x["word"]) + 1 for x in words_out[i:j + 1])
        span = max(0.5, w["end"] - words_out[i]["start"])
        if chars / span > QC["caption_max_cps"] * 1.25:
            issues.append(issue("too_fast", "captions", "minor",
                                f"Captions run at {chars / span:.0f} chars/s around {w['start']:.1f}s.",
                                "Use fewer words per caption or slow that section (speed ≤ 1.0).", w["start"]))
            break
    return issues


def compliance_lint(plan: dict[str, Any], brief: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    """Campaign rules the creator set (hashtags, mentions, disclosure, CTA, banned words)."""
    issues: list[dict[str, Any]] = []
    req = (brief or {}).get("requirements") or {}
    post = plan.get("post") or {}
    text = " ".join([post.get("caption") or ""] + list(post.get("hashtags") or [])).lower()
    for tag in req.get("hashtags") or []:
        t = tag.strip().lower()
        if t and (t if t.startswith("#") else "#" + t) not in text and t.lstrip("#") not in text:
            issues.append(issue("hashtag", "compliance", "major", f"Required hashtag {tag} missing from the post.",
                                f"Add {tag} to the post caption/hashtags."))
    for mention in req.get("mentions") or []:
        mt = mention.strip().lower()
        if mt and mt not in text:
            issues.append(issue("mention", "compliance", "major", f"Required mention {mention} missing.",
                                f"Add {mention} to the post caption."))
    overlays = plan.get("overlays") or []
    on_screen = " ".join((o.get("text") or "") for o in overlays).lower()
    disclosure = (req.get("disclosure") or "").strip()
    if disclosure:
        early = [o for o in overlays if float(o.get("start") or 0) <= 3.0]
        if disclosure.lower() not in text and not any(disclosure.lower() in (o.get("text") or "").lower()
                                                         for o in early):
            issues.append(issue("disclosure", "compliance", "blocker",
                                f"Disclosure '{disclosure}' not shown at the start or in the caption.",
                                f"Add a '{disclosure}' label overlay in the first 3s and put it in the caption."))
    cta = (req.get("cta") or "").strip()
    if cta and cta.lower() not in on_screen and cta.lower() not in text:
        issues.append(issue("cta", "compliance", "major", f"Required CTA '{cta}' missing.",
                            f"Add a CTA overlay '{cta}' in the last 3s ({max(0.0, duration - 3):.1f}s→end)."))
    mark = (req.get("watermark") or "").strip()
    if mark and not any(mark.lower() in (o.get("text") or "").lower() and float(o.get("start") or 0) <= 0.5
                        and float(o.get("end") or 0) >= duration - 0.5 for o in overlays):
        issues.append(issue("watermark", "compliance", "blocker",
                            f"'{mark}' must be on screen for the whole clip.",
                            f"Add a label overlay '{mark}' from 0s to the end."))
    other = " ".join(req.get("other") or []).lower()
    if ("facecam" in other or "face cam" in other) and any(
            ((s.get("reframe") or {}).get("mode") not in ("stack", "fit_blur", "fill"))
            for s in plan.get("segments") or []):
        issues.append(issue("facecam", "compliance", "blocker",
                            "The brief requires the streamer's facecam in every clip, but a segment crops it out.",
                            "Use the stack layout (facecam on top) or fit_blur on every segment."))
    banned = [b.strip().lower() for b in req.get("banned") or [] if b.strip()]
    for b in banned:
        if b in on_screen or b in text:
            issues.append(issue("banned", "compliance", "blocker", f"Banned content '{b}' appears in text.",
                                f"Remove '{b}' from overlays and the caption."))
    return issues


# -- layout lint: where the text and the facecam really are --------------------------------------------
def _hit(a: tuple, b: tuple, gap: float = 0.0) -> bool:
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def layout_lint(plan: dict[str, Any], brief: dict[str, Any], *, words: list[dict[str, Any]], width: int, height: int,
                platform: str, fonts_dir: Any = None, src_size: tuple[int, int] | None = None,
                notes: list[str] | None = None, debug: dict[str, Any] | None = None,
                measured_faces: dict[float, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Measure every text layer with the writer's own geometry (captions.plan_captions / plan_overlays) and
    real font metrics, then check frame, safe zone, collisions, the stacked facecam band and upscaling.
    ``words`` are the output-timed words; ``src_size`` the source video size (None → 16:9 assumed, upscale
    check skipped). Checks that cannot run append a line to ``notes``.
    ``measured_faces`` (``measure_cam_faces``) = the face found on the OUTPUT frames of each cam band; it beats the
    plan's reframe.face (a model guess from thumbnails), which stays the fallback when it is None."""
    from ..roles.editor import requires_facecam  # roles import media; keep the dependency lazy

    LY = LAYOUT
    W, H = width, height
    sx, sy = W / 1080, H / 1920
    tol = LY["tolerance_px"] * sx
    notes = notes if notes is not None else []
    segs = plan.get("segments") or []
    if not segs:
        return []
    tl = Timeline(segs)
    D = tl.duration
    src_w, src_h = src_size or (1920, 1080)
    if not src_size:
        notes.append("source size unknown: facecam band assumed for a 1920x1080 source; upscale check skipped")
    font = pick_font(fonts_dir, "")
    meter = Meter(fonts_dir, font)
    est = "" if meter.measured else f" [text widths ESTIMATED: font file '{font}' not found]"
    if not meter.measured:
        notes.append(f"font file '{font}' not found: text widths estimated per character")

    seams = stack_seams(plan, src_size, W, H)  # (out_start, out_end, cam band px, segment) really stacked

    def seam_at(t: float) -> int | None:
        return next((y for a, b, y, _ in seams if a - 0.01 <= t < b), None)

    cap = plan.get("captions") or {}
    doc = AssDoc(W, H)
    caption_styles(doc, font, cap)
    tfont = pick_font(fonts_dir, "Anton")  # titles are set in the bold condensed face, as Renderer.render does
    tmeter = Meter(fonts_dir, tfont)
    overlay_styles(doc, font, tfont)
    req = (brief or {}).get("requirements") or {}
    marks = [m.strip().lower() for m in [req.get("watermark")] + list(req.get("mentions") or []) if m and m.strip()]

    layers: list[dict[str, Any]] = []
    cstyle = doc.styles["Caption"]
    for ev in plan_captions(words, cap, platform, W, H, cstyle.size, D, seam_at if seams else None,
                          box_pad(cstyle)):
        lines = [" ".join(ln) for ln in ev.lines]
        layers.append({"kind": "caption", "text": " ".join(lines), "lines": lines, "a": ev.start, "b": ev.end,
                       "size": cstyle.size, "box": text_box(lines, cstyle.size, ev.x, ev.y, ev.an, box_pad(cstyle), meter)})
    # same rule as Renderer.render (layers = captions so far)
    seam_caps = seam_at if seams and layers and rides_seam(cap) else None
    for ev in plan_overlays(doc, plan.get("overlays") or [], platform, D, seam_caps, cstyle.size, box_pad(cstyle)):
        st = doc.styles[ev.style]
        lines = [" ".join(ln) for ln in ev.lines]
        text = " ".join(lines)
        kind = "watermark" if any(m in text.lower() for m in marks) else ev.kind
        # per-line font px (OvEvent.sizes); the writer's one style size when the event carries none
        sizes = [int(v) for v in (getattr(ev, "sizes", None) or [])][:len(lines)] or [st.size] * len(lines)
        sizes += [sizes[-1]] * (len(lines) - len(sizes))
        box = text_box(lines, sizes, ev.x, ev.y, getattr(ev, "an", 5), box_pad(st),
                       tmeter if ev.style == "Title" else meter)
        # ponytail: the −3° tilt (\frz-3, ±~19 px at the ends of a 740 px line) and the 10 px shadow are not in the
        # box — writer placement ignores them too, so lint and writer agree; add both to text_box if it bites
        layers.append({"kind": kind, "text": text, "lines": lines, "a": ev.start, "b": ev.end, "size": max(sizes),
                       "sizes": sizes, "box": box})

    if debug is not None:  # `agency frames --debug` draws exactly what was measured
        debug.update(layers=layers, seams=[(a, b, band) for a, b, band, _ in seams], faces=[])
    found: dict[str, list[Any]] = {}

    def flag(check: str, sev: str, t: float, desc: str, fix: str, **evidence: Any) -> None:
        if check in found:
            found[check][0] += 1
        else:
            found[check] = [1, sev, t, desc, fix, {"font_metrics": "measured" if meter.measured else "estimated",
                                                   **evidence}]

    def quote(ly: dict[str, Any]) -> str:
        return f"{ly['kind']} '{ly['text'][:40]}' at {ly['a']:.1f}s"

    # (a)+(A5) frame, safe zone, margins
    z = safe_zone(platform, W, H)
    safe = (z["left"], z["top"], W - z["right"], H - z["bottom"])
    m = LY["edge_margin_px"] * sx
    for ly in layers:
        x0, y0, x1, y1 = ly["box"]
        box = [round(v) for v in ly["box"]]
        if x0 < -tol or y0 < -tol or x1 > W + tol or y1 > H + tol:
            flag(f"clipped_{ly['kind']}", "blocker", ly["a"],
                 f"{quote(ly)} runs outside the {W}x{H} frame (box {box}).{est}",
                 "Shorten the text or lower its font size so every glyph stays inside the frame.", box=box)
        elif x0 < safe[0] - tol or y0 < safe[1] - tol or x1 > safe[2] + tol or y1 > safe[3] + tol:
            flag(f"safe_zone_{ly['kind']}", "major", ly["a"],
                 f"{quote(ly)} leaves the {platform} safe zone {list(safe)} (box {box}).{est}",
                 "Move it inside the safe zone (other anchor) or shorten it.", box=box, safe=list(safe))
        elif x0 < m - tol or y0 < m - tol or x1 > W - m + tol or y1 > H - m + tol:
            flag(f"edge_margin_{ly['kind']}", "major", ly["a"],
                 f"{quote(ly)} is closer than {m:.0f}px to the frame edge (box {box}).{est}",
                 "Keep text at least that far from the frame edge.", box=box)

    # (A3) captions: size, cap height, lines, line length
    if any(ly["kind"] == "caption" for ly in layers):
        cap_px = cstyle.size * meter.cap_ratio
        need = max(LY["caption_min_size_px"] * sy / cstyle.size, LY["caption_min_cap_px"] * sy / max(cap_px, 1e-6))
        if need > 1.0 + 1e-6:
            cur = float(cap.get("font_scale") or 1.0)
            flag("caption_small", "major", 0.0,
                 f"Captions are {cstyle.size}px (cap height {cap_px:.0f}px); need ≥ {LY['caption_min_size_px'] * sy:.0f}px "
                 f"and cap height ≥ {LY['caption_min_cap_px'] * sy:.0f}px at this frame size.",
                 f"Set captions.font_scale to ≥ {cur * need:.2f}.", size=cstyle.size, cap_height=round(cap_px, 1))
    for ly in layers:
        if ly["kind"] != "caption":
            continue
        if len(ly["lines"]) > LY["caption_max_lines"]:
            flag("caption_lines", "major", ly["a"], f"Caption '{ly['text'][:40]}' at {ly['a']:.1f}s needs "
                 f"{len(ly['lines'])} lines (max {LY['caption_max_lines']}).",
                 "Use fewer words per caption (captions.words_per_caption).", lines=len(ly["lines"]))
        if any(len(ln) > LY["caption_max_line_chars"] for ln in ly["lines"]):
            flag("caption_chars", "major", ly["a"], f"Caption '{ly['text'][:40]}' at {ly['a']:.1f}s has a line over "
                 f"{LY['caption_max_line_chars']} characters.", "Use fewer words per caption.")

    # (MF-1) hook / punch title: far bigger than the captions, and not one size on every line
    for ly in layers:
        if ly["kind"] not in ("hook_title", "punch_title"):
            continue
        sizes = ly.get("sizes") or [ly["size"]]
        big = max(sizes)
        if big < LY["hook_title_max_word_px"] * sy - tol:
            flag(f"{ly['kind']}_small", "major", ly["a"], f"{quote(ly)} is only {big}px (biggest line); a hook/punch "
                 f"title needs ≥ {LY['hook_title_max_word_px'] * sy:.0f}px or it reads as a caption.",
                 f"Give the key word of the title a font of ≥ {LY['hook_title_max_word_px'] * sy:.0f}px.", sizes=sizes)
        if len(sizes) > 1 and big / max(min(sizes), 1) < LY["hook_title_ratio_min"] - 1e-6:
            flag(f"{ly['kind']}_one_size", "major", ly["a"], f"{quote(ly)} runs {len(sizes)} lines at nearly one size "
                 f"({min(sizes)}-{big}px); the biggest line must be ≥ {LY['hook_title_ratio_min']:.0f}x the smallest.",
                 "Size the lines in steps: the key word huge, the rest at half its size or less.", sizes=sizes)

    # (A4) hook title
    for ly in layers:
        if ly["kind"] != "hook_title":
            continue
        n = len(ly["text"].split())
        if n > LY["hook_max_words"]:
            flag("hook_long", "minor", ly["a"], f"Hook title has {n} words (max {LY['hook_max_words']}).",
                 f"Cut the hook title to {LY['hook_max_words']} words.")
        if ly["a"] > LY["hook_latest_start_s"] + 1e-6:
            flag("hook_late", "major", ly["a"], f"Hook title starts at {ly['a']:.2f}s; it must be on screen from the first frame.",
                 "Start the hook title at 0.0s.")
        if ly["b"] - ly["a"] < LY["hook_min_s"] - 1e-6 and ly["b"] < D - 0.05:
            flag("hook_short", "major", ly["a"], f"Hook title is on screen {ly['b'] - ly['a']:.1f}s (min {LY['hook_min_s']}s).",
                 f"Hold the hook title for ≥ {LY['hook_min_s']}s.")

    # (b)+(A5) collisions between layers visible at the same time
    gap = LY["text_gap_px"] * sx
    for i, p in enumerate(layers):
        for q in layers[i + 1:]:
            if p["kind"] == q["kind"] == "caption" or min(p["b"], q["b"]) - max(p["a"], q["a"]) <= 0.1:
                continue
            kinds = "_".join(sorted((p["kind"], q["kind"])))
            t = max(p["a"], q["a"])
            if _hit(p["box"], q["box"]):
                flag(f"overlap_{kinds}", "major", t, f"{quote(p)} and {quote(q)} overlap on screen.{est}",
                     "Give one of them another anchor/position so the boxes do not touch.",
                     boxes=[[round(v) for v in p["box"]], [round(v) for v in q["box"]]])
            elif _hit(p["box"], q["box"], gap):
                flag(f"gap_{kinds}", "minor", t, f"{quote(p)} and {quote(q)} are closer than {gap:.0f}px.{est}",
                     "Move one of them to leave a clear gap.")

    # (c)+(A1)(A2)(A4)(A8) stacked layout
    noted_face = False
    cam_n = sum(v["n"] for v in (measured_faces or {}).values())
    cam_hits = sum(v["hits"] for v in (measured_faces or {}).values())
    if (measured_faces and seams and cam_n and requires_facecam(brief)
            and cam_hits / cam_n < LY["face_found_min_share"] - 1e-6):
        flag("face_not_found", "major", seams[0][0], f"No face found in the cam band of {cam_n - cam_hits} of {cam_n} "
             f"sampled output frames (the brief requires the facecam).",
             "Re-crop the facecam so the streamer's face is inside it, or the stream is not showing the streamer.",
             hits=cam_hits, frames=cam_n)
    for a, b, band, seg in seams:
        share = band / H
        if share < LY["cam_band_min_share"] - 1e-6:
            flag("cam_small", "major", a, f"Facecam band is {share:.0%} of the frame height (min {LY['cam_band_min_share']:.0%}).",
                 "Crop the facecam tighter or give it a larger band.", band_px=band)
        elif share < LY["cam_band_warn_share"] - 1e-6:
            flag("cam_small_warn", "minor", a, f"Facecam band is {share:.0%} of the frame height "
                 f"(aim for ≥ {LY['cam_band_warn_share']:.0%}).", "Crop the facecam tighter or give it a larger band.",
                 band_px=band)
        face = (seg.get("reframe") or {}).get("face")
        fr = None
        try:
            fr = tuple(float(face[k]) for k in ("x", "y", "w", "h")) if face else None
        except (KeyError, TypeError, ValueError):
            fr = None
        meas = (measured_faces or {}).get(round(a, 2))
        if meas and meas["box"] and meas["n"] and meas["hits"] / meas["n"] >= LY["face_found_min_share"] - 1e-6:
            bx, by, bw, bh = meas["box"]
            if fr and _iou((fr[0] * W, fr[1] * band, fr[2] * W, fr[3] * band), meas["box"]) < LY["face_iou_min"]:
                # minor: the renderer never reads reframe.face — the measured box below already drives every check,
                # so a stale plan field must not cost the editor a round
                flag("plan_face_mismatch", "minor", a, "The plan's face box disagrees with the frame: the face found on "
                     f"the output is at x {bx}-{bx + bw}, y {by}-{by + bh}px, the plan put it at x "
                     f"{fr[0] * W:.0f}-{(fr[0] + fr[2]) * W:.0f}, y {fr[1] * band:.0f}-{(fr[1] + fr[3]) * band:.0f}px.",
                     "Re-locate the face on a full-size frame (reframe.face / reframe.cam) before judging the crop.",
                     plan_box=[round(v) for v in (fr[0] * W, fr[1] * band, fr[2] * W, fr[3] * band)],
                     measured_box=list(meas["box"]))
            fr = (bx / W, by / band, bw / W, bh / band)  # the measured face drives every check below
        if fr:
            cx, cy = fr[0] + fr[2] / 2, fr[1] + fr[3] / 2
            em = LY["face_edge_margin"]
            eye = (fr[1] + 0.4 * fr[3]) * band  # eye line ≈ 40% down the face box
            cam_up = None
            if src_size and _valid_cam((seg.get("reframe") or {}).get("cam")):
                c = seg["reframe"]["cam"]
                cam_up = max(W / max(float(c["w"]) * src_w, 1), band / max(float(c["h"]) * src_h, 1))
            # minor, and silent once the crop is at the magnification limit: Haar boxes the same face at 64-268 px,
            # and zooming further in would trade it for a cam_upscale major — an unfixable loop
            if fr[3] < LY["face_min_band_share"] and not (cam_up and cam_up >= LY["cam_max_upscale"] * 0.97):
                flag("face_small", "minor", a, f"The face fills {fr[3]:.0%} of the facecam band height "
                     f"(min {LY['face_min_band_share']:.0%}).", "Zoom the facecam crop in on the face.")
            if not (em <= cx <= 1 - em and em <= cy <= 1 - em):
                flag("face_off_centre", "major", a, "The face centre sits too close to the facecam band edge.",
                     "Re-centre the facecam crop on the face.")
            if eye < LY["eye_line_min_px"] * sy:
                # minor: with the cam in the top band and ≤ 2.5× magnification, a cam in the source's top corner
                # can never put the eyes lower — flagging it major would just loop the editor to escalation
                flag("eye_line_high", "minor", a, f"Eye line at {eye:.0f}px; TikTok's top UI covers the first "
                     f"{LY['eye_line_min_px'] * sy:.0f}px.", "If the cam crop has headroom above the face, include "
                     "more of it; otherwise accept (stack layout limit).")
        elif not noted_face:
            noted_face = True
            notes.append("face-size/eye-line checks skipped: the plan carries no face box (reframe.face); "
                         "text-vs-face uses a fallback face area")
        raw = (fr[0] * W, fr[1] * band, (fr[0] + fr[2]) * W, (fr[1] + fr[3]) * band) if fr else (
            LY["face_area"][0] * W, LY["face_area"][1] * band, LY["face_area"][2] * W, LY["face_area"][3] * band)
        area = (raw[0], raw[1], raw[2], min(band, raw[3]))  # nothing of the face exists below the seam
        # a head box runs past the chin; the seam caption only has to clear the face itself (top 85% of the box)
        core = (raw[0], raw[1], raw[2], min(band, raw[1] + 0.85 * (raw[3] - raw[1])))
        if debug is not None:
            debug["faces"].append((a, b, area, bool(fr)))
        for ly in layers:
            if min(ly["b"], b) - max(ly["a"], a) <= 0.05:
                continue
            titled = ly["kind"] in ("hook_title", "punch_title")
            if titled and _hit(ly["box"], (0, 0, W, band)):
                flag(f"{ly['kind']}_in_cam_band" if ly["kind"] == "punch_title" else "hook_in_cam_band", "major",
                     ly["a"], f"{quote(ly)} sits inside the facecam band (0-{band}px); in a stacked layout the top "
                     f"title always hits the face or the platform UI.{est}",
                     "Place the title on the gameplay half (position 'center' or lower).")
            elif not titled and _hit(ly["box"], core if ly["kind"] == "caption" else area):
                flag(f"over_face_{ly['kind']}", "major", ly["a"], f"{quote(ly)} covers the face area of the facecam "
                     f"band (box {[round(v) for v in ly['box']]}).{est}",
                     "If it is the seam caption, the face sits low in the cam band: extend reframe.cam downward "
                     "(more chest below the chin) so the face rises above the seam; otherwise fewer words or "
                     "another anchor.")
        if src_size:
            cam = seg["reframe"]["cam"]
            cw, ch = float(cam["w"]) * src_w, float(cam["h"]) * src_h
            up = max(W / max(cw, 1), band / max(ch, 1))
            if up > LY["cam_max_upscale"]:
                # a little over the limit is a trade the creative review may make (a tight crop keeps chat and
                # overlay text out); far over it the face goes visibly soft
                sev_up = "major" if up > LY["cam_max_upscale_major"] else "minor"
                flag("cam_upscale", sev_up, a, f"The facecam is magnified {up:.1f}x from the source "
                     f"(max {LY['cam_max_upscale']}x): it will look soft.", "Use a larger facecam crop or a higher-resolution source.",
                     scale=round(up, 2))
            zoom = seg.get("zoom") or {}
            gz = ((H - band) / src_h) * (float(zoom.get("scale") or 1.0) if zoom.get("type") not in (None, "none") else 1.0)
            if gz > LY["game_max_upscale"]:
                flag("game_upscale", "major", a, f"The gameplay band is magnified {gz:.1f}x from the source "
                     f"(max {LY['game_max_upscale']}x).", "Drop the punch-in on stacked segments or use a higher-resolution source.",
                     scale=round(gz, 2))

    # (A7) watermark / mention overlays
    for ly in layers:
        if ly["kind"] != "watermark":
            continue
        cap_h = ly["size"] * meter.cap_ratio
        if ly["size"] < LY["watermark_min_px"] * sy - tol or cap_h < LY["watermark_min_cap_px"] * sy - tol:
            flag("watermark_small", "major", ly["a"], f"{quote(ly)} is {ly['size']}px (cap height {cap_h:.0f}px); the "
                 f"watermark needs ≥ {LY['watermark_min_px'] * sy:.0f}px and cap height ≥ "
                 f"{LY['watermark_min_cap_px'] * sy:.0f}px.", f"Raise the label's font size to ≥ {LY['watermark_min_px']}px "
                 f"(at {W}x{H}).", size=ly["size"], cap_height=round(cap_h, 1))
        zh = safe[3] - safe[1]
        mid = (ly["box"][1] + ly["box"][3]) / 2
        if not (mid >= safe[3] - LY["watermark_bottom_share"] * zh or mid <= safe[1] + LY["watermark_top_share"] * zh):
            flag("watermark_misplaced", "minor", ly["a"], f"{quote(ly)} sits mid-frame (y {mid:.0f}px) over the action; "
                 f"keep it in the bottom {LY['watermark_bottom_share']:.0%} of the safe zone or the top strip.",
                 "Anchor the watermark 'bottom' (or 'top').", y=round(mid))
        if ly["box"][2] > LY["watermark_max_x_px"] * sx + tol and ly["box"][3] > LY["watermark_column_y_px"] * sy:
            flag("watermark_column", "major", ly["a"], f"{quote(ly)} reaches into the platform's right button column "
                 f"(x > {LY['watermark_max_x_px'] * sx:.0f}).{est}", "Shorten the watermark or move it left.")

    # (d) facecam must stay visible
    if requires_facecam(brief) and src_w / max(src_h, 1) > W / H + 0.02:
        bad = [p for p in tl.placed if (segs[p.index].get("reframe") or {}).get("mode") not in ("stack", "fit_blur")]
        if bad:
            flag("facecam_hidden", "blocker", bad[0].out_start,
                 f"The brief requires the facecam, but {len(bad)} of {len(segs)} segment(s) crop it out "
                 f"(first at {bad[0].out_start:.1f}s).", "Use the stack layout (facecam on top) or fit_blur on every segment.")

    out = []
    for check, (n, sev, t, desc, fix, ev) in found.items():
        out.append(issue(check, "layout", sev, desc + (f" (+{n - 1} more)" if n > 1 else ""), fix, t, ev))
    return out
