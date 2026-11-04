"""Senior editor: writes the edit plan (EDL), revises it against review notes, renders it."""

from __future__ import annotations

import copy
import logging
import re
from pathlib import Path
from typing import Any

from ..media import faces
from ..media.analyze import contact_sheets, extract_frames
from ..media.render import Renderer, RenderResult, RenderSpec, stack_layout
from ..media.sfx import AUDIO_EXT, sfx_file
from ..media.timeline import Timeline, jump_cut, remove_output_range, sanitize_segments
from ..media.transcribe import all_words, words_between
from ..schemas import EDIT_PLAN, SFX_KINDS, conform, example
from ..standards import LAYOUT
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
                    "audio:loudness", "audio:true_peak", "compliance:too_long"}


_LIMP_TAIL = {"the", "a", "an", "to", "of", "and", "but", "or", "because", "so", "it", "it's", "is", "my", "your",
              "with", "for", "in", "on", "at", "that", "this", "yang", "dan", "di", "ke", "itu"}


def short_hook(text: str, max_words: int = 7) -> str:
    words = re.sub(r"\s+", " ", text or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words).rstrip(",;:")
    head = words[:max_words]
    clause = max((i for i, w in enumerate(head) if w[-1:] in ",.!?;:"), default=-1)
    if clause >= 2:  # end on a clause boundary when there is one
        return " ".join(head[:clause + 1]).rstrip(",;:")
    while len(head) > 3 and head[-1].lower().strip(",.") in _LIMP_TAIL:  # never end on "to"/"the"…
        head.pop()
    return " ".join(head).rstrip(",;:") + "…"


def requires_facecam(brief: dict[str, Any]) -> bool:
    other = " ".join(((brief or {}).get("requirements") or {}).get("other") or []).lower()
    return "facecam" in other or "face cam" in other or "webcam" in other


def comply_post(post: dict[str, Any], brief: dict[str, Any], fallback_caption: str = "") -> dict[str, Any]:
    """Required hashtags, mentions and disclosure in the post copy — re-applied on every
    plan and again at delivery, so no later step (or model) can drop them."""
    req = (brief or {}).get("requirements") or {}
    post = dict(post or {})
    tags = list(post.get("hashtags") or [])
    have = {t.lower().lstrip("#") for t in tags}
    for t in req.get("hashtags") or []:
        if t.lower().lstrip("#") not in have:
            tags.append(t)
            have.add(t.lower().lstrip("#"))
    post["hashtags"] = [t if t.startswith("#") else f"#{t}" for t in tags if t.strip("# ")]
    caption = post.get("caption") or fallback_caption
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


class Editor(Role):
    name = "editor"

    # -- inputs ---------------------------------------------------------------------------------------
    def prepare(self, job: dict[str, Any], source: Path, moment: dict[str, Any], transcript: dict[str, Any],
                blueprint: dict[str, Any], source_info: dict[str, Any]) -> dict[str, Any]:
        work = self.ax.job_dir(job)
        words = all_words(transcript)
        a, b = float(moment["start_s"]), float(moment["end_s"])
        pacing = blueprint.get("pacing") or {}
        max_gap = float(pacing.get("remove_silences_over_s") or 0.45)
        ranges = jump_cut(words, a, b, max_gap=max(0.25, max_gap), cut_fillers=bool(pacing.get("cut_fillers", True)))
        ranges = split_long(ranges, words, float(pacing.get("target_shot_s") or 2.8))
        times = [round(a + (b - a) * (i + 0.5) / 8, 2) for i in range(8)]
        sheets: list[str] = []
        sx = cam = None
        try:
            frames = extract_frames(source, times, work / "moment_frames", width=1280)  # big enough for facecams
            sheets = [str(p) for p in contact_sheets(frames, times, work / "moment_sheet")]
            sx = faces.subject_x(frames)
            cam = faces.facecam_box(frames)
        except Exception as exc:  # frames are a nice-to-have for framing decisions
            log.info("moment frames unavailable: %s", exc)
        face = cam.pop("face", None) if cam else None
        return {"words": words, "moment_words": words_between(transcript, a, b), "ranges": ranges,
                "sheets": sheets, "subject_x": sx, "facecam": cam, "facecam_face": face,
                "source_info": source_info}

    # -- planning -----------------------------------------------------------------------------------------
    def plan(self, job: dict[str, Any], moment: dict[str, Any], brief: dict[str, Any], blueprint: dict[str, Any],
             prep: dict[str, Any]) -> dict[str, Any]:
        cfg = self.ax.cfg
        max_s = self._max_len(brief)
        task = (
            f"Write the edit plan for this clip.\n\nBrief:\n{dump(brief, 8000)}\n\nBlueprint:\n{dump(blueprint, 8000)}\n\n"
            f"Moment (source seconds):\n{dump(moment, 3000)}\n\nSource: {prep['source_info'].get('width')}x"
            f"{prep['source_info'].get('height')} @ {prep['source_info'].get('fps')}fps, "
            f"duration {prep['source_info'].get('duration')}s. Detected speaker x (0-1, may be null): {prep['subject_x']}\n"
            f"Detected facecam overlay (source fractions, may be null): {prep.get('facecam')}; "
            f"face inside it (fractions of the cam): {prep.get('facecam_face')} — check both against the frames; "
            "for stack mode set reframe.cam and reframe.face to what you see.\n"
            f"Target: {cfg.width}x{cfg.height}, max length {max_s:.0f}s.\n\n"
            f"Suggested tight cut (pauses/fillers removed), source seconds:\n{dump(prep['ranges'], 4000)}\n\n"
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
        punch = float(motion.get("punch_scale") or 1.12)
        trans_pool = [t for t in (motion.get("transitions") or []) if t != "cut"]
        segs = []
        prev_end = None
        for i, (a, b) in enumerate(prep["ranges"]):
            gap = (a - prev_end) if prev_end is not None else 0.0
            trans = "cut"
            if i > 0 and gap > 2.0 and trans_pool:
                trans = trans_pool[0]
            segs.append({"src_start": a, "src_end": b, "speed": 1.0,
                         "reframe": {"mode": mode, "x": x or 0.5, "cam": cam if mode == "stack" else None,
                                     "face": prep.get("facecam_face") if mode == "stack" else None},
                         "zoom": {"type": "punch" if i % 2 == 1 else "none", "scale": punch},
                         "shake": False, "transition_in": trans, "note": ""})
            prev_end = b
        plan = example(EDIT_PLAN)
        plan.update({
            "title": moment.get("title") or "clip",
            "segments": segs,
            "captions": {**(blueprint.get("captions") or {}), "enabled": bool(prep["moment_words"]), "font_scale": 1.0},
            "overlays": [], "sfx": [],
            "music": {"enabled": bool((blueprint.get("sound") or {}).get("music_mood")),
                      "mood": (blueprint.get("sound") or {}).get("music_mood") or "", "asset": "",
                      "gain_db": float((blueprint.get("sound") or {}).get("music_gain_db") or -19.0), "duck": True},
            "color": blueprint.get("color") or "punchy",
            "progress_bar": False,
            "post": {"caption": moment.get("title") or "", "hashtags": []},
            "used_lessons": [], "rationale": "heuristic plan from blueprint + tight cut",
        })
        if (blueprint.get("text_overlays") or {}).get("hook_title", True):
            # the moment's title frames the line; the hook line itself is already in the captions
            hook = short_hook(moment.get("title") or moment.get("hook_line") or "")
            if hook:
                plan["overlays"].append({"kind": "hook_title", "text": hook.upper(), "start": 0.0, "end": 2.6,
                                         # stacked: the top band is the facecam and captions ride the seam
                                         "position": "center" if mode == "stack" else "top",
                                         "style": (blueprint.get("text_overlays") or {}).get("style") or "pop"})
        else:
            plan["segments"][0]["zoom"] = {"type": "punch", "scale": punch}
        if mode == "stack":
            plan["captions"]["position"] = "upper"  # = ride the cam/gameplay seam
        self._place_sfx(plan, blueprint)
        return plan

    def _place_sfx(self, plan: dict[str, Any], blueprint: dict[str, Any]) -> None:
        sound = blueprint.get("sound") or {}
        spacing = SFX_SPACING.get(sound.get("sfx_density") or "low", 6.0)
        palette = [k for k in (sound.get("sfx_palette") or []) if k in SFX_KINDS] or ["whoosh", "pop"]
        if not spacing:
            return
        tl = Timeline(sanitize_segments(plan["segments"], 1e9))
        cues = []
        if any(o["kind"] == "hook_title" for o in plan["overlays"]):
            cues.append({"kind": "pop" if "pop" in palette else palette[0], "at": 0.05, "gain_db": -9.0})
        last = 0.0
        for p in tl.placed[1:]:
            seg = plan["segments"][p.index]
            beat = seg.get("transition_in") not in (None, "cut") or (seg.get("zoom") or {}).get("type") == "punch"
            if beat and p.out_start - last >= spacing:
                kind = "whoosh" if seg.get("transition_in") not in (None, "cut") else palette[len(cues) % len(palette)]
                cues.append({"kind": kind if kind in SFX_KINDS else "whoosh", "at": max(0.0, p.out_start - 0.12),
                             "gain_db": -10.0})
                last = p.out_start
        plan["sfx"] = cues

    def finalize(self, plan: dict[str, Any], moment: dict[str, Any], brief: dict[str, Any], blueprint: dict[str, Any],
                 prep: dict[str, Any]) -> dict[str, Any]:
        """Make any plan renderable and brief-compliant (poka-yoke, runs on every plan)."""
        plan = conform(plan, EDIT_PLAN)
        src_dur = float(prep["source_info"].get("duration") or 1e9)
        segs = sanitize_segments(plan["segments"], src_dur, (moment["start_s"], moment["end_s"]),
                                 max_total=self._max_len(brief))
        if not segs:  # an unusable plan never reaches the renderer
            segs = sanitize_segments([{"src_start": a, "src_end": b, "speed": 1.0,
                                       "reframe": {"mode": "center", "x": 0.5}, "zoom": {"type": "none", "scale": 1.0},
                                       "shake": False, "transition_in": "cut", "note": ""}
                                      for a, b in prep["ranges"]], src_dur, (moment["start_s"], moment["end_s"]),
                                     max_total=self._max_len(brief))
        plan["segments"] = segs
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
            if not chosen and cam and info.get("width") and info.get("height"):  # only the detector's guess grows
                wider = fit_cam_upscale(cam, int(info["width"]), int(info["height"]), self.ax.cfg.width,
                                        self.ax.cfg.height, LAYOUT["cam_max_upscale"])
                face = reproject_box(face, cam, wider) if face else None
                cam = wider
            rf["cam"], rf["face"] = cam, face
        for s in segs:  # a replay range outside the source renders a band with no video (and exits 0)
            bs = s.get("band_src")
            if bs:
                a = max(0.0, float(bs.get("start") or 0.0))
                b = min(src_dur, float(bs.get("end") or 0.0))
                s["band_src"] = ({"start": round(a, 3), "end": round(b, 3), "speed": float(bs.get("speed") or 1.0)}
                                 if b - a >= 0.3 else None)
        D = Timeline(segs).duration
        for o in plan["overlays"]:
            o["start"] = max(0.0, min(float(o["start"]), D - 0.3))
            o["end"] = max(o["start"] + 0.3, min(float(o["end"] or o["start"] + 2.5), D))
        seen: set[tuple] = set()
        kept = []
        for o in plan["overlays"]:  # empty texts and exact duplicates never reach the screen
            key = (o.get("kind"), (o.get("text") or "").strip().lower(), round(o["start"], 1), o.get("position"))
            if key[1] and key not in seen:
                seen.add(key)
                kept.append(o)
        plan["overlays"] = kept
        plan["sfx"] = [s for s in plan["sfx"] if 0.0 <= float(s["at"]) < D][:40]
        cap = plan["captions"]
        cap["words_per_caption"] = min(6, max(1, int(cap.get("words_per_caption") or 3)))
        cap["font_scale"] = min(1.5, max(0.7, float(cap.get("font_scale") or 1.0)))
        if not cap.get("enabled") and prep["moment_words"] and self._captions_required(brief):
            cap["enabled"] = True
        self.enforce_compliance(plan, brief, D)
        self._declutter(plan, D)
        return plan

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
        return self.finalize(out, moment, brief, blueprint, prep)

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
