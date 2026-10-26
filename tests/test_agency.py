"""Agency units: contracts, timeline maths, transcripts, captions, briefs, QC lint,
the editor's fix library and the learning loop (no ffmpeg, no network, no LLM)."""

import time

import pytest

from noze.agency.config import AgencySettings
from noze.agency.context import AgencyContext
from noze.agency.leads import automation_forbidden, html_to_text, LeadFinder
from noze.agency.learning import Learner, Playbook, lesson_problem, similarity
from noze.agency.media.captions import AssDoc, ass_color, build_captions, caption_styles, group_words, overlay_styles
from noze.agency.media.qc import caption_lint, compliance_lint
from noze.agency.media.timeline import Timeline, jump_cut, remove_output_range, sanitize_segments
from noze.agency.media.transcribe import parse_subtitles, spread_words
from noze.agency.roles.analyst import sentences, snap_moment
from noze.agency.roles.editor import Editor
from noze.agency.roles.manager import heuristic_brief
from noze.agency.schemas import BRIEF, EDIT_PLAN, conform
from noze.config import Settings

BASE_ENV = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off"}


@pytest.fixture
def ax(tmp_path):
    env = {**BASE_ENV, "NOZE_DATA_DIR": str(tmp_path / "bank")}
    base = Settings.load(env=env, dotenv=False)
    a = AgencyContext(AgencySettings.load(base, env=env, dotenv=False))
    yield a
    a.close()


def seg(a, b, **kw):
    return {"src_start": a, "src_end": b, "speed": 1.0, "reframe": {"mode": "center", "x": 0.5},
            "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut", "note": "", **kw}


# -- contracts --------------------------------------------------------------------------------------
def test_conform_fills_defaults_and_snaps_bad_values():
    out = conform({"segments": [{"src_start": "1.5", "src_end": 3, "zoom": {"type": "PUNCH"}, "bogus": 1}],
                   "captions": {"style": "nonsense"}, "extra": "dropped"}, EDIT_PLAN)
    s = out["segments"][0]
    assert s["src_start"] == 1.5 and s["zoom"]["type"] == "punch" and "bogus" not in s
    assert s["transition_in"] == "cut"  # missing enum → first option
    assert out["captions"]["style"] == "bold_pop" and "extra" not in out
    assert out["overlays"] == [] and out["music"]["enabled"] is False
    brief = conform({"payout": {"rate_usd": None}}, BRIEF)
    assert brief["payout"]["rate_usd"] is None  # nullable stays null
    assert brief["permission"]["granted"] is False


# -- timeline -------------------------------------------------------------------------------------------
def test_timeline_maps_both_ways_with_speed_and_cuts():
    tl = Timeline([seg(10, 12), seg(15, 19, speed=2.0)])
    assert tl.duration == pytest.approx(4.0)
    assert tl.to_output(11) == pytest.approx(1.0)
    assert tl.to_output(17) == pytest.approx(3.0)
    assert tl.to_output(13) is None  # cut away
    assert tl.to_source(3.0) == pytest.approx(17.0)
    words = [{"start": 11.0, "end": 11.4, "word": "kept"}, {"start": 13.0, "end": 13.3, "word": "cut"},
             {"start": 16.0, "end": 16.4, "word": "fast"}]
    out = tl.map_words(words)
    assert [w["word"] for w in out] == ["kept", "fast"]
    assert out[1]["start"] == pytest.approx(2.5)


def test_remove_output_range_splits_segment():
    segs = remove_output_range([seg(0, 10, transition_in="flash")], 4.0, 5.0)
    assert [(s["src_start"], s["src_end"]) for s in segs] == [(0, 4.0), (5.0, 10)]
    assert segs[0]["transition_in"] == "flash" and segs[1]["transition_in"] == "cut"
    assert Timeline(segs).duration == pytest.approx(9.0)


def test_sanitize_and_jump_cut():
    segs = sanitize_segments([seg(-5, 2), seg(3, 3.1), seg(4, 50)], source_duration=30, bounds=(0, 20),
                             max_total=10)
    assert segs[0]["src_start"] == 0.0  # clamped into the source
    assert all(s["src_end"] - s["src_start"] >= 0.25 for s in segs)  # sliver dropped
    assert Timeline(segs).duration == pytest.approx(10.0)
    words = spread_words("one two three", 0.0, 1.5) + [{"start": 1.6, "end": 1.8, "word": "um"}] + \
        spread_words("four five", 3.0, 4.0)
    ranges = jump_cut(words, 0.0, 4.0, max_gap=0.45)
    assert len(ranges) == 2 and ranges[1][0] > 2.5  # pause + filler removed


# -- transcripts -------------------------------------------------------------------------------------------
def test_parse_srt_and_youtube_vtt_word_timings():
    srt = "1\n00:00:01,000 --> 00:00:03,000\nHello there friend.\n\n2\n00:00:03,500 --> 00:00:05,000\nSecond line!\n"
    segs = parse_subtitles(srt)
    assert [s["text"] for s in segs] == ["Hello there friend.", "Second line!"]
    assert segs[0]["words"][0]["start"] == pytest.approx(1.0) and segs[0]["words"][-1]["end"] == pytest.approx(3.0)
    vtt = ("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nwhy<00:00:00.500><c> do</c><00:00:01.000><c> people</c>\n\n"
           "00:00:02.000 --> 00:00:04.000\nwhy do people\nfail<00:00:02.600><c> fast</c>\n")
    words = [w for s in parse_subtitles(vtt) for w in s["words"]]
    assert [w["word"] for w in words][:3] == ["why", "do", "people"]
    assert words[1]["start"] == pytest.approx(0.5)
    assert sum(1 for w in words if w["word"] == "why") == 1  # rolling duplicate removed


# -- captions -------------------------------------------------------------------------------------------------
def test_caption_grouping_and_ass_output():
    assert ass_color("#FFE600") == "&H0000E6FF"
    words = spread_words("This is the hook. And then the payoff lands right here", 0.0, 4.0)
    chunks = group_words(words, max_words=3)
    assert [len(c) for c in chunks][0] == 3 and chunks[1][0]["word"] == "hook."
    doc = AssDoc(1080, 1920)
    caption_styles(doc, "Arial", {"style": "karaoke"})
    overlay_styles(doc, "Arial")
    n = build_captions(doc, words, {"enabled": True, "style": "karaoke", "words_per_caption": 3,
                                    "position": "lower", "uppercase": True}, "tiktok", 4.0)
    text = doc.text()
    assert n == len(group_words(words, 3, 99)) or n > 0
    assert "\\kf" in text and "PlayResY: 1920" in text and "THIS" in text


# -- briefs & compliance --------------------------------------------------------------------------------------------
TERMS = ("[HIRING] Clippers for my podcast. Clip my episodes and post on TikTok and Shorts. $2 per 1k views, "
         "budget $3k. Clips 20-45 seconds. Include #grind and tag @thegrind. Add #ad. "
         "Footage: https://drive.google.com/drive/folders/x")


def test_heuristic_brief_extracts_terms_and_permission():
    b = heuristic_brief(TERMS, "https://example.com/c")
    assert b["payout"]["model"] == "cpm" and b["payout"]["rate_usd"] == 2.0 and b["payout"]["budget_usd"] == 3000
    assert b["clip_length"] == {"min_s": 20.0, "max_s": 45.0}
    assert b["requirements"]["hashtags"] == ["#grind"] and b["requirements"]["mentions"] == ["@thegrind"]
    assert b["requirements"]["disclosure"] == "#ad"
    assert b["permission"]["granted"] and "Clip my episodes" in b["permission"]["evidence"]
    assert set(b["platforms"]) >= {"tiktok", "shorts"} and b["source_material"]
    assert not heuristic_brief("Selling my course, DM me")["permission"]["granted"]
    assert "casino" in heuristic_brief("clip my casino streams, $1 cpm")["risks"]


def test_compliance_lint_and_editor_enforcement(ax):
    brief = heuristic_brief(TERMS)
    brief["requirements"]["cta"] = "Follow for part 2"
    plan = conform({"segments": [seg(0, 20)], "post": {"caption": "great clip", "hashtags": []}}, EDIT_PLAN)
    ids = {i["id"] for i in compliance_lint(plan, brief, 20.0)}
    assert {"compliance:hashtag", "compliance:mention", "compliance:disclosure", "compliance:cta"} <= ids
    Editor(ax).enforce_compliance(plan, brief, 20.0)
    assert compliance_lint(plan, brief, 20.0) == []
    assert "#grind" in plan["post"]["hashtags"] and plan["post"]["caption"].startswith("#ad")
    assert any(o["kind"] == "cta" and o["start"] == 17.0 for o in plan["overlays"])


def test_caption_lint_flags_missing_and_fast_captions():
    assert caption_lint([], False, True)[0]["id"] == "captions:missing"
    fast = spread_words(" ".join(["extraordinarily"] * 12), 0.0, 2.0)
    assert caption_lint(fast, True, False)[0]["id"] == "captions:too_fast"


# -- analyst helpers ---------------------------------------------------------------------------------------------------
def test_snap_moment_lands_on_sentence_boundaries():
    words = spread_words("Why do people fail?", 0.0, 2.0) + spread_words("Because nobody tells them.", 2.3, 5.0) + \
        spread_words("Here is the rule.", 5.5, 8.0) + spread_words("Pay yourself first and", 8.4, 11.0)
    assert len(sentences(words)) == 4
    m = snap_moment({"start_s": 0.4, "end_s": 7.0}, words, min_s=4.0, max_s=9.0)
    assert m["start_s"] <= 0.0 + 0.01 and 7.9 <= m["end_s"] <= 8.4  # ends after "rule.", not mid-sentence
    assert snap_moment({"start_s": 0.0, "end_s": 30.0}, words, min_s=20.0, max_s=25.0) is None


# -- editor fix library -------------------------------------------------------------------------------------------------
def test_fix_library_cuts_measured_dead_air_latest_first(ax):
    plan = conform({"segments": [seg(0, 10), seg(12, 22)], "captions": {"words_per_caption": 3}}, EDIT_PLAN)
    issues = [{"id": "pacing:dead_air", "timecode_s": 2.0, "evidence": {"start": 2.0, "end": 3.2}},
              {"id": "pacing:dead_air", "timecode_s": 14.0, "evidence": {"start": 14.0, "end": 15.0}},
              {"id": "captions:too_fast", "timecode_s": None}]
    out = Editor(ax).apply_fixes(plan, issues, {"words": []}, {}, {})
    assert Timeline(out["segments"]).duration == pytest.approx(20.0 - (1.2 - 0.24) - (1.0 - 0.24))
    assert out["captions"]["words_per_caption"] == 2
    assert {f["issue_id"] for f in out["fixes"]} == {"pacing:dead_air", "captions:too_fast"}


# -- learning ------------------------------------------------------------------------------------------------------------
def test_lesson_validation_blocks_unsafe_and_lenient_lessons():
    assert lesson_problem("editor", "Skip the QC check when the deadline is tight.")
    assert lesson_problem("reviewer", "Don't flag minor caption timing slips on fast talkers.")
    assert not lesson_problem("editor", "Punch in on the first stressed word of the hook.")
    assert similarity("Punch in on the first stressed word of the hook.",
                      "Punch-in on the first stressed word in the hook.") > 0.72
    assert similarity("Punch in on the hook word.", "Keep music under -18 dB.") < 0.4


def test_playbook_render_and_credit_assignment(ax):
    st = ax.store
    a = st.add_lesson("editor", "Punch in on the first stressed word of the hook.", status="active", section="hook")
    c = st.add_lesson("editor", "Open with the payoff line as a 2s teaser.", status="candidate")
    text, shown = Playbook(st).render("editor", ["global"], canary=False)
    assert f"[{a}] helpful=0 harmful=0 :: Punch in" in text and c not in shown
    text, shown = Playbook(st).render("editor", ["global"], canary=True)
    assert c in shown and "Trial lessons" in text
    used = Playbook(st).record_use([a, "edi-99999", c], shown, job_id=7)
    assert used == [a, c] and st.get_lesson(a)["uses"] == 1 and st.get_lesson(a)["jobs"] == [7]


def _finished_clip(st, state="delivered", first_pass=True, used=(), learned=False):
    jid = st.create_job("clip", state, title="t")
    st.add_review(jid, 1, "reviewer", "pass" if first_pass else "fail", 8.0,
                  [] if first_pass else [{"id": "pacing:dead_air", "severity": "major", "description": "x", "fix": "y"}])
    st.put_artifact(jid, "plan", {"used_lessons": list(used)}, role="editor")
    st.update_job(jid, finished_at=time.time(), data={"learned": learned})
    return st.get_job(jid)


def test_curate_tags_only_used_lessons_dedupes_and_validates(ax):
    st = ax.store
    a = st.add_lesson("editor", "Punch in on the first stressed word of the hook.", status="active")
    b = st.add_lesson("editor", "Keep music 18 dB under the voice.", status="active")
    job = _finished_clip(st, used=[a])
    lr = Learner(ax.cfg, st, ax.llm)
    traj = lr.trajectory(job)
    changes = lr.curate({"bullet_tags": [{"id": a, "tag": "helpful"}, {"id": b, "tag": "harmful"}],
                         "new_lessons": [
                             {"role": "editor", "section": "hook", "scope": "global", "evidence": "",
                              "text": "Punch-in on the first stressed word in the hook"},  # duplicate → upvote
                             {"role": "reviewer", "section": "qc", "scope": "global", "evidence": "",
                              "text": "Don't flag dead air under one second on podcasts"},  # lenient → rejected
                             {"role": "editor", "section": "audio", "scope": "global", "evidence": "",
                              "text": "Duck music an extra 4 dB under fast talkers"}]}, traj)
    assert st.get_lesson(a)["helpful"] == 1  # tagged once (the duplicate ADD can't touch it again)
    assert st.get_lesson(b)["harmful"] == 0  # b wasn't used in this job → its tag is ignored
    assert changes["upvoted"] == [] and len(changes["rejected"]) == 1 and len(changes["added"]) == 1
    new = st.get_lesson(changes["added"][0])
    assert new["status"] == "candidate" and new["text"].endswith(".")


def test_promotion_archiving_miner_and_regression_guard(ax):
    st = ax.store
    lr = Learner(ax.cfg, st, ax.llm)
    good = st.add_lesson("editor", "Alternate punch-ins across jump cuts.", status="candidate")
    st.update_lesson(good, uses=4, helpful=3)
    bad = st.add_lesson("editor", "Use a whoosh on every single cut.", status="candidate")
    st.update_lesson(bad, uses=3, harmful=2)
    res = lr.promote_and_prune()
    assert good in res["promoted"] and bad in res["archived"]
    st.update_lesson(good, activated_at=time.time() - 20_000)  # it went live long before the drop
    # recurring first-round issue → preventive editor rule
    for _ in range(3):
        _finished_clip(st, first_pass=False)
    mined = lr.mine_recurring()
    assert mined and "pause" in st.get_lesson(mined[0])["text"]
    assert lr.mine_recurring() == []  # never twice
    # regression guard: 10 good clips, then a new lesson, then 10 bad clips → quarantine
    for j in st.list_jobs(kind="clip"):
        st.update_job(j["id"], finished_at=time.time() - 10_000)
    for _ in range(10):
        j = _finished_clip(st)
        st.add_metric(j["id"], "first_pass", 1.0)
        st.update_job(j["id"], finished_at=time.time() - 5_000)
    suspect = st.add_lesson("editor", "Open every clip with a glitch transition.", status="active")
    st.update_lesson(suspect, activated_at=time.time() - 4_000)
    for _ in range(10):
        j = _finished_clip(st, first_pass=False)
        st.add_metric(j["id"], "first_pass", 0.0)
    guard = lr.regression_guard()
    assert suspect in guard["rolled_back"] and st.get_lesson(suspect)["status"] == "quarantined"
    assert st.get_lesson(good)["status"] == "active"  # promoted before the drop → kept


# -- leads ----------------------------------------------------------------------------------------------------------------------
def test_lead_intake_respects_platform_terms(ax):
    assert automation_forbidden("https://whop.com/discover/x") and automation_forbidden("https://app.vyro.com/c/1")
    assert not automation_forbidden("https://example.com/post")
    assert html_to_text("<p>Hi<script>x()</script></p><li>clip my vods</li>") == "Hi\nclip my vods"
    lf = LeadFinder(ax)
    with pytest.raises(PermissionError):
        lf.add_manual("https://whop.com/c/abc")  # no pasted terms → we don't fetch Whop
    q = lf.add_manual("https://whop.com/c/abc", TERMS)
    assert q["decision"] == "accept" and q["score"] >= 70
    cid = lf.accept(q["id"])
    camp = ax.store.get_campaign(cid)
    assert camp["permission"]["granted"] and camp["brief"]["requirements"]["hashtags"] == ["#grind"]
    risky = lf.add_manual("https://example.com/r", "Clip my casino streams! $5 per 1k views, pay to join $20")
    assert risky["decision"] == "reject"


def test_claude_request_shape_and_metering(tmp_path):
    """The real SDK, a fake transport: structured output, effort, caching, fallbacks, cost."""
    anthropic = pytest.importorskip("anthropic")
    httpx2 = pytest.importorskip("httpx2")
    import json as _json

    from noze.agency.llm import LLM
    from noze.agency.schemas import APPROVAL
    from noze.agency.store import Store

    seen = {}

    def handler(request):
        seen["headers"], seen["body"] = dict(request.headers), _json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": _json.dumps({"decision": "approve", "reasons": ["ok"]})}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1000, "output_tokens": 200, "cache_read_input_tokens": 3000,
                      "cache_creation_input_tokens": 0}})

    env = {"NOZE_DATA_DIR": str(tmp_path), "AGENCY_LLM": "claude"}
    cfg = AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False)
    store = Store(tmp_path / "a.db")
    llm = LLM(cfg, store)
    llm._client = anthropic.Anthropic(api_key="test", http_client=anthropic.DefaultHttpxClient(
        transport=httpx2.MockTransport(handler)))
    out = llm.json("manager", "SYSTEM", "TASK", APPROVAL, job_id=5)
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5" and body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["fallbacks"] == "default" and "server-side-fallback" in seen["headers"]["anthropic-beta"]
    assert out["decision"] == "approve" and out["notes_for_editor"] == []
    assert store.spend(job_ids=[5]) == pytest.approx(0.0086)


def test_manager_routines_write_the_team_report_on_schedule(ax):
    from noze.agency.pipeline import Agency

    ag = Agency(ax)
    assert ag.routines() == []  # nothing produced yet, no lead sources → nothing to do
    ax.store.create_job("clip", "planning", title="x")
    ax.store.set_meta("routine:team_report", "0")
    assert ag.routines() == ["team_report"]
    assert list((ax.cfg.reports_dir / "team").glob("team_*.md"))
    assert ag.routines() == []  # not again until the interval passes


def test_model_revision_is_not_recut_with_stale_timecodes(ax, monkeypatch):
    """The model already cut the pause; the old render's dead-air timecode must not cut speech now."""
    words = [{"start": round(10 + 0.4 * i, 2), "end": round(10 + 0.4 * i + 0.35, 2), "word": f"a{i}"} for i in range(10)]
    words += [{"start": round(15 + 0.4 * i, 2), "end": round(15 + 0.4 * i + 0.35, 2), "word": f"b{i}"} for i in range(12)]
    model_plan = conform({"segments": [seg(10.0, 14.0), seg(15.0, 20.0)], "captions": {"words_per_caption": 3},
                          "fixes": [{"issue_id": "pacing:dead_air", "change": "cut the pause"}]}, EDIT_PLAN)
    ed = Editor(ax)
    monkeypatch.setattr(ed, "ask", lambda *a, **k: model_plan)
    issue = {"id": "pacing:dead_air", "source": "qc", "severity": "major", "timecode_s": 4.0,
             "evidence": {"start": 4.0, "end": 5.0}, "description": "", "fix": ""}
    prep = {"words": words, "moment_words": words, "sheets": [], "ranges": [], "source_info": {"duration": 60}}
    out = ed.revise({"id": 1, "campaign_id": None}, model_plan, [issue], {"start_s": 10.0, "end_s": 20.0},
                    conform({}, BRIEF), {}, prep, [])
    kept = {w["word"] for w in Timeline(out["segments"]).map_words(words)}
    assert kept == {w["word"] for w in words}


def test_too_short_clip_gets_a_longer_moment(ax):
    from noze.agency.pipeline import Agency

    words, t = [], 0.0
    while t < 60:
        for k in range(5):
            words.append({"start": round(t + 0.35 * k, 2), "end": round(t + 0.35 * k + 0.3, 2),
                          "word": "w." if k == 4 else "w"})
        t += 2.0
    moment = {"start_s": 10.0, "end_s": 20.0}
    brief = conform({"clip_length": {"min_s": 15, "max_s": 30}}, BRIEF)
    jid = ax.store.create_job("clip", "revising", title="short", input={"moment": moment})
    ax.store.put_artifact(jid, "render", {"duration": 8.9})
    new = Agency(ax)._extend_moment(ax.store.get_job(jid), {"moment": moment, "brief": brief, "words": words})
    assert new["end_s"] >= 26.0 and ax.store.get_job(jid)["input"]["moment"]["end_s"] == new["end_s"]
    ed = Editor(ax)
    plan = conform({"segments": [seg(10.0, 13.5), seg(14.0, 17.5), seg(18.0, 19.9)]}, EDIT_PLAN)
    prep = {"words": words, "moment_words": words, "ranges": [], "source_info": {"duration": 60}}
    fixed = ed.apply_fixes(plan, [{"id": "compliance:too_short", "timecode_s": None}], prep, {}, brief)
    final = ed.finalize(fixed, new, brief, {}, prep)
    assert Timeline(final["segments"]).duration >= 15.0
