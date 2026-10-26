"""How the studio keeps getting better without breaking its own flow.

Design (adapted from ACE, ExpeL, Reflexion, ChatDev IER — see docs/AGENCY.md):

* **Playbooks, not prompt rewrites.** Each role reads its SOP (fixed, reviewed by
  humans) plus a playbook of short lessons ("bullets") rendered in ACE format::

      [edi-00012] helpful=5 harmful=0 :: Punch in on the first stressed word of the hook.

  Roles return the ids they actually applied (``used_lessons``) → credit assignment.

* **Delta updates only** (no full rewrites → no "context collapse"): after every
  finished clip a Reflector tags the bullets that were used (helpful/harmful) and
  proposes at most a few new ones. A deterministic Curator validates every op:
  length, no instructions that weaken QC, de-duplication (a near-duplicate ADD
  becomes an UPVOTE), at most one op per bullet per job.

* **Gated promotion.** New lessons start as *candidates* and are only shown on a
  canary share of jobs. They become *active* after ``uses ≥ 3``,
  ``helpful − harmful ≥ 2`` and ``harmful/uses < 0.2`` (max 3 promotions per role
  per day). Bullets with ``harmful ≥ 2`` and ``harmful ≥ helpful`` are archived.

* **Recurring-issue miner** (no LLM): an issue that keeps coming back in first-round
  reviews becomes a preventive editor rule — "shift left" from review to planning.

* **Regression guard.** First-pass approval and escalation rates of the last N
  clips are compared with the N before; if quality drops, every lesson that went
  live in between is quarantined automatically (rollback to last-known-good).

* **Short-term memory stays short.** Revision notes live in the job (Reflexion
  style, last 3 rounds) and never leak into the long-term playbook directly.
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections import Counter
from typing import Any

from .config import AgencySettings
from .llm import LLM, LLMError
from .schemas import REFLECTION
from .store import Store

log = logging.getLogger("noze.agency.learning")

ROLES = ("manager", "scout", "analyst", "editor", "reviewer")
PREFIX = {"manager": "man", "scout": "sco", "analyst": "ana", "editor": "edi", "reviewer": "rev"}

MAX_ACTIVE_PER_ROLE = 25
MAX_CANDIDATES_SHOWN = 8
MAX_NEW_PER_JOB = 3
MAX_OPS_PER_JOB = 6
MAX_PROMOTIONS_PER_DAY = 3
LESSON_MAX_CHARS = 300
DUPLICATE_SIM = 0.72
GUARD_WINDOW = 10
GUARD_DROP = 0.10  # first-pass rate drop that triggers a rollback
GUARD_ESCALATION_X = 1.5

# Lessons may add taste; they may never loosen the gates.
UNSAFE = re.compile(
    r"(skip|bypass|disable|turn off|ignore)\s+(the\s+)?(qc|review|reviewer|brief|checks?|safe ?zone|loudness|"
    r"compliance|disclosure|permission)|auto-?approve|without (review|permission)|lower (the )?(bar|standard)",
    re.I)
LENIENT = re.compile(r"\b(don'?t|do not|no need to|never)\s+(flag|report|fail|check)\b|\b(tolerate|overlook|let it pass|"
                     r"be lenient|pass anyway|accept (minor|small) )", re.I)

# Recurring QC issue → preventive rule for the editor (shift-left).
PREVENTIVE = {
    "pacing:dead_air": "Before rendering, jump-cut every pause over 0.4s inside the moment — dead air is the most common bounce.",
    "hook:silent_open": "Start the first segment on the first spoken word (≤0.15s lead-in), never on silence.",
    "hook:slow_open": "Put a hook title on screen from 0.0s and punch in on the first key word within 1.5s.",
    "pacing:static_stretch": "Never hold one framing for more than ~4s: alternate punch-ins (1.0 ↔ 1.12) across jump cuts.",
    "captions:too_fast": "Use at most 2-3 words per caption when the speaker talks faster than ~3 words per second.",
    "compliance:hashtag": "Always copy every required hashtag from the brief into post.hashtags before rendering.",
    "compliance:mention": "Always copy every required @mention from the brief into the post caption.",
    "compliance:disclosure": "When the brief needs a disclosure, show it as a label overlay in the first 3s and in the caption.",
    "compliance:cta": "When the brief needs a CTA, add it as a CTA overlay in the last 3 seconds.",
    "compliance:too_long": "Plan to the brief's max length minus 2s; cut setup before cutting the payoff.",
    "compliance:too_short": "If the moment is short, keep a little context before the hook so the clip meets the minimum length.",
    "visual:frozen": "Cover still or frozen stretches with a punch-in, push or a cut — never let the picture freeze >1.5s.",
    "visual:black_frames": "Avoid fade transitions that dip to black at the very start or end of the clip.",
    "audio:loudness": "Keep music 16-20dB under the voice and SFX around -8dB so loudness normalisation stays linear.",
}

_STOP = set("a an the to of and or in on for with at by is are be it this that as from your you our we use when "
            "then than into over under each every all any no not".split())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1}


def _grams(text: str) -> Counter:
    t = re.sub(r"\s+", " ", text.lower())
    return Counter(t[i:i + 3] for i in range(max(0, len(t) - 2)))


def similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    jac = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    ga, gb = _grams(a), _grams(b)
    dot = sum(ga[k] * gb.get(k, 0) for k in ga)
    na = math.sqrt(sum(v * v for v in ga.values()))
    nb = math.sqrt(sum(v * v for v in gb.values()))
    cos = dot / (na * nb) if na and nb else 0.0
    return max(jac, cos)


def clean_lesson(text: str) -> str:
    text = " ".join((text or "").split()).strip(" -•*")
    if text and text[-1] not in ".!?":
        text += "."
    return text


def lesson_problem(role: str, text: str) -> str:
    """Why a proposed lesson must be rejected ('' = acceptable)."""
    if len(text) < 20:
        return "too short to be actionable"
    if len(text) > LESSON_MAX_CHARS:
        return "too long"
    if UNSAFE.search(text):
        return "would weaken a quality gate"
    if role == "reviewer" and LENIENT.search(text):
        return "reviewer lessons may only make the review stricter or sharper"
    return ""


def scopes_for(campaign: dict[str, Any] | None) -> list[str]:
    out = ["global"]
    if campaign:
        out.append(f"campaign:{campaign['id']}")
        if campaign.get("creator"):
            out.append(f"creator:{campaign['creator'].strip().lower()}")
    return out


class Playbook:
    def __init__(self, store: Store):
        self.store = store

    def render(self, role: str, scopes: list[str], canary: bool) -> tuple[str, list[str]]:
        """Prompt section with the role's lessons (+ trial lessons on canary jobs) and the ids shown."""
        active = self.store.lessons(role, ["active"], scopes)[:MAX_ACTIVE_PER_ROLE]
        trial = self.store.lessons(role, ["candidate"], scopes)[:MAX_CANDIDATES_SHOWN] if canary else []
        if not active and not trial:
            return "", []

        def line(l: dict[str, Any]) -> str:
            scope = "" if l["scope"] == "global" else f" ({l['scope']})"
            return f"[{l['id']}] helpful={l['helpful']} harmful={l['harmful']} :: {l['text']}{scope}"

        parts = ["## Team playbook (lessons learned on past jobs)",
                 "Apply the ones that fit this job and list the ids you actually applied in `used_lessons`. "
                 "The SOP, the brief and the house standards always win over a lesson."]
        by_section: dict[str, list[str]] = {}
        for l in active:
            by_section.setdefault(l["section"], []).append(line(l))
        for section, lines in sorted(by_section.items()):
            parts.append(f"### {section}")
            parts.extend(lines)
        if trial:
            parts.append("### Trial lessons (unproven — use only if clearly right for this job)")
            parts.extend(line(l) for l in trial)
        return "\n".join(parts), [l["id"] for l in active + trial]

    def record_use(self, used: list[str], shown: list[str], job_id: int | None) -> list[str]:
        valid = [i for i in dict.fromkeys(used or []) if i in set(shown)]
        for lid in valid:
            l = self.store.get_lesson(lid)
            if not l:
                continue
            jobs = list(l.get("jobs") or [])
            if job_id and job_id not in jobs:
                jobs.append(job_id)
            self.store.update_lesson(lid, uses=l["uses"] + 1, jobs=jobs[-50:])
        return valid


class Learner:
    def __init__(self, cfg: AgencySettings, store: Store, llm: LLM, sop_text: str = ""):
        self.cfg = cfg
        self.store = store
        self.llm = llm
        self.sop_text = sop_text

    # -- per finished clip ------------------------------------------------------------------
    def trajectory(self, job: dict[str, Any]) -> dict[str, Any]:
        reviews = self.store.reviews(job["id"])
        data = job.get("data") or {}
        used: dict[str, list[str]] = {}
        for art in self.store.artifacts(job["id"]):
            ids = (art.get("data") or {}).get("used_lessons") if isinstance(art.get("data"), dict) else None
            if ids:
                used.setdefault(art.get("role") or art["kind"], [])
                used[art.get("role") or art["kind"]] += [i for i in ids if i not in used[art.get("role") or art["kind"]]]
        first = next((r for r in reviews if r["reviewer"] == "reviewer"), None)
        reviewer_passed = [r for r in reviews if r["reviewer"] == "reviewer" and r["verdict"] == "pass"]
        later_catches = [i for r in reviews if r["reviewer"] in ("manager", "human") and r["verdict"] != "pass"
                         for i in r.get("issues") or []]
        return {
            "job_id": job["id"], "title": job.get("title"), "state": job["state"], "rounds": job.get("round", 0),
            "first_pass": bool(first and first["verdict"] == "pass"),
            "escalated": bool(data.get("escalated")),
            "reviews": [{"round": r["round"], "by": r["reviewer"], "verdict": r["verdict"], "score": r["score"],
                         "issues": [{k: i.get(k) for k in ("id", "category", "severity", "description", "fix")}
                                    for i in (r.get("issues") or [])][:12]} for r in reviews],
            "editor_fixes": data.get("fix_log") or [],
            "reviewer_missed": later_catches if reviewer_passed else [],
            "used_lessons": used,
            "metrics": self.store.job_metrics(job["id"]),
        }

    def after_clip(self, job: dict[str, Any]) -> dict[str, Any]:
        """Run once per terminal clip: reflect → curate → promote/prune → mine → guard."""
        if (job.get("data") or {}).get("learned"):
            return {}
        traj = self.trajectory(job)
        changes: dict[str, Any] = {"tags": 0, "added": [], "upvoted": [], "rejected": []}
        if traj["reviews"]:  # learn only from jobs with a verifiable signal
            reflection = self.reflect(traj)
            changes = self.curate(reflection, traj)
        self.store.merge_job_data(job["id"], {"learned": True, "learning": changes})
        if any(r["by"] == "reviewer" for r in traj["reviews"]):
            # quality metrics only for clips that were actually reviewed — a missing file or a
            # full disk says nothing about the team's craft (and must not trip the guard)
            self.store.add_metric(job["id"], "first_pass", 1.0 if traj["first_pass"] else 0.0)
            self.store.add_metric(job["id"], "rounds", float(traj["rounds"]))
            self.store.add_metric(job["id"], "escalated", 1.0 if traj["escalated"] else 0.0)
            self.store.add_metric(job["id"], "approved", 1.0 if job["state"] == "delivered" else 0.0)
        promo = self.promote_and_prune()
        mined = self.mine_recurring()
        guard = self.regression_guard()
        if changes.get("added") or changes.get("upvoted") or promo["promoted"] or promo["archived"] or mined:
            self.store.new_version(f"after job {job['id']}", {**changes, **promo, "mined": mined})
        return {**changes, **promo, "mined": mined, "guard": guard}

    def reflect(self, traj: dict[str, Any]) -> dict[str, Any]:
        if self.llm.available:
            try:
                system = (self.sop_text or "You are the studio's reflector.") + (
                    "\n\nYou review one finished clip job and improve the team's playbooks. Tag each used lesson "
                    "helpful/harmful/neutral based on evidence in the trajectory. Propose at most "
                    f"{MAX_NEW_PER_JOB} NEW lessons, only for root causes that will recur. A lesson is one concrete, "
                    "reusable instruction (imperative, ≤ 220 chars, ends with a period), with creator-specific "
                    "values abstracted unless scope is creator/campaign. Never propose lessons that skip, weaken or "
                    "bypass QC, review, the brief or permissions. Reviewer lessons may only make reviews sharper. "
                    "If the job went smoothly and nothing new was learned, return empty lists.")
                existing = "\n".join(f"[{l['id']}] ({l['role']}/{l['status']}) {l['text']}"
                                     for l in self.store.lessons(statuses=["active", "candidate"])[:120])
                content = (f"Existing lessons (do not duplicate; tag by id):\n{existing or '(none)'}\n\n"
                           f"Trajectory:\n{_json(traj)}")
                return self.llm.json("reflector", system, content, REFLECTION, job_id=traj["job_id"])
            except LLMError as exc:
                log.info("reflection fell back to heuristics: %s", exc)
        return self._heuristic_reflection(traj)

    def _heuristic_reflection(self, traj: dict[str, Any]) -> dict[str, Any]:
        tags = []
        good = traj["first_pass"] and traj["state"] == "delivered"
        bad = traj["state"] in ("rejected", "failed") or traj["escalated"]
        for ids in traj["used_lessons"].values():
            for lid in ids:
                tags.append({"id": lid, "tag": "helpful" if good else ("harmful" if bad else "neutral"),
                             "why": "outcome-level credit (no LLM reflector)"})
        return {"bullet_tags": tags, "new_lessons": [], "root_causes": [], "summary": "heuristic reflection"}

    def curate(self, reflection: dict[str, Any], traj: dict[str, Any]) -> dict[str, Any]:
        """Apply validated delta ops. Returns what changed."""
        changes: dict[str, Any] = {"tags": 0, "added": [], "upvoted": [], "rejected": []}
        used_ids = {i for ids in traj["used_lessons"].values() for i in ids}
        touched: set[str] = set()
        ops = 0
        for tag in reflection.get("bullet_tags") or []:
            lid = tag.get("id")
            if ops >= MAX_OPS_PER_JOB or lid in touched or lid not in used_ids or tag.get("tag") == "neutral":
                continue
            l = self.store.get_lesson(lid)
            if not l:
                continue
            if tag["tag"] == "helpful":
                self.store.update_lesson(lid, helpful=l["helpful"] + 1)
            else:
                self.store.update_lesson(lid, harmful=l["harmful"] + 1)
            touched.add(lid)
            changes["tags"] += 1
            ops += 1
        campaign = None
        job = self.store.get_job(traj["job_id"]) or {}
        if job.get("campaign_id"):
            campaign = self.store.get_campaign(job["campaign_id"])
        version = self.store.current_version() + 1
        for new in (reflection.get("new_lessons") or [])[:MAX_NEW_PER_JOB]:
            if ops >= MAX_OPS_PER_JOB:
                break
            role = new.get("role") or "editor"
            text = clean_lesson(new.get("text") or "")
            problem = lesson_problem(role, text)
            if problem:
                changes["rejected"].append({"text": text, "why": problem})
                continue
            scope = "global"
            if new.get("scope") == "campaign" and campaign:
                scope = f"campaign:{campaign['id']}"
            elif new.get("scope") == "creator" and campaign and campaign.get("creator"):
                scope = f"creator:{campaign['creator'].strip().lower()}"
            dup = self._duplicate(role, text)
            if dup:
                if dup["id"] not in touched:
                    self.store.update_lesson(dup["id"], helpful=dup["helpful"] + 1)
                    touched.add(dup["id"])
                    changes["upvoted"].append(dup["id"])
                    ops += 1
                continue
            lid = self.store.add_lesson(role, text, section=(new.get("section") or "general")[:40].lower(),
                                        scope=scope, evidence=[new.get("evidence", "")[:400]], job_id=traj["job_id"],
                                        version=version)
            changes["added"].append(lid)
            ops += 1
        return changes

    def _duplicate(self, role: str, text: str) -> dict[str, Any] | None:
        best, best_sim = None, 0.0
        for l in self.store.lessons(role, ["active", "candidate", "quarantined"]):
            s = similarity(text, l["text"])
            if s > best_sim:
                best, best_sim = l, s
        return best if best_sim >= DUPLICATE_SIM else None

    # -- lifecycle -------------------------------------------------------------------------------
    def promote_and_prune(self) -> dict[str, list[str]]:
        promoted, archived = [], []
        day = time.time() - 24 * 3600
        for role in ROLES:
            recent = [l for l in self.store.lessons(role, ["active"]) if (l.get("activated_at") or 0) > day
                      and l["origin"] != "human"]
            budget = MAX_PROMOTIONS_PER_DAY - len(recent)
            for l in self.store.lessons(role, ["candidate"]):
                if l["harmful"] >= 2 and l["harmful"] >= l["helpful"]:
                    self.store.update_lesson(l["id"], status="archived")
                    archived.append(l["id"])
                    continue
                if (budget > 0 and l["uses"] >= 3 and l["helpful"] - l["harmful"] >= 2
                        and l["harmful"] / max(1, l["uses"]) < 0.2):
                    self.store.update_lesson(l["id"], status="active", activated_at=time.time())
                    promoted.append(l["id"])
                    budget -= 1
            active = self.store.lessons(role, ["active"])
            for l in active:
                if not l["protected"] and l["harmful"] >= 2 and l["harmful"] >= l["helpful"]:
                    self.store.update_lesson(l["id"], status="archived")
                    archived.append(l["id"])
            active = [l for l in self.store.lessons(role, ["active"]) if not l["protected"]]
            if len(active) > MAX_ACTIVE_PER_ROLE:
                for l in sorted(active, key=lambda x: (x["helpful"] - x["harmful"], x["uses"]))[
                        :len(active) - MAX_ACTIVE_PER_ROLE]:
                    self.store.update_lesson(l["id"], status="archived")
                    archived.append(l["id"])
        return {"promoted": promoted, "archived": archived}

    def mine_recurring(self, window: int = 20, min_clips: int = 3, share: float = 0.3) -> list[str]:
        """Issues that keep failing first-round review become preventive editor rules."""
        firsts = []
        for j in self.store.list_jobs(kind="clip", limit=window * 3):
            first = next((r for r in self.store.reviews(j["id"]) if r["reviewer"] == "reviewer"), None)
            if j["state"] in TERMINAL and first:
                firsts.append(first)
        clips = firsts[:window]
        if len(clips) < min_clips:
            return []
        counts: Counter = Counter()
        for first in clips:
            counts.update({i.get("id") for i in first.get("issues") or [] if i.get("id") in PREVENTIVE})
        added = []
        for issue_id, n in counts.items():
            if n >= min_clips and n / len(clips) >= share:
                text = PREVENTIVE[issue_id]
                if any(l["text"] == text for l in self.store.lessons("editor", ["active", "candidate", "archived",
                                                                                "quarantined"])):
                    continue
                lid = self.store.add_lesson("editor", text, section="preflight", status="active", origin="miner",
                                            evidence=[f"{issue_id} failed first review on {n}/{len(clips)} clips"],
                                            version=self.store.current_version() + 1)
                self.store.update_lesson(lid, activated_at=time.time())
                added.append(lid)
        return added

    def regression_guard(self) -> dict[str, Any]:
        """Quarantine lessons that went live right before quality dropped."""
        finished = [j for j in self.store.list_jobs(kind="clip", limit=500)
                    if j["state"] in TERMINAL and j.get("finished_at")
                    and "first_pass" in self.store.job_metrics(j["id"])]  # reviewed clips only
        finished.sort(key=lambda j: j["finished_at"])
        last_rb = float(self.store.get_meta("guard_last_rollback", "0") or 0)
        finished_after_rb = [j for j in finished if j["finished_at"] > last_rb]
        if len(finished_after_rb) < 2 * GUARD_WINDOW:
            return {"checked": False, "reason": "not enough finished clips yet"}
        base = finished_after_rb[-2 * GUARD_WINDOW:-GUARD_WINDOW]
        recent = finished_after_rb[-GUARD_WINDOW:]

        def rates(jobs):
            fp = sum(self.store.job_metrics(j["id"]).get("first_pass", 0.0) for j in jobs) / len(jobs)
            esc = sum(self.store.job_metrics(j["id"]).get("escalated", 0.0) for j in jobs) / len(jobs)
            return fp, esc

        fp_b, esc_b = rates(base)
        fp_r, esc_r = rates(recent)
        degraded = fp_r < fp_b - GUARD_DROP or esc_r > max(esc_b * GUARD_ESCALATION_X, esc_b + 0.1)
        result = {"checked": True, "first_pass": [round(fp_b, 2), round(fp_r, 2)],
                  "escalation": [round(esc_b, 2), round(esc_r, 2)], "rolled_back": []}
        if not degraded:
            return result
        since = base[-1]["finished_at"]
        suspects = [l for l in self.store.lessons(statuses=["active", "candidate"])
                    if not l["protected"] and l["origin"] != "human"
                    and (l.get("activated_at") or l["created_at"]) > since]  # went live after the good window
        for l in suspects:
            self.store.update_lesson(l["id"], status="quarantined")
        result["rolled_back"] = [l["id"] for l in suspects]
        self.store.set_meta("guard_last_rollback", str(time.time()))
        v = self.store.new_version("regression guard rollback", result)
        self.store.log(None, "learning", "rollback",
                       f"quality dropped (first-pass {fp_b:.0%}→{fp_r:.0%}, escalations {esc_b:.0%}→{esc_r:.0%}); "
                       f"quarantined {len(suspects)} recent lessons (playbook v{v})", result)
        return result


TERMINAL = ("delivered", "rejected", "failed", "cancelled")


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=1, default=str)[:60000]
