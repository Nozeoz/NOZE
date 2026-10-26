"""House standards: platform delivery specs, safe zones and QC thresholds.

This is the agency's "constitution" — code, not learned. Playbooks may add
taste on top, but nothing the team learns can loosen these numbers; the QC
gate enforces them on every render.
"""

from __future__ import annotations

from typing import Any

# Pixels to keep free of text on a 1080×1920 frame (scaled for other sizes).
# Platform UI (captions, buttons, progress bar, account name) sits in these bands.
# Compiled from the platforms' ad-template safe zones (TikTok's right-hand button
# column is ~180px wide from y≈840). "other" is the box that is safe on all three.
SAFE_ZONES: dict[str, dict[str, int]] = {
    "tiktok": {"top": 240, "bottom": 660, "left": 120, "right": 180},
    "reels": {"top": 269, "bottom": 672, "left": 65, "right": 120},
    "shorts": {"top": 288, "bottom": 672, "left": 48, "right": 192},
    "x": {"top": 120, "bottom": 300, "left": 64, "right": 64},
    "facebook": {"top": 269, "bottom": 672, "left": 65, "right": 120},
    "other": {"top": 288, "bottom": 672, "left": 120, "right": 192},
}

PLATFORM_LIMITS: dict[str, dict[str, Any]] = {
    "tiktok": {"max_s": 600, "sweet_spot_s": (21, 60)},
    "reels": {"max_s": 180, "sweet_spot_s": (15, 60)},
    "shorts": {"max_s": 180, "sweet_spot_s": (20, 58)},  # Content ID'd music blocks Shorts > 60 s
    "x": {"max_s": 140, "sweet_spot_s": (15, 45)},
    "facebook": {"max_s": 180, "sweet_spot_s": (15, 60)},
    "other": {"max_s": 180, "sweet_spot_s": (15, 60)},
}

# Delivery spec every render must meet.
DELIVERY = {
    "vcodec": "h264",
    "pix_fmt": "yuv420p",
    "acodec": "aac",
    "sample_rate": 48000,
    "true_peak_max": -1.0,  # dBTP (we encode at -1.5 to leave AAC headroom)
    "lufs_tolerance": 1.0,  # LU around the target
    "max_file_mb": 280,
}

# QC thresholds (seconds unless noted). Sources: Netflix timed-text (20 cps),
# auto-editor defaults, platform hook guidance, practitioner pacing heuristics.
QC = {
    "max_dead_air_s": 0.8,  # silence inside the clip
    "hook_first_sound_s": 0.6,  # someone/something audible by then
    "hook_first_change_s": 1.6,  # first visual change (cut/zoom/text) by then
    "max_static_s": 5.0,  # longest stretch with no cut/zoom/overlay change
    "max_black_s": 0.1,  # outside intended flashes/dips
    "max_freeze_s": 1.5,
    "caption_max_cps": 20.0,  # characters per second a viewer can read
    "caption_min_s": 0.3,
    "min_review_score": 7.0,  # creative review overall score (0-10) to pass
}


def safe_zone(platform: str, width: int = 1080, height: int = 1920) -> dict[str, int]:
    base = SAFE_ZONES.get(platform) or SAFE_ZONES["other"]
    sx, sy = width / 1080, height / 1920
    return {"top": int(base["top"] * sy), "bottom": int(base["bottom"] * sy),
            "left": int(base["left"] * sx), "right": int(base["right"] * sx)}


def standards_text(platform: str, target_lufs: float, width: int, height: int, fps: int) -> str:
    """The house standards as prompt text (generated from the constants, so they never drift)."""
    z = safe_zone(platform, width, height)
    lim = PLATFORM_LIMITS.get(platform) or PLATFORM_LIMITS["other"]
    return (
        f"Delivery: {width}x{height} @ {fps}fps, H.264 yuv420p, AAC 48 kHz; loudness {target_lufs:.0f} LUFS "
        f"±{DELIVERY['lufs_tolerance']:.0f}, true peak ≤ {DELIVERY['true_peak_max']} dBTP.\n"
        f"Safe zone ({platform}): keep text out of the top {z['top']}px, bottom {z['bottom']}px, "
        f"left {z['left']}px and right {z['right']}px.\n"
        f"Length: sweet spot {lim['sweet_spot_s'][0]}-{lim['sweet_spot_s'][1]}s (platform max {lim['max_s']}s) "
        f"unless the brief says otherwise.\n"
        f"Hook: audible within {QC['hook_first_sound_s']}s, first visual change within {QC['hook_first_change_s']}s; "
        f"no dead air over {QC['max_dead_air_s']}s; never hold an unchanged frame over {QC['max_static_s']}s.\n"
        f"Captions: ≤ {QC['caption_max_cps']:.0f} characters/second, each on screen ≥ {QC['caption_min_s']}s.\n"
        f"Creative review pass mark: {QC['min_review_score']}/10 with no blocker or major issue."
    )
