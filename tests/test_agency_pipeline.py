"""The studio end to end on a synthetic video: heuristic mode, a scripted "Claude"
(prompts, credit assignment, the revision loop, reflection), human approval, the
permission gate and the dashboard API. Needs ffmpeg; renders at 360x640 to stay fast."""

import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noze.agency.config import AgencySettings
from noze.agency.context import AgencyContext
from noze.agency.media.ffmpeg import run
from noze.agency.pipeline import Agency
from noze.agency.reports import team_report
from noze.agency.roles.analyst import DEFAULT_BLUEPRINT
from noze.agency.roles.manager import heuristic_brief
from noze.agency.schemas import APPROVAL, BLUEPRINT, BRIEF, CREATIVE_REVIEW, EDIT_PLAN, MOMENTS, REFLECTION, conform
from noze.api import create_app
from noze.config import Settings

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")

LINES = ["Why do most people fail at saving money?", "Because nobody tells them the one rule that matters.",
         "Here is the secret.", "You pay yourself first, before anything else.", "That one habit changed my life!",
         "Now the biggest mistake.", "People buy things they don't understand.", "Never do that."]
TERMS = ("Clipping campaign: clip my podcast and post on TikTok. $1.50 per 1k views. Use #moneytips and tag "
         "@moneyguy. Clips 8-20 seconds.")


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    d = tmp_path_factory.mktemp("src")
    video = d / "talk.mp4"
    run(["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=30", "-f", "lavfi",
         "-i", "sine=frequency=200:duration=30:sample_rate=48000", "-af", "volume=0.4", "-c:v", "libx264",
         "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)])
    srt, t = [], 1.0
    for i, line in enumerate(LINES):
        d_ = 0.32 * len(line.split()) + 0.3
        a, b = t, t + d_
        srt.append(f"{i + 1}\n00:00:{int(a):02d},{int(a % 1 * 1000):03d} --> 00:00:{int(b):02d},{int(b % 1 * 1000):03d}\n{line}\n")
        t = b + 0.2
    (d / "talk.srt").write_text("\n".join(srt))
    return video


def make_ax(tmp_path, llm=None, **env):
    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "NOZE_DATA_DIR": str(tmp_path / "bank"),
           "AGENCY_LLM": "off", "AGENCY_WIDTH": "360", "AGENCY_HEIGHT": "640", "AGENCY_FPS": "15",
           "AGENCY_MIN_CLIP_S": "8", "AGENCY_MAX_CLIP_S": "20", "AGENCY_CLIPS_PER_SOURCE": "1", **env}
    base = Settings.load(env=env, dotenv=False)
    return AgencyContext(AgencySettings.load(base, env=env, dotenv=False), llm=llm)


def drain(agency, max_steps=60):
    agency.run(once=True, idle_sleep=0)
    return agency.store.list_jobs(limit=50)


class ScriptedClaude:
    """Stands in for Claude: answers each role's contract and records every prompt."""

    available = True
    reason = ""

    def __init__(self):
        self.calls = []
        self.reviews = 0
        self.lesson_ids = {}

    def json(self, role, system, content, schema, *, job_id=None, budget_job_ids=None, max_tokens=16000):
        text = content if isinstance(content, str) else "\n".join(b.get("text", "") for b in content
                                                                   if b.get("type") == "text")
        images = 0 if isinstance(content, str) else sum(1 for b in content if b.get("type") == "image")
        self.calls.append({"role": role, "system": system, "text": text, "images": images})
        return conform(self.answer(role, schema, text), schema)

    def answer(self, role, schema, text):
        if schema is BRIEF:
            return heuristic_brief(text)
        if schema is BLUEPRINT:
            return {**DEFAULT_BLUEPRINT, "name": "scripted blueprint"}
        if schema is MOMENTS:
            return {"moments": [{"start_s": 1.0, "end_s": 14.0, "title": "The one money rule",
                                 "hook_line": "Why do most people fail at saving money?", "hook_type": "question",
                                 "summary": "", "rationale": "question hook, clear payoff", "keywords": [],
                                 "scores": {"hook": 9, "flow": 8, "value": 8, "trend": 6, "emotion": 7}}],
                    "used_lessons": []}
        if schema is EDIT_PLAN:
            fixes = [{"issue_id": i, "change": "moved the hook title earlier"} for i in
                     sorted(set(re.findall(r'"id": "(creative:[^"]+)"', text)))]
            return {"title": "The one money rule",
                    "segments": [{"src_start": 1.0, "src_end": 6.0, "speed": 1.0, "reframe": {"mode": "center", "x": 0.5},
                                  "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut"},
                                 {"src_start": 6.2, "src_end": 13.5, "speed": 1.0, "reframe": {"mode": "fit_blur", "x": 0.5},
                                  "zoom": {"type": "punch", "scale": 1.12}, "shake": False, "transition_in": "flash"}],
                    "captions": {"enabled": True, "style": "bold_pop", "words_per_caption": 3, "position": "lower",
                                 "uppercase": True, "highlight_color": "#FFE600", "font_scale": 1.0},
                    "overlays": [{"kind": "hook_title", "text": "THE ONE MONEY RULE", "start": 0.0, "end": 2.5,
                                  "position": "top", "style": "pop"}],
                    "sfx": [{"kind": "whoosh", "at": 4.9, "gain_db": -10}], "music": {"enabled": False},
                    "color": "punchy", "progress_bar": True,
                    "post": {"caption": "The one rule nobody tells you", "hashtags": ["#money"]},
                    "fixes": fixes, "used_lessons": [self.lesson_ids["editor"]], "rationale": "scripted"}
        if schema is CREATIVE_REVIEW:
            self.reviews += 1
            if self.reviews == 1:
                return {"scores": {"overall": 6.0}, "summary": "hook title lands late",
                        "issues": [{"category": "hook", "severity": "major", "timecode_s": 0.0,
                                    "description": "Hook title arrives late", "fix": "show it from 0.0s"}],
                        "resolved_previous": [], "used_lessons": []}
            prev = re.findall(r'"id": "(creative:[^"]+)"', text)
            return {"scores": {"overall": 8.6}, "summary": "clean", "issues": [],
                    "resolved_previous": [{"issue_id": i, "resolved": True, "note": "fixed"} for i in prev],
                    "used_lessons": []}
        if schema is APPROVAL:
            return {"decision": "approve", "reasons": ["hook lands, brief met"], "notes_for_editor": [],
                    "post": {"title": "The one money rule", "caption": "The one rule nobody tells you",
                             "hashtags": ["#money"]}, "risk_flags": [], "used_lessons": []}
        if schema is REFLECTION:
            return {"bullet_tags": [{"id": self.lesson_ids["editor"], "tag": "helpful", "why": "hook worked"}],
                    "new_lessons": [{"role": "editor", "section": "hook", "scope": "creator",
                                     "text": "Show the hook title from frame one for this creator",
                                     "evidence": "round 1 flagged a late hook title"}],
                    "root_causes": ["late hook title"], "summary": "ok"}
        return {}


def test_scripted_studio_runs_the_full_loop(tmp_path, source):
    claude = ScriptedClaude()
    ax = make_ax(tmp_path, llm=claude)
    claude.lesson_ids["editor"] = ax.store.add_lesson("editor", "Put the payoff line on screen as a label.",
                                                      status="active", section="text")
    ag = Agency(ax)
    cid = ag.create_campaign("money", terms=TERMS, url="https://example.com/c", creator="Money Guy")
    ag.submit(str(source), cid, references=[str(source)])
    jobs = drain(ag)
    clip = next(j for j in jobs if j["kind"] == "clip")
    assert clip["state"] == "delivered", ax.store.events(clip["id"])
    assert clip["round"] == 2  # creative issue in round 1, fixed in round 2
    assert next(j for j in jobs if j["kind"] == "source")["state"] == "done"

    by_role = {}
    for c in claude.calls:
        by_role.setdefault(c["role"], []).append(c)
    editor_sys = by_role["editor"][0]["system"]
    assert "Senior Editor" in editor_sys and "Put the payoff line on screen" in editor_sys
    assert "House standards" in editor_sys and "Safe zone" in editor_sys
    assert by_role["reviewer"][0]["images"] >= 1 and by_role["manager"][-1]["images"] >= 1
    assert by_role["analyst"] and any("Measured facts" in c["text"] for c in by_role["analyst"])
    assert "Hook title arrives late" in by_role["editor"][1]["text"]  # the revision saw the pointed note

    lesson = ax.store.get_lesson(claude.lesson_ids["editor"])
    assert lesson["uses"] >= 2 and lesson["helpful"] == 1  # used in both plans, credited once by reflection
    learned = [l for l in ax.store.lessons("editor") if l["id"] != claude.lesson_ids["editor"]]
    assert learned and learned[0]["status"] == "candidate" and learned[0]["scope"] == "creator:money guy"

    data = ax.store.get_job(clip["id"])["data"]
    video = Path(data["final_path"])
    assert video.exists() and video.stat().st_size > 10_000
    caption = video.with_suffix(".txt").read_text()
    assert "#moneytips" in caption and "@moneyguy" in caption  # poka-yoke added the brief's rules
    assert (ax.cfg.reports_dir / "clips" / f"clip_{clip['id']:05d}.md").exists()
    fixes = [f for r in data["fix_log"] for f in r["fixes"]]
    assert any(f["issue_id"].startswith("creative:hook") for f in fixes)
    md, metrics = team_report(ax, days=1)
    assert metrics["throughput"]["delivered"] == 1 and metrics["editor"]["first_pass_rate_pct"] == 0.0
    assert "Team report" in md.read_text()
    ax.close()


def test_heuristic_mode_with_human_approval(tmp_path, source):
    ax = make_ax(tmp_path, AGENCY_AUTO_APPROVE="0")
    assert not ax.llm.available
    ag = Agency(ax)
    ag.submit(str(source), own_content=True)
    jobs = drain(ag)
    clip = next(j for j in jobs if j["kind"] == "clip")
    if clip["state"] == "escalated":  # heuristics couldn't converge — still parked for you
        pytest.fail(f"unexpected escalation: {ax.store.reviews(clip['id'])}")
    assert clip["state"] == "awaiting_human"
    with pytest.raises(ValueError):
        ag.decide(clip["id"] + 99, "approve")
    assert ag.decide(clip["id"], "approve") == "approved"
    drain(ag)
    assert ax.store.get_job(clip["id"])["state"] == "delivered"
    assert ax.store.get_job(clip["id"])["data"]["learned"] is True
    ax.close()


def test_no_permission_blocks_until_fixed(tmp_path, source):
    ax = make_ax(tmp_path)
    ag = Agency(ax)
    cid = ag.create_campaign("vague", terms="Great podcast, check it out every week.")
    jid = ag.submit(str(source), cid)
    ag.tick()
    job = ax.store.get_job(jid)
    assert job["state"] == "awaiting_human" and "permission" in job["error"]
    camp = ax.store.get_campaign(cid)
    ax.store.update_campaign(cid, brief={**camp["brief"], "permission": {"granted": True, "evidence": "DM'd ok",
                                                                         "url": None}})
    assert ag.retry(jid) == "queued"
    ag.tick()
    assert ax.store.get_job(jid)["state"] == "research"
    ax.close()


def test_dashboard_api(tmp_path):
    settings = Settings.load(data_dir=tmp_path / "bank", env={"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0",
                                                                "AGENCY_LLM": "off"}, dotenv=False)
    with TestClient(create_app(settings, start_worker=False)) as client:
        assert "NOZE Studio" in client.get("/agency").text
        s = client.get("/api/agency/status").json()
        assert s["jobs"] == [] and s["llm"]["available"] is False
        assert client.post("/api/agency/leads", json={"url": "https://whop.com/c/x"}).status_code == 400
        q = client.post("/api/agency/leads", json={"url": "https://whop.com/c/x", "terms": TERMS}).json()
        assert q["decision"] in ("accept", "maybe")
        assert client.post(f"/api/agency/leads/{q['id']}/accept").status_code == 200
        assert client.get("/api/agency/leads").json()["campaigns"][0]["permission"]["granted"] is True
        assert client.post("/api/agency/playbook", json={"role": "editor", "text": "short"}).status_code == 422
        r = client.post("/api/agency/playbook", json={"role": "editor", "text": "Keep the creator's logo bug top-left."})
        lid = r.json()["id"]
        pb = client.get("/api/agency/playbook").json()
        assert any(l["id"] == lid and l["protected"] for l in pb["lessons"]) and pb["version"] >= 1
        assert client.post("/api/agency/jobs/999/decision", json={"decision": "approve"}).status_code == 400
        assert client.post("/api/agency/jobs/1/decision", json={"decision": "nope"}).status_code == 422
        bad_origin = client.post("/api/agency/tick", headers={"Origin": "https://evil.example"})
        assert bad_origin.status_code == 403
        assert json.loads(client.get("/api/agency/report?days=1").text)["throughput"]["clips"] == 0
