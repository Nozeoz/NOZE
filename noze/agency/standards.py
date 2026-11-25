"""House standards: platform delivery specs, safe zones and QC thresholds.

This is the agency's "constitution" — code, not learned. Playbooks may add
taste on top, but nothing the team learns can loosen these numbers; the QC
gate enforces them on every render.
"""

from __future__ import annotations

import re
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
    # frame 0 of the OUTPUT (t ~0.1 s) on the gameplay band (stack) or the whole frame: a near-black opener scrolls
    # past (mandor MF-5, twice). [D]: calibrate against clips that passed review before trusting the numbers
    "frame0_t_s": 0.1,
    "frame0_min_luma": 40,  # [D] mean luma (0-255) of the opener band
    "frame0_min_std": 25,  # [D] luma spread: a flat grey/black frame has no picture to stop the scroll
}

# Content rules every clip obeys (editor prompt + reviewer). Not measurable by a script: the reviewer flags a frame.
HOUSE_RULES = (
    "No sexual or nudity scenes, even in-game (FYP reach; clips are paid per view): never pick a range or a "
    "band_src that shows one; when the moment contains it, cut to the reaction or another stretch of the moment.",
)


# Layout lint thresholds (media/qc.layout_lint). Pixel values are for a 1080x1920 frame and scale with the
# real frame. Tags: [S] secondary source, [D] design-supervisor estimate — re-measure against real clips.
LAYOUT = {
    "cam_band_min_share": 0.30,  # [S] stack layout: facecam band >= 30% of frame height (OpusClip gaming layout 30/70)
    "cam_band_warn_share": 0.33,  # [S] below this (but >= min) is a minor warning
    "face_min_band_share": 0.35,  # [D] face box height >= 35% of the cam band height
    "face_edge_margin": 0.08,  # [D] face centre keeps >= 8% of the band away from each band edge
    "eye_line_min_px": 300,  # [D] eye line >= 300px from the top (TikTok top UI)
    "face_area": (0.15, 0.10, 0.85, 0.70),  # [D] fallback face area (x0, y0, x1, y1 as band fractions) when no face box
    "caption_min_size_px": 75,  # [D] caption font size (mandor MF-2, 23 Nov: 64 read small on a phone)
    "caption_min_cap_px": 55,  # [D] caption cap-height (mandor CP1 23 Nov: glyphs ~68px TOTAL read small; 44 was too low)
    "caption_max_lines": 2,  # [D]
    "caption_max_line_chars": 22,  # [D]
    "hook_max_words": 7,  # [D]
    "hook_latest_start_s": 0.05,  # [D] hook title is on screen from the first frame
    "hook_min_s": 1.5,  # [D]
    "text_gap_px": 24,  # [D] visible text layers keep >= 24px between boxes (and never intersect)
    "edge_margin_px": 24,  # [D] box-to-frame-edge margin even where a safe zone is smaller
    "hook_title_max_word_px": 110,  # [D] hook / punch title: the biggest line is >= 110px (a ~35px cap read as a caption)
    "hook_setup_min_px": 55,  # [D] MF-3: the small "setup" line of a mixed-scale title is >= 55px (font size, legacy floor)
    "hook_setup_min_cap_px": 55,  # [D] MF-3 (2nd time, CP1): the setup line's CAP-HEIGHT is >= 55px (cap, not font size)
    "hook_emphasis_min_px": 200,  # [D] CP1: the emphasis word of a hook/punch title is >= 200px condensed (Anton)
    "eye_line_band_share": (0.28, 0.32),  # [D] MF-4/C14 talking-head crop: eyes at 28-32% of the frame height (editor target; needs a face box to measure)
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
    # mandor CP2 (24 Nov, clipper-r1): the facecam crop leaked foreign pixels (a leaf strip on top, a wall on the right,
    # a white box on the edge) and the title sat on the game character's face. [D]: calibrated on the CP2 render
    # (leak: median step 42-131 at the boundary; clean crops of the same frames and natural edges: <= 26)
    "cam_edge_major_frac": 0.02,  # [D] foreign edge strip deeper than 2% of the frame width = major, else minor
    "cam_inset": 0.02,  # [D] a DETECTOR cam crop is inset this share of its size on every side (a human/model crop is respected)
    "cam_edge_search": 0.15,  # [D] framing:cam_edge_foreign looks for a hard boundary within the outer 15% of the cam band ...
    "cam_edge_step": 35,  # [D] ... where the median per-line colour step (RGB distance) across it is >= 35 ...
    "cam_edge_color": 40,  # [D] ... and the outer strip's median colour is >= 40 from the band's inner median
    "cam_edge_samples": 3,  # [D] frames sampled per stacked segment; an edge must show in a majority
    "title_face_overlap_min": 0.25,  # [D] layout:title_over_subject: the title box covers >= 25% of a face in the gameplay band
    "title_subject_top_share": 0.4,  # [D] editor: a gameplay subject centred in the top 40% of the band pushes the title to the bottom
}


# Story / emotion QC (media/qc.story_lint). All [D] = mandor checklist C1-C19 estimates, re-measure on real clips.
STORY_QC = {
    "frame0_window_s": 0.3,  # [D] C1: a hook/title is on screen by 0.3 s and frame 0 is real footage (not black / a transition)
    "sfx_min_gap_s": 1.5,  # [D] C9: at most 1 SFX per 1.5 s on average
    "max_flash_per_s": 3,  # [D] C9: > 3 flashes inside any 1 s window = photosensitivity blocker
    "effect_repeat_max": 2,  # [D] C9: the same effect / transition 3 times in a row = minor
    "hold_max_s": 1.2,  # [D] longest freeze-frame reaction hold
    "teaser_s": (1.0, 2.5),  # [D] C1: cold-open teaser length
    "card_s": 1.4,  # [D] time card on screen
    "phrase_gap_s": 0.25,  # [D] CP1: words closer than this inside one sentence are ONE phrase: a freeze never splits it
    # reference research 24 Nov 2026 (docs/REFERENSI-CLIPPER-2026-11.md): the moment decides, the edit only serves it
    "peak_teaser_s": (0.8, 1.5),  # [D] linear clip with its peak late: frame 0 = a 0.8-1.5 s teaser of that peak
    "peak_early_s": 3.0,  # [D] a peak this close to the clip's start needs no teaser (it already opens on it)
    "gameplay_min_gap_s": 0.9,  # [D] stack/gameplay: only pauses longer than this are cut (a game's action keeps running)
    "gameplay_max_cuts_30s": 4,  # [D] target cuts per 30 s on stack/gameplay (time jumps excluded)
    "over_cut_per_30s": 8,  # [D] pacing:over_cut (minor) above this many cuts per 30 s without a time jump
    "loop_hold_s": 0.6,  # [D] loop: a cold-open / funny / shock / sad clip ends on a held reaction
    "long_for_stream_s": 35.0,  # [D] pacing:long_for_stream (minor): a linear clip longer than this
    "title_max_chars": 45,  # [D] hook:title_long (minor): hook_title text longer than this ...
    "title_max_lines": 2,  # [D] ... or with more lines than this
    "repeat_line_window_s": 8.0,  # [D] pacing:repeat_line (minor): the ending = the last 8 s of output ...
    "repeat_line_min": 3,  # [D] ... the same line (>= 2 words) / the same long word said this many times
}

# Sweet spot of a linear streamer-reaction clip, seconds [D]: Shorts median views/day 11.1k (<=30 s) vs 5.6k (>30 s).
STREAM_SWEET_SPOT_S = (20, 30)
# Emotions whose clip should loop (the last beat = the reaction on frame 0) besides every cold_open.
LOOP_EMOTIONS = ("funny", "shock", "sad")

_DENSITY = {"none": 0, "low": 1, "medium": 2, "high": 3}

# The emotion -> effect palette constitution. Every number is a [D] estimate (mandor C8, 23 Nov 2026).
#   zoom       the default move on a beat (punch = fast scale-in, push = slow creep)
#   shake      is shake allowed at all (only ever on the payoff impact)
#   transitions / no_transitions   preferred (in order) / forbidden; rewind + time_card are story tools, always allowed
#   sfx / no_sfx / sfx_density     preferred palette, forbidden kinds, density cap
#   hold_s     reaction freeze on the payoff (0 = none), hold_style its treatment
#   drop       music cuts out just before the payoff (music.drop_at)
VIBES: dict[str, dict[str, Any]] = {
    "hype": {"color": "punchy", "zoom": {"type": "punch", "scale": 1.15}, "shake": True,
             "transitions": ["flash", "whip", "glitch", "zoom"], "no_transitions": ["fade"],
             "sfx": ["boom", "hit", "bass_drop", "whoosh"], "no_sfx": ["heartbeat"], "sfx_density": "high",
             "highlight": "#FFE600", "music": "hype energetic bass", "music_gain_db": -18.0,
             "hold_s": 0.0, "hold_style": "zoom", "title": "pop", "drop": False,
             "fx": {"vignette": False, "grain": False, "letterbox": False}, "no_fx": ["letterbox"]},
    "funny": {"color": "punchy", "zoom": {"type": "punch", "scale": 1.12}, "shake": False,
              "transitions": ["zoom", "whip"], "no_transitions": ["glitch", "fade"],
              "sfx": ["pop", "ding", "shutter", "click"], "no_sfx": ["riser", "boom", "heartbeat", "sting", "bass_drop"],
              "sfx_density": "medium", "highlight": "#FFD60A", "music": "playful comedic upbeat", "music_gain_db": -20.0,
              "hold_s": 0.75, "hold_style": "zoom", "title": "stamp", "drop": False,
              "fx": {"vignette": False, "grain": False, "letterbox": False}, "no_fx": ["letterbox"]},
    "shock": {"color": "cinematic", "zoom": {"type": "push", "scale": 1.08}, "shake": False,
              "transitions": ["zoom", "fade"], "no_transitions": ["flash", "glitch", "whip"],
              "sfx": ["heartbeat", "riser", "sting", "hit"], "no_sfx": ["pop", "ding", "glitch", "bass_drop"],
              "sfx_density": "low", "highlight": "#FF453A", "music": "dark tense cinematic drone", "music_gain_db": -21.0,
              "hold_s": 0.0, "hold_style": "bw", "title": "fade", "drop": True,
              "fx": {"vignette": True, "grain": False, "letterbox": True}, "no_fx": []},
    "tense": {"color": "night", "zoom": {"type": "push", "scale": 1.08}, "shake": False,
              "transitions": ["fade", "zoom"], "no_transitions": ["flash", "glitch", "whip"],
              "sfx": ["heartbeat", "riser", "sting", "tape_stop"], "no_sfx": ["pop", "ding", "glitch", "bass_drop"],
              "sfx_density": "low", "highlight": "#FF453A", "music": "dark suspense tension", "music_gain_db": -21.0,
              "hold_s": 0.0, "hold_style": "bw", "title": "fade", "drop": True,
              "fx": {"vignette": True, "grain": True, "letterbox": True}, "no_fx": []},
    "wholesome": {"color": "warm", "zoom": {"type": "push", "scale": 1.06}, "shake": False,
                  "transitions": ["fade", "zoom"], "no_transitions": ["flash", "glitch", "whip"],
                  "sfx": ["ding", "swoosh"], "no_sfx": ["boom", "hit", "bass_drop", "glitch", "sting", "riser", "heartbeat"],
                  "sfx_density": "low", "highlight": "#FFC9A3", "music": "soft warm acoustic piano", "music_gain_db": -19.0,
                  "hold_s": 0.8, "hold_style": "polaroid", "title": "fade", "drop": False,
                  "fx": {"vignette": True, "grain": True, "letterbox": False}, "no_fx": ["letterbox"]},
    "sad": {"color": "warm", "zoom": {"type": "push", "scale": 1.07}, "shake": False,
            "transitions": ["fade", "zoom"], "no_transitions": ["flash", "glitch", "whip"],
            "sfx": ["swoosh", "ding"], "no_sfx": ["boom", "hit", "bass_drop", "glitch", "sting", "pop", "riser"],
            "sfx_density": "low", "highlight": "#FFC9A3", "music": "soft sad piano ambient", "music_gain_db": -19.0,
            "hold_s": 0.9, "hold_style": "bw", "title": "fade", "drop": False,
            "fx": {"vignette": True, "grain": True, "letterbox": False}, "no_fx": ["letterbox"]},
    "rage": {"color": "punchy", "zoom": {"type": "punch", "scale": 1.18}, "shake": True,
             "transitions": ["glitch", "flash", "whip"], "no_transitions": ["fade"],
             "sfx": ["hit", "boom", "bass_drop", "glitch"], "no_sfx": ["pop", "ding"], "sfx_density": "high",
             "highlight": "#FF3B30", "music": "aggressive heavy bass", "music_gain_db": -18.0,
             "hold_s": 0.0, "hold_style": "zoom", "title": "glitch", "drop": False,
             "fx": {"vignette": True, "grain": False, "letterbox": False}, "no_fx": ["letterbox"]},
    "awe": {"color": "cinematic", "zoom": {"type": "push", "scale": 1.08}, "shake": False,
            "transitions": ["fade", "zoom"], "no_transitions": ["flash", "glitch", "whip"],
            "sfx": ["riser", "swoosh", "boom", "sting"], "no_sfx": ["pop", "ding", "glitch", "hit"],
            "sfx_density": "low", "highlight": "#FFE9A8", "music": "epic cinematic ambient", "music_gain_db": -19.0,
            "hold_s": 0.0, "hold_style": "zoom", "title": "fade", "drop": True,
            "fx": {"vignette": True, "grain": False, "letterbox": True}, "no_fx": []},
}


# Who is heard in a stretch of transcript (segment.voice). Heuristic [D], deliberately conservative: 'game' only on strong
# evidence, and any streamer slang (EN + ID) wins. When in doubt it is the streamer (a wrong 'game' mislabels a real reaction).
_STREAMER_WORDS = {"i", "i'm", "im", "i've", "ive", "i'll", "i'd", "my", "me", "myself", "we", "we're", "let's", "lets",
                   "gonna", "wanna", "chat", "bro", "bruh", "bruhh", "dude", "yo", "lol", "lmao", "omg", "wtf", "fuck",
                   "fucking", "shit", "holy", "damn", "nah", "man", "guys", "gang", "everybody", "everyone", "again",
                   "serious", "believe", "gue", "gw", "gua", "aku", "lu", "lo", "anjir", "anjay", "anjrit", "banget",
                   "dong", "sih", "deh", "wkwk", "wkwkwk", "buset", "bang", "nih", "tuh", "gila", "parah", "nya", "kok",
                   "kan", "ya", "yah", "nggak", "gak", "ga", "susah", "mantap"}
_GAME_WORDS = {"sir", "ma'am", "madam", "welcome", "please", "ladies", "gentlemen", "mister", "mr", "mrs", "sincerely",
               "congratulations", "mission", "objective", "officer", "contract", "professional", "sponsored"}
_GAME_PATTERNS = re.compile(
    r"leave a message|after the (tone|beep)|your call|this call|brought to you by|limited time offer|call now|"
    r"available now|coming soon|terms and conditions|press (the )?(button|key)|you have reached|new voicemail", re.I)


def voice_of(text: str) -> str:
    """'game' for NPC / ad / phone / cutscene dialogue, else 'streamer' (also when unsure). Game = no streamer slang word
    AND strong evidence: a quotation mark, an ad / phone-menu phrase, or >= 2 different formal NPC words."""
    t = (text or "").strip()
    toks = [re.sub(r"^[^\w']+|[^\w']+$", "", w).lower() for w in t.split()]
    toks = [w for w in toks if w]
    if len(toks) < 3 or any(w in _STREAMER_WORDS for w in toks):
        return "streamer"
    if re.search("[\"\u201c\u201d]", t) or _GAME_PATTERNS.search(t) or len(_GAME_WORDS & set(toks)) >= 2:
        return "game"
    return "streamer"


def vibe(emotion: str | None) -> dict[str, Any]:
    return VIBES.get(emotion or "") or VIBES["hype"]


def density_cap(*levels: str) -> str:
    """The quietest of several SFX density levels."""
    return min((lv for lv in levels if lv in _DENSITY), key=_DENSITY.get, default="low")


def vibe_text(emotion: str | None) -> str:
    """One prompt paragraph for ONE emotion (the editor prompt never carries the whole table)."""
    v, name = vibe(emotion), (emotion if emotion in VIBES else "hype")
    drop = "; cut the music ~0.35 s before the payoff (music.drop_at)" if v["drop"] else ""
    hold = f"; hold the reaction frame {v['hold_s']:.2f}s (hold_style {v['hold_style']})" if v["hold_s"] else ""
    fx = ", ".join(k for k, on in v["fx"].items() if on) or "none"
    return (f"VIBE {name} (set plan.vibe='{name}'): colour {v['color']}; default move {v['zoom']['type']} "
            f"{v['zoom']['scale']}; shake {'only on the payoff impact' if v['shake'] else 'NEVER'}; transitions "
            f"prefer {', '.join(v['transitions'])}, never {', '.join(v['no_transitions']) or '-'}; SFX {', '.join(v['sfx'])} "
            f"({v['sfx_density']} density, never {', '.join(v['no_sfx']) or '-'}); caption highlight {v['highlight']}; "
            f"music '{v['music']}' at {v['music_gain_db']:.0f} dB{drop}{hold}; title style {v['title']}; fx {fx}.")


# Internal words that must never reach the viewer's post copy (mandor MF-1 / C17).
# a bracket group that IS an internal tag as a whole: "(re-cut 2)", "[draft]", "(v3)", "(plan v2)", "[wip]", "(test)".
# "(Plan B)", "(ft. X)", "(Part 2)" are titles, not tags (round-2 review), so the whole group must match.
# a group needs one unmistakable tag word; "plan"/digits may only ride along: "[draft plan]", "( v2)", "(plan v2)".
# "(Plan 2)", "(Test)", "(V2)" (uppercase = a name) are titles.
_W = r"(?:re-?cut|draft|wip|(?-i:v\d+)|(?-i:test))"  # lowercase "(test)" = tag; "(Test)" = a title
_INT = r"\s*(?:plan\s+)?" + _W + r"(?:\s+(?:" + _W + r"|\d+|plan))*\s*"
_POST_BRACKETS = re.compile(r"\(" + _INT + r"\)|\[" + _INT + r"\]", re.I)
_POST_WORDS = re.compile(r"(?<![#\w@])re-?cut(?:\s*\d+)?(?!\w)", re.I)
# a version/draft tag at the END only after an explicit separator: "Big heist - v2", "Clip | draft".
# "Reacting to the NFL Draft", "Hitting 300 in the V12", "My plan worked!" stay.
# Only after a dash/pipe ("Big heist - v2", "Clip | draft"): a bare " v8" or "Season 2: Draft" is a real title.
_POST_TAIL = re.compile(r"\s+[\-|]\s*(?:plan\s+v\d+|(?-i:v\d+)|draft)\s*$", re.I)
_POST_TAG = re.compile(r"^#?(?:re-?cut|v\d+|draft|plan)$", re.I)


def clean_post_text(text: str, keep: list[str] | None = None) -> str:
    """Post title/caption without internal tokens: "re-cut N" anywhere, a bracket group that is wholly an internal
    tag ("(re-cut 2)", "[draft]", "(v3)", "(plan v2)", "[wip]", "(test)"), and a "- v2" / "| draft" tail — except a
    group that carries a string the brief requires (``keep``: disclosure, mentions). Real titles ("(Plan B)",
    "NFL Draft", "V12", "(ft. X)") are left alone."""
    keep_l = [k.lower() for k in keep or [] if k and k.strip()]

    def drop(m: re.Match[str]) -> str:
        return m.group(0) if any(k in m.group(0).lower() for k in keep_l) else " "

    out = _POST_BRACKETS.sub(drop, text or "")
    out = _POST_TAIL.sub("", _POST_WORDS.sub(" ", out))
    out = re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s{2,}", " ", out))
    return re.sub(r"^[\s\-|:,;]+|[\s\-|:,;]+$", "", out)


def post_leaks(text: str, keep: list[str] | None = None) -> list[str]:
    """The internal tokens still in ``text`` (empty list = clean)."""
    keep_l = [k.lower() for k in keep or [] if k and k.strip()]
    groups = [g for g in _POST_BRACKETS.findall(text or "") if not any(k in g.lower() for k in keep_l)]
    rest = _POST_BRACKETS.sub(" ", text or "")
    return groups + _POST_WORDS.findall(rest) + [m.strip(" -|:,") for m in _POST_TAIL.findall(rest)]


def internal_tag(tag: str) -> bool:
    return bool(_POST_TAG.match((tag or "").strip()))


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
        f"unless the brief says otherwise; a linear streamer-reaction clip aims {STREAM_SWEET_SPOT_S[0]}-"
        f"{STREAM_SWEET_SPOT_S[1]}s (lint above {STORY_QC['long_for_stream_s']:.0f}s).\n"
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
        f"Story: the first {STORY_QC['frame0_window_s']}s show a hook title over real footage (never black or a "
        f"transition); a time card must say the REAL gap; at most 1 SFX per {STORY_QC['sfx_min_gap_s']}s, never "
        f"> {STORY_QC['max_flash_per_s']} flashes in any second, the same effect not "
        f"{STORY_QC['effect_repeat_max'] + 1}x in a row; effects obey the clip's vibe (plan.vibe); the clip ends on "
        f"the punchline/reaction, not a fade to black; post copy carries no internal words (re-cut, v2, draft, plan, "
        f"(...), [...]).\n"
        f"CP1 type rules: the emphasis word of a hook/punch title ≥ {LAYOUT['hook_emphasis_min_px']}px condensed, its "
        f"setup line cap height ≥ {LAYOUT['hook_setup_min_cap_px']}px; captions cap height ≥ "
        f"{LAYOUT['caption_min_cap_px']}px; a freeze-frame hold never lands inside a phrase (words closer than "
        f"{STORY_QC['phrase_gap_s']}s in one sentence): before the phrase or after it is finished; frame 0 "
        f"(t≈{QC['frame0_t_s']}s) of the gameplay band has mean luma ≥ {QC['frame0_min_luma']} and spread ≥ "
        f"{QC['frame0_min_std']}, never a dark opener.\n"
        + "".join(f"House rule: {r}\n" for r in HOUSE_RULES) +
        f"Creative review pass mark: {QC['min_review_score']}/10 with no blocker or major issue."
    )
