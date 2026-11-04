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
    # empty stage: measured on the RENDERED file (media/qc.empty_band_stretches). Numbers are estimates [D]
    "empty_band_sample_fps": 2.0,  # [D] frames sampled per second (>= 2)
    "empty_band_luma_delta": 24,  # [D] a pixel "differs" when its luma is > 24 levels from the band's median luma
    "empty_band_min_share": 0.08,  # [D] < 8% of the band's pixels differing from the median = nothing is happening
    "empty_band_motion_share": 0.01,  # [D] ... or < 1% of the band's pixels changed since the previous sample (a still stage)
    "empty_band_motion_window": 5,  # [D] samples the motion share is median-filtered over (a lone blip does not break a still stretch)
    "empty_band_max_s": 2.0,  # [D] an empty stretch longer than this is a major
}


# Layout lint thresholds (media/qc.layout_lint). Pixel values are for a 1080x1920 frame and scale with the
# real frame. Tags: [S] secondary source, [D] design-supervisor estimate — re-measure against real clips.
LAYOUT = {
    "cam_band_min_share": 0.30,  # [S] stack layout: facecam band >= 30% of frame height (OpusClip gaming layout 30/70)
    "cam_band_warn_share": 0.33,  # [S] below this (but >= min) is a minor warning
    "face_min_band_share": 0.35,  # [D] face box height >= 35% of the cam band height
    "face_edge_margin": 0.08,  # [D] face centre keeps >= 8% of the band away from each band edge
    "eye_line_min_px": 300,  # [D] eye line >= 300px from the top (TikTok top UI)
    "face_area": (0.15, 0.10, 0.85, 0.70),  # [D] fallback face area (x0, y0, x1, y1 as band fractions) when no face box
    "caption_min_size_px": 64,  # [D] caption font size (Netflix 42px cap is the ceiling, not the floor)
    "caption_min_cap_px": 44,  # [D] caption cap-height
    "caption_max_lines": 2,  # [D]
    "caption_max_line_chars": 22,  # [D]
    "hook_max_words": 7,  # [D]
    "hook_latest_start_s": 0.05,  # [D] hook title is on screen from the first frame
    "hook_min_s": 1.5,  # [D]
    "text_gap_px": 24,  # [D] visible text layers keep >= 24px between boxes (and never intersect)
    "edge_margin_px": 24,  # [D] box-to-frame-edge margin even where a safe zone is smaller
    "hook_title_max_word_px": 110,  # [D] hook / punch title: the biggest line is >= 110px (a ~35px cap read as a caption)
    "hook_title_ratio_min": 2.0,  # [D] ... and with several lines the biggest font is >= 2x the smallest (one size = a wall of text)
    "watermark_min_px": 64,  # [D] watermark / mention font size
    "watermark_min_cap_px": 36,  # [D] watermark cap height
    "watermark_bottom_share": 0.25,  # [D] the watermark sits in the bottom 25% of the safe zone ...
    "watermark_top_share": 0.12,  # [D] ... or in the top 12% strip of it; never mid-gameplay (minor)
    "face_iou_min": 0.3,  # [D] plan face box vs the face measured on the output frame: IoU below = the plan guessed wrong
    "face_found_min_share": 0.5,  # [D] brief needs the facecam: the face is found in >= 50% of the sampled cam-band frames
    "watermark_max_x_px": 900,  # [D] TikTok right button column starts at x=900 (for y > 840)
    "watermark_column_y_px": 840,  # [D]
    "cam_max_upscale": 2.5,  # [D] facecam pixels magnified at most 2.5x from the source (above = minor)
    "cam_max_upscale_major": 3.2,  # [D] live run 3 Nov: a tight crop at ~2.6-3x read fine; far beyond goes soft
    "game_max_upscale": 1.5,  # [D] gameplay band magnified at most 1.5x (zoom included)
    "tolerance_px": 2,  # rounding slack on every box test
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
        f"Layout (measured by QC on every render, scaled from 1080x1920): every glyph inside the frame and the safe "
        f"zone, ≥ {LAYOUT['edge_margin_px']}px from the edge; texts on screen together never overlap and keep "
        f"≥ {LAYOUT['text_gap_px']}px apart; captions ≥ {LAYOUT['caption_min_size_px']}px (cap height "
        f"≥ {LAYOUT['caption_min_cap_px']}px), ≤ {LAYOUT['caption_max_lines']} lines of ≤ "
        f"{LAYOUT['caption_max_line_chars']} characters; hook title from 0s for ≥ {LAYOUT['hook_min_s']}s, "
        f"≤ {LAYOUT['hook_max_words']} words, its biggest line ≥ {LAYOUT['hook_title_max_word_px']}px and, with "
        f"several lines, ≥ {LAYOUT['hook_title_ratio_min']:.0f}x the smallest (hook and punch titles are bigger "
        f"than the captions, never one size); watermark ≥ {LAYOUT['watermark_min_px']}px (cap height ≥ "
        f"{LAYOUT['watermark_min_cap_px']}px), in the bottom {LAYOUT['watermark_bottom_share']:.0%} of the safe zone "
        f"or the top strip (not mid-gameplay), clear of the right button column "
        f"(x > {LAYOUT['watermark_max_x_px']} below y {LAYOUT['watermark_column_y_px']}).\n"
        f"Empty stage: QC samples the rendered gameplay band at {QC['empty_band_sample_fps']:.0f} fps; "
        f"< {QC['empty_band_min_share']:.0%} of its pixels differing > {QC['empty_band_luma_delta']} luma levels "
        f"from the band median, or < {QC['empty_band_motion_share']:.0%} of them changing between samples, "
        f"for > {QC['empty_band_max_s']}s is an empty stage (major): cut it or move on to action.\n"
        f"Facecam: QC detects the face on the OUTPUT frames of the cam band (not the plan's guess); it must be "
        f"found in ≥ {LAYOUT['face_found_min_share']:.0%} of them and the plan's face box must overlap it "
        f"(IoU ≥ {LAYOUT['face_iou_min']}).\n"
        f"Stack layout: facecam band ≥ {LAYOUT['cam_band_min_share']:.0%} of the height (aim "
        f"{LAYOUT['cam_band_warn_share']:.0%}+), face ≥ {LAYOUT['face_min_band_share']:.0%} of the band and centred, "
        f"no hook title in the cam band, no text over the face; magnify the cam ≤ {LAYOUT['cam_max_upscale']}x "
        f"(never beyond {LAYOUT['cam_max_upscale_major']}x) and the gameplay ≤ {LAYOUT['game_max_upscale']}x of "
        f"source pixels; crop the cam to the webcam only (no chat, alerts or overlay text). captions.position "
        f"'upper' rides the cam/gameplay seam; 'center'/'lower' put captions on the gameplay band.\n"
        f"Creative review pass mark: {QC['min_review_score']}/10 with no blocker or major issue."
    )
