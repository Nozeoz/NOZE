"""Studio dashboard API (``/api/agency/*``) and page (``/agency``), mounted on NOZE's app."""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import Settings, _bool

log = logging.getLogger("noze.agency.web")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|changes|reject)$")
    notes: list[str] = []


class LessonIn(BaseModel):
    role: str = Field(pattern="^(manager|scout|analyst|editor|reviewer)$")
    text: str = Field(min_length=20, max_length=300)
    section: str = "general"
    scope: str = "global"


class LessonStatusIn(BaseModel):
    status: str = Field(pattern="^(active|archived)$")


class LeadIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    terms: str = Field(default="", max_length=30000)


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    terms: str = Field(min_length=10, max_length=30000)
    url: str = ""
    creator: str = ""


class SubmitIn(BaseModel):
    source: str = Field(min_length=1, max_length=2000)
    campaign: str | None = None
    clips: int | None = Field(default=None, ge=1, le=20)
    own: bool = False


class AgencyWeb:
    """Owns the AgencyContext for the web process and (optionally) the background runner."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._ax = None
        self._lock = threading.Lock()
        self._runner: tuple[threading.Thread, threading.Event] | None = None

    @property
    def ax(self):
        with self._lock:
            if self._ax is None:
                from .config import AgencySettings
                from .context import AgencyContext

                self._ax = AgencyContext(AgencySettings.load(self.settings))
            return self._ax

    def start(self) -> None:
        if _bool(os.environ.get("AGENCY_AUTORUN"), False):
            from .pipeline import start_background

            self._runner = start_background(self.ax)
            log.info("agency runner started")

    def stop(self) -> None:
        if self._runner:
            self._runner[1].set()

    @property
    def running(self) -> bool:
        return self._runner is not None and self._runner[0].is_alive()


def _job_json(ax, j: dict[str, Any]) -> dict[str, Any]:
    camp = ax.store.get_campaign(j["campaign_id"]) if j.get("campaign_id") else None
    return {"id": j["id"], "kind": j["kind"], "state": j["state"], "title": j["title"], "round": j["round"],
            "campaign": camp["name"] if camp else "", "parent_id": j.get("parent_id"), "error": j.get("error"),
            "canary": bool(j.get("canary")), "created_at": j["created_at"], "updated_at": j["updated_at"]}


def mount(app: FastAPI, web: AgencyWeb) -> None:
    def ax():
        return web.ax

    def agency():
        from .pipeline import Agency

        return Agency(ax())

    @app.get("/agency", include_in_schema=False)
    async def page() -> FileResponse:
        return FileResponse(WEB_DIR / "agency.html")

    @app.get("/api/agency/status")
    async def status() -> dict[str, Any]:
        def work():
            from .roles import Manager

            a = ax()
            jobs = a.store.list_jobs(limit=200)
            return {"jobs": [_job_json(a, j) for j in jobs], "counts": a.store.state_counts("clip"),
                    "alerts": Manager(a).monitor(), "spend_24h": round(a.store.spend(since=time.time() - 86400), 3),
                    "llm": {"available": a.llm.available, "reason": a.llm.reason, "model": a.cfg.model},
                    "auto_approve": a.cfg.auto_approve, "runner": web.running}
        return await run_in_threadpool(work)

    @app.get("/api/agency/jobs/{job_id}")
    async def job(job_id: int) -> dict[str, Any]:
        def work():
            a = ax()
            j = a.store.get_job(job_id)
            if not j:
                raise HTTPException(404, "job not found")
            plan = (a.store.artifact(job_id, "plan") or {}).get("data") or {}
            render = (a.store.artifact(job_id, "render") or {}).get("data") or {}
            return {**_job_json(a, j), "input": j["input"],
                    "data": {k: v for k, v in (j.get("data") or {}).items()
                             if k in ("history", "fix_log", "post", "delivery", "learning", "escalated", "duration")},
                    "events": a.store.events(job_id, limit=200), "reviews": a.store.reviews(job_id),
                    "plan": {k: plan.get(k) for k in ("title", "overlays", "captions", "music", "color", "post",
                                                      "rationale", "used_lessons")} if plan else None,
                    "segments": len(plan.get("segments") or []),
                    "render": {k: render.get(k) for k in ("duration", "loudness", "captions", "sfx", "font")}
                    if render else None,
                    "has_video": bool(render), "publications": a.store.publications(job_id),
                    "children": [_job_json(a, c) for c in a.store.list_jobs(parent_id=job_id, limit=100)],
                    "spend": round(a.store.spend(job_ids=[job_id]), 4)}
        return await run_in_threadpool(work)

    @app.get("/api/agency/jobs/{job_id}/video")
    async def video(job_id: int):
        a = ax()
        j = a.store.get_job(job_id)
        data = (j or {}).get("data") or {}
        path = data.get("final_path") or data.get("render_path")
        if not path or not Path(path).exists():
            raise HTTPException(404, "no video yet")
        return FileResponse(path, media_type="video/mp4")

    @app.post("/api/agency/jobs/{job_id}/decision")
    async def decision(job_id: int, body: DecisionIn) -> dict[str, Any]:
        try:
            state = await run_in_threadpool(agency().decide, job_id, body.decision, body.notes)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"state": state}

    @app.post("/api/agency/jobs/{job_id}/retry")
    async def retry(job_id: int) -> dict[str, Any]:
        try:
            return {"state": await run_in_threadpool(agency().retry, job_id)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/agency/tick")
    async def tick() -> dict[str, Any]:
        """Advance the queue a few steps (for setups without the background runner)."""
        return {"moved": await run_in_threadpool(agency().tick, 2)}

    @app.post("/api/agency/submit")
    async def submit(body: SubmitIn) -> dict[str, Any]:
        try:
            jid = await run_in_threadpool(lambda: agency().submit(body.source, body.campaign, clips=body.clips,
                                                                  own_content=body.own))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"id": jid}

    @app.get("/api/agency/report")
    async def report(days: float = 7.0) -> dict[str, Any]:
        from .reports import team_metrics

        return await run_in_threadpool(team_metrics, ax(), days)

    @app.get("/api/agency/playbook")
    async def playbook(all: bool = False) -> dict[str, Any]:
        a = ax()
        rows = a.store.lessons(statuses=None if all else ["active", "candidate", "quarantined"])
        return {"version": a.store.current_version(), "lessons": rows, "versions": a.store.versions(limit=15)}

    @app.post("/api/agency/playbook")
    async def add_lesson(body: LessonIn) -> dict[str, Any]:
        st = ax().store
        lid = st.add_lesson(body.role, body.text.strip() if body.text.strip().endswith(".") else body.text.strip() + ".",
                            section=body.section, scope=body.scope, status="active", origin="human", protected=True,
                            version=st.current_version() + 1)
        st.update_lesson(lid, activated_at=time.time())
        st.new_version(f"human lesson {lid}", {"added": [lid]})
        return {"id": lid}

    @app.post("/api/agency/playbook/{lesson_id}/status")
    async def lesson_status(lesson_id: str, body: LessonStatusIn) -> dict[str, Any]:
        st = ax().store
        if not st.get_lesson(lesson_id):
            raise HTTPException(404, "lesson not found")
        st.update_lesson(lesson_id, status=body.status,
                         activated_at=time.time() if body.status == "active" else None)
        st.new_version(f"{body.status} {lesson_id} (dashboard)", {body.status: [lesson_id]})
        return {"ok": True}

    @app.get("/api/agency/leads")
    async def leads(status: str = "") -> dict[str, Any]:
        a = ax()
        return {"leads": a.store.list_leads(status or None, limit=200), "campaigns": a.store.list_campaigns()}

    @app.post("/api/agency/leads")
    async def add_lead(body: LeadIn) -> dict[str, Any]:
        from .leads import LeadFinder

        try:
            return await run_in_threadpool(LeadFinder(ax()).add_manual, body.url, body.terms)
        except PermissionError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/agency/leads/{lead_id}/accept")
    async def accept_lead(lead_id: int) -> dict[str, Any]:
        from .leads import LeadFinder

        try:
            return {"campaign_id": await run_in_threadpool(LeadFinder(ax()).accept, lead_id, "")}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/agency/campaigns")
    async def add_campaign(body: CampaignIn) -> dict[str, Any]:
        if ax().store.get_campaign(body.name):
            raise HTTPException(400, "a campaign with that name exists")
        cid = await run_in_threadpool(lambda: agency().create_campaign(body.name, terms=body.terms, url=body.url,
                                                                       creator=body.creator))
        return {"id": cid}
