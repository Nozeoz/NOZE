"""The studio's workflow as an explicit state machine (the part learning never touches).

Source job (one long video)::

    queued ─ingest→ research ─scout+analyst→ select ─analyst+manager→ producing ──(all clips done)→ done
                                                         └─ spawns one clip job per chosen moment

Clip job::

    planning → rendering → reviewing ─pass→ approval ─approve→ approved → delivered
                   ▲            │fail                │changes        (manager / you)
                   └─ revising ◄┘ (round < max)      ├─reject→ rejected
                                └─(round = max)→ escalated → approved | rejected
    any step can park in awaiting_human (AGENCY_AUTO_APPROVE=0) or fail after 3 attempts.

Every step persists its artifact before the state moves, so a crash/restart resumes
exactly where it stopped (jobs are leased, not locked).
"""

from __future__ import annotations

import json
import logging
import random
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .context import AgencyContext
from .learning import TERMINAL
from .media.analyze import contact_sheets, extract_frames, loudness, measure, sample_times
from .media.ffmpeg import MediaError, probe
from .media.fetch import fetch_source
from .media.transcribe import all_words, speech_rate, text_between, transcribe
from .publish import Publisher
from .reports import clip_report, source_report
from .roles import Analyst, Editor, Manager, Reviewer, Scout
from .roles.manager import clean_brief
from .schemas import BRIEF, conform, example
from .story import envelope, label_parts, moment_parts

log = logging.getLogger("noze.agency.pipeline")

SOURCE_STEPS = ("queued", "research", "select", "producing")
CLIP_STEPS = ("planning", "rendering", "reviewing", "revising", "approval", "escalated", "approved")
MAX_ATTEMPTS = 3


PEAK_MIN_HEAT = 6.0  # [D] heat 0-10; below this no stretch is a peak worth opening on


def _overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    from .roles.analyst import parts_overlap

    return parts_overlap(a, b) > 0


def peak_second(sig: dict[str, Any] | None, parts: list[dict[str, Any]]) -> float | None:
    """Source second of the hottest signal bin inside the moment's parts (chat spike, scream, viewer clip),
    or None without signals. Speechless peaks (a scream, a crash) count — the editor's word search can't see them."""
    if not sig or not sig.get("bins"):
        return None
    step = float(sig.get("bin_s") or 2.0)
    best = None
    for b in sig["bins"]:
        t = float(b.get("t") or 0.0) + step / 2
        if any(p["start_s"] <= t <= p["end_s"] for p in parts) and (best is None or b.get("heat", 0) > best[0]):
            best = (float(b.get("heat") or 0.0), t)
    return round(best[1], 2) if best and best[0] >= PEAK_MIN_HEAT else None


class Blocked(Exception):
    """A job can't continue without a human (e.g. no permission evidence)."""


class Agency:
    def __init__(self, ax: AgencyContext):
        self.ax = ax
        self.store = ax.store
        self.cfg = ax.cfg
        self.manager = Manager(ax)
        self.scout = Scout(ax)
        self.analyst = Analyst(ax)
        self.editor = Editor(ax)
        self.reviewer = Reviewer(ax)
        self.publisher = Publisher(ax)
        self._handlers = {
            ("source", "queued"): self._ingest, ("source", "research"): self._research,
            ("source", "select"): self._select, ("source", "producing"): self._producing,
            ("clip", "planning"): self._plan, ("clip", "rendering"): self._render,
            ("clip", "reviewing"): self._review, ("clip", "revising"): self._revise,
            ("clip", "approval"): self._approve, ("clip", "escalated"): self._escalate,
            ("clip", "approved"): self._deliver,
        }

    # -- intake ----------------------------------------------------------------------------------------
    def submit(self, source: str, campaign: str | int | None = None, *, references: list[str] | None = None,
               clips: int | None = None, own_content: bool = False, notes: str = "", priority: int = 0,
               signals_url: str = "", offset_s: float = 0.0, internal_test: bool = False,
               vod_map: list[dict[str, Any]] | None = None, moments: list[dict[str, Any]] | None = None) -> int:
        """``signals_url``: the public VOD/video page the file came from (Twitch VOD, YouTube) so the
        analyst can read chat replay / viewer clips / most-replayed; ``offset_s``: where the file starts
        inside that VOD (a downloaded section). A platform URL as ``source`` is its own signals URL."""
        camp = self.store.get_campaign(campaign) if campaign is not None else None
        if campaign is not None and camp is None:
            raise ValueError(f"no campaign {campaign!r}")
        if not signals_url and str(source).startswith(("http://", "https://")):
            signals_url = str(source)
        jid = self.store.create_job(
            "source", "queued", campaign_id=camp["id"] if camp else None, title=Path(str(source)).name[:120],
            input={"source": str(source), "references": references or [], "clips": clips,
                   "own_content": own_content, "notes": notes, "signals_url": signals_url,
                   "offset_s": float(offset_s or 0.0), "internal_test": bool(internal_test),
                   # a story pack (several VOD ranges glued): file second → stream second, for chat & time cards
                   "vod_map": vod_map or None,
                   # moments the scan already picked (VOD seconds) — used as-is so a found arc is not lost
                   "moments": moments or None},
            priority=priority, playbook_version=self.store.current_version())
        self.store.log(jid, "manager", "submitted", f"new source {source}" + (f" for {camp['name']}" if camp else ""))
        return jid

    def create_campaign(self, name: str, terms: str = "", url: str = "", brief: dict[str, Any] | None = None,
                        creator: str = "", lead_id: int | None = None) -> int:
        if brief is None:
            brief = self.manager.brief_from_terms(terms, url, name)
        brief = clean_brief(conform(brief, BRIEF))
        permission = {**brief.get("permission", {}), "terms_excerpt": terms[:4000], "url": url or
                      (brief.get("permission") or {}).get("url"), "recorded_at": time.time()}
        cid = self.store.create_campaign(name, brief, permission, creator=creator or brief.get("creator", ""),
                                         lead_id=lead_id)
        self.store.log(None, "manager", "campaign", f"campaign '{name}' created "
                       f"(permission {'granted' if permission.get('granted') else 'NOT recorded'})", {"id": cid})
        return cid

    def add_clip(self, source_id: int, start_s: float, end_s: float, title: str = "") -> int:
        """The manager assigns one more clip from a source at a moment they picked themselves."""
        src = self.store.get_job(source_id)
        if not src or src["kind"] != "source" or not (src.get("data") or {}).get("transcript_path"):
            raise ValueError(f"job {source_id} is not a researched source")
        if not 0 <= start_s < end_s <= float(src["data"].get("duration") or 1e9):
            raise ValueError(f"{start_s}-{end_s}s is not a range inside the source")
        tr = json.loads(Path(src["data"]["transcript_path"]).read_text(encoding="utf-8"))
        text = text_between(tr, start_s, end_s)
        first = next((s["text"] for s in tr.get("segments") or [] if s["end"] > start_s), "")
        m = {"start_s": round(start_s, 3), "end_s": round(end_s, 3), "title": title or first[:70] or "clip",
             "hook_line": first[:120], "hook_type": "other", "summary": text[:200],
             "rationale": "picked by the manager", "keywords": [], "overall": None,
             "scores": {"hook": 0, "flow": 0, "value": 0, "trend": 0, "emotion": 0}}
        cid = self.store.create_job("clip", "planning", campaign_id=src.get("campaign_id"), parent_id=source_id,
                                    title=m["title"], input={"moment": m}, canary=False,
                                    playbook_version=self.store.current_version())
        self.store.log(cid, "manager", "assigned", f"editor assigned by hand: '{m['title']}' "
                       f"({start_s:.1f}-{end_s:.1f}s)")
        if src["state"] == "done":  # the source report waits for the new clip too
            self._move(src, "producing", "manager", "done → producing: extra clip assigned")
        return cid

    def retry(self, job_id: int) -> str:
        """Put a failed / blocked job back to the furthest step its saved artifacts allow."""
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError(f"no job {job_id}")
        if job["state"] not in ("failed", "awaiting_human", "rejected", "done"):
            raise ValueError(f"job {job_id} is {job['state']}; only failed/blocked/rejected jobs can be retried")
        if job["kind"] == "source":
            data = job.get("data") or {}
            has_clips = bool(self.store.list_jobs(parent_id=job_id, limit=1))
            state = ("queued" if not data.get("source_path") else
                     "research" if not self.store.artifact(job_id, "blueprint") else
                     "producing" if has_clips else "select")
        else:
            state = "rendering" if self.store.artifact(job_id, "plan") else "planning"
            self.store.merge_job_data(job_id, {"learned": False, "escalated": False, "render_failures": 0,
                                               "render_failed": False})
            self.store.update_job(job_id, round=0)
        self.store.update_job(job_id, finished_at=None)
        self._move(job, state, "human", f"retry: {job['state']} → {state}")
        return state

    def scan_inbox(self) -> list[int]:
        """Files dropped in ``agency/inbox/<campaign>/`` (or ``inbox/own/``) become source jobs."""
        from .media.fetch import VIDEO_EXT

        submitted = []
        root = self.cfg.inbox_dir
        if not root.exists():
            return submitted
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            own = folder.name.lower() in ("own", "mine", "own-content")
            camp = None if own else self.store.get_campaign(folder.name)
            if not own and camp is None:
                continue
            for f in sorted(folder.iterdir()):
                if f.suffix.lower() not in VIDEO_EXT or f.name.startswith(".") or not f.is_file():
                    continue  # (a broken symlink is not a file)
                try:
                    st = f.stat()
                    if time.time() - st.st_mtime < 30:  # still being copied
                        continue
                    # move it out of the inbox: the job owns the file from now on
                    dest_dir = self.cfg.root / "sources" / folder.name
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / f.name
                    if dest.exists():
                        dest = dest_dir / f"{f.stem}_{int(st.st_mtime)}{f.suffix}"
                    shutil.move(str(f), dest)
                    for side in list(folder.iterdir()):  # .srt / .vtt / .json sidecars travel along
                        if side.name.startswith(f.stem + ".") and side.suffix.lower() in (".srt", ".vtt", ".json"):
                            shutil.move(str(side), dest_dir / (dest.stem + side.name[len(f.stem):]))
                except OSError as exc:
                    log.warning("inbox file %s skipped: %s", f, exc)
                    continue
                submitted.append(self.submit(str(dest), camp["id"] if camp else None, own_content=own))
        return submitted

    # -- running ----------------------------------------------------------------------------------------
    def tick(self, max_jobs: int = 4) -> int:
        """Advance up to ``max_jobs`` jobs by one step each. Returns how many moved."""
        states = list(SOURCE_STEPS) + list(CLIP_STEPS)
        jobs = self.store.claim_jobs(states, limit=max(max_jobs, self.cfg.parallel + 1))

        def one(job: dict[str, Any]) -> int:
            try:
                return 1 if self.step(job) else 0
            finally:
                self.store.release_job(job["id"])

        sources = [j for j in jobs if j["kind"] == "source"]
        clips = [j for j in jobs if j["kind"] != "source"]
        moved = 0
        if len(clips) > 1 and self.cfg.parallel > 1:  # each clip is its own editor/reviewer: no shared state
            with ThreadPoolExecutor(max_workers=min(self.cfg.parallel, len(clips)),
                                    thread_name_prefix="noze-clip") as pool:
                moved += sum(pool.map(one, clips))
        else:
            moved += sum(one(j) for j in clips)
        moved += sum(one(j) for j in sources)
        return moved

    def run(self, stop: threading.Event | None = None, idle_sleep: float = 5.0, once: bool = False) -> None:
        stop = stop or threading.Event()
        last_monitor = 0.0
        while not stop.is_set():
            try:
                moved = self._iteration(once, last_monitor)
                if time.time() - last_monitor > 300:
                    last_monitor = time.time()
            except Exception:  # a bad iteration (locked DB, odd file …) must not kill the studio
                log.exception("studio loop error")
                if once:
                    raise
                stop.wait(max(idle_sleep, 5.0) * 2)
                continue
            if once and moved == 0:
                break
            if moved == 0:
                stop.wait(idle_sleep)

    def _iteration(self, once: bool, last_monitor: float) -> int:
        self.scan_inbox()
        moved = self.tick()
        if time.time() - last_monitor > 300:
            for alert in self.manager.monitor():
                log.info("monitor: %s", alert["message"])
            if not once:
                self.routines()
        if moved == 0:  # wrap up batches whose clips all finished (don't wait for the 20 s re-check)
            for src in self.store.list_jobs(kind="source", states=["producing"], limit=200):
                kids = self.store.list_jobs(parent_id=src["id"], limit=500)
                if not kids or all(k["state"] in TERMINAL for k in kids):
                    self.store.update_job(src["id"], next_run=0)
                    moved += self.tick()
        return moved

    def routines(self) -> list[str]:
        """The manager's recurring chores while the studio runs: scout for new clipping
        campaigns and publish the team report on schedule. Each is optional and never
        allowed to stop production."""
        done = []
        now = time.time()
        cfg = self.cfg
        if cfg.lead_scout_every_h > 0 and now - float(self.store.get_meta("routine:lead_scout", "0") or 0) \
                >= cfg.lead_scout_every_h * 3600:
            self.store.set_meta("routine:lead_scout", str(now))
            if cfg.key("WHOP_API_KEY") or cfg.base.key("REDDIT_CLIENT_ID") or cfg.base.key("YOUTUBE_API_KEY") \
                    or cfg.lead_feeds:
                try:
                    from .leads import LeadFinder

                    rep = LeadFinder(self.ax).scout()
                    good = [q for q in rep["qualified"] if q["decision"] == "accept"]
                    if good and (cfg.key("AGENCY_WEBHOOK_URL") or cfg.key("TELEGRAM_BOT_TOKEN")):
                        self.publisher.notify("🔎 New clipping campaigns worth a look:\n" + "\n".join(
                            f"#{q['id']} ({q['score']:.0f}) {q['title'][:90]}" for q in good[:10]))
                    done.append("lead_scout")
                except Exception as exc:
                    log.warning("lead scouting failed: %s", exc)
        if cfg.report_every_h > 0 and now - float(self.store.get_meta("routine:team_report", "0") or 0) \
                >= cfg.report_every_h * 3600:
            self.store.set_meta("routine:team_report", str(now))
            if self.store.list_jobs(kind="clip", limit=1):
                try:
                    from .reports import team_report

                    path, _ = team_report(self.ax, days=max(1.0, cfg.report_every_h / 24))
                    if cfg.key("AGENCY_WEBHOOK_URL") or cfg.key("TELEGRAM_BOT_TOKEN"):
                        self.publisher.notify(path.read_text(encoding="utf-8")[:3800])
                    done.append("team_report")
                except Exception as exc:
                    log.warning("team report failed: %s", exc)
        return done

    def step(self, job: dict[str, Any]) -> bool:
        handler = self._handlers.get((job["kind"], job["state"]))
        if handler is None:
            return False
        try:
            new_state = handler(job)
        except Blocked as exc:
            self._move(job, "awaiting_human", "manager", f"blocked: {exc}", error=str(exc))
            return True
        except Exception as exc:
            attempts = int(job.get("attempts") or 0) + 1
            msg = f"{type(exc).__name__}: {exc}"
            log.warning("job %s (%s/%s) failed: %s", job["id"], job["kind"], job["state"], msg)
            self.store.log(job["id"], "system", "error", msg[:1500], {"trace": traceback.format_exc()[-3000:]})
            if attempts >= MAX_ATTEMPTS:
                self._move(job, "failed", "manager", f"giving up after {attempts} attempts: {msg[:300]}",
                           error=msg[:1000])
            else:
                self.store.update_job(job["id"], attempts=attempts, error=msg[:1000],
                                      next_run=time.time() + 30 * (2 ** attempts))
            return True
        if new_state and new_state != job["state"]:
            self._move(job, new_state, "system", "")
        return True

    def _move(self, job: dict[str, Any], state: str, role: str, message: str, error: str = "") -> bool:
        """Move a job to ``state`` — only if nobody else moved it meanwhile (compare-and-set)."""
        fields: dict[str, Any] = {"state": state, "attempts": 0, "next_run": 0, "error": error}
        if state in TERMINAL or state == "done":
            fields["finished_at"] = time.time()
        if not self.store.transition(job["id"], job["state"], **fields):
            current = (self.store.get_job(job["id"]) or {}).get("state")
            log.info("job %s: %s → %s skipped, it is now %s", job["id"], job["state"], state, current)
            self.store.log(job["id"], role, "state_conflict",
                           f"{job['state']} → {state} skipped: the job was moved to {current} meanwhile")
            return False
        self.store.log(job["id"], role, "state", message or f"{job['state']} → {state}",
                       {"from": job["state"], "to": state})
        if job["kind"] == "clip" and state in TERMINAL:
            self._after_clip(self.store.get_job(job["id"]))
            if state == "delivered":
                try:
                    clip_report(self.ax, self.store.get_job(job["id"]))
                except Exception as exc:  # a report must never undo a delivery
                    log.warning("clip report for %s failed: %s", job["id"], exc)
        return True

    # -- source steps -----------------------------------------------------------------------------------
    def _brief(self, job: dict[str, Any]) -> dict[str, Any]:
        camp = self.store.get_campaign(job["campaign_id"]) if job.get("campaign_id") else None
        if camp:
            return clean_brief(conform(camp["brief"], BRIEF))  # also heals briefs saved before the fix
        b = example(BRIEF)
        b["campaign_name"] = "own content"
        b["permission"] = {"granted": True, "evidence": "user's own content", "url": None}
        return b

    def _ingest(self, job: dict[str, Any]) -> str:
        inp = job["input"]
        brief = self._brief(job)
        if inp.get("internal_test") and not (brief.get("permission") or {}).get("granted"):
            self.store.log(job["id"], "manager", "internal_test",
                           "no permission recorded: rendering for internal review only — never delivered/published")
        elif not (brief.get("permission") or {}).get("granted") and not inp.get("own_content"):
            raise Blocked("no clipping permission recorded for this campaign — paste the campaign terms "
                          "(`noze agency campaign add --terms`) or mark the source as your own content (--own)")
        d = self.ax.job_dir(job)
        bank = self.ax.bank

        def bank_path(aid: str):
            a = bank.db.get_asset(aid) if bank else None
            return bank.storage.local_path(a["blob_key"]) if a and a.get("blob_key") else None

        path = fetch_source(inp["source"], d / "source", allow_download=self.cfg.allow_download,
                            allow_private=self.cfg.base.allow_private_fetch, bank_path=bank_path)
        info = probe(path)
        if not info.get("has_video"):
            raise MediaError("source has no video stream")
        names = [brief.get("creator") or ""] + [h.rsplit("/", 1)[-1] for h in brief.get("creator_handles") or []]
        hint = ", ".join(dict.fromkeys(n.lstrip("@") for n in names if n))  # spell the creator's name right
        tr = transcribe(path, self.cfg.transcriber, self.cfg.whisper_model, language=brief.get("language") or None,
                        cache=d / "transcript.json", hint=f"{hint}." if hint else "")
        dur = float(info.get("duration") or 0)
        facts: dict[str, Any] = measure(path) if dur <= 20 * 60 else {"probe": info, "loudness": loudness(path)}
        facts["speech_wpm"] = speech_rate(tr)
        facts["transcript_source"] = tr.get("source")
        if inp.get("vod_map"):
            facts["vod_map"] = inp["vod_map"]
        self.store.put_artifact(job["id"], "source_info", facts, path=path, role="manager")
        self._collect_signals(job, path, d, dur)
        self.store.merge_job_data(job["id"], {"source_path": str(path), "transcript_path": str(d / "transcript.json"),
                                              "language": tr.get("language"), "duration": dur})
        words = len(all_words(tr))
        self.store.log(job["id"], "manager", "ingested",
                       f"{dur / 60:.1f} min, {info.get('width')}x{info.get('height')}, transcript: "
                       f"{tr.get('source')} ({words} words)")
        return "research"

    def _collect_signals(self, job: dict[str, Any], path: Path, d: Path, dur: float) -> None:
        """Chat replay, viewer clips, most-replayed, laughter/cheer — whatever this source has. Optional:
        a missing signal never stops the job (the analyst falls back to transcript + loudness)."""
        inp = job["input"]
        try:
            from .media.signals import collect_signals

            sig = collect_signals(path, d, url=inp.get("signals_url") or "", offset_s=float(inp.get("offset_s") or 0),
                                  vod_map=inp.get("vod_map") or None,
                                  duration=dur,
                                  # --vod-url is the user opting in to reading that page's chat/clips
                                  allow_network=self.cfg.allow_download or bool(inp.get("signals_url")),
                                  models_dir=self.cfg.root / "cache" / "models")
        except Exception as exc:
            log.warning("signals unavailable for job %s: %s", job["id"], exc)
            self.store.log(job["id"], "analyst", "signals", f"no signals: {str(exc)[:300]}")
            return
        self.store.merge_job_data(job["id"], {"signals_path": str(d / "signals.json")})
        self.store.log(job["id"], "analyst", "signals",
                       f"signals: {', '.join(sig.get('sources') or []) or 'none'}; {len(sig.get('peaks') or [])} peaks, "
                       f"{len(sig.get('clips') or [])} viewer clips" + (f"; notes: {'; '.join(sig['notes'])[:300]}"
                                                                      if sig.get("notes") else ""))

    def _scan_moments(self, job: dict[str, Any], tr: dict[str, Any], facts: dict[str, Any], brief: dict[str, Any],
                      min_s: float, max_s: float) -> list[dict[str, Any]]:
        """Moments `noze agency scan` picked (VOD seconds) mapped onto the pack file and re-checked by the analyst's
        own gate (snap, quote, link) — never trusted blindly; a part outside the pack drops the moment."""
        raw = (job.get("input") or {}).get("moments") or []
        if not raw:
            return []
        vod_map = facts.get("vod_map")
        offset = float((job.get("input") or {}).get("offset_s") or 0.0)
        from .roles.analyst import build_moment
        from .story import to_file

        def file_t(t: float) -> float | None:
            if vod_map:
                return to_file(t, vod_map)
            v = t - offset  # a plain section (fetch + --vod-offset): one offset for the whole file
            return v if 0.0 <= v <= float(facts.get("probe", {}).get("duration") or 1e12) else None

        words = all_words(tr)
        out, dropped = [], []
        for m in raw:
            parts, why = [], []
            for p in m.get("parts") or [{"start_s": m["start_s"], "end_s": m["end_s"], "role": "build"}]:
                a, b = file_t(float(p["start_s"])), file_t(float(p["end_s"]))
                if a is None or b is None or b - a < 1.0:
                    why, parts = ["part outside this source file"], []
                    break
                parts.append({**p, "start_s": a, "end_s": b})
            built = None
            if parts:
                mm = {**m, "parts": parts, "start_s": min(p["start_s"] for p in parts),
                      "end_s": max(p["end_s"] for p in parts)}
                built = build_moment(mm, words, self._signals(job), min_s, max_s, why, vod_map, brief)
            if not built:
                dropped.append(f"'{m.get('title', '')[:50]}': {why[0] if why else 'failed the checks'}")
                continue
            # the scan already scored and ranked it: keep its numbers (a second build double-counted the boosts and
            # dropped the arc-gap bonus — the Lucia arc fell from first to last)
            for k in ("scores", "overall", "emotion", "structure", "story", "title"):
                if m.get(k) not in (None, ""):
                    built[k] = m[k]
            built["rationale"] = "picked by the stream scan; " + str(m.get("rationale") or built.get("rationale") or "")
            built["from_scan"] = True
            out.append(built)
        self.store.log(job["id"], "analyst", "scan_moments",
                       f"{len(out)} of {len(raw)} scan-picked moment(s) passed the analyst's checks on this source"
                       + (f"; dropped: {'; '.join(dropped)}"[:900] if dropped else ""))
        # cross-period arcs lead: they are what the scan exists for
        out.sort(key=lambda m: (m.get("structure") in ("arc", "cold_open", "montage"), float(m.get("overall") or 0)),
                 reverse=True)
        return out

    def _signals(self, job: dict[str, Any]) -> dict[str, Any] | None:
        p = (job.get("data") or {}).get("signals_path")
        try:
            return json.loads(Path(p).read_text(encoding="utf-8")) if p and Path(p).exists() else None
        except (OSError, ValueError):
            return None

    def _research(self, job: dict[str, Any]) -> str:
        brief = self._brief(job)
        picks = self.scout.pick(job, brief)
        self.store.put_artifact(job["id"], "references", picks, role="scout")
        self.store.log(job["id"], "scout", "references",
                       f"{len(picks['picks'])} reference(s) picked from {picks.get('candidates', 0)} candidate(s)")
        refs_dir = self.cfg.root / "cache" / "reference_files"
        breakdowns = []
        for pick in picks["picks"]:
            p = self.scout.resolve(pick["ref"], refs_dir)
            if p is None:
                continue
            bd = self.analyst.breakdown(job, p, pick.get("why", ""))
            breakdowns.append(bd)
            self.store.put_artifact(job["id"], "breakdown", bd, path=p, role="analyst")
        facts = (self.store.artifact(job["id"], "source_info") or {}).get("data") or {}
        bp = self.analyst.blueprint(job, breakdowns, brief, {k: facts.get(k) for k in ("shots", "speech_wpm",
                                                                                       "silence_share")})
        self.store.put_artifact(job["id"], "blueprint", bp, role="analyst")
        self.store.log(job["id"], "analyst", "blueprint", f"blueprint '{bp.get('name')}' from {len(breakdowns)} "
                       f"reference breakdown(s)")
        return "select"

    def _select(self, job: dict[str, Any]) -> str:
        brief = self._brief(job)
        data = job["data"]
        tr = json.loads(Path(data["transcript_path"]).read_text(encoding="utf-8"))
        facts = (self.store.artifact(job["id"], "source_info") or {}).get("data") or {}
        bp = (self.store.artifact(job["id"], "blueprint") or {}).get("data") or {}
        n = int(job["input"].get("clips") or (brief.get("deliverables") or {}).get("clips_per_source")
                or self.cfg.clips_per_source)
        length = brief.get("clip_length") or {}
        min_s = float(length.get("min_s") or self.cfg.min_clip_s)
        max_s = float(length.get("max_s") or self.cfg.max_clip_s)
        # the scan's picks lead (mandor CP2 #4: re-mining the pack lost the 43-minute Lucia arc); the analyst only
        # fills the slots left, never overlapping a scan pick
        self.analyst.last_rejected = []
        picked = self._scan_moments(job, tr, facts, brief, min_s, max_s)
        chosen = []
        for m in picked:  # scan order (arcs first); the manager's length rule still applies, picks never overlap
            ok = self.manager.select_moments([m], 1, min_s, max_s)
            if len(chosen) < n and ok and not any(_overlaps(m, c) for c in chosen):
                chosen.append(ok[0])
        moments = list(picked)
        if len(chosen) < n:
            from .roles.analyst import parts_overlap

            mined = self.analyst.moments(job, tr, facts, brief, bp, n, min_s, max_s, signals=self._signals(job))
            free = [m for m in mined if not any(parts_overlap(m, c) > 0 for c in chosen)]
            chosen += self.manager.select_moments(free, n - len(chosen), min_s, max_s)
            moments += mined
        sig = self._signals(job)
        for m in chosen:  # the editor opens on the peak (docs/REFERENSI-CLIPPER-2026-11.md): measured, not guessed
            if m.get("peak_s") is None:
                m["peak_s"] = peak_second(sig, moment_parts(m))
        self.store.put_artifact(job["id"], "moments", {"candidates": moments[:30], "chosen": chosen,
                                                  "rejected": (getattr(self.analyst, "last_rejected", None) or [])[:30]},
                                role="analyst")
        if not chosen:
            self.store.log(job["id"], "manager", "alert", "no usable moments found in this source")
            return "done"
        version = self.store.current_version()
        for m in chosen:
            cid = self.store.create_job("clip", "planning", campaign_id=job.get("campaign_id"), parent_id=job["id"],
                                        title=m.get("title") or "clip", input={"moment": m},
                                        canary=random.Random(f"{job['id']}:{m['start_s']}").random() < self.cfg.canary_share,
                                        playbook_version=version)
            parts = moment_parts(m)
            self.store.log(cid, "manager", "assigned",
                           f"editor assigned: '{m.get('title')}' [{m.get('structure') or 'linear'}/"
                           f"{m.get('emotion') or '?'}] " + " → ".join(f"{p['start_s']:.0f}-{p['end_s']:.0f}s"
                                                                       for p in parts)
                           + f", score {m.get('overall')}")
        self.store.log(job["id"], "manager", "staffed", f"{len(chosen)} clip(s) assigned out of "
                       f"{len(moments)} candidate moments")
        return "producing"

    def _producing(self, job: dict[str, Any]) -> str:
        kids = self.store.list_jobs(parent_id=job["id"], limit=500)
        if all(k["state"] in TERMINAL for k in kids):  # (no clips at all → nothing left to wait for)
            path = source_report(self.ax, job, kids)
            self.store.merge_job_data(job["id"], {"report": str(path)})
            return "done"
        self.store.update_job(job["id"], next_run=time.time() + 20)
        return "producing"

    # -- clip steps ------------------------------------------------------------------------------------
    def clip_ctx(self, job: dict[str, Any]) -> dict[str, Any]:
        parent = self.store.get_job(job["parent_id"])
        pdata = parent["data"]
        tr = json.loads(Path(pdata["transcript_path"]).read_text(encoding="utf-8"))
        facts = (self.store.artifact(parent["id"], "source_info") or {}).get("data") or {}
        return {
            "parent": parent, "source": Path(pdata["source_path"]), "transcript": tr, "words": all_words(tr),
            "blueprint": (self.store.artifact(parent["id"], "blueprint") or {}).get("data") or {},
            "brief": self._brief(job), "moment": job["input"]["moment"], "source_info": facts.get("probe") or {},
        }

    def _prep(self, job: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
        return self.editor.prepare(job, c["source"], c["moment"], c["transcript"], c["blueprint"], c["source_info"])

    def _plan(self, job: dict[str, Any]) -> str:
        c = self.clip_ctx(job)
        prep = self._prep(job, c)
        plan = self.editor.plan(job, c["moment"], c["brief"], c["blueprint"], prep)
        v = self.store.put_artifact(job["id"], "plan", plan, role="editor")
        self.store.merge_job_data(job["id"], {"plan_version": v})
        self.store.log(job["id"], "editor", "plan", f"plan v{v}: {len(plan['segments'])} segments, "
                       f"{len(plan['overlays'])} text beats, {len(plan['sfx'])} SFX")
        return "rendering"

    def _render(self, job: dict[str, Any]) -> str:
        c = self.clip_ctx(job)
        if not c["source"].exists():  # not the plan's fault — retry/backoff, then fail
            raise FileNotFoundError(f"source video is gone: {c['source']}")
        art = self.store.artifact(job["id"], "plan")
        plan = art["data"]
        try:
            res = self.editor.render(job, plan, c["source"], c["words"], art["version"])
        except MediaError as exc:
            failures = int((job.get("data") or {}).get("render_failures") or 0) + 1
            self.store.merge_job_data(job["id"], {"render_failures": failures})
            self.store.log(job["id"], "editor", "render_failed", str(exc)[-500:])
            if failures >= 2:  # a simplified plan failed too: the environment is the problem
                raise
            # a plan the engine can't render goes back to the editor once, like a review note
            issue = {"id": "technical:render_failed", "category": "technical", "severity": "blocker",
                     "timecode_s": None, "description": f"render failed: {str(exc)[-300:]}",
                     "fix": "simplify the plan: no shake/push/pull zooms, plain cuts", "source": "qc"}
            self.store.merge_job_data(job["id"], {"open_issues": [issue], "render_failed": True})
            return "revising"
        self.store.put_artifact(job["id"], "render", res.as_dict(), path=res.path, role="editor")
        self.store.merge_job_data(job["id"], {"render_path": str(res.path)})
        self.store.log(job["id"], "editor", "render", f"rendered v{art['version']}: {res.duration:.1f}s, "
                       f"{res.loudness.get('integrated')} LUFS, {res.captions} caption chunks")
        return "reviewing"

    def _review(self, job: dict[str, Any]) -> str:
        c = self.clip_ctx(job)
        plan = self.store.artifact(job["id"], "plan")["data"]
        render = self.store.artifact(job["id"], "render")["data"]
        previous = (job.get("data") or {}).get("open_issues") or []
        rnd = int(job.get("round") or 0) + 1
        rev = self.reviewer.review(job, plan, render, c["brief"], c["blueprint"], c["words"], rnd, previous)
        self.store.add_review(job["id"], rnd, "reviewer", rev["verdict"], rev["score"], rev["issues"], rev["summary"])
        self.store.put_artifact(job["id"], "review", rev, role="reviewer")
        self.store.update_job(job["id"], round=rnd)
        history = list((job.get("data") or {}).get("history") or [])
        history.append({"round": rnd, "verdict": rev["verdict"], "score": rev["score"],
                        "issues": [{k: i.get(k) for k in ("id", "severity", "description")} for i in rev["issues"]]})
        self.store.merge_job_data(job["id"], {"open_issues": rev["issues"], "history": history[-6:],
                                              "review_sheets": rev.get("sheets") or []})
        self.store.log(job["id"], "reviewer", "review", f"round {rnd}: {rev['verdict'].upper()} — {rev['summary']}")
        if rev["verdict"] == "pass":
            return "approval"
        if rnd >= self.cfg.max_rounds:
            self.store.merge_job_data(job["id"], {"escalated": True})
            return "escalated"
        return "revising"

    def _revise(self, job: dict[str, Any]) -> str:
        c = self.clip_ctx(job)
        data = job.get("data") or {}
        issues = data.get("open_issues") or []
        prev = self.store.artifact(job["id"], "plan")["data"]
        if any(i["id"] == "compliance:too_short" for i in issues):
            c["moment"] = self._extend_moment(job, c)
        prep = self._prep(job, c)
        plan = self.editor.revise(job, prev, issues, c["moment"], c["brief"], c["blueprint"], prep,
                                  data.get("history") or [])
        if data.get("render_failed"):  # whatever the model wrote, the next render is the simple one
            for s in plan["segments"]:
                s["shake"], s["zoom"], s["transition_in"] = False, {"type": "none", "scale": 1.0}, "cut"
                s["look"], s["hold"] = "none", 0.0
            plan["fx"] = {"vignette": False, "grain": False, "letterbox": False}
            plan.setdefault("music", {})["drop_at"] = None
            self.store.merge_job_data(job["id"], {"render_failed": False})
        v = self.store.put_artifact(job["id"], "plan", plan, role="editor")
        fix_log = list(data.get("fix_log") or []) + [{"round": job.get("round"), "fixes": plan.get("fixes") or []}]
        self.store.merge_job_data(job["id"], {"plan_version": v, "fix_log": fix_log[-6:]})
        self.store.log(job["id"], "editor", "revision", f"plan v{v}: addressed {len(plan.get('fixes') or [])} "
                       f"of {len(issues)} issue(s)")
        return "rendering"

    def _extend_moment(self, job: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
        """A clip came out shorter than the brief allows: let the moment run on to the end of
        a later sentence (within the max length), so the editor has material to add."""
        from .roles.analyst import sentences

        m = dict(c["moment"])
        parts = moment_parts(m)
        last = dict(parts[-1])
        old_end = last["end_s"]
        length = c["brief"].get("clip_length") or {}
        min_s = float(length.get("min_s") or self.cfg.min_clip_s)
        max_s = float(length.get("max_s") or self.cfg.max_clip_s)
        render = (self.store.artifact(job["id"], "render") or {}).get("data") or {}
        short_by = max(0.0, min_s - float(render.get("duration") or 0.0)) + 1.0
        others = sum(p["end_s"] - p["start_s"] for p in parts[:-1])
        nxt = min([p["start_s"] for p in parts if p["start_s"] > old_end]  # never run into another part ...
                  + [float(v["file_end"]) for v in m.get("vod_map") or [] if float(v["file_end"]) >= old_end - 0.05]
                  or [1e12])  # ... nor across a story-pack seam
        later = [s for s in sentences(c["words"]) if s["end"] > old_end]
        for i, sent in enumerate(later):
            if others + sent["end"] - last["start_s"] > max_s or sent["end"] > nxt:
                break
            next_start = later[i + 1]["start"] if i + 1 < len(later) else sent["end"] + 1.0
            last["end_s"] = round(min(sent["end"] + 0.25, next_start - 0.02, nxt - 0.02), 3)
            if last["end_s"] - old_end >= short_by:
                break
        if last["end_s"] != old_end:
            parts = label_parts(parts[:-1] + [last], m.get("vod_map"))
            m["parts"] = parts
            m["start_s"], m["end_s"] = envelope(parts)
            self.store.update_job(job["id"], input={**job["input"], "moment": m})
            self.store.log(job["id"], "manager", "moment_extended",
                           f"last part now ends at {last['end_s']:.1f}s (was {old_end:.1f}s) to reach "
                           f"the {min_s:.0f}s minimum")
        return m

    def _packet(self, job: dict[str, Any], frames: bool = True) -> tuple[dict[str, Any], list[str]]:
        c = self.clip_ctx(job)
        plan = self.store.artifact(job["id"], "plan")["data"]
        rev = (self.store.artifact(job["id"], "review") or {}).get("data") or {}
        render = self.store.artifact(job["id"], "render")["data"]
        sheets = [s for s in (job.get("data") or {}).get("review_sheets") or [] if Path(s).exists()]
        if not sheets and frames:
            times = sample_times(render["duration"], [], n=12)
            frames = extract_frames(render["path"], times, self.ax.job_dir(job) / "approval_frames", width=360)
            sheets = [str(p) for p in contact_sheets(frames, times, self.ax.job_dir(job) / "approval_sheet")]
        packet = {"title": job.get("title"), "moment": c["moment"], "brief": c["brief"],
                  "review": {k: rev.get(k) for k in ("verdict", "score", "summary", "issues", "scores", "creative_review")},
                  "qc": {k: (rev.get("metrics") or {}).get(k) for k in ("duration", "loudness", "longest_static_s")},
                  "post": plan.get("post"), "history": (job.get("data") or {}).get("history"),
                  "plan": {k: plan.get(k) for k in ("overlays", "captions", "music", "color")},
                  "internal_test": bool((c["parent"].get("input") or {}).get("internal_test"))
                  and not (c["brief"].get("permission") or {}).get("granted")}
        return packet, sheets

    def _approve(self, job: dict[str, Any]) -> str:
        if not self.cfg.auto_approve:
            self.store.log(job["id"], "manager", "awaiting_human", "passed review — waiting for your approval")
            return "awaiting_human"
        packet, sheets = self._packet(job, frames=False)  # the reviewer already judged the frames
        if self._hold_for_human(job, packet):
            return "awaiting_human"
        dec = self.manager.approve(job, packet, sheets)
        return self._apply_decision(job, dec, "manager")

    def _hold_for_human(self, job: dict[str, Any], packet: dict[str, Any]) -> bool:
        """A QC-only review (no creative pass) is never enough for an automatic approval."""
        why = self.manager.needs_human(packet)
        if why:
            self.store.merge_job_data(job["id"], {"hold_reason": why})
            self.store.log(job["id"], "manager", "awaiting_human", why)
        return bool(why)

    def _escalate(self, job: dict[str, Any]) -> str:
        if not self.cfg.auto_approve:
            return "awaiting_human"
        packet, sheets = self._packet(job)
        if self._hold_for_human(job, packet):
            return "awaiting_human"
        dec = self.manager.approve(job, packet, sheets, escalation=True)
        if dec["decision"] == "changes":
            dec["decision"] = "reject"  # no more rounds after an escalation
        return self._apply_decision(job, dec, "manager")

    def _apply_decision(self, job: dict[str, Any], dec: dict[str, Any], who: str) -> str:
        verdict = {"approve": "pass", "changes": "fail", "reject": "reject"}[dec["decision"]]
        notes = [{"id": f"{who}:{k + 1}", **n, "source": who} for k, n in enumerate(dec.get("notes_for_editor") or [])]
        self.store.add_review(job["id"], int(job.get("round") or 0), who, verdict, None, notes,
                              "; ".join(dec.get("reasons") or [])[:1000])
        self.store.put_artifact(job["id"], "approval", dec, role=who)
        self.store.log(job["id"], who, "decision", f"{dec['decision'].upper()}: " + "; ".join(dec.get("reasons") or []))
        if dec["decision"] == "approve":
            self.store.merge_job_data(job["id"], {"post": dec.get("post")})
            return "approved"
        if dec["decision"] == "changes" and int(job.get("round") or 0) <= self.cfg.max_rounds:
            self.store.merge_job_data(job["id"], {"open_issues": notes})
            self.store.update_job(job["id"], round=int(job.get("round") or 0) + 1)
            return "revising"
        return "rejected"

    def decide(self, job_id: int, decision: str, notes: list[str] | None = None) -> str:
        """Your call on a clip (approve / changes / reject), from the CLI or dashboard."""
        job = self.store.get_job(job_id)
        if not job or job["kind"] != "clip":
            raise ValueError(f"no clip job {job_id}")
        if job["state"] not in ("awaiting_human", "escalated", "approval", "approved"):
            raise ValueError(f"clip {job_id} is {job['state']} — decisions apply to clips waiting for approval")
        if job["state"] != "awaiting_human" and float(job.get("locked_until") or 0) > time.time():
            raise ValueError(f"the manager is deciding on clip {job_id} right now — try again in a moment")
        plan = (self.store.artifact(job_id, "plan") or {}).get("data") or {}
        dec = {"decision": decision, "reasons": ["decided by you"],
               "notes_for_editor": [{"category": "other", "severity": "major", "timecode_s": None,
                                     "description": n, "fix": n} for n in notes or []],
               "post": {"title": job.get("title"), **(plan.get("post") or {})}, "risk_flags": [], "used_lessons": []}
        new_state = self._apply_decision(job, dec, "human")
        if decision == "changes" and new_state == "rejected":
            new_state = "revising"  # you can always ask for one more round
            self.store.merge_job_data(job_id, {"open_issues": [{"id": f"human:{k + 1}", **n, "source": "human"}
                                                               for k, n in enumerate(dec["notes_for_editor"])]})
        if not self._move(job, new_state, "human", f"your decision: {decision}"):
            raise ValueError(f"clip {job_id} changed state while you were deciding — reload and try again")
        return new_state

    def _deliver(self, job: dict[str, Any]) -> str:
        c = self.clip_ctx(job)
        if (c["parent"].get("input") or {}).get("internal_test") and \
                not (c["brief"].get("permission") or {}).get("granted") and \
                not (c["parent"].get("input") or {}).get("own_content"):
            raise Blocked("internal test without campaign permission: paste the real campaign terms "
                          "(`noze agency campaign add`) before anything is delivered or posted")
        delivery = self.publisher.deliver(job, c["brief"])
        self.store.merge_job_data(job["id"], {"final_path": delivery["video"], "delivery": delivery})
        self.store.log(job["id"], "manager", "delivered", f"delivered to {', '.join(delivery['targets'])}")
        return "delivered"

    def _after_clip(self, job: dict[str, Any]) -> None:
        try:
            changes = self.ax.learner.after_clip(job)
            if changes and (changes.get("added") or changes.get("promoted") or changes.get("mined")
                            or (changes.get("guard") or {}).get("rolled_back")):
                self.store.log(job["id"], "learning", "playbook",
                               f"lessons +{len(changes.get('added') or [])} new, "
                               f"{len(changes.get('promoted') or [])} promoted, "
                               f"{len(changes.get('archived') or [])} archived, "
                               f"{len(changes.get('mined') or [])} preflight rules", changes)
        except Exception as exc:  # learning must never break delivery
            log.warning("learning after job %s failed: %s", job["id"], exc)
            self.store.log(job["id"], "learning", "error", str(exc)[:500])


def start_background(ax: AgencyContext) -> tuple[threading.Thread, threading.Event]:
    """Run the studio in a daemon thread (used by ``noze serve`` when AGENCY_AUTORUN=1)."""
    stop = threading.Event()
    agency = Agency(ax)
    t = threading.Thread(target=agency.run, kwargs={"stop": stop}, name="noze-agency", daemon=True)
    t.start()
    return t, stop
