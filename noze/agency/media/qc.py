"""Technical QC + plan lint: the reviewer's checklist that never needs an LLM.

Every check yields issues with a stable ``id`` (``category:check``) so the same
problem can be tracked across revision rounds and counted by the learning loop.
"""

from __future__ import annotations

from typing import Any

from ..standards import DELIVERY, QC, PLATFORM_LIMITS
from .analyze import blacks, freezes, loudness, scene_cuts, silences
from .ffmpeg import probe


def issue(check: str, category: str, severity: str, description: str, fix: str,
          timecode: float | None = None, evidence: Any = None) -> dict[str, Any]:
    return {"id": f"{category}:{check}", "category": category, "severity": severity,
            "timecode_s": None if timecode is None else round(float(timecode), 2),
            "description": description, "fix": fix, "source": "qc", "evidence": evidence}


def _near(t: float, points: list[float], tol: float) -> bool:
    return any(abs(t - p) <= tol for p in points)


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
    banned = [b.strip().lower() for b in req.get("banned") or [] if b.strip()]
    for b in banned:
        if b in on_screen or b in text:
            issues.append(issue("banned", "compliance", "blocker", f"Banned content '{b}' appears in text.",
                                f"Remove '{b}' from overlays and the caption."))
    return issues
