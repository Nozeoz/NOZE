"""Reviewer / QC lead: measured QC + plan lint + creative review → pass or pointed fixes."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from ..media.analyze import contact_sheets, extract_frames, sample_times
from ..media.qc import (caption_lint, compliance_lint, layout_lint, measure_cam_faces, stack_seams, story_lint,
                        technical_qc)
from ..media.timeline import Timeline
from ..schemas import CREATIVE_REVIEW
from ..standards import QC
from ..story import moment_parts
from .base import Role, dump

log = logging.getLogger("noze.agency.reviewer")

SEV_WEIGHT = {"blocker": 4.0, "major": 1.5, "minor": 0.4}
MIN_STORY_SCORE = 6.0  # [D] a clean clip that tells no story / feels flat is not a pass (Dalvin 23 Nov)


def hold_windows(plan: dict[str, Any], tl: Timeline) -> list[tuple[float, float]]:
    """Output windows where a segment's last frame is frozen on purpose (the reaction beat)."""
    out = []
    for p in tl.placed:
        hold = float((plan["segments"][p.index] or {}).get("hold") or 0.0)
        if hold > 0.05:
            out.append((round(p.out_end - hold, 3), round(p.out_end, 3)))
    return out


class Reviewer(Role):
    name = "reviewer"

    def review(self, job: dict[str, Any], plan: dict[str, Any], render: dict[str, Any], brief: dict[str, Any],
               blueprint: dict[str, Any], words: list[dict[str, Any]], round_: int,
               previous: list[dict[str, Any]]) -> dict[str, Any]:
        cfg = self.ax.cfg
        path = render["path"]
        tl = Timeline(plan["segments"])
        D = tl.duration
        segs = plan["segments"]
        changes = [p.out_start for p in tl.placed[1:]]
        changes += [float(o["start"]) for o in plan.get("overlays") or [] if float(o["start"]) > 0.05]
        dips = [p.out_start for p in tl.placed[1:] if segs[p.index].get("transition_in") == "fade"]
        length = brief.get("clip_length") or {}
        min_s = float(length.get("min_s") or cfg.min_clip_s)
        max_s = float(length.get("max_s") or cfg.max_clip_s)
        hook_overlay = any(o.get("kind") == "hook_title" and float(o["start"]) <= 0.5 for o in plan.get("overlays") or [])
        src_size = self._source_size(job)
        seams = stack_seams(plan, src_size, cfg.width, cfg.height)
        qc_issues, metrics = technical_qc(path, width=cfg.width, height=cfg.height, fps=cfg.fps,
                                          target_lufs=cfg.target_lufs, min_s=min_s, max_s=max_s,
                                          platform=cfg.platform, intended_dips=dips,
                                          intended_holds=hold_windows(plan, tl),
                                          render_info={"visual_changes": changes, "hook_overlay": hook_overlay,
                                                       "seams": seams})
        out_words = tl.map_words(words)
        required = any(k in " ".join((brief.get("requirements") or {}).get("other") or []).lower()
                       for k in ("caption", "subtitle"))
        qc_issues += caption_lint(out_words, bool((plan.get("captions") or {}).get("enabled")), required)
        qc_issues += compliance_lint(plan, brief, D)
        qc_issues += story_lint(plan, moment=(job.get("input") or {}).get("moment"), words=out_words)
        layout_notes: list[str] = []
        measured = None  # the face on the OUTPUT frames beats the plan's guess (a model reading thumbnails)
        if seams:
            try:
                st = Path(path).stat()  # re-renders may reuse a name: key the frame cache by content too
                cache = Path(path).parent / f"review_{Path(path).stem}" / f"cam_{int(st.st_mtime)}_{st.st_size}"
                measured = measure_cam_faces(path, seams, cache)
            except Exception as exc:  # a broken detector must not fail the review
                log.info("face measurement failed: %s", exc)
            if measured is None:
                layout_notes.append("face box taken from the plan (not measured on the output): OpenCV face "
                                    "detection unavailable or failed")
            else:
                metrics["cam_faces"] = {str(k): v for k, v in measured.items()}
        lay = layout_lint(plan, brief, words=out_words, width=cfg.width, height=cfg.height, platform=cfg.platform,
                          fonts_dir=cfg.fonts_dir, src_size=src_size, notes=layout_notes, measured_faces=measured,
                          video_path=str(path))  # title_over_subject looks for the game subject on the output frames
        if any(i["id"] == "compliance:facecam" for i in qc_issues):  # same defect, already reported
            lay = [i for i in lay if i["id"] != "layout:facecam_hidden"]
        qc_issues += lay
        metrics["layout_notes"] = layout_notes

        creative = self._creative(job, plan, path, D, metrics, qc_issues, brief, blueprint, out_words, previous)
        issues = list(qc_issues)
        scores = {}
        resolved = []
        summary = ""
        if creative:
            scores = creative.get("scores") or {}
            resolved = creative.get("resolved_previous") or []
            summary = creative.get("summary") or ""
            for k, iss in enumerate(creative.get("issues") or []):
                issues.append({"id": f"creative:{iss['category']}:{round_}.{k + 1}", **iss, "source": "creative"})
        # carry forward creative issues from last round the reviewer says are still open
        open_ids = {r["issue_id"] for r in resolved if not r.get("resolved")}
        for prev in previous:
            if prev.get("source") == "creative" and prev["id"] in open_ids and not any(i["id"] == prev["id"] for i in issues):
                issues.append({**prev, "description": prev["description"] + " (still open)"})
        blockers = [i for i in issues if i["severity"] == "blocker"]
        majors = [i for i in issues if i["severity"] == "major"]
        penalty = sum(SEV_WEIGHT.get(i["severity"], 0.4) for i in issues)
        score = float(scores.get("overall") or 0.0) if scores else max(0.0, 10.0 - penalty)
        passed = not blockers and not majors and score >= QC["min_review_score"]
        if creative and passed:  # the story/emotion gate: what Dalvin judges first
            weak = {k: float(scores.get(k) or 0) for k in ("story", "emotion") if float(scores.get(k) or 0) < MIN_STORY_SCORE}
            if weak:
                passed = False
                issues.append({"id": f"creative:story:{round_}.gate", "category": "story", "severity": "major",
                               "timecode_s": None, "source": "creative",
                               "description": f"the edit does not deliver its story/emotion ({', '.join(f'{k} {v:.1f}' for k, v in weak.items())} < {MIN_STORY_SCORE:.0f})",
                               "fix": "rebuild the arc: payoff/strongest beat at frame 0 or a clear setup → turn → payoff, "
                                      "effects from the vibe palette that push the intended emotion, end on the reaction"})
        if not summary:
            summary = (f"{len(blockers)} blocker(s), {len(majors)} major, "
                       f"{len(issues) - len(blockers) - len(majors)} minor; score {score:.1f}/10")
        if not creative:  # a QC-only score says nothing about taste: never let it read as a full pass
            summary = f"QC-only, no creative review — {summary}"
        return {"verdict": "pass" if passed else "fail", "score": round(score, 2), "issues": issues,
                "creative_review": bool(creative),
                "scores": scores, "resolved_previous": resolved, "summary": summary, "metrics": metrics,
                "sheets": creative.get("_sheets", []) if creative else [],
                "used_lessons": (creative or {}).get("used_lessons", [])}

    def _source_size(self, job: dict[str, Any]) -> tuple[int, int] | None:
        """Source video size from the parent source job's probe (None when unknown)."""
        try:
            facts = (self.store.artifact(job["parent_id"], "source_info") or {}).get("data") or {}
            p = facts.get("probe") or {}
            return (int(p["width"]), int(p["height"])) if p.get("width") and p.get("height") else None
        except (KeyError, TypeError, ValueError):
            return None

    def _creative(self, job, plan, path, D, metrics, qc_issues, brief, blueprint, out_words,
                  previous) -> dict[str, Any] | None:
        if not self.ax.llm.available:
            return None
        work = Path(path).parent / f"review_{Path(path).stem}"
        # the ending is judged too: live run 23 Nov the last sampled frame was 15.3 s of a 17.5 s clip
        tail = {round(max(0.0, D - x), 2) for x in (1.2, 0.6, 0.15)}
        times = sorted(set(sample_times(D, metrics.get("cuts") or [], n=16)) | {0.15, 0.9, 1.8} | tail)
        try:
            frames = extract_frames(path, times, work, width=360)
            sheets = [str(p) for p in contact_sheets(frames, times, work / "sheet")]
        except Exception as exc:
            log.info("review frames unavailable: %s", exc)
            sheets = []
        text = " ".join(f"[{w['start']:.1f}]{w['word']}" for w in out_words[:900])
        m = (job.get("input") or {}).get("moment") or {}
        intent = {"structure": m.get("structure") or "linear", "emotion": m.get("emotion") or plan.get("vibe"),
                  "story": m.get("story") or m.get("summary"), "vibe_in_plan": plan.get("vibe"),
                  "parts": [{k: p[k] for k in ("start_s", "end_s", "role", "label")} for p in moment_parts(m)]
                  if m.get("start_s") is not None else []}
        task = (
            f"Review this rendered clip ({D:.1f}s). Frames are labelled with OUTPUT timecodes.\n\n"
            f"Intended story & emotion (analyst → editor hand-off):\n{dump(intent, 3000)}\n"
            "Score `story` (does it set up, turn and pay off — and is every time-jump/callback honest and "
            "understandable without context?) and `emotion` (do the cuts, effects, text, SFX and music make the "
            f"viewer feel '{intent['emotion']}', or is it a flat clip with effects on top?). Below "
            f"{MIN_STORY_SCORE:.0f} on either fails the clip; say exactly which beat loses the viewer and how to fix it.\n\n"
            f"Output transcript:\n{text or '(no speech)'}\n\nEdit plan:\n{dump(plan, 12000)}\n\n"
            f"Automated QC already found (don't repeat these; add only what QC can't see):\n"
            f"{dump([{k: i[k] for k in ('id', 'severity', 'description')} for i in qc_issues], 4000)}\n\n"
            f"QC measurements:\n{dump({k: metrics.get(k) for k in ('duration', 'loudness', 'longest_static_s', 'silences', 'empty_band')}, 2000)}\n\n"
            f"Brief:\n{dump(brief, 6000)}\n\nBlueprint:\n{dump(blueprint, 4000)}\n\n"
            f"Issues from the previous round to verify (resolved_previous):\n"
            f"{dump([{k: i.get(k) for k in ('id', 'severity', 'description', 'fix')} for i in previous], 5000)}"
        )
        internal = self._internal_test(job)
        if internal:  # permission is pending BY DESIGN; the delivery gate (not this review) blocks the clip
            task += ("\n\nINTERNAL TEST: this clip is rendered only for the owner's review while the campaign terms "
                     "are pending; delivery and posting are blocked in code until real terms grant permission. Do NOT "
                     "raise the missing campaign permission — judge the edit (music/Content ID licence risks still count).")
        out = self.ask(job, task, CREATIVE_REVIEW, images=sheets, campaign=self.campaign_of(job))
        if out is not None:
            if internal:  # belt and braces: a permission note can't fail an internal test round after round
                out["issues"] = [i for i in out.get("issues") or []
                                 if not re.search(r"\b(permission|campaign terms|terms? (?:are|is) (?:missing|pending|not)|"
                                                  r"licen[cs]e (?:to clip|for this campaign)|permission (?:is |isn'?t |not )*(?:verified|granted))",
                                                  f"{i.get('description', '')} {i.get('fix', '')}", re.I)]
            out["_sheets"] = sheets
        return out

    def _internal_test(self, job: dict[str, Any]) -> bool:
        try:
            parent = self.store.get_job(job["parent_id"]) if job.get("parent_id") else job
            camp = self.campaign_of(job)
            granted = ((camp or {}).get("brief", {}).get("permission") or {}).get("granted")
            return bool(((parent or {}).get("input") or {}).get("internal_test")) and not granted
        except (KeyError, TypeError):
            return False
