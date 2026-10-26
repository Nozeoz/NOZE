"""Reviewer / QC lead: measured QC + plan lint + creative review → pass or pointed fixes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..media.analyze import contact_sheets, extract_frames, sample_times
from ..media.qc import caption_lint, compliance_lint, technical_qc
from ..media.timeline import Timeline
from ..schemas import CREATIVE_REVIEW
from ..standards import QC
from .base import Role, dump

log = logging.getLogger("noze.agency.reviewer")

SEV_WEIGHT = {"blocker": 4.0, "major": 1.5, "minor": 0.4}


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
        qc_issues, metrics = technical_qc(path, width=cfg.width, height=cfg.height, fps=cfg.fps,
                                          target_lufs=cfg.target_lufs, min_s=min_s, max_s=max_s,
                                          platform=cfg.platform, intended_dips=dips,
                                          render_info={"visual_changes": changes, "hook_overlay": hook_overlay})
        out_words = tl.map_words(words)
        required = any(k in " ".join((brief.get("requirements") or {}).get("other") or []).lower()
                       for k in ("caption", "subtitle"))
        qc_issues += caption_lint(out_words, bool((plan.get("captions") or {}).get("enabled")), required)
        qc_issues += compliance_lint(plan, brief, D)

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
        if not summary:
            summary = (f"{len(blockers)} blocker(s), {len(majors)} major, "
                       f"{len(issues) - len(blockers) - len(majors)} minor; score {score:.1f}/10")
        return {"verdict": "pass" if passed else "fail", "score": round(score, 2), "issues": issues,
                "scores": scores, "resolved_previous": resolved, "summary": summary, "metrics": metrics,
                "sheets": creative.get("_sheets", []) if creative else [],
                "used_lessons": (creative or {}).get("used_lessons", [])}

    def _creative(self, job, plan, path, D, metrics, qc_issues, brief, blueprint, out_words,
                  previous) -> dict[str, Any] | None:
        if not self.ax.llm.available:
            return None
        work = Path(path).parent / f"review_{Path(path).stem}"
        times = sorted(set(sample_times(D, metrics.get("cuts") or [], n=16)) | {0.15, 0.9, 1.8})
        try:
            frames = extract_frames(path, times, work, width=360)
            sheets = [str(p) for p in contact_sheets(frames, times, work / "sheet")]
        except Exception as exc:
            log.info("review frames unavailable: %s", exc)
            sheets = []
        text = " ".join(f"[{w['start']:.1f}]{w['word']}" for w in out_words[:900])
        task = (
            f"Review this rendered clip ({D:.1f}s). Frames are labelled with OUTPUT timecodes.\n\n"
            f"Output transcript:\n{text or '(no speech)'}\n\nEdit plan:\n{dump(plan, 12000)}\n\n"
            f"Automated QC already found (don't repeat these; add only what QC can't see):\n"
            f"{dump([{k: i[k] for k in ('id', 'severity', 'description')} for i in qc_issues], 4000)}\n\n"
            f"QC measurements:\n{dump({k: metrics.get(k) for k in ('duration', 'loudness', 'longest_static_s', 'silences')}, 2000)}\n\n"
            f"Brief:\n{dump(brief, 6000)}\n\nBlueprint:\n{dump(blueprint, 4000)}\n\n"
            f"Issues from the previous round to verify (resolved_previous):\n"
            f"{dump([{k: i.get(k) for k in ('id', 'severity', 'description', 'fix')} for i in previous], 5000)}"
        )
        out = self.ask(job, task, CREATIVE_REVIEW, images=sheets, campaign=self.campaign_of(job))
        if out is not None:
            out["_sheets"] = sheets
        return out
