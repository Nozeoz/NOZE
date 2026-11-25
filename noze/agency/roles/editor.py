"""Senior editor: writes the edit plan (EDL), revises it against review notes, renders it."""

from __future__ import annotations

import copy
import logging
import re
from pathlib import Path
from typing import Any

from .. import story
from ..media import faces
from ..media.analyze import contact_sheets, extract_frames
from ..media.qc import (arc_coverage, card_expectations, hold_of, phrase_around, plan_duration, segment_starts,
                        subject_in_game)
from ..media.render import Renderer, RenderResult, RenderSpec, _valid_cam, stack_layout
from ..media.sfx import AUDIO_EXT, sfx_file
from ..media.timeline import Timeline, jump_cut, remove_output_range, sanitize_segments
from ..media.transcribe import all_words, words_between
from ..schemas import EDIT_PLAN, EMOTIONS, SFX_KINDS, conform, example
from ..standards import (HOUSE_RULES, LAYOUT, LOOP_EMOTIONS, STORY_QC, STREAM_SWEET_SPOT_S, clean_post_text,
                         density_cap, internal_tag, vibe, vibe_text, voice_of)
from .base import Role, dump

log = logging.getLogger("noze.agency.editor")


def same_box(a: Any, b: Any, tol: float = 0.005) -> bool:
    try:
        return all(abs(float(a[k]) - float(b[k])) <= tol for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        return False


def reproject_box(box: dict[str, Any], src: dict[str, Any], dst: dict[str, Any]) -> dict[str, Any] | None:
    """A box given as fractions of rectangle ``src`` (both in source-frame fractions) → fractions of ``dst``.
    None when less than half of the box lands inside ``dst`` (a face the new crop cuts off is no face box)."""
    sx, sy, sw, sh = (float(src[k]) for k in ("x", "y", "w", "h"))
    dx, dy, dw, dh = (float(dst[k]) for k in ("x", "y", "w", "h"))
    x0, y0 = sx + float(box["x"]) * sw, sy + float(box["y"]) * sh
    x1, y1 = x0 + float(box["w"]) * sw, y0 + float(box["h"]) * sh
    clamp = lambda v: round(min(max(v, 0.0), 1.0), 3)  # noqa: E731
    nx, ny = clamp((x0 - dx) / dw), clamp((y0 - dy) / dh)
    out = {"x": nx, "y": ny, "w": clamp((x1 - dx) / dw - nx), "h": clamp((y1 - dy) / dh - ny)}
    kept = (out["w"] * dw * out["h"] * dh) / max((x1 - x0) * (y1 - y0), 1e-9)
    return out if kept >= 0.5 else None


def inset_box(cam: dict[str, Any], share: float) -> dict[str, Any]:
    """The crop shrunk ``share`` of its own size on every side (the detector's box can touch the stream layout)."""
    x, y, w, h = (float(cam[k]) for k in ("x", "y", "w", "h"))
    return {"x": round(x + share * w, 3), "y": round(y + share * h, 3),
            "w": round(w * (1 - 2 * share), 3), "h": round(h * (1 - 2 * share), 3)}


def fit_cam_upscale(cam: dict[str, Any], src_w: int, src_h: int, w: int, h: int, limit: float) -> dict[str, Any]:
    """Grow the facecam crop around its centre (same shape) until the band magnifies it ≤ ``limit``.

    Face detectors crop inside the overlay on purpose; at 1080p that small crop lands just over the
    softness limit (2.6× on a typical streamer cam), so a few more source pixels fix it for free.
    """
    out = {k: float(cam[k]) for k in ("x", "y", "w", "h")}
    for _ in range(4):  # clamping at the frame edge can cost a little; settle in a few passes
        top, _ = stack_layout(out, src_w, src_h, w, h)
        up = max(w / max(out["w"] * src_w, 1.0), top / max(out["h"] * src_h, 1.0))
        if up <= limit * 0.98 or (out["w"] >= 1.0 and out["h"] >= 1.0):
            break
        k = up / (limit * 0.97)
        cx, cy = out["x"] + out["w"] / 2, out["y"] + out["h"] / 2
        out["w"], out["h"] = min(1.0, out["w"] * k), min(1.0, out["h"] * k)
        out["x"] = min(max(cx - out["w"] / 2, 0.0), 1.0 - out["w"])
        out["y"] = min(max(cy - out["h"] / 2, 0.0), 1.0 - out["h"])
    return {k: round(v, 3) for k, v in out.items()} if out != {k: float(cam[k]) for k in out} else dict(cam)

SFX_SPACING = {"none": 0.0, "low": 6.0, "medium": 3.5, "high": 2.0}

# Fixes that are safe to re-apply on top of a model's revision: idempotent and not tied to
# the old render's timecodes (those would cut/shift the *new* timeline in the wrong place).
SAFE_AFTER_MODEL = {"hook:silent_open", "hook:slow_open", "captions:missing", "visual:black_frames",
                    "audio:loudness", "audio:true_peak", "compliance:too_long", "visual:flash_rate"}

STORY_TOOLS = """\
STORY TOOLS (they tell the story; never decoration):
- transition_in 'rewind' (+ sfx 'rewind') = a jump BACK in time; 'glitch' = a jolt; flash/whip/zoom/fade only as the vibe allows.
- overlay kind 'time_card' = a big card on the first frame of a part that jumps over a minute; its text MUST equal that
  part's label below (code recomputes it from the real gap and overwrites a wrong one).
- segment `look`: 'flashback' for setup/foreshadow footage from EARLIER than the payoff (vhs / noir / dream also exist).
- segment `hold` (0-1.2 s freeze of its LAST frame) + `hold_style`: the reaction beat after a punchline.
- zoom.fx / zoom.fy = where a punch/push aims (0-1 of the OUTPUT frame): aim at the face or the object, not the centre.
- overlay 'callout' (at_x/at_y, <= 3 words) circles a foreshadowed detail; style 'stamp' slams a one-word verdict.
- music.drop_at = output second of the payoff: the bed cuts ~0.35 s before it (tense / shock / awe).
- plan.vibe + plan.fx {vignette, grain, letterbox}; stack mode: reframe.scale / reframe.y move and zoom the GAMEPLAY band
  so the player is clear of the TikTok UI.
STRUCTURE RECIPES:
- cold_open: frame 0 = the PAYOFF for 1-2.5 s with the hook title from 0.0 s; then transition 'rewind' + the time card
  into the setup, the build, the full payoff, and end on the reaction (funny: + hold).
- arc: setup (look 'flashback' when it is earlier than the payoff) -> time card at each jump -> callout/hold on the
  foreshadowed detail -> payoff; the reaction is the last thing seen.
- montage: a time card at every part, the rhythm tightening (later parts shorter), the strongest instance last.
- linear: hook -> build -> payoff, no cards. If the emotional peak (scream, tears, 'no way', the weirdest picture) sits
  later than the first ~3 s, OPEN on a 0.8-1.5 s teaser of that peak (the streamer's face at the peak, role cold_open,
  plain cut) and then play the clip from its start; if the clip already starts on the peak, add nothing. Aim 20-30 s.
REFERENCE RULES (viral clips of this niche share ONE template; the moment and these decide, not effects):
- LOOP: a cold_open (or funny / shock / sad) clip ends on the same / a similar reaction as frame 0 (or a held reaction),
  plain cut, no fade to black, so the end runs straight back into the start.
- FEW CUTS on stack / gameplay: cut only pauses over 0.9 s, never split a running game action, at most ~4 cuts per
  30 s unless a time jump needs one (lint pacing:over_cut above 8 per 30 s).
- LENGTH: linear clips aim 20-30 s (lint pacing:long_for_stream above 35 s); an arc may reach ~45 s if the payoff is clear.
- HOOK TITLE: [known subject] + [one specific stakes claim], <= 45 characters, <= 2 lines ('STREAM ALMOST ENDED
  IMMEDIATELY', not 'Their reactions'); lint hook:title_long.
- Effects serve the moment: an effect that hides the peak or the face is a defect, not style.
FREEZE PLACEMENT: a hold never lands between two words of one phrase (words < 0.25 s apart in a sentence): put it on
the jaw-drop BEFORE the punchline phrase, or right after the phrase is finished (code moves a misplaced one).
ALWAYS: end on the punchline or the reaction (never a fade to black); sound leads the picture (riser -> a beat of
silence -> payoff); J/L cuts where the audio crosses a time jump; at most 1 SFX per 1.5 s and never the same effect 3x
in a row."""
STORY_TOOLS += "\nHOUSE RULES: " + " ".join(HOUSE_RULES)


_LIMP_TAIL = {"the", "a", "an", "to", "of", "and", "but", "or", "because", "so", "it", "it's", "is", "my", "your",
              "with", "for", "in", "on", "at", "that", "this", "yang", "dan", "di", "ke", "itu"}


def cap_chars(text: str, limit: int = STORY_QC["title_max_chars"]) -> str:
    """A title within ``limit`` characters (reference research: <= 45): drop whole words from the end, never end on "to"/"the"."""
    if len(text) <= limit:
        return text
    words = text[:limit + 1].rsplit(" ", 1)[0].split() if " " in text[:limit + 1] else [text[:limit]]
    while len(words) > 3 and words[-1].lower().strip(",.…") in _LIMP_TAIL:
        words.pop()
    return " ".join(words).rstrip(",;:…")[:limit]


def short_hook(text: str, max_words: int = 7) -> str:
    words = re.sub(r"\s+", " ", text or "").strip().split()
    if len(words) <= max_words:
        return cap_chars(" ".join(words).rstrip(",;:"))
    head = words[:max_words]
    clause = max((i for i, w in enumerate(head) if w[-1:] in ",.!?;:"), default=-1)
    if clause >= 2:  # end on a clause boundary when there is one
        return cap_chars(" ".join(head[:clause + 1]).rstrip(",;:"))
    while len(head) > 3 and head[-1].lower().strip(",.") in _LIMP_TAIL:  # never end on "to"/"the"…
        head.pop()
    out = " ".join(head).rstrip(",;:")
    return cap_chars(out) if len(out) >= STORY_QC["title_max_chars"] else out + "…"


# Words that mark the emotional peak inside a stretch (scream, disbelief, tears): the reference clips open on it.
_PEAK_WORDS = {"omg", "wtf", "holy", "fuck", "fucking", "shit", "cry", "crying", "cried", "tears", "scream", "screaming",
               "wow", "dude", "yo", "bruh"}
_PEAK_BIGRAMS = {("no", "way"), ("oh", "my"), ("what", "the")}


def find_peak(words: list[dict[str, Any]], a: float, b: float, moment: dict[str, Any] | None = None) -> float | None:
    """Source second of the emotional peak inside [a, b], or None. The moment's own ``peak_s`` wins (a signal measured
    upstream: chat spike, scream, laughter); else the 1.5 s window with the most peak words (the latest on a tie).
    ponytail: text keywords only, no audio loudness here; add the loudest second of the part when the scout exports it."""
    ps = (moment or {}).get("peak_s")
    if isinstance(ps, (int, float)) and a <= float(ps) <= b:
        return float(ps)
    ws = [w for w in words if w["start"] >= a - 0.05 and w["end"] <= b + 0.05]
    tok = [re.sub(r"[^a-z']", "", str(w.get("word") or "").lower()) for w in ws]
    hits = [ws[i]["start"] for i, t in enumerate(tok)
            if t in _PEAK_WORDS or (i + 1 < len(tok) and (t, tok[i + 1]) in _PEAK_BIGRAMS)]
    if not hits:
        return None
    best = max(hits, key=lambda h: (sum(1 for u in hits if h <= u < h + 1.5), h))
    return float(best)


def _unit(v: Any) -> float | None:
    """0-1 clamp for focus points / crop positions; None stays None (= centre)."""
    try:
        return None if v is None else round(min(1.0, max(0.0, float(v))), 3)
    except (TypeError, ValueError):
        return None


def requires_facecam(brief: dict[str, Any]) -> bool:
    other = " ".join(((brief or {}).get("requirements") or {}).get("other") or []).lower()
    return "facecam" in other or "face cam" in other or "webcam" in other


def comply_post(post: dict[str, Any], brief: dict[str, Any], fallback_caption: str = "") -> dict[str, Any]:
    """Required hashtags, mentions and disclosure in the post copy — re-applied on every
    plan and again at delivery, so no later step (or model) can drop them."""
    req = (brief or {}).get("requirements") or {}
    post = dict(post or {})
    keep = [req.get("disclosure") or ""] + list(req.get("mentions") or [])  # brief text survives the cleaning
    tags = [t for t in (post.get("hashtags") or []) if not internal_tag(t)]
    have = {t.lower().lstrip("#") for t in tags}
    for t in req.get("hashtags") or []:
        if t.lower().lstrip("#") not in have:
            tags.append(t)
            have.add(t.lower().lstrip("#"))
    post["hashtags"] = [t if t.startswith("#") else f"#{t}" for t in tags if t.strip("# ")]
    # MF-1 / C17: no internal wording (re-cut, v2, draft, plan, (...), [...]) in what the viewer reads, on every path
    caption = clean_post_text(post.get("caption") or "", keep) or clean_post_text(fallback_caption, keep)
    if post.get("title"):
        post["title"] = clean_post_text(post["title"], keep)
    creator = ((brief or {}).get("creator") or "").strip()
    handles = [h.rsplit("/", 1)[-1].lstrip("@").lower() for h in (brief or {}).get("creator_handles") or [] if h]
    shown = f"{caption} {post.get('title') or ''}".lower()
    if creator and creator.lower() not in shown and not any(h and h in shown for h in handles):
        caption = f"{caption} | {creator}" if caption else creator
    if not post.get("title") and "title" in post:
        post["title"] = creator or caption
    for m in req.get("mentions") or []:
        if m.lower() not in caption.lower():
            caption = f"{caption} {m}".strip()
    disclosure = (req.get("disclosure") or "").strip()
    if disclosure and disclosure.lower() not in caption.lower():
        caption = f"{disclosure} {caption}".strip()
    for b in (x.strip() for x in req.get("banned") or []):
        if b:
            caption = re.sub(r"\s{2,}", " ", re.sub(re.escape(b), "", caption, flags=re.I)).strip()
            post["hashtags"] = [t for t in post["hashtags"] if b.lower() not in t.lower()]
    post["caption"] = caption
    return post


def split_long(ranges: list[tuple[float, float]], words: list[dict[str, Any]], target: float) -> list[tuple[float, float]]:
    """Split ranges longer than ~1.5× target at word gaps so framing can alternate."""
    out: list[tuple[float, float]] = []
    for a, b in ranges:
        if b - a <= target * 1.5:
            out.append((a, b))
            continue
        inside = [w for w in words if a <= w["start"] and w["end"] <= b]
        cuts, last = [], a
        for w in inside:
            if w["start"] - last >= target and b - w["start"] >= target * 0.6:
                cuts.append(w["start"])
                last = w["start"]
        bounds = [a] + cuts + [b]
        out += [(round(x, 3), round(y, 3)) for x, y in zip(bounds, bounds[1:]) if y - x > 0.25]
    return out


CAM_SOFT_MAX = 3.1  # [D] detector cam magnification ceiling: above it the inset is given back (3.2x = major)


def cam_magnification(cam: dict[str, Any], src_w: int, src_h: int, w: int, h: int) -> float:
    from ..media.render import stack_layout

    top, _ = stack_layout(cam, src_w, src_h, w, h)
    return max(w / max(1e-6, cam["w"] * src_w), top / max(1e-6, cam["h"] * src_h))


SEAM_MIN_PIECE_S = 1.0  # [D] a shorter piece of another stream hour is a flash, not footage


class Editor(Role):
    name = "editor"

    # -- inputs ---------------------------------------------------------------------------------------
    def prepare(self, job: dict[str, Any], source: Path, moment: dict[str, Any], transcript: dict[str, Any],
                blueprint: dict[str, Any], source_info: dict[str, Any]) -> dict[str, Any]:
        work = self.ax.job_dir(job)
        words = all_words(transcript)
        pacing = blueprint.get("pacing") or {}
        max_gap = float(pacing.get("remove_silences_over_s") or 0.45)
        # a moment is one or more parts played in order (they may jump around the stream): cut each on its own
        parts = story.label_parts(story.moment_parts(moment), moment.get("vod_map"))
        # frame sheet spread evenly over ALL parts (not one stretch), labelled with source timestamps
        n_frames = min(12, max(8, 3 * len(parts)))
        total, times = story.parts_duration(parts), []
        for i in range(n_frames):
            u = total * (i + 0.5) / n_frames
            for part in parts:
                d = part["end_s"] - part["start_s"]
                if u <= d:
                    times.append(round(part["start_s"] + u, 2))
                    break
                u -= d
        sheets: list[str] = []
        sx = cam = game_subject = None
        try:
            frames = extract_frames(source, times, work / "moment_frames", width=1280)  # big enough for facecams
            sheets = [str(p) for p in contact_sheets(frames, times, work / "moment_sheet")]
            sx = faces.subject_x(frames)
            cam = faces.facecam_box(frames)
            game_subject = subject_in_game(frames, cam)  # a face / head in the game: the title keeps off it
        except Exception as exc:  # frames are a nice-to-have for framing decisions
            log.info("moment frames unavailable: %s", exc)
        face = cam.pop("face", None) if cam else None
        vertical = bool(source_info.get("width") and source_info.get("height")
                        and source_info["width"] / source_info["height"] < 0.75)
        fmode = (blueprint.get("framing") or {}).get("mode") or "auto"
        gameplay = not vertical and (fmode == "stack" or (fmode == "auto" and cam is not None))
        # never above the over_cut lint (8 cuts / 30 s) with the editor's own splits; gameplay goes down to ~4 / 30 s
        target = max(float(pacing.get("target_shot_s") or 2.8), 30.0 / STORY_QC["over_cut_per_30s"])
        if gameplay:  # a game's action keeps running through short pauses: cut only long ones, ~4 cuts per 30 s at most
            max_gap = max(max_gap, STORY_QC["gameplay_min_gap_s"])
            target = max(target, 30.0 / STORY_QC["gameplay_max_cuts_30s"])
        ranges: list[tuple[float, float]] = []
        range_parts: list[int] = []
        for pi, part in enumerate(parts):
            dur = part["end_s"] - part["start_s"]
            n_words = sum(1 for w in words if w["start"] >= part["start_s"] - 0.05 and w["end"] <= part["end_s"] + 0.05)
            if n_words / max(dur, 0.1) < 1.2:  # action / scream / sparse talk: the picked stretch IS the moment, keep it whole
                rs = [(round(part["start_s"], 3), round(part["end_s"], 3))]
            else:
                rs = jump_cut(words, part["start_s"], part["end_s"], max_gap=max(0.25, max_gap),
                              cut_fillers=bool(pacing.get("cut_fillers", True)))
            rs = split_long(rs, words, target)
            ranges += rs
            range_parts += [pi] * len(rs)
        moment_words = [w for part in parts for w in words_between(transcript, part["start_s"], part["end_s"])]
        return {"words": words, "moment_words": moment_words, "ranges": ranges,
                "parts": parts, "range_parts": range_parts,  # parts in play order; range i belongs to part range_parts[i]
                "sheets": sheets, "subject_x": sx, "facecam": cam, "facecam_face": face, "game_subject": game_subject,
                "source_info": source_info}

    # -- planning -----------------------------------------------------------------------------------------
    def plan(self, job: dict[str, Any], moment: dict[str, Any], brief: dict[str, Any], blueprint: dict[str, Any],
             prep: dict[str, Any]) -> dict[str, Any]:
        cfg = self.ax.cfg
        max_s = self._max_len(brief)
        parts = prep.get("parts") or story.label_parts(story.moment_parts(moment), moment.get("vod_map"))
        tagged = [{"src": [a, b], "part": (prep.get("range_parts") or [0] * len(prep["ranges"]))[i]}
                  for i, (a, b) in enumerate(prep["ranges"])]
        emotion = moment.get("emotion") if moment.get("emotion") in EMOTIONS else ""
        tell = (
            f"STORY: structure={moment.get('structure') or 'linear'}, emotion={emotion or 'unknown'}, "
            f"story=\"{moment.get('story') or ''}\".\nParts in PLAY order (source seconds; `label` = the exact time-card "
            f"text when that part starts, '' = no card):\n{dump(parts, 2500)}\n"
            f"{vibe_text(emotion or None)}\n{STORY_TOOLS}\n\n"
        )
        task = (
            f"Write the edit plan for this clip.\n\nBrief:\n{dump(brief, 8000)}\n\nBlueprint:\n{dump(blueprint, 8000)}\n\n"
            f"{tell}"
            f"Moment (source seconds):\n{dump(moment, 3000)}\n\nSource: {prep['source_info'].get('width')}x"
            f"{prep['source_info'].get('height')} @ {prep['source_info'].get('fps')}fps, "
            f"duration {prep['source_info'].get('duration')}s. Detected speaker x (0-1, may be null): {prep['subject_x']}\n"
            f"Detected facecam overlay (source fractions, may be null): {prep.get('facecam')}; "
            f"face inside it (fractions of the cam): {prep.get('facecam_face')} — check both against the frames; "
            "for stack mode set reframe.cam and reframe.face to what you see (inset the cam >= 2% inside its border).\n"
            f"Head found in the GAMEPLAY (source fractions cx, cy; may be null): {prep.get('game_subject')} — keep the "
            "title off it (head in the top of the band -> title position 'bottom').\n"
            "Set segment.voice per segment: 'game' for NPC / ad / cutscene dialogue, else 'streamer'. An arc / cold_open / "
            "montage across periods = the heart of the request: play a part of EACH period with its time card.\n"
            f"Target: {cfg.width}x{cfg.height}, max length {max_s:.0f}s"
            + (f"; a linear clip aims {STREAM_SWEET_SPOT_S[0]}-{STREAM_SWEET_SPOT_S[1]}s" if (
                moment.get("structure") or "linear") == "linear" else "") + ".\n\n"
            f"Suggested tight cut (pauses/fillers removed), source seconds, tagged with their part:\n{dump(tagged, 4000)}\n\n"
            f"Words with source timings:\n{self._words_text(prep['moment_words'])}\n\n"
            f"SFX kinds available: {', '.join(SFX_KINDS)}. Music library moods: {self._music_menu()}\n"
            "The images are frame sheets across the moment, labelled with SOURCE timestamps — use them for "
            "reframe.x and to decide where punch-ins/b-roll-like beats belong."
        )
        out = self.ask(job, task, EDIT_PLAN, images=prep["sheets"], campaign=self.campaign_of(job))
        if out is None:
            out = self.heuristic_plan(moment, brief, blueprint, prep)
            out["fixes"] = []
        return self.finalize(out, moment, brief, blueprint, prep)

    def heuristic_plan(self, moment: dict[str, Any], brief: dict[str, Any], blueprint: dict[str, Any],
                       prep: dict[str, Any]) -> dict[str, Any]:
        """The no-LLM plan. Story-aware when the moment carries an emotion or several parts: the structure recipe
        (cold open / flashback / time cards / rewind / reaction hold) and the emotion's palette (standards.VIBES)."""
        info = prep["source_info"]
        vertical = info.get("width") and info.get("height") and info["width"] / info["height"] < 0.75
        mode = (blueprint.get("framing") or {}).get("mode") or "auto"
        x = prep.get("subject_x")
        cam = prep.get("facecam")
        if requires_facecam(brief) and not vertical:
            mode = "stack" if cam else "fit_blur"  # the facecam must stay visible
        elif mode == "auto":
            mode = "fill" if vertical else ("stack" if cam else ("fixed" if x is not None else "center"))
        if mode == "stack":
            x = 0.5  # x is the gameplay centre in stack mode
        motion = blueprint.get("motion") or {}
        parts = story.label_parts(story.moment_parts(moment), moment.get("vod_map"))
        emotion = moment.get("emotion") if moment.get("emotion") in EMOTIONS else ""
        aware = bool(emotion) or len(parts) > 1  # a plain legacy moment keeps the blueprint-only behaviour
        v = vibe(emotion or None)
        structure = moment.get("structure") or ("arc" if len(parts) > 1 else "linear")
        zoom_t = v["zoom"]["type"] if aware else "punch"
        punch = float(v["zoom"]["scale"]) if aware else float(motion.get("punch_scale") or 1.12)
        trans_pool = [t for t in (motion.get("transitions") or []) if t != "cut"]
        if aware:
            trans_pool = [t for t in trans_pool if t not in v["no_transitions"]] or list(v["transitions"])

        ranges, rp = self._range_parts(prep, parts)
        ranges, rp = self._ensure_parts(ranges, rp, parts)  # an arc never loses a part (mandor CP2 #4)
        if structure == "cold_open" and len(parts) > 1:
            ranges, rp = self._trim_teaser(ranges, rp, prep.get("words") or [])
        teaser = False
        if structure == "linear" and len(parts) == 1:  # frame 0 = the emotional peak, even when it sits late in the clip
            ranges, rp, teaser = self._peak_teaser(ranges, rp, prep.get("words") or [], parts[0], moment)
        roles =[parts[i]["role"] for i in rp]
        # the payoff = the last range of the last part that plays the payoff / reaction / button role
        pay_i = max((i for i, r in enumerate(roles) if r in ("payoff", "reaction", "button")), default=len(ranges) - 1)
        past_limit = min((p["start_s"] for p in parts if p["role"] in ("cold_open", "payoff", "reaction", "button")),
                         default=None)
        segs = []
        prev_end = None
        for i, (a, b) in enumerate(ranges):
            part = parts[rp[i]]
            new_part = i > 0 and rp[i] != rp[i - 1]
            gap = (a - prev_end) if prev_end is not None else 0.0
            trans = "cut"
            if i > 0:
                if aware and new_part and a < prev_end - 0.5:
                    trans = "rewind"  # the source jumps back in time
                elif aware and new_part:
                    trans = trans_pool[0] if trans_pool else "cut"
                elif gap > 2.0 and trans_pool:
                    trans = trans_pool[0]
            flash = (aware and structure in ("cold_open", "arc") and part["role"] in ("setup", "foreshadow")
                     and past_limit is not None and part["end_s"] <= past_limit - story.MIN_LABEL_GAP_S)
            if not aware:
                zoom = {"type": "punch" if i % 2 == 1 else "none", "scale": punch, "fx": None, "fy": None}
            else:
                on = (i % 2 == 1) if zoom_t == "punch" else (b - a >= 1.5 and i % 2 == 0)
                zoom = {"type": zoom_t if (on or i == pay_i) else "none", "scale": punch, "fx": None, "fy": None}
            seg = {"src_start": a, "src_end": b, "speed": 1.0,
                   "reframe": {"mode": mode, "x": x or 0.5, "cam": cam if mode == "stack" else None,
                               "face": prep.get("facecam_face") if mode == "stack" else None},
                   "zoom": zoom, "shake": False, "transition_in": trans, "role": part["role"],
                   "look": "flashback" if flash else "none", "hold": 0.0, "hold_style": v["hold_style"], "note": "",
                   "label": part["label"] if new_part else "",
                   "voice": voice_of(" ".join(w["word"] for w in prep.get("words") or [] if a - 0.05 <= w["start"] < b))}
            if aware and i == pay_i:
                if v["shake"] and motion.get("shake_on_impact", True):
                    seg["shake"] = True  # impact only, and only where the vibe allows it
                if v["hold_s"]:
                    seg["hold"] = float(v["hold_s"])  # the reaction beat
                    if mode == "stack":
                        seg["zoom"].update({"fx": 0.5, "fy": 0.17})  # the hold pushes in on the face (cam band)
            segs.append(seg)
            prev_end = b
        if teaser:
            segs[0]["role"], segs[0]["note"] = "cold_open", "peak teaser (frame 0 = the emotional peak)"
            segs[1]["transition_in"] = "cut"
        self._close_loop(segs, structure, emotion, mode, aware)
        self._break_runs(segs)
        starts = segment_starts(segs)
        plan = example(EDIT_PLAN)
        sound = blueprint.get("sound") or {}
        mood = sound.get("music_mood") or (v["music"] if emotion else "")
        plan.update({
            "title": moment.get("title") or "clip",
            "segments": segs,
            "captions": {**(blueprint.get("captions") or {}), "enabled": bool(prep["moment_words"]), "font_scale": 1.0},
            "overlays": [], "sfx": [],
            "music": {"enabled": bool(mood), "mood": mood, "asset": "",
                      "gain_db": float(sound.get("music_gain_db") or (v["music_gain_db"] if emotion else -19.0)),
                      "duck": True, "drop_at": None},
            "color": v["color"] if emotion else (blueprint.get("color") or "punchy"),
            "progress_bar": False,
            "post": {"caption": moment.get("title") or "", "hashtags": []},
            "used_lessons": [], "rationale": "heuristic plan from blueprint + tight cut"
            + (f" ({structure}, {emotion or 'no emotion'})" if aware else ""),
        })
        if emotion:
            plan["vibe"] = emotion
            plan["fx"] = dict(v["fx"])
            if not (blueprint.get("captions") or {}).get("highlight_color"):
                plan["captions"]["highlight_color"] = v["highlight"]
        title_style = v["title"] if emotion else (blueprint.get("text_overlays") or {}).get("style") or "pop"
        if (blueprint.get("text_overlays") or {}).get("hook_title", True):
            # the moment's title frames the line; the hook line itself is already in the captions
            hook = short_hook(moment.get("title") or moment.get("hook_line") or "")
            if hook:
                plan["overlays"].append({"kind": "hook_title", "text": hook.upper(), "start": 0.0, "end": 2.6,
                                         # stacked: the top band is the facecam and captions ride the seam
                                         "position": "center" if mode == "stack" else "top",
                                         "style": title_style})
        else:
            plan["segments"][0]["zoom"] = {"type": "punch", "scale": punch, "fx": None, "fy": None}
        for i in range(1, len(segs)):  # a time card on every part that jumps over a minute: the label is the real gap
            label = parts[rp[i]]["label"]
            if rp[i] != rp[i - 1] and label:
                plan["overlays"].append({"kind": "time_card", "text": label, "start": round(starts[i][0], 3),
                                         "end": round(starts[i][0] + STORY_QC["card_s"], 3), "position": "center",
                                         "style": "pop"})
        if mode == "stack":
            plan["captions"]["position"] = "upper"  # = ride the cam/gameplay seam
        self._place_sfx(plan, blueprint, v if emotion else None)
        if emotion and v["drop"] and starts[pay_i][0] >= 2.0:
            plan["music"]["drop_at"] = round(starts[pay_i][0], 2)  # the bed cuts just before the payoff
        self._place_holds(plan, prep.get("words") or [])  # the reaction beat: before the punchline phrase or after it
        return plan

    @staticmethod
    def _range_parts(prep: dict[str, Any], parts: list[dict[str, Any]]) -> tuple[list[tuple[float, float]], list[int]]:
        """The tight cut and the part each range belongs to (prepare tags them; hand-made preps are matched by overlap)."""
        ranges = [tuple(r) for r in prep["ranges"]]
        rp = list(prep.get("range_parts") or [])
        if len(rp) != len(ranges):
            rp = [max(range(len(parts)), key=lambda k: min(b, parts[k]["end_s"]) - max(a, parts[k]["start_s"]))
                  for a, b in ranges]
        return ranges, rp

    @staticmethod
    def _ensure_parts(ranges: list[tuple[float, float]], rp: list[int], parts: list[dict[str, Any]]
                      ) -> tuple[list[tuple[float, float]], list[int]]:
        """Every part of the moment is played at least once: a part the tight cut lost (no ranges) comes back whole,
        in its play position."""
        ranges, rp = list(ranges), list(rp)
        for k, part in enumerate(parts):
            if k not in rp:
                at = next((i for i, p in enumerate(rp) if p > k), len(rp))
                ranges.insert(at, (round(part["start_s"], 3), round(part["end_s"], 3)))
                rp.insert(at, k)
        return ranges, rp

    @staticmethod
    def _peak_teaser(ranges: list[tuple[float, float]], rp: list[int], words: list[dict[str, Any]],
                     part: dict[str, Any], moment: dict[str, Any]) -> tuple[list[tuple[float, float]], list[int], bool]:
        """Linear clip whose emotional peak sits later than the opening: frame 0 = a 0.8-1.5 s teaser of that peak (the
        streamer's face at the peak), then the clip plays from its start. Nothing is added when the clip already opens
        on the peak (within ``peak_early_s``) or no peak is found. Idempotent per call: it only reads the part."""
        lo, hi = STORY_QC["peak_teaser_s"]
        if not ranges:
            return ranges, rp, False
        peak = find_peak(words, part["start_s"], part["end_s"], moment)
        if peak is None or peak - ranges[0][0] < STORY_QC["peak_early_s"]:
            return ranges, rp, False
        a = max(ranges[0][0], peak - 0.3)
        b = min(part["end_s"], a + 1.2)
        cross = next((w for w in words if w["start"] < b < w["end"]), None)  # never end inside a word
        if cross is not None:
            b = cross["end"] if cross["end"] - a <= hi else max(cross["start"], a + lo)
        if b - a < lo or b > part["end_s"] + 1e-6:
            return ranges, rp, False
        return [(round(a, 3), round(b, 3))] + ranges, [rp[0]] + rp, True

    @staticmethod
    def _close_loop(segs: list[dict[str, Any]], structure: str, emotion: str, mode: str, aware: bool) -> None:
        """Loop: a cold-open (or funny / shock / sad) clip ends on the reaction it opened with: held, plain cut, no fade,
        so the end runs straight back into frame 0."""
        if not aware or len(segs) < 2 or not (structure == "cold_open" or emotion in LOOP_EMOTIONS):
            return
        last = segs[-1]
        if last.get("transition_in") == "fade":
            last["transition_in"] = "cut"
        if hold_of(last) < STORY_QC["loop_hold_s"]:
            last["hold"] = STORY_QC["loop_hold_s"]
            if mode == "stack" and (last.get("zoom") or {}).get("fx") is None:
                last["zoom"] = {**(last.get("zoom") or {}), "fx": 0.5, "fy": 0.17}

    @staticmethod
    def _trim_teaser(ranges: list[tuple[float, float]], rp: list[int], words: list[dict[str, Any]],
                     ) -> tuple[list[tuple[float, float]], list[int]]:
        """Cold open: the payoff teaser at frame 0 runs ~1-2.5 s. A longer first part keeps its TAIL (the payoff
        is where it ends), cut on a word start."""
        lo, hi = STORY_QC["teaser_s"]
        idx = [i for i, p in enumerate(rp) if p == rp[0]]
        if sum(ranges[i][1] - ranges[i][0] for i in idx) <= hi + 0.5:
            return ranges, rp
        keep, total = [], 0.0
        for i in reversed(idx):
            d = ranges[i][1] - ranges[i][0]
            if keep and total + d > hi:
                break
            keep.insert(0, i)
            total += d
        first = keep[0]
        a, b = ranges[first]
        if b - a > hi:  # one long range: start on the first word that leaves <= hi seconds
            a = next((w["start"] for w in words if b - hi <= w["start"] < b - lo), b - hi)
            ranges = ranges[:first] + [(round(a, 3), b)] + ranges[first + 1:]
        keep_set = set(keep)
        pairs = [(r, p) for i, (r, p) in enumerate(zip(ranges, rp)) if p != rp[0] or i in keep_set]
        return [r for r, _ in pairs], [p for _, p in pairs]

    @staticmethod
    def _break_runs(segs: list[dict[str, Any]]) -> None:
        """Never the same transition / zoom three times in a row (QC pacing:effect_repeat): break the third."""
        for key in ("transition_in", "zoom"):
            for i in range(2, len(segs)):
                tok = [(s.get("transition_in") if key == "transition_in" else (s.get("zoom") or {}).get("type")) or ""
                       for s in segs[i - 2:i + 1]]
                if tok[0] == tok[1] == tok[2] and tok[0] not in ("", "cut", "none"):
                    if key == "transition_in":
                        segs[i]["transition_in"] = "cut"
                    else:
                        segs[i]["zoom"] = {**segs[i]["zoom"], "type": "none"}

    def _place_sfx(self, plan: dict[str, Any], blueprint: dict[str, Any], v: dict[str, Any] | None = None) -> None:
        """SFX on the beats. With a vibe: only its palette, at most its density (and 1 per 1.5 s overall), plus the
        story cues (rewind on a time jump, the riser/sting into a tense payoff, the ding on a funny reaction hold)."""
        sound = blueprint.get("sound") or {}
        want = sound.get("sfx_density") or ("low" if v is None else v["sfx_density"])
        spacing = SFX_SPACING.get(density_cap(want, v["sfx_density"]) if v else want, 6.0)
        palette = [k for k in (sound.get("sfx_palette") or []) if k in SFX_KINDS and (v is None or k not in v["no_sfx"])]
        if v:
            palette = palette or [k for k in v["sfx"] if k in SFX_KINDS]
        palette = palette or ["whoosh", "pop"]
        if not spacing:
            return
        segs = sanitize_segments(plan["segments"], 1e9)
        starts = segment_starts(segs)
        D = starts[-1][1] if starts else 0.0
        cues = []
        if any(o["kind"] == "hook_title" for o in plan["overlays"]):
            cues.append({"kind": "pop" if "pop" in palette else palette[0], "at": 0.05, "gain_db": -9.0})
        last = 0.0
        for i, seg in enumerate(segs[1:], start=1):
            beat = seg.get("transition_in") not in (None, "cut") or (seg.get("zoom") or {}).get("type") == "punch"
            if seg.get("transition_in") == "rewind" and "rewind" in SFX_KINDS:
                cues.append({"kind": "rewind", "at": max(0.0, starts[i][0] - 0.3), "gain_db": -8.0})
                last = starts[i][0]
            elif beat and starts[i][0] - last >= spacing:
                kind = "whoosh" if seg.get("transition_in") not in (None, "cut") else palette[len(cues) % len(palette)]
                if v is not None and kind not in palette:
                    kind = palette[len(cues) % len(palette)]
                cues.append({"kind": kind if kind in SFX_KINDS else "whoosh", "at": max(0.0, starts[i][0] - 0.12),
                             "gain_db": -10.0})
                last = starts[i][0]
        if v:
            pay = max((i for i, s in enumerate(segs) if s.get("role") in ("payoff", "reaction", "button")),
                      default=len(segs) - 1)
            if segs:
                pa, pb = starts[pay]
                if v["drop"]:  # sound leads: riser, then the sting on the payoff
                    cues.append({"kind": "riser" if "riser" in palette else palette[0], "at": max(0.0, pa - 1.2),
                                 "gain_db": -12.0})
                    if "sting" in palette:
                        cues.append({"kind": "sting", "at": pa + 0.02, "gain_db": -9.0})
                if hold_of(segs[pay]) > 0.05 and v["hold_s"]:  # a beat on the frozen reaction
                    cues.append({"kind": "ding" if "ding" in palette else palette[0],
                                 "at": max(0.0, pb - hold_of(segs[pay]) + 0.03), "gain_db": -10.0})
                elif v["shake"] and "boom" in palette:
                    cues.append({"kind": "boom" if "boom" in palette else palette[0], "at": pa + 0.02, "gain_db": -8.0})
            keep: list[dict[str, Any]] = []  # <= 1 per 1.5 s on average and never two on top of each other
            for c in sorted(cues, key=lambda c: (c["kind"] not in ("rewind", "riser", "sting", "ding", "boom"), c["at"])):
                if len(keep) < max(1, int(D / STORY_QC["sfx_min_gap_s"])) and all(abs(c["at"] - k["at"]) >= 0.4 for k in keep):
                    keep.append(c)
            cues = sorted(keep, key=lambda c: c["at"])
        plan["sfx"] = cues

    def finalize(self, plan: dict[str, Any], moment: dict[str, Any], brief: dict[str, Any], blueprint: dict[str, Any],
                 prep: dict[str, Any], fresh: bool = True) -> dict[str, Any]:
        """Make any plan renderable and brief-compliant (poka-yoke, runs on every plan). ``fresh`` = a first plan, not a
        revision: only then are undecided titles moved off the game's subject (a revision keeps what was decided)."""
        raw_vibe = (plan or {}).get("vibe")
        plan = conform(plan, EDIT_PLAN)
        if raw_vibe not in EMOTIONS and moment.get("emotion") in EMOTIONS:
            plan["vibe"] = moment["emotion"]  # the plan did not pick a vibe: the moment's emotion is the default
        src_dur = float(prep["source_info"].get("duration") or 1e9)
        parts = story.moment_parts(moment)
        # a multi-part moment bounds the segments by EACH part (they may jump around the stream), not one envelope
        bounds: Any = (moment["start_s"], moment["end_s"]) if len(parts) == 1 else [(p["start_s"], p["end_s"]) for p in parts]
        full = sanitize_segments(plan["segments"], src_dur, bounds)
        segs = sanitize_segments(plan["segments"], src_dur, bounds, max_total=self._max_len(brief))
        if segs and full and Timeline(full).duration > Timeline(segs).duration + 0.05:
            self._remap_cues(plan, full, segs)  # the cap trimmed mid-edit: cues after the trim move with it
        if not segs:  # an unusable plan never reaches the renderer
            segs = sanitize_segments([{"src_start": a, "src_end": b, "speed": 1.0,
                                       "reframe": {"mode": "center", "x": 0.5}, "zoom": {"type": "none", "scale": 1.0},
                                       "shake": False, "transition_in": "cut", "note": ""}
                                      for a, b in prep["ranges"]], src_dur, bounds, max_total=self._max_len(brief))
        plan["segments"] = segs
        # a freeze never splits a phrase; BEFORE the clamp so a moved/extended hold still obeys the length cap, and
        # bounded by the part (an extension never leaves it)
        self._place_holds(plan, prep.get("words") or [], src_dur, [(p["start_s"], p["end_s"]) for p in parts])
        self._clamp_story_fields(plan["segments"], self._max_len(brief))
        # LAST word on time: no segment plays across a story-pack glue point, whatever moved it (slack, a hold's
        # extension, a model's range) — review 24 Nov found three paths that did
        before = list(plan["segments"])
        segs, origin = self._split_at_seams(before, moment.get("vod_map"), parts)
        if len(segs) != len(before) or any(a is not b for a, b in zip(segs, before)):
            self._retime_after_split(plan, before, segs, origin)
        self._label_segments(segs, moment)
        plan["segments"] = segs
        self._ensure_cards(plan, segs)
        info = prep["source_info"]
        det_cam, det_face = prep.get("facecam"), prep.get("facecam_face")
        for s in segs:
            rf = s.get("reframe") or {}
            if rf.get("mode") != "stack":
                continue
            # missing boxes fall back to what the face detector measured; its face box is relative to *its*
            # cam, so re-project it whenever the plan (model, human, revision) chose another cam
            # the model's / a human's crop is a decision (e.g. tight to keep chat out); the detector's own box
            # copied into the plan (heuristic plan, or a model echoing it) is still just the detector's guess
            chosen = rf.get("cam") if not same_box(rf.get("cam"), det_cam) else None
            cam = chosen or det_cam
            face = rf.get("face") or (reproject_box(det_face, det_cam, cam) if det_face and det_cam and cam else None)
            if not chosen and cam:  # only the detector's guess is inset (stream-layout pixels at its edge) and grows
                # no growth past the inset box: fit_cam_upscale grew it back over the stream layout (CP2 leak); a
                # magnification a little over the limit is only a minor lint (cam_upscale)
                inner = inset_box(cam, LAYOUT["cam_inset"])
                if info.get("width") and info.get("height"):
                    sw, sh = int(info["width"]), int(info["height"])
                    if cam_magnification(inner, sw, sh, self.ax.cfg.width, self.ax.cfg.height) > CAM_SOFT_MAX:
                        # review CP2: the inset pushed a small cam over the 3.2x major line (no fix exists for it)
                        # -> give the inset back, and only if even the raw box is too small, grow it just enough
                        inner = cam
                        if cam_magnification(cam, sw, sh, self.ax.cfg.width, self.ax.cfg.height) > CAM_SOFT_MAX:
                            inner = fit_cam_upscale(cam, sw, sh, self.ax.cfg.width, self.ax.cfg.height, CAM_SOFT_MAX)
                face = reproject_box(face, cam, inner) if face else None
                cam = inner
            rf["cam"], rf["face"] = cam, face
        for s in segs:  # a replay range outside the source renders a band with no video (and exits 0)
            bs = s.get("band_src")
            if bs:
                a = max(0.0, float(bs.get("start") or 0.0))
                b = min(src_dur, float(bs.get("end") or 0.0))
                s["band_src"] = ({"start": round(a, 3), "end": round(b, 3), "speed": float(bs.get("speed") or 1.0)}
                                 if b - a >= 0.3 else None)
        D = plan_duration(segs)  # includes the freeze-frame holds
        for o in plan["overlays"]:
            o["start"] = max(0.0, min(float(o["start"]), D - 0.3))
            o["end"] = max(o["start"] + 0.3, min(float(o["end"] or o["start"] + 2.5), D))
            for k in ("at_x", "at_y"):
                o[k] = _unit(o.get(k))
        da = plan["music"].get("drop_at")
        plan["music"]["drop_at"] = round(float(da), 2) if da is not None and 0.5 <= float(da) < D - 0.2 else None
        seen: set[tuple] = set()
        kept = []
        for o in plan["overlays"]:  # empty texts and exact duplicates never reach the screen
            key = (o.get("kind"), (o.get("text") or "").strip().lower(), round(o["start"], 1), o.get("position"))
            if key[1] and key not in seen:
                seen.add(key)
                kept.append(o)
        plan["overlays"] = kept
        for c in card_expectations(plan, parts if (moment.get("parts") or len(parts) > 1) else None, moment.get("vod_map")):  # a card never lies about time
            if not c["ok"]:
                o = c["overlay"]
                note = (f"time card '{o.get('text')}' → '{c['expected']}' (the real gap)" if c["expected"]
                        else f"time card '{o.get('text')}' removed (the parts are under a minute apart)")
                if c["expected"]:
                    o["text"] = c["expected"]
                else:
                    plan["overlays"] = [x for x in plan["overlays"] if x is not o]
                plan.setdefault("fixes", []).append({"issue_id": "story:label_mismatch", "change": note})
        if fresh:
            self._place_titles(plan, segs, prep)
        self._note_dropped_parts(plan, moment)
        plan["sfx"] = [s for s in plan["sfx"] if 0.0 <= float(s["at"]) < D][:40]
        cap = plan["captions"]
        cap["words_per_caption"] = min(6, max(1, int(cap.get("words_per_caption") or 3)))
        cap["font_scale"] = min(1.5, max(1.0, float(cap.get("font_scale") or 1.0)))  # < 1.0 sinks the cap height under the floor
        if not cap.get("enabled") and prep["moment_words"] and self._captions_required(brief):
            cap["enabled"] = True
        self.enforce_compliance(plan, brief, D)
        self._declutter(plan, D)
        return plan

    def _inset_leaks(self, segs: list[dict[str, Any]], ev: dict[str, Any], prep: dict[str, Any]) -> int:
        """Inset the cam crop of each segment the lint measured leaking, by that segment's own depth per edge. The depth is
        in OUTPUT px; the band shows a centred window of the crop (scale to fill, then crop), so it is converted through
        the real scale into source px and measured from the window's edge. A crop that would be magnified past
        cam_max_upscale_major is left alone (the lint then keeps flagging it: that is the floor, not an endless loop)."""
        W, info = float(ev.get("width") or self.ax.cfg.width), prep.get("source_info") or {}
        sw, sh = float(info.get("width") or 1920), float(info.get("height") or 1080)
        starts = segment_starts(segs)
        done = 0
        for rec in ev.get("segments") or []:
            i = next((k for k, (a, _) in enumerate(starts) if abs(a - float(rec["t"])) <= 0.15), None)
            rf = (segs[i].get("reframe") or {}) if i is not None else {}
            cam, edges, band = rf.get("cam"), rec.get("edges") or {}, float(rec.get("band") or 0)
            if rf.get("mode") != "stack" or not _valid_cam(cam) or not edges or band <= 0:
                continue
            x0, y0 = float(cam["x"]) * sw, float(cam["y"]) * sh
            cw, ch = float(cam["w"]) * sw, float(cam["h"]) * sh
            k = max(W / cw, band / ch)  # output px per source px
            vw, vh = W / k, band / k  # the visible window (source px), centred in the crop
            wx0, wy0 = x0 + (cw - vw) / 2, y0 + (ch - vh) / 2
            wx1, wy1 = wx0 + vw, wy0 + vh
            m = 0.01  # margin: 1% of the window
            nx0, ny0, nx1, ny1 = x0, y0, x0 + cw, y0 + ch
            if "top" in edges:
                ny0 = max(ny0, wy0 + edges["top"] / k + m * vh)
            if "bottom" in edges:
                ny1 = min(ny1, wy1 - edges["bottom"] / k - m * vh)
            if "left" in edges:
                nx0 = max(nx0, wx0 + edges["left"] / k + m * vw)
            if "right" in edges:
                nx1 = min(nx1, wx1 - edges["right"] / k - m * vw)
            new = {"x": round(nx0 / sw, 3), "y": round(ny0 / sh, 3), "w": round((nx1 - nx0) / sw, 3),
                   "h": round((ny1 - ny0) / sh, 3)}
            if new["w"] <= 0.02 or new["h"] <= 0.02:
                continue
            top_px, _ = stack_layout(new, int(sw), int(sh), int(W), self.ax.cfg.height)
            if max(W / (new["w"] * sw), top_px / (new["h"] * sh)) > LAYOUT["cam_max_upscale_major"]:
                continue
            if rf.get("face"):
                rf["face"] = reproject_box(rf["face"], cam, new)
            rf["cam"] = new
            done += 1
        return done

    @staticmethod
    def _readd_parts(segs: list[dict[str, Any]], ev: dict[str, Any]) -> list[str]:
        """The reviewer flagged story:arc_dropped: play each missing part again, in its play position (after the last
        segment of an earlier part), as a plain cut; the card and the label come from finalize."""
        sp = list(ev.get("seg_parts") or [])
        if len(sp) != len(segs):
            sp = [-1] * len(segs)  # stale evidence: the missing parts go to the end, in order
        added = []
        for m in sorted(ev.get("missing") or [], key=lambda m: m["k"]):
            if not segs:
                break
            at = next((i for i, k in enumerate(sp) if k > m["k"]), len(segs))
            a, b = float(m["start_s"]), float(m["end_s"])
            if m.get("role") in ("payoff", "reaction", "button", "cold_open") and b - a > 12.0:
                a = b - 12.0  # a long payoff keeps its tail; finalize's cap trims the rest
            else:
                b = min(b, a + 12.0)
            base = copy.deepcopy(segs[min(max(at - 1, 0), len(segs) - 1)])
            base.update({"src_start": round(a, 3), "src_end": round(b, 3), "role": m.get("role") or "build", "hold": 0.0,
                         "transition_in": "cut", "band_src": None, "label": "", "note": "arc part re-added",
                         "zoom": {"type": "none", "scale": 1.0, "fx": None, "fy": None}, "shake": False})
            segs.insert(at, base)
            sp.insert(at, m["k"])
            added.append(m.get("label") or f"part {m['k'] + 1}")
        return added

    def _place_titles(self, plan: dict[str, Any], segs: list[dict[str, Any]], prep: dict[str, Any]) -> None:
        """Mandor CP2 #3: a stacked title lands right under the seam; when the game's subject (a head found in the
        source frames) sits in the top of the visible gameplay band, an UNDECIDED title (position 'center' = the default
        under the seam) goes to the bottom. Never touches a title someone already placed (model / human / a fix: any
        other position, or a `layout:title_over_subject` entry in `fixes`), so it is idempotent and never fights the fix
        library. ponytail: one median subject for the whole clip, not tracked over time."""
        subject = prep.get("game_subject")
        stack = next((s["reframe"] for s in segs if (s.get("reframe") or {}).get("mode") == "stack"), None)
        info = prep.get("source_info") or {}
        if not subject or stack is None or any(f.get("issue_id") == "layout:title_over_subject"
                                               for f in plan.get("fixes") or []):
            return
        sc = min(1.5, max(1.0, float(stack.get("scale") or 1.0)))
        gh = 1.0 / sc
        y = 0.5 if stack.get("y") is None else float(stack["y"])
        top = min(max(y - gh / 2, 0.0), 1.0 - gh)
        cy = (float(subject["cy"]) - top) / gh  # where the subject sits in the visible band (0 = top, 1 = bottom)
        if not 0.0 <= cy < LAYOUT["title_subject_top_share"]:
            return
        sw, sh = float(info.get("width") or 0), float(info.get("height") or 0)
        if sw and sh and _valid_cam(stack.get("cam")):  # the visible gameplay crop is narrower than the source
            _, bottom = stack_layout(stack["cam"], int(sw), int(sh), self.ax.cfg.width, self.ax.cfg.height)
            gw = min(gh * sh * self.ax.cfg.width / bottom, sw)
            x0 = min(max(float(stack.get("x") if stack.get("x") is not None else 0.5) * sw - gw / 2, 0.0), sw - gw)
            if not x0 / sw <= float(subject.get("cx", 0.5)) <= (x0 + gw) / sw:
                return  # the head is outside the crop: nothing on screen to avoid
        moved = []
        for o in plan["overlays"]:
            if o.get("kind") in ("hook_title", "punch_title") and o.get("position") in (None, "", "center"):
                o["position"] = "bottom"
                moved.append(o["kind"])
        if moved:
            plan.setdefault("fixes", []).append({"issue_id": "layout:title_over_subject", "change": (
                f"{', '.join(moved)} → bottom of the gameplay band (the game's subject is in its top, y {cy:.0%})")})

    @staticmethod
    def _note_dropped_parts(plan: dict[str, Any], moment: dict[str, Any]) -> None:
        """Mandor CP2 #4: an arc part the plan does not play is never silently dropped: it is named in `rationale` (NOT in
        `fixes`: nothing was fixed) and the lint (story:arc_dropped) judges it; the fix library re-adds the part when the
        reviewer flags it. No footage is added here: the plan is the model's."""
        arc = arc_coverage(plan, moment)
        if not arc:
            return
        parts, _, played, _ = arc
        for k, part in enumerate(parts):
            note = f"[arc part {k + 1} ({part.get('label') or part.get('role')}) is not played]"
            if k not in played and note not in (plan.get("rationale") or ""):
                plan["rationale"] = f"{plan.get('rationale') or ''} {note}".strip()

    @staticmethod
    def _place_holds(plan: dict[str, Any], words: list[dict[str, Any]], src_dur: float = 1e9,
                     bounds: list[tuple[float, float]] | None = None) -> None:
        """CP1 (mandor): a freeze-frame hold sits at the END of its segment; when that end falls inside a phrase (word
        gap < STORY_QC['phrase_gap_s'] in one sentence, or inside a word) the beat splits the line ("Fuck… [hold] you").
        Move it: to the end of the finished phrase (splitting the segment that holds it), else extend the segment to
        the phrase end, else back to the phrase start (the jaw-drop), else drop the hold. Idempotent; the cues
        (text, SFX, music drop) ride with the picture they were placed on.
        ponytail: phrase = pause < 0.25 s, no sentence end; no semantic parsing. A cue exactly on a hold START stays."""
        segs = plan.get("segments") or []
        if not words or not any(hold_of(s) > 0.05 for s in segs):
            return
        def edge(s: dict[str, Any]) -> float:  # the end of the part this segment plays in: an extension never leaves it
            return max((b for a, b in bounds or [] if a - 0.05 <= float(s["src_start"]) < b), default=1e9)

        old = Timeline(segs)
        for k, s in enumerate(segs):
            s["_o"] = k
        moved: dict[int, dict[str, Any]] = {}  # old segment index → the segment object that now holds its freeze
        i = 0
        while i < len(segs):
            s, h = segs[i], hold_of(segs[i])
            ph = phrase_around(words, float(s["src_end"])) if h > 0.05 else None
            if ph is None:
                i += 1
                continue
            ps, pe = ph
            j = i + 1
            while j < len(segs) and abs(float(segs[j]["src_start"]) - float(segs[j - 1]["src_end"])) <= 0.3:
                if float(segs[j]["src_start"]) < pe <= float(segs[j]["src_end"]) + 0.03:
                    break  # this segment plays the end of the phrase
                j += 1
            else:
                j = len(segs)
            if j < len(segs) and abs(float(segs[i + 1]["src_start"]) - float(s["src_end"])) <= 0.3:
                cut = round(min(pe + 0.03, float(segs[j]["src_end"])), 3)
                tgt = segs[j]
                if cut < float(tgt["src_end"]) - 0.15 and cut > float(tgt["src_start"]) + 0.1:
                    tail = {**copy.deepcopy(tgt), "src_start": cut, "transition_in": "cut", "shake": False,
                            "zoom": {**(tgt.get("zoom") or {}), "type": "none"}}  # the tail keeps tgt's own hold
                    tgt["src_end"], tgt["hold"] = cut, round(h, 2)
                    segs.insert(j + 1, tail)
                else:
                    tgt["hold"] = round(max(hold_of(tgt), h), 2)
                s["hold"] = 0.0
                moved[s["_o"]] = tgt
            elif pe - float(s["src_end"]) <= 1.5 and float(s["src_end"]) < pe + 0.03 <= min(src_dur, edge(s)) and (
                    i + 1 >= len(segs) or not float(s["src_end"]) < float(segs[i + 1]["src_start"]) <= pe + 0.03):
                s["src_end"] = round(pe + 0.03, 3)  # the phrase finishes, THEN the beat
            elif ps - float(s["src_start"]) >= 0.3 and float(s["src_end"]) - (ps - 0.02) <= h + 1e-6:
                s["src_end"] = round(ps - 0.02, 3)  # the jaw-drop (never drops more footage than the hold is long)
            else:
                s["hold"] = 0.0  # no safe place: the beat goes, the footage stays
                plan.setdefault("fixes", []).append({"issue_id": "pacing:freeze_in_phrase",
                                                     "change": f"{h:.2f}s hold dropped: no safe spot inside a long phrase"})
            i += 1
        new = Timeline(segs)
        if (len(new.placed) != len(old.placed) or any(
                abs(a.out_start - b.out_start) > 1e-6 or abs(a.hold - b.hold) > 1e-6 for a, b in zip(old.placed, new.placed))):
            Editor._retime_cues(plan, old, new, moved)
        for s in segs:
            s.pop("_o", None)

    @staticmethod
    def _split_at_seams(segs: list[dict[str, Any]], vod_map: list[dict[str, Any]] | None,
                        parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """sanitize_segments' 1.5 s slack can carry a segment over a story-pack glue point (file_start / file_end of a
        vod_map piece): cut it there and keep only the pieces that play inside a part (>= 0.25 s); the hold rides on
        the last kept piece."""
        if not vod_map:
            return segs, list(range(len(segs)))
        seams = sorted({float(p["file_end"]) for p in vod_map} | {float(p["file_start"]) for p in vod_map})
        out: list[dict[str, Any]] = []
        origin: list[int] = []
        for i, s in enumerate(segs):
            a, b = float(s["src_start"]), float(s["src_end"])
            cuts = [a] + [t for t in seams if a + 1e-6 < t < b - 1e-6] + [b]
            if len(cuts) == 2:
                out.append(s)
                origin.append(i)
                continue
            # each piece plays only if it is real footage of a part (>= 1 s: no flash of another hour) and no OTHER
            # segment already plays it (review 24 Nov: a [60,61.2] sliver repeated the next segment's footage). The
            # jump between pieces gets its label + card below, so it never reads as continuous.
            others = [(float(o["src_start"]), float(o["src_end"])) for j, o in enumerate(segs) if j != i]
            kept = [(x, y) for x, y in zip(cuts, cuts[1:])
                    if max((min(y, p["end_s"]) - max(x, p["start_s"]) for p in parts), default=y - x) >= SEAM_MIN_PIECE_S
                    and not any(min(y, oe) - max(x, os_) > 0.5 * (y - x) for os_, oe in others)]
            for k, (x, y) in enumerate(kept):
                piece = copy.deepcopy(s)
                piece["src_start"], piece["src_end"] = round(x, 3), round(y, 3)
                if k:
                    piece.update(transition_in="cut", shake=False)
                    piece["zoom"] = {**(s.get("zoom") or {}), "type": "none"}
                if k < len(kept) - 1:
                    piece["hold"] = 0.0
                out.append(piece)
                origin.append(i)
        return out, origin

    @staticmethod
    def _retime_after_split(plan: dict[str, Any], before: list[dict[str, Any]], after: list[dict[str, Any]],
                            origin: list[int]) -> None:
        """Cues keep their spot on the picture when the seam pass trimmed or dropped footage: a cue inside kept
        footage follows it, a cue inside trimmed footage snaps to the nearest kept edge of the same segment."""
        old, new = Timeline(before), Timeline(after)

        def move(t: Any) -> Any:
            if t is None:
                return None
            p = old.segment_at(float(t))
            if p is None:
                return t
            src = p.src_start + max(0.0, float(t) - p.out_start) * p.speed
            mine = [q for q in new.placed if origin[q.index] == p.index]
            if not mine:  # the whole segment went: the cue lands where the next kept footage starts
                later = [q for q in new.placed if origin[q.index] > p.index]
                return round(later[0].out_start if later else new.duration, 3)
            for q in mine:
                if q.src_start - 1e-6 <= src <= q.src_end + 1e-6:
                    return round(q.out_start + (src - q.src_start) / q.speed, 3)
            q = min(mine, key=lambda q: min(abs(src - q.src_start), abs(src - q.src_end)))
            return round(q.out_start if src < q.src_start else q.out_end, 3)

        for cue in plan.get("sfx") or []:
            cue["at"] = move(cue.get("at"))
        for o in plan.get("overlays") or []:
            if float(o.get("start") or 0) <= 0.05:
                continue
            o["start"] = move(o["start"])
            if o.get("end") is not None and float(o["end"]) < old.duration - 0.05:
                o["end"] = move(o["end"])
        music = plan.get("music") or {}
        if music.get("drop_at") is not None:
            music["drop_at"] = move(music["drop_at"])

    @staticmethod
    def _ensure_cards(plan: dict[str, Any], segs: list[dict[str, Any]]) -> None:
        """A jump of minutes or hours is never shown as continuous footage: every segment that opens a labelled
        part gets a time card at its start unless the plan already has one there (any text — the card check below
        corrects a wrong one)."""
        tl = Timeline(segs)
        for p in tl.placed:
            label = (segs[p.index].get("label") or "").strip()
            if not label:
                continue
            if any(o.get("kind") == "time_card" and abs(float(o.get("start") or 0) - p.out_start) <= 0.6
                   for o in plan.get("overlays") or []):
                continue
            plan.setdefault("overlays", []).append({
                "kind": "time_card", "text": label, "start": round(p.out_start, 3),
                "end": round(min(tl.duration, p.out_start + 1.0), 3), "position": "center", "style": "slide",
                "emphasis": "", "align": "center", "box": False, "at_x": None, "at_y": None})

    @staticmethod
    def _label_segments(segs: list[dict[str, Any]], moment: dict[str, Any]) -> None:
        """The first segment of every part after the opening carries that part's true time-jump label (the rewind
        pill); every other segment ''."""
        lp = story.label_parts(story.moment_parts(moment), moment.get("vod_map"))
        prev = None
        for i, s in enumerate(segs):
            a, b = float(s["src_start"]), float(s["src_end"])
            idx = max(range(len(lp)), key=lambda k: min(b, lp[k]["end_s"]) - max(a, lp[k]["start_s"]))
            ok = min(b, lp[idx]["end_s"]) - max(a, lp[idx]["start_s"]) > 0
            s["label"] = lp[idx]["label"] if (i and ok and idx != prev) else ""
            prev = idx

    @staticmethod
    def _retime_cues(plan: dict[str, Any], old: Timeline, new: Timeline, moved: dict[int, dict[str, Any]]) -> None:
        """Cues placed on the old timeline keep their spot ON THE PICTURE: same source frame in the same segment (pieces
        of a split one included); a cue inside a freeze follows that freeze, also when it was moved."""
        pieces: dict[int, list[Any]] = {}
        for p in new.placed:
            pieces.setdefault(new.segments[p.index]["_o"], []).append(p)

        def move(t: Any) -> Any:
            if t is None:
                return None
            t = float(t)
            p = old.segment_at(t)
            if p is None:
                return t
            mine = pieces.get(p.index) or []
            if p.hold > 0.05 and t >= p.play_end - 1e-6:  # inside the freeze
                tgt = moved.get(p.index)
                q = next((q for q in new.placed if new.segments[q.index] is tgt), None) if tgt is not None else (
                    mine[-1] if mine and mine[-1].hold > 0.05 else None)
                if q is None:
                    return round(min(t, new.duration), 3)
                return round(q.play_end + min(t - p.play_end, max(q.hold, 0.0)), 3)
            src = p.src_start + (t - p.out_start) * p.speed
            for q in mine:
                if q.src_start - 1e-6 <= src <= q.src_end + 1e-6:
                    return round(q.out_start + (src - q.src_start) / q.speed, 3)
            return round(min(t, new.duration), 3)  # that bit of picture was trimmed away

        for cue in plan.get("sfx") or []:
            cue["at"] = move(cue.get("at"))
        for o in plan.get("overlays") or []:
            if float(o.get("start") or 0) <= 0.05:
                continue  # frame-0 text keeps its own timing
            o["start"] = move(o["start"])
            if o.get("end") is not None and float(o["end"]) < old.duration - 0.05:
                o["end"] = move(o["end"])
        music = plan.get("music") or {}
        if music.get("drop_at") is not None:
            music["drop_at"] = move(music["drop_at"])

    @staticmethod
    def _clamp_story_fields(segs: list[dict[str, Any]], max_s: float) -> None:
        """Ranges the renderer relies on: first frame is a plain cut, hold 0-1.2 s, zoom focus and crop 0-1; the
        holds count toward the length limit (they are shed before footage is cut)."""
        if segs:
            segs[0]["transition_in"] = "cut"
        for s in segs:
            try:
                s["hold"] = round(min(STORY_QC["hold_max_s"], max(0.0, float(s.get("hold") or 0.0))), 2)
            except (TypeError, ValueError):
                s["hold"] = 0.0
            z = dict(s.get("zoom") or {})
            z["fx"], z["fy"] = _unit(z.get("fx")), _unit(z.get("fy"))
            s["zoom"] = z
            rf = dict(s.get("reframe") or {})
            if rf.get("scale") is not None:
                rf["scale"] = round(min(1.5, max(1.0, float(rf["scale"]))), 3)
            rf["y"] = _unit(rf.get("y"))
            s["reframe"] = rf
        over = plan_duration(segs) - max_s
        for s in reversed(segs):
            if over <= 0.0:
                break
            cut = min(float(s["hold"]), over)
            s["hold"] = round(float(s["hold"]) - cut, 2)
            over -= cut
        if over > 0.05 and segs:  # still too long: shorten the last piece of footage
            s = segs[-1]
            s["src_end"] = round(max(s["src_start"] + 0.3, s["src_end"] - over * float(s.get("speed") or 1.0)), 3)

    @staticmethod
    def _remap_cues(plan: dict[str, Any], before: list[dict[str, Any]], after: list[dict[str, Any]]) -> None:
        """Output-time cues (SFX, text, music drop) were placed on the uncapped edit. The length cap trims
        segments in the middle (setup first, payoff last), so every cue keeps its offset inside ITS segment."""
        old, new = Timeline(before), Timeline(after)

        def move(t: Any) -> Any:
            if t is None:
                return None
            p = old.segment_at(float(t))
            if p is None:
                return t
            if p.index >= len(new.placed):
                return new.duration
            q = new.placed[p.index]
            return round(q.out_start + min(float(t) - p.out_start, max(0.0, q.out_duration - 0.05)), 3)

        for cue in plan.get("sfx") or []:
            cue["at"] = move(cue.get("at"))
        for o in plan.get("overlays") or []:
            if float(o.get("start") or 0) <= 0.05:  # frame-0 text (hook title, watermark) keeps its own timing
                continue
            o["start"] = move(o["start"])
            if o.get("end") is not None and float(o["end"]) < old.duration - 0.05:  # whole-clip labels keep running
                o["end"] = move(o["end"])
        music = plan.get("music") or {}
        if music.get("drop_at") is not None:
            music["drop_at"] = move(music["drop_at"])

    @staticmethod
    def _declutter(plan: dict[str, Any], duration: float) -> None:
        """Text layers must not stack on one strip: a persistent bottom label (watermark) lifts
        lower captions to the centre, and titles/beats never share the captions' strip. On stacked
        segments the renderer puts captions on the cam/gameplay seam (≈ the `upper` strip)."""
        cap = plan["captions"]
        if not cap.get("enabled"):
            return
        modes = {(s.get("reframe") or {}).get("mode") for s in plan["segments"]}
        # a lifted talking head (reframe.scale > 1) fills the top and middle: the chest strip is the only free one
        lifted = any(float((s.get("reframe") or {}).get("scale") or 1.0) > 1.0 for s in plan["segments"])
        if cap.get("position") == "lower" and any(
                o["kind"] == "label" and o.get("position") == "bottom" and o["end"] - o["start"] >= duration * 0.5
                for o in plan["overlays"]):
            if lifted and "stack" not in modes:
                # live run 4 Nov: "center" = on the lifted face; stay on the chest, one line clears the pill
                cap["words_per_caption"] = min(2, int(cap.get("words_per_caption") or 2))
                plan.setdefault("fixes", []).append({"issue_id": "house:declutter", "change": (
                    "captions stay lower (lifted face), ≤ 2 words so one line clears the watermark pill")})
            elif "stack" in modes:
                # live run 3 Nov: "center" is where stacked titles live — back to the seam, one line (≤ 2 words)
                # so the chunk can't grow up into the face
                cap["position"] = "upper"
                cap["words_per_caption"] = min(2, int(cap.get("words_per_caption") or 2))
            else:
                cap["position"] = "center"
            # a house rule changed the editor's choice: say so, or the reviewer reads the fix log as a lie
            plan.setdefault("fixes", []).append({"issue_id": "house:declutter", "change": (
                f"captions lower → {cap['position']}: the watermark pill owns the bottom strip")})
        taken = ({cap.get("position")} if modes - {"stack"} else set()) | ({"upper"} if "stack" in modes else set())
        prefs = ("center", "top", "lower") if "stack" in modes else ("upper", "top", "center")  # top = face on stack
        for o in plan["overlays"]:
            where = o.get("position") or ("top" if o["kind"] == "hook_title" else "center")  # renderer defaults
            if o["kind"] in ("hook_title", "punch_title") and where in ("lower", "bottom"):
                continue  # captions pause under a title in their strip (captions.title_holds) — no clash to fix
            if o["kind"] != "label" and where in taken:
                o["position"] = next(p for p in prefs if p not in taken)

    def enforce_compliance(self, plan: dict[str, Any], brief: dict[str, Any], duration: float) -> None:
        req = (brief or {}).get("requirements") or {}
        plan["post"] = comply_post(plan["post"], brief, plan.get("title") or "")
        disclosure = (req.get("disclosure") or "").strip()
        if disclosure and not any(disclosure.lower() in (o.get("text") or "").lower() and o["start"] <= 3.0
                                  for o in plan["overlays"]):
            plan["overlays"].append({"kind": "label", "text": disclosure, "start": 0.0,
                                     "end": min(3.0, duration), "position": "bottom", "style": "fade"})
        mark = (req.get("watermark") or "").strip()
        if mark:
            # one watermark for the whole clip: stretch an existing one (a revision may have made the clip
            # longer) and drop copies, instead of stacking a second label on top of the first
            marks = [o for o in plan["overlays"] if mark.lower() in (o.get("text") or "").lower()]
            # keep the label that says exactly the mark (a copy may carry instruction text around it)
            marks.sort(key=lambda o: (o.get("text") or "").strip().lower() != mark.lower())
            marks = [o for o in marks if o["kind"] == "label"]  # a CTA/title that names the handle is its own text
            # house style (mandor 3 Nov): bottom-left of the safe zone on a dark pill, out of the action area
            house = {"start": 0.0, "end": duration, "text": mark, "position": "bottom", "align": "left", "box": True}
            if marks:
                marks[0].update(house)
                extra = {id(o) for o in marks[1:]}
                plan["overlays"] = [o for o in plan["overlays"] if id(o) not in extra]
            else:
                plan["overlays"].append({"kind": "label", "style": "fade", **house})
        if mark and disclosure:  # the disclosure would sit on the bottom-left watermark pill
            for o in plan["overlays"]:
                if disclosure.lower() in (o.get("text") or "").lower() and o.get("position") == "bottom":
                    o["position"] = "lower"
        cta = (req.get("cta") or "").strip()
        if cta and not any(cta.lower() in (o.get("text") or "").lower() for o in plan["overlays"]):
            plan["overlays"].append({"kind": "cta", "text": cta, "start": max(0.0, duration - 3.0),
                                     "end": duration, "position": "center", "style": "pop"})
        banned = [b.lower() for b in req.get("banned") or [] if b.strip()]
        for o in plan["overlays"]:
            for b in banned:
                o["text"] = re.sub(re.escape(b), "", o["text"], flags=re.I).strip()

    # -- revising ----------------------------------------------------------------------------------------
    def revise(self, job: dict[str, Any], plan: dict[str, Any], issues: list[dict[str, Any]], moment: dict[str, Any],
               brief: dict[str, Any], blueprint: dict[str, Any], prep: dict[str, Any],
               history: list[dict[str, Any]]) -> dict[str, Any]:
        task = (
            "Revise your edit plan. Fix EVERY issue below (blockers first) and change nothing else. "
            "Return the full revised plan; in `fixes` map each issue id to what you changed.\n\n"
            f"Issues to fix:\n{dump(issues, 10000)}\n\n"
            f"Earlier rounds (what you already tried):\n{dump(history[-3:], 6000)}\n\n"
            f"Current plan:\n{dump(plan, 20000)}\n\nBrief:\n{dump(brief, 6000)}\n\nBlueprint:\n{dump(blueprint, 5000)}\n\n"
            f"Moment:\n{dump(moment, 2000)}\n\nWords with source timings:\n{self._words_text(prep['moment_words'])}"
        )
        out = self.ask(job, task, EDIT_PLAN, images=prep["sheets"][:1], campaign=self.campaign_of(job))
        if out is None:
            out = self.apply_fixes(plan, issues, prep, blueprint, brief)
        else:
            # idempotent deterministic fixes still run for measurable problems the model may have missed
            out = self.apply_fixes(out, [i for i in issues if i.get("id") in SAFE_AFTER_MODEL], prep, blueprint,
                                   brief, keep_fixes=True)
        return self.finalize(out, moment, brief, blueprint, prep, fresh=False)

    def apply_fixes(self, plan: dict[str, Any], issues: list[dict[str, Any]], prep: dict[str, Any],
                    blueprint: dict[str, Any], brief: dict[str, Any], keep_fixes: bool = False) -> dict[str, Any]:
        """The fix library: one deterministic remedy per known QC issue."""
        p = copy.deepcopy(plan)
        fixes = list(p.get("fixes") or []) if keep_fixes else []
        segs = p["segments"]
        tl = Timeline(sanitize_segments(segs, 1e9))
        punch = float((blueprint.get("motion") or {}).get("punch_scale") or 1.12)

        def note(iid: str, change: str) -> None:
            fixes.append({"issue_id": iid, "change": change})

        def shift_cues(a: float, b: float) -> None:
            """Output time [a, b] was removed: later SFX/text move earlier with the picture."""
            cut = b - a
            for cue in p["sfx"]:
                t = float(cue["at"])
                cue["at"] = round(t - cut if t >= b else (a if t > a else t), 3)
            for o in p["overlays"]:
                for key in ("start", "end"):
                    t = float(o[key])
                    o[key] = round(t - cut if t >= b else (a if t > a else t), 3)

        # Timecoded fixes run latest-first: cutting late material never shifts earlier timecodes.
        ordered = sorted(issues, key=lambda i: -(i.get("timecode_s") if i.get("timecode_s") is not None else -1))
        for iss in ordered:
            iid = iss.get("id") or ""
            tc = iss.get("timecode_s")
            ev = iss.get("evidence") if isinstance(iss.get("evidence"), dict) else {}
            if iid == "pacing:dead_air" and tc is not None:
                a = float(ev.get("start", tc)) + 0.12
                b = float(ev.get("end", float(tc) + 1.0)) - 0.12
                if b - a > 0.1:
                    p["segments"] = segs = remove_output_range(segs, a, b)
                    shift_cues(a, b)
                    tl = Timeline(sanitize_segments(segs, 1e9))
                    note(iid, f"cut the measured pause {a:.2f}-{b:.2f}s (output)")
            elif iid == "hook:silent_open" and segs:
                first_word = next((w for w in prep["words"] if w["start"] >= segs[0]["src_start"] - 0.05), None)
                if first_word and first_word["start"] - 0.1 > segs[0]["src_start"]:
                    trimmed = (first_word["start"] - 0.1 - segs[0]["src_start"]) / float(segs[0].get("speed") or 1.0)
                    segs[0]["src_start"] = round(first_word["start"] - 0.1, 3)
                    shift_cues(0.0, trimmed)
                    for o in p["overlays"]:  # text that opened the clip still opens it
                        o["end"] = max(o["end"], o["start"] + 0.5)
                    tl = Timeline(sanitize_segments(segs, 1e9))
                    note(iid, f"first segment now starts on the first word ({first_word['word']})")
            elif iid == "hook:title_long":
                for o in p["overlays"]:
                    if o["kind"] == "hook_title":
                        o["text"] = cap_chars(" ".join(str(o.get("text") or "").split()).strip())
                        if o.get("emphasis") and str(o["emphasis"]).upper() not in o["text"].upper():
                            o["emphasis"] = ""  # the cut dropped it: the last word is the emphasis again
                        note(iid, f"hook title shortened to {len(o['text'])} characters on one line")
                        break
            elif iid == "hook:slow_open":
                if not any(o["kind"] == "hook_title" for o in p["overlays"]):
                    # a lifted talking head (reframe.scale > 1) fills the top: the title goes on the chest
                    lifted = bool(segs) and float((segs[0].get("reframe") or {}).get("scale") or 1.0) > 1.0
                    p["overlays"].insert(0, {"kind": "hook_title", "text": short_hook(p.get("title", "")).upper(),
                                             "start": 0.0, "end": 2.6, "position": "lower" if lifted else "top",
                                             "style": "pop"})
                if segs:
                    segs[0]["zoom"] = {"type": "punch", "scale": punch}
                note(iid, "hook title from 0s + punch-in on the opening")
            elif iid in ("pacing:static_stretch", "visual:frozen") and tc is not None:
                at = float(tc) + 1.0
                seg = tl.segment_at(at)
                if seg is not None:
                    s = segs[seg.index]
                    mid = round((s["src_start"] + s["src_end"]) / 2, 3)
                    word = min((w for w in prep["words"] if s["src_start"] + 0.5 < w["start"] < s["src_end"] - 0.5),
                               key=lambda w: abs(w["start"] - mid), default=None)
                    cut = word["start"] if word else mid
                    if cut - s["src_start"] > 0.5 and s["src_end"] - cut > 0.5:
                        a = {**s, "src_end": cut}
                        b = {**s, "src_start": cut, "transition_in": "cut",
                             "zoom": {"type": "none" if (s["zoom"] or {}).get("type") == "punch" else "punch",
                                      "scale": punch}}
                        p["segments"] = segs = segs[:seg.index] + [a, b] + segs[seg.index + 1:]
                        tl = Timeline(sanitize_segments(segs, 1e9))
                        note(iid, f"split segment at {cut:.2f}s (source) and alternated the punch-in")
            elif iid == "captions:too_fast":
                p["captions"]["words_per_caption"] = max(1, int(p["captions"].get("words_per_caption") or 3) - 1)
                note(iid, f"captions now {p['captions']['words_per_caption']} words each")
            elif iid == "captions:missing":
                p["captions"]["enabled"] = True
                note(iid, "captions enabled")
            elif iid == "visual:black_frames":
                for s in segs:
                    if s.get("transition_in") == "fade":
                        s["transition_in"] = "cut"
                note(iid, "removed dip-to-black transitions")
            elif iid == "compliance:too_long":
                limit = self._max_len(brief)
                p["segments"] = segs = sanitize_segments(segs, 1e9, max_total=max(5.0, limit - 1.0))
                tl = Timeline(segs)
                note(iid, f"trimmed to ≤ {limit - 1:.0f}s")
            elif iid == "compliance:too_short" and segs:
                min_s = float((brief.get("clip_length") or {}).get("min_s") or self.ax.cfg.min_clip_s)
                need = min_s - tl.duration + 1.0
                nxt = [w for w in prep["words"] if w["start"] >= segs[-1]["src_end"]]
                if nxt and need > 0:
                    target = segs[-1]["src_end"] + need
                    end_w = next((w for w in nxt if w["end"] >= target and re.search(r"[.!?]$", w["word"])),
                                 nxt[min(len(nxt) - 1, int(need * 2.5))])
                    segs[-1]["src_end"] = round(end_w["end"] + 0.2, 3)
                    note(iid, f"extended the ending to {segs[-1]['src_end']:.1f}s (source)")
            elif iid.startswith("compliance:"):
                note(iid, "compliance fields re-applied from the brief")  # enforce_compliance does the work
            elif iid in ("layout:caption_lines", "layout:caption_chars"):
                p["captions"]["words_per_caption"] = max(1, int(p["captions"].get("words_per_caption") or 3) - 1)
                note(iid, f"captions now {p['captions']['words_per_caption']} words each")
            elif iid == "layout:caption_small":
                m = re.search(r"≥\s*([\d.]+)", iss.get("fix") or "")
                p["captions"]["font_scale"] = min(1.5, float(m.group(1)) if m else 1.2)
                note(iid, f"captions.font_scale → {p['captions']['font_scale']:.2f}")
            elif iid == "layout:hook_in_cam_band":
                for o in p["overlays"]:
                    if o["kind"] == "hook_title":
                        o["position"] = "center"
                note(iid, "hook title moved onto the gameplay half")
            elif iid.startswith(("layout:overlap_", "layout:gap_", "layout:over_face_")):
                # move the movable text one strip down; captions and the watermark keep their places
                kinds = iid.split(":", 1)[1].split("_", 1)[1]  # e.g. "caption_hook_title"
                mark = ((brief.get("requirements") or {}).get("watermark") or "").lower()
                order = ("top", "upper", "center", "lower")
                moved = []
                for o in p["overlays"]:
                    is_mark = bool(mark) and mark in (o.get("text") or "").lower()
                    if is_mark or o["kind"] not in kinds:
                        continue
                    where = o.get("position") or ("top" if o["kind"] == "hook_title" else "center")
                    if where in order[:-1]:
                        o["position"] = order[order.index(where) + 1]
                        moved.append(f"{o['kind']} → {o['position']}")
                if not moved and iid == "layout:over_face_caption":
                    cap = p["captions"]
                    n = int(cap.get("words_per_caption") or 3)
                    if n > 1:  # a seam caption grows UP into the face only when it wraps: keep it one line
                        cap["words_per_caption"] = n - 1
                        moved.append(f"captions {n} → {n - 1} words (one line on the seam)")
                    elif cap.get("position") in ("upper", None, ""):
                        cap["position"] = "lower"  # last resort; _declutter keeps it off the watermark strip
                        moved.append("captions → lower (gameplay band)")
                if moved:  # only claim what changed — a fix log that lies makes the reviewer loop
                    note(iid, "; ".join(moved))
            elif iid == "framing:cam_edge_foreign":
                fixed = self._inset_leaks(segs, ev, prep)
                if fixed:
                    note(iid, f"cam crop inset past the measured strip on {fixed} segment(s) (only the leaking ones)")
            elif iid == "story:arc_dropped":
                added = self._readd_parts(segs, ev)
                if added:
                    p["segments"] = segs = sanitize_segments(segs, 1e9)
                    tl = Timeline(segs)
                    note(iid, f"played the missing arc part(s) again: {', '.join(added)}")
            elif iid == "layout:title_over_subject":
                low = float(ev.get("face_cy") if ev.get("face_cy") is not None else 0.5) >= LAYOUT["title_subject_top_share"]
                moved = []
                for o in p["overlays"]:
                    if o.get("kind") in ("hook_title", "punch_title"):
                        o["position"] = "center" if low else "bottom"
                        moved.append(o["kind"])
                if moved:
                    note(iid, f"{', '.join(moved)} → {'under the seam' if low else 'bottom'} of the gameplay band, off the subject")
            elif iid == "captions:speaker_style":
                n = 0
                for s in segs:
                    ws = [w["word"] for w in prep["words"] if s["src_start"] - 0.05 <= w["start"] < s["src_end"]]
                    v = voice_of(" ".join(ws)) if len(ws) >= 3 else "streamer"
                    if v != (s.get("voice") or "streamer"):
                        s["voice"], n = v, n + 1
                if n:
                    note(iid, f"segment.voice set on {n} segment(s) from the transcript")
            elif iid == "pacing:freeze_in_phrase":
                note(iid, "the freeze moves off the phrase (finalize places it before the line or after it is finished)")
            elif iid == "pacing:effect_repeat":
                self._break_runs(segs)
                note(iid, "broke up the repeated transition/zoom with plain cuts")
            elif iid == "visual:flash_rate":
                kept: list[float] = []
                for s, (t0, _) in zip(segs, segment_starts(segs)):  # greedy: <= 3 flashes in any 1 s; idempotent
                    if s.get("transition_in") == "flash":
                        if sum(1 for u in kept if t0 - 1.0 < u <= t0) >= STORY_QC["max_flash_per_s"]:
                            s["transition_in"] = "cut"
                        else:
                            kept.append(t0)
                note(iid, "thinned the flash transitions (strobing)")
            elif iid == "audio:sfx_density":
                D = plan_duration(segs)
                keep = max(1, int(D / STORY_QC["sfx_min_gap_s"]))
                big = ("rewind", "riser", "sting", "ding", "boom")  # story cues outlive the filler ones
                ranked = sorted(p["sfx"], key=lambda c: (c["kind"] not in big, c["at"]))[:keep]
                p["sfx"] = sorted(ranked, key=lambda c: c["at"])
                note(iid, f"kept {len(p['sfx'])} SFX on the story beats (≤ 1 per {STORY_QC['sfx_min_gap_s']}s)")
            elif iid == "visual:palette":
                v = vibe(p.get("vibe"))
                for s in segs:
                    if s.get("transition_in") in v["no_transitions"]:
                        s["transition_in"] = "cut"
                    if s.get("shake") and not v["shake"]:
                        s["shake"] = False
                p["sfx"] = [c for c in p["sfx"] if c["kind"] not in v["no_sfx"]]
                for k in v["no_fx"]:
                    p.setdefault("fx", {})[k] = False
                note(iid, f"effects brought back inside the '{p.get('vibe')}' palette")
            elif iid == "hook:frame0":
                if segs:
                    segs[0]["transition_in"] = "cut"
                    if not any(o["kind"] in ("hook_title", "punch_title") and float(o["start"]) <= STORY_QC["frame0_window_s"]
                               for o in p["overlays"]):
                        p["overlays"].insert(0, {"kind": "hook_title", "text": short_hook(p.get("title", "")).upper(),
                                                 "start": 0.0, "end": 2.6, "position": "top", "style": "pop"})
                note(iid, "hook title from the first frame on a plain cut")
            elif iid == "story:fade_ending":
                if len(segs) > 1 and segs[-1].get("transition_in") == "fade":
                    segs[-1]["transition_in"] = "cut"
                note(iid, "the last beat now cuts in (no fade to black)")
            elif iid == "story:label_mismatch":
                note(iid, "time cards re-written from the real gap")  # finalize recomputes every card
            elif iid == "audio:loudness" or iid == "audio:true_peak":
                for cue in p["sfx"]:
                    cue["gain_db"] = min(float(cue.get("gain_db") or -8.0), -10.0)
                p["music"]["gain_db"] = min(float(p["music"].get("gain_db") or -18.0), -20.0)
                note(iid, "lowered SFX/music so normalisation stays linear")
        p["fixes"] = fixes
        return p

    # -- rendering ----------------------------------------------------------------------------------------
    def render(self, job: dict[str, Any], plan: dict[str, Any], source: Path, words: list[dict[str, Any]],
               version: int) -> RenderResult:
        cfg = self.ax.cfg
        work = self.ax.job_dir(job)
        music = self.resolve_music(plan) if (plan.get("music") or {}).get("enabled") else None
        if (plan.get("music") or {}).get("enabled") and music is None:
            self.store.log(job["id"], self.name, "music_missing",
                           f"no music found for mood '{plan['music'].get('mood')}' — rendering without a bed")
        kinds = {c["kind"] for c in plan.get("sfx") or []}
        sfx = {k: sfx_file(k, cfg.assets_dir, cfg.root / "cache" / "sfx") for k in kinds}
        spec = RenderSpec(width=cfg.width, height=cfg.height, fps=cfg.fps, platform=cfg.platform,
                          target_lufs=cfg.target_lufs)
        out = work / f"render_v{version}.mp4"
        return Renderer(spec, fonts_dir=cfg.fonts_dir).render(plan, source, out, work / "render_work", words,
                                                              music_path=music, sfx_paths=sfx)

    def resolve_music(self, plan: dict[str, Any]) -> Path | None:
        m = plan.get("music") or {}
        asset = (m.get("asset") or "").strip()
        bank = self.ax.bank
        if asset:
            if asset.startswith("noze:") and bank is not None:
                a = bank.db.get_asset(asset[5:])
                if a and a.get("blob_key") and a.get("usage") in ("free", "credit", "own"):
                    return bank.storage.local_path(a["blob_key"])
            elif Path(asset).exists():
                return Path(asset)
        mood = set(re.findall(r"[a-z]+", (m.get("mood") or "").lower()))
        folder = self.ax.cfg.assets_dir / "music"
        files = sorted(p for p in folder.glob("**/*") if p.suffix.lower() in AUDIO_EXT) if folder.exists() else []
        if files:
            scored = sorted(files, key=lambda p: -len(mood & set(re.findall(r"[a-z]+", str(p.relative_to(folder)).lower()))))
            return scored[0]
        if bank is not None and mood:
            try:
                from ...db import Filters

                hits = bank.db.fts_search(sorted(mood), Filters(kinds={"audio"}, usages={"free", "credit", "own"}),
                                          limit=30)
                rows = bank.db.get_assets([h[0] for h in hits])
                for aid, _ in hits:
                    a = rows.get(aid)
                    if a and a.get("blob_key") and (a.get("duration") or 0) >= 20:
                        return bank.storage.local_path(a["blob_key"])
            except Exception as exc:  # pragma: no cover
                log.info("bank music lookup failed: %s", exc)
        return None

    # -- helpers ------------------------------------------------------------------------------------------
    def _max_len(self, brief: dict[str, Any]) -> float:
        b = (brief or {}).get("clip_length") or {}
        return float(b.get("max_s") or self.ax.cfg.max_clip_s)

    def _captions_required(self, brief: dict[str, Any]) -> bool:
        other = " ".join((brief.get("requirements") or {}).get("other") or []).lower()
        return "caption" in other or "subtitle" in other

    def _music_menu(self) -> str:
        folder = self.ax.cfg.assets_dir / "music"
        names = [p.stem for p in sorted(folder.glob("**/*")) if p.suffix.lower() in AUDIO_EXT][:30] \
            if folder.exists() else []
        return ", ".join(names) or "(no local tracks; a mood keyword searches the NOZE bank)"

    @staticmethod
    def _words_text(words: list[dict[str, Any]], limit: int = 1200) -> str:
        return " ".join(f"[{w['start']:.2f}]{w['word']}" for w in words[:limit]) or "(no transcript)"
