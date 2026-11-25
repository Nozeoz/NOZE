"""Editor story upgrade (23 Nov 2026): multi-part prepare, structure recipes + emotion palettes in the no-LLM plan,
finalize's time-card honesty, and the story/post lints. Every lint has a bad case that must go RED and a good case
that must stay GREEN (positive control). No ffmpeg, no network, no LLM."""

from pathlib import Path

import pytest

from noze.agency import story
from noze.agency.config import AgencySettings
from noze.agency.context import AgencyContext
from noze.agency.media.qc import card_expectations, compliance_lint, plan_holds, story_lint
from noze.agency.roles.editor import Editor, comply_post
from noze.agency.schemas import BRIEF, EDIT_PLAN, conform
from noze.agency.standards import LAYOUT, VIBES, clean_post_text
from noze.config import Settings

BASE_ENV = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off"}
INFO = {"width": 1920, "height": 1080, "fps": 30, "duration": 4000.0}


@pytest.fixture
def ax(tmp_path):
    env = {**BASE_ENV, "NOZE_DATA_DIR": str(tmp_path / "bank")}
    a = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    yield a
    a.close()


def words_in(a, b, step=0.4):
    out, t, n = [], a, 0
    while t + 0.35 <= b:
        out.append({"start": round(t, 2), "end": round(t + 0.35, 2), "word": f"w{n}"})
        t, n = t + step, n + 1
    return out


def transcript(*ranges):
    return {"segments": [{"words": words_in(a, b)} for a, b in ranges]}


def prepared(ax, moment, *ranges, blueprint=None):
    ed = Editor(ax)
    tr = transcript(*ranges)
    prep = ed.prepare({"id": 1, "campaign_id": None}, Path("missing.mp4"), moment, tr, blueprint or {}, INFO)
    return ed, prep


COLD = {"start_s": 100.0, "end_s": 2506.0, "structure": "cold_open", "emotion": "hype", "title": "He called it",
        "parts": [{"start_s": 2500.0, "end_s": 2503.5, "role": "cold_open", "label": ""},
                  {"start_s": 100.0, "end_s": 112.0, "role": "setup", "label": ""},
                  {"start_s": 2500.0, "end_s": 2506.0, "role": "payoff", "label": ""}]}
COLD_RANGES = [(2500.0, 2506.0), (100.0, 112.0)]
ARC = {"start_s": 100.0, "end_s": 2506.0, "structure": "arc", "emotion": "funny", "title": "Told you",
       "parts": [{"start_s": 100.0, "end_s": 112.0, "role": "setup", "label": ""},
                 {"start_s": 2500.0, "end_s": 2506.0, "role": "payoff", "label": ""}]}


def single(emotion, a=100.0, b=116.0):
    return {"start_s": a, "end_s": b, "emotion": emotion, "structure": "linear", "title": "Big moment"}


# -- prepare ------------------------------------------------------------------------------------------------------------
def test_prepare_cuts_every_part_in_play_order(ax):
    ed, prep = prepared(ax, COLD, *COLD_RANGES)
    assert [p["role"] for p in prep["parts"]] == ["cold_open", "setup", "payoff"]
    assert [p["label"] for p in prep["parts"]] == ["", "40 MIN EARLIER", "40 MIN LATER"]  # computed from the gap
    rp = prep["range_parts"]
    assert rp == sorted(rp) and set(rp) == {0, 1, 2} and len(rp) == len(prep["ranges"])
    first = [r for r, p in zip(prep["ranges"], rp) if p == 0]
    assert all(2500.0 <= a and b <= 2503.6 for a, b in first)  # part 0 stays inside its own range
    assert any(100.0 <= a < 112.0 for a, _ in prep["ranges"]) and prep["moment_words"]
    single_prep = prepared(ax, single("hype"), (100.0, 116.0))[1]
    assert set(single_prep["range_parts"]) == {0} and len(single_prep["parts"]) == 1


# -- heuristic plan: structure ------------------------------------------------------------------------------------------
def test_cold_open_plan_opens_on_the_payoff_then_rewinds_with_the_true_card(ax):
    ed, prep = prepared(ax, COLD, *COLD_RANGES)
    plan = ed.heuristic_plan(COLD, {}, {}, prep)
    segs = plan["segments"]
    assert 2500.0 <= segs[0]["src_start"] < 2503.6 and segs[0]["transition_in"] == "cut"  # frame 0 = the payoff
    hook = [o for o in plan["overlays"] if o["kind"] == "hook_title"]
    assert hook and hook[0]["start"] == 0.0  # the title is on frame 0
    jump = next(i for i, s in enumerate(segs) if 100.0 <= s["src_start"] < 112.0)
    assert segs[jump]["transition_in"] == "rewind"  # the source jumps back
    cards = card_expectations(plan, COLD["parts"] and story.moment_parts(COLD))
    assert [c["overlay"]["text"] for c in cards] == ["40 MIN EARLIER", "40 MIN LATER"] and all(c["ok"] for c in cards)
    assert any(c["kind"] == "rewind" for c in plan["sfx"])
    assert segs[jump]["look"] == "flashback" and segs[jump]["role"] == "setup"
    assert segs[-1]["role"] == "payoff" and segs[-1]["transition_in"] != "fade"  # ends on the payoff
    assert plan["vibe"] == "hype"


def test_cold_open_teaser_is_trimmed_to_a_short_payoff(ax):
    long = dict(COLD, parts=[{**COLD["parts"][0], "end_s": 2508.0}] + COLD["parts"][1:])
    ed, prep = prepared(ax, long, (2500.0, 2510.0), (100.0, 112.0))
    plan = ed.heuristic_plan(long, {}, {}, prep)
    teaser = [s for s in plan["segments"] if s["src_start"] >= 2500.0 and s["src_end"] <= 2508.1][0]
    assert teaser["src_end"] - teaser["src_start"] <= 2.6 and teaser["src_end"] > 2507.0  # the tail, where the payoff is


def test_arc_plan_puts_the_flashback_look_on_the_setup_only(ax):
    ed, prep = prepared(ax, ARC, *COLD_RANGES)
    plan = ed.heuristic_plan(ARC, {}, {}, prep)
    looks = {(s["role"], s["look"]) for s in plan["segments"]}
    assert ("setup", "flashback") in looks and ("payoff", "none") in looks
    assert [o["text"] for o in plan["overlays"] if o["kind"] == "time_card"] == ["40 MIN LATER"]


# -- heuristic plan: emotion palettes -----------------------------------------------------------------------------------
def test_funny_plan_holds_the_reaction_and_never_shakes(ax):
    m = single("funny")
    ed, prep = prepared(ax, m, (100.0, 116.0), blueprint={"motion": {"shake_on_impact": True}})
    plan = ed.finalize(ed.heuristic_plan(m, {}, {"motion": {"shake_on_impact": True}}, prep), m, {}, {}, prep)
    segs = plan["segments"]
    assert segs[-1]["hold"] == pytest.approx(0.75) and segs[-1]["hold_style"] == "zoom"
    assert not any(s["shake"] for s in segs) and plan["vibe"] == "funny"
    assert not {c["kind"] for c in plan["sfx"]} & set(VIBES["funny"]["no_sfx"])
    assert any(c["kind"] in ("ding", "pop") for c in plan["sfx"])  # a beat on the frozen reaction
    assert story_lint(plan) == [] or all(i["id"] != "visual:palette" for i in story_lint(plan))
    assert plan_holds(segs) and plan_holds(segs)[0][1] == pytest.approx(sum(
        (s["src_end"] - s["src_start"]) + s["hold"] for s in segs), abs=0.01)


def test_tense_plan_has_no_flash_or_shake_and_drops_the_music_before_the_payoff(ax):
    m = single("tense", 100.0, 126.0)
    bp = {"motion": {"transitions": ["flash", "whip"], "shake_on_impact": True}}
    ed, prep = prepared(ax, m, (100.0, 126.0), blueprint=bp)
    plan = ed.finalize(ed.heuristic_plan(m, {}, bp, prep), m, {}, bp, prep)
    segs = plan["segments"]
    assert not {s["transition_in"] for s in segs} & {"flash", "whip", "glitch"}
    assert not any(s["shake"] for s in segs)
    d = plan["music"]["drop_at"]
    assert d is not None and 2.0 <= d < plan["sfx"][-1]["at"] + 5 and any(c["kind"] == "riser" for c in plan["sfx"])
    assert plan["fx"]["letterbox"] and plan["color"] == "night"
    assert story_lint(plan) == []  # the whole plan is inside the palette


def test_hype_plan_is_allowed_to_shake_on_the_payoff_only(ax):
    m = single("hype", 100.0, 126.0)
    ed, prep = prepared(ax, m, (100.0, 126.0))
    plan = ed.heuristic_plan(m, {}, {}, prep)
    shaking = [i for i, s in enumerate(plan["segments"]) if s["shake"]]
    assert shaking == [len(plan["segments"]) - 1]


# -- finalize ------------------------------------------------------------------------------------------------------------
def test_finalize_overwrites_a_lying_time_card_and_bounds_each_part(ax):
    ed, prep = prepared(ax, COLD, *COLD_RANGES)
    plan = ed.heuristic_plan(COLD, {}, {}, prep)
    for o in plan["overlays"]:
        if o["kind"] == "time_card":
            o["text"] = "10 MIN LATER"  # the model made a time up
    plan["segments"].append({**plan["segments"][-1], "src_start": 3000.0, "src_end": 3004.0})  # outside every part
    out = ed.finalize(plan, COLD, {}, {}, prep)
    assert [o["text"] for o in out["overlays"] if o["kind"] == "time_card"] == ["40 MIN EARLIER", "40 MIN LATER"]
    assert all(c["ok"] for c in card_expectations(out, story.moment_parts(COLD)))
    assert not any(3000.0 <= s["src_start"] for s in out["segments"])
    assert any(f["issue_id"] == "story:label_mismatch" for f in out["fixes"])


def test_finalize_drops_a_card_over_a_short_gap_and_clamps_the_new_fields(ax):
    m = single("funny", 100.0, 130.0)
    ed, prep = prepared(ax, m, (100.0, 130.0))
    prep["words"] = []  # the fixture's talk has no pause at all (one endless "phrase"): hold placement is not under test here
    plan = ({"segments": [{"src_start": 100.0, "src_end": 105.0, "transition_in": "flash", "hold": 5.0,
                                  "zoom": {"type": "push", "scale": 1.1, "fx": 3.0, "fy": -1.0}},
                                 {"src_start": 110.0, "src_end": 115.0, "hold": -2}],
                    "overlays": [{"kind": "time_card", "text": "5 MIN LATER", "start": 5.0, "end": 6.0},
                                 {"kind": "callout", "text": "LOOK", "start": 1.0, "end": 2.0, "at_x": 9, "at_y": -4}],
                    "music": {"enabled": True, "drop_at": 999}})  # raw: no vibe key
    out = ed.finalize(plan, m, {}, {}, prep)
    s0, s1 = out["segments"]
    assert s0["hold"] == 1.2 and s1["hold"] == 0.0 and s0["transition_in"] == "cut"
    assert s0["zoom"]["fx"] == 1.0 and s0["zoom"]["fy"] == 0.0
    assert not [o for o in out["overlays"] if o["kind"] == "time_card"]  # 5 s apart: no card at all
    callout = next(o for o in out["overlays"] if o["kind"] == "callout")
    assert (callout["at_x"], callout["at_y"]) == (1.0, 0.0) and out["music"]["drop_at"] is None
    assert out["vibe"] == "funny"  # the plan chose none: the moment's emotion is the default


# -- story lint: RED on the bad plan, GREEN on the good one ---------------------------------------------------------------
def seg(a, b, **kw):
    return {"src_start": a, "src_end": b, "speed": 1.0, "reframe": {"mode": "center", "x": 0.5},
            "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut", "note": "", **kw}


def plan_of(segs, **kw):
    base = {"segments": segs, "overlays": [{"kind": "hook_title", "text": "X", "start": 0.0, "end": 2.0}], "sfx": [],
            "vibe": "hype", "fx": {"vignette": False, "grain": False, "letterbox": False}}
    return {**base, **kw}


def ids(issues):
    return {i["id"] for i in issues}


def test_lint_label_mismatch():
    good = plan_of([seg(100, 106), seg(2500, 2506)],
                   overlays=[{"kind": "hook_title", "text": "X", "start": 0.0, "end": 2.0},
                             {"kind": "time_card", "text": "40 min later", "start": 6.0, "end": 7.4}])
    assert "story:label_mismatch" not in ids(story_lint(good))
    bad = plan_of(good["segments"], overlays=[good["overlays"][0], {**good["overlays"][1], "text": "2 HOURS LATER"}])
    hit = [i for i in story_lint(bad) if i["id"] == "story:label_mismatch"]
    assert hit and hit[0]["severity"] == "major" and hit[0]["evidence"]["real"] == "40 MIN LATER"
    short = plan_of([seg(100, 106), seg(130, 136)],  # 24 s apart: any card is a lie
                    overlays=[good["overlays"][0], {"kind": "time_card", "text": "40 MIN LATER", "start": 6.0, "end": 7.4}])
    assert "story:label_mismatch" in ids(story_lint(short))


def test_lint_flash_rate_is_a_blocker_only_when_strobing():
    ok = plan_of([seg(0, 2), seg(2, 4, transition_in="flash"), seg(4, 6, transition_in="flash")])
    assert "visual:flash_rate" not in ids(story_lint(ok))
    strobe = plan_of([seg(0, 1)] + [seg(1 + 0.25 * i, 1.25 + 0.25 * i, transition_in="flash") for i in range(5)])
    hit = [i for i in story_lint(strobe) if i["id"] == "visual:flash_rate"]
    assert hit and hit[0]["severity"] == "blocker"


def test_lint_effect_repeat():
    ok = plan_of([seg(0, 2), seg(2, 4, transition_in="whip"), seg(4, 6), seg(6, 8, transition_in="whip")])
    assert "pacing:effect_repeat" not in ids(story_lint(ok))
    bad = plan_of([seg(0, 2)] + [seg(2 * i, 2 * i + 2, transition_in="whip") for i in range(1, 4)])
    assert "pacing:effect_repeat" in ids(story_lint(bad))
    zooms = plan_of([seg(2 * i, 2 * i + 2, zoom={"type": "punch", "scale": 1.1}) for i in range(4)])
    assert "pacing:effect_repeat" in ids(story_lint(zooms))


def test_lint_sfx_density_and_palette():
    segs = [seg(0, 12)]
    ok = plan_of(segs, sfx=[{"kind": "pop", "at": 1.0 + 3 * i, "gain_db": -10} for i in range(4)])
    assert not ids(story_lint(ok)) & {"audio:sfx_density", "visual:palette"}
    busy = plan_of(segs, sfx=[{"kind": "pop", "at": 0.5 * i, "gain_db": -10} for i in range(20)])
    assert "audio:sfx_density" in ids(story_lint(busy))
    tense = plan_of([seg(0, 6), seg(6, 12, transition_in="flash", shake=True)], vibe="tense",
                    sfx=[{"kind": "pop", "at": 3.0, "gain_db": -10}])
    pal = [i for i in story_lint(tense) if i["id"] == "visual:palette"]
    assert pal and set(pal[0]["evidence"]) == {"transitions", "sfx", "shake", "fx"}
    assert pal[0]["evidence"]["transitions"] == ["flash"] and pal[0]["evidence"]["shake"] == [1]
    assert "visual:palette" not in ids(story_lint({**tense, "vibe": "hype", "sfx": [], "segments": [seg(0, 6), seg(6, 12, shake=True)]}))


def test_lint_frame0_and_fade_ending():
    good = plan_of([seg(0, 4), seg(4, 8)])
    assert not ids(story_lint(good)) & {"hook:frame0", "story:fade_ending"}
    late = plan_of(good["segments"], overlays=[{"kind": "hook_title", "text": "X", "start": 1.0, "end": 3.0}])
    assert "hook:frame0" in ids(story_lint(late))
    dip = plan_of([seg(0, 4, transition_in="fade"), seg(4, 8)])
    assert "hook:frame0" in ids(story_lint(dip))  # frame 0 would be black
    assert "story:fade_ending" in ids(story_lint(plan_of([seg(0, 4), seg(4, 8, transition_in="fade")])))


def test_fix_library_clears_the_story_findings(ax):
    ed = Editor(ax)
    bad = conform(plan_of([seg(0, 4)] + [seg(4 * i, 4 * i + 4, transition_in="flash") for i in range(1, 4)]
                          + [seg(16, 20, transition_in="fade")], overlays=[], vibe="tense"), EDIT_PLAN)  # 4 s shots: calm enough for pacing:over_cut
    found = [i for i in story_lint(bad)]
    assert ids(found) >= {"pacing:effect_repeat", "hook:frame0", "visual:palette", "story:fade_ending"}
    fixed = ed.apply_fixes(bad, found, {"words": []}, {}, {})
    assert ids(story_lint(fixed)) == set()


# -- post copy -------------------------------------------------------------------------------------------------------------
BRIEF_POST = conform({"creator": "StreamerX", "requirements": {"hashtags": ["#gta6"], "mentions": ["@streamerx"],
                                                               "disclosure": "#ad"}}, BRIEF)


def test_post_title_lint_is_red_on_a_leak_and_green_on_clean_copy():
    dirty = {"caption": "He called it (re-cut v2) [draft plan] #gta6 @streamerx #ad StreamerX", "hashtags": ["#gta6"],
             "title": "Clip (v3)"}
    hit = [i for i in compliance_lint({"post": dirty, "overlays": [], "segments": []}, BRIEF_POST, 20.0)
           if i["id"] == "compliance:post_title"]
    assert hit and hit[0]["severity"] == "major"
    clean = comply_post(dirty, BRIEF_POST)
    assert "compliance:post_title" not in ids(compliance_lint({"post": clean, "overlays": [], "segments": []}, BRIEF_POST, 20.0))
    text = f"{clean['caption']} {clean['title']}".lower()
    assert not any(t in text for t in ("re-cut", "v2", "v3", "draft", "plan", "(", "["))
    assert "streamerx" in text and "@streamerx" in clean["caption"] and "#ad" in clean["caption"]
    assert "#gta6" in clean["hashtags"]


def test_comply_post_adds_the_creator_and_drops_internal_hashtags():
    out = comply_post({"caption": "Wild stream moment", "hashtags": ["#recut", "#v2", "#gta6"]}, BRIEF_POST)
    assert "StreamerX" in out["caption"] and out["hashtags"] == ["#gta6"]
    assert clean_post_text("Epic (v2) moment re-cut") == "Epic moment"
    assert clean_post_text("Keep (#ad) here", ["#ad"]) == "Keep (#ad) here"  # a required group survives


def test_publisher_cleans_the_copy_on_every_path(ax, tmp_path):
    from noze.agency.publish import Publisher

    render = tmp_path / "r.mp4"
    render.write_bytes(b"x")
    camp = ax.store.create_campaign("c", conform({"creator": "StreamerX"}, BRIEF), {}, creator="StreamerX")
    jid = ax.store.create_job("clip", "approved", title="clip (v2) re-cut", campaign_id=camp,
                              input={}, data={"render_path": str(render), "post": {"title": "Wow (re-cut)",
                                                                                   "caption": "nice cap (draft) [wip]"}})
    job = ax.store.get_job(jid)
    res = Publisher(ax).deliver(job, conform({"creator": "StreamerX"}, BRIEF))
    txt = Path(res["caption_file"]).read_text(encoding="utf-8").lower()
    assert "re-cut" not in txt and "draft" not in txt and "(v2)" not in txt and "[wip]" not in txt and "streamerx" in txt


# -- numbers ---------------------------------------------------------------------------------------------------------------
def test_new_layout_numbers_and_vibe_table():
    assert LAYOUT["caption_min_size_px"] == 75 and LAYOUT["hook_setup_min_px"] == 55
    assert LAYOUT["eye_line_band_share"] == (0.28, 0.32)
    from noze.agency.schemas import EMOTIONS, SFX_KINDS, TRANSITIONS

    assert set(VIBES) == set(EMOTIONS)
    for name, v in VIBES.items():
        assert set(v["transitions"]) | set(v["no_transitions"]) <= set(TRANSITIONS), name
        assert set(v["sfx"]) | set(v["no_sfx"]) <= set(SFX_KINDS), name
        assert not set(v["sfx"]) & set(v["no_sfx"]) and not set(v["transitions"]) & set(v["no_transitions"]), name


# -- reviewer fixes #7 #11 #12 ---------------------------------------------------------------------------------------------
def test_sparse_part_is_kept_whole_but_dense_talk_is_still_jump_cut(ax):
    m = single("hype", 100.0, 120.0)
    tr = {"segments": [{"words": [{"start": 110.0, "end": 110.4, "word": "no"}]}]}  # a scream in a 20 s action stretch
    prep = Editor(ax).prepare({"id": 1, "campaign_id": None}, Path("missing.mp4"), m, tr, {}, INFO)
    r = prep["ranges"]
    assert r[0][0] == 100.0 and r[-1][1] == 120.0 and all(a[1] == b[0] for a, b in zip(r, r[1:]))  # nothing dropped
    dense = Editor(ax).prepare({"id": 1, "campaign_id": None}, Path("missing.mp4"), m,
                               transcript((100.0, 108.0), (112.0, 120.0)), {}, INFO)
    assert len(dense["ranges"]) >= 2 and dense["ranges"][0][1] < 109.0  # the 4 s pause is cut out


def test_flash_fix_is_idempotent_and_leaves_far_flashes_alone(ax):
    segs = [seg(0, 2)] + [seg(2 + 0.25 * i, 2.25 + 0.25 * i, transition_in="flash") for i in range(6)]
    segs += [seg(20, 22, transition_in="flash"), seg(30, 32, transition_in="flash")]
    plan = conform(plan_of(segs), EDIT_PLAN)
    once = Editor(ax).apply_fixes(plan, [{"id": "visual:flash_rate"}], {"words": []}, {}, {})
    assert "visual:flash_rate" not in ids(story_lint(once))
    assert [s["transition_in"] for s in once["segments"][-2:]] == ["flash", "flash"]
    twice = Editor(ax).apply_fixes(once, [{"id": "visual:flash_rate"}], {"words": []}, {}, {})
    assert [s["transition_in"] for s in twice["segments"]] == [s["transition_in"] for s in once["segments"]]


def test_post_cleaning_hits_internal_tokens_only():
    from noze.agency.standards import post_leaks

    assert clean_post_text("My plan worked!") == "My plan worked!"
    assert clean_post_text("Epic fail (ft. Bob) (Part 2)") == "Epic fail (ft. Bob) (Part 2)"
    for bad, good in (("Epic fail (re-cut 2)", "Epic fail"), ("Epic fail [draft]", "Epic fail"),
                      ("Epic fail (v3)", "Epic fail"), ("Epic fail (test)", "Epic fail"), ("Epic fail - v2", "Epic fail"),
                      ("Epic fail - draft", "Epic fail"), ("Epic recut fail", "Epic fail")):
        assert clean_post_text(bad) == good, bad
    for real in ("Racing my v8", "Dota 2 TI v10", "Season 2: Draft", "Prison escape (Plan 2)", "IQ (Test)"):
        assert clean_post_text(real) == real, real  # fix-round review: real titles are not tags
    assert post_leaks("My plan worked! (ft. Bob)") == [] and post_leaks("Epic fail (v3)")


def test_length_cap_moves_cues_with_the_trimmed_segments():
    """Round-2 review: the cap trims the setup mid-edit, so cues placed on the payoff must move with it."""
    from noze.agency.media.timeline import Timeline, sanitize_segments
    from noze.agency.roles.editor import Editor

    segs = [{"src_start": 100, "src_end": 120, "speed": 1, "role": "setup", "hold": 0.0},
            {"src_start": 500, "src_end": 525, "speed": 1, "role": "payoff", "hold": 0.8}]
    bounds = [(100, 120), (500, 525)]
    before, after = sanitize_segments(segs, 1e9, bounds), sanitize_segments(segs, 1e9, bounds, max_total=40)
    pay = Timeline(after).placed[1].out_start
    assert pay < Timeline(before).placed[1].out_start  # control: the cap really moved the payoff
    plan = {"sfx": [{"at": 3.0}, {"at": 20.0}], "music": {"drop_at": 20.0},
            "overlays": [{"start": 0.0, "end": 2.5}, {"start": 20.0, "end": 21.0}]}
    Editor._remap_cues(plan, before, after)
    assert plan["music"]["drop_at"] == pytest.approx(pay) and plan["overlays"][1]["start"] == pytest.approx(pay)
    assert plan["sfx"][0]["at"] == 3.0 and plan["overlays"][0] == {"start": 0.0, "end": 2.5}


def test_post_title_cleaner_keeps_real_titles_round2():
    """Round-2 review: only whole internal tags are stripped; real titles survive."""
    from noze.agency.standards import clean_post_text, post_leaks
    
    keep = ["Heist goes wrong (Plan B)", "Reacting to the NFL Draft", "Hitting 300 in the V12", "My plan worked!",
            "Kai loses it (ft. Druski)", "GTA 6 chase (Part 2)"]
    drop = {"Kai loses it (re-cut 2)": "Kai loses it", "Big heist [draft]": "Big heist", "Chase (v3)": "Chase",
            "Chase - v2": "Chase", "Police chase | draft": "Police chase", "Heist recut 3 lol": "Heist lol",
            "Clip (plan v2)": "Clip", "Clip [WIP]": "Clip"}
    for t in keep:
        assert clean_post_text(t) == t, (t, clean_post_text(t))
    for t, want in drop.items():
        got = clean_post_text(t)
        assert got == want, (t, got)


def test_internal_test_review_drops_permission_issues_but_normal_review_keeps_them():
    """An --internal-test clip must not fail review on the (deliberately) missing permission every round."""
    from types import SimpleNamespace
    from noze.agency.roles.reviewer import Reviewer

    issues = [{"category": "compliance", "severity": "blocker", "timecode_s": None,
               "description": "Permission isn't verified", "fix": "paste the campaign terms"},
              {"category": "hook", "severity": "major", "timecode_s": 0.0, "description": "hook title misattributes",
               "fix": "rewrite it"}]
    for internal, want in ((True, ["hook"]), (False, ["compliance", "hook"])):
        r = Reviewer.__new__(Reviewer)
        jobs = {1: {"id": 1, "input": {"internal_test": internal}}}
        r.store = SimpleNamespace(get_job=jobs.get, get_campaign=lambda cid: {"brief": {"permission": {"granted": False}}})
        r.ax = SimpleNamespace(llm=SimpleNamespace(available=True))
        r.ask = lambda *a, **k: {"issues": [dict(i) for i in issues], "scores": {}}
        job = {"id": 2, "parent_id": 1, "campaign_id": 9, "input": {"moment": {"start_s": 0, "end_s": 5}}}
        out = r._creative(job, {"segments": []}, "missing.mp4", 5.0, {}, [], {}, {}, [], [])
        assert [i["category"] for i in out["issues"]] == want, internal


# -- CP1 (mandor 23 Nov, round 2): freeze placement, dark opener, face validation, vod_map, CP1 type sizes -----------------
import subprocess  # noqa: E402

from noze.agency.media import qc  # noqa: E402
from noze.agency.media.ffmpeg import ffmpeg_bin  # noqa: E402
from noze.agency.media.timeline import Timeline  # noqa: E402
from noze.agency.standards import HOUSE_RULES, QC, standards_text  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not ffmpeg_bin(), reason="ffmpeg not installed")

# "Fuck… you dude." = ONE phrase (words 0.15 s / 0.05 s apart); the hold at 10.5 splits "Fuck…" from "you"
FUCK_YOU = [{"word": "Fuck…", "start": 10.0, "end": 10.45}, {"word": "you", "start": 10.6, "end": 11.0},
            {"word": "dude.", "start": 11.05, "end": 11.4}, {"word": "Anyway", "start": 12.5, "end": 13.0}]


def hold_plan(second_src=(10.5, 14.0)):
    return plan_of([seg(10.0, 10.5, hold=0.55), seg(*second_src)],
                   sfx=[{"kind": "ding", "at": 0.6, "gain_db": -10.0}])  # the ding sits inside the hold (0.5-1.05)


def out_words(plan, words=FUCK_YOU):
    return Timeline(plan["segments"]).map_words(words)


def hold_prep(words=FUCK_YOU):
    return {"words": words, "moment_words": words, "ranges": [(10.0, 14.0)], "source_info": INFO, "sheets": [],
            "subject_x": None, "facecam": None, "facecam_face": None}


def test_freeze_in_phrase_is_red_on_fuck_hold_you_and_green_after_finalize(ax):
    m = single("funny", 10.0, 14.0)
    bad = hold_plan()
    found = [i for i in story_lint(bad, words=out_words(bad)) if i["id"] == "pacing:freeze_in_phrase"]
    assert found and found[0]["severity"] == "major"  # RED: the freeze splits the line
    ed = Editor(ax)
    fixed = ed.finalize(hold_plan(), m, {}, {}, hold_prep())
    assert "pacing:freeze_in_phrase" not in ids(story_lint(fixed, words=out_words(fixed)))  # GREEN after the move
    held = [(s["src_start"], s["src_end"], s["hold"]) for s in fixed["segments"] if s["hold"]]
    assert held == [(10.5, 11.43, 0.55)]  # right after "dude." is finished, same length; nothing cut from the footage
    assert abs(Timeline(fixed["segments"]).duration - Timeline(bad["segments"]).duration) < 1e-6
    assert fixed["sfx"][0]["at"] == pytest.approx(1.53, abs=0.01)  # the ding rode along with its freeze
    again = ed.finalize(fixed, m, {}, {}, hold_prep())  # idempotent
    assert [(s["src_start"], s["src_end"], s["hold"]) for s in again["segments"]] == [
        (s["src_start"], s["src_end"], s["hold"]) for s in fixed["segments"]]


def test_freeze_before_a_source_jump_or_a_sentence_end_is_not_a_split():
    jump = hold_plan((50.0, 52.0))  # the next segment is another part of the stream: the freeze sits on a real cut
    assert "pacing:freeze_in_phrase" not in ids(story_lint(jump, words=out_words(jump)))
    p = hold_plan()
    sentence = [{"word": "No.", "start": 10.0, "end": 10.45}, {"word": "you", "start": 10.6, "end": 11.0}]
    assert "pacing:freeze_in_phrase" not in ids(story_lint(p, words=out_words(p, sentence)))
    pause = [{"word": "Fuck", "start": 10.0, "end": 10.4}, {"word": "you", "start": 10.9, "end": 11.2}]  # 0.5 s pause
    assert "pacing:freeze_in_phrase" not in ids(story_lint(p, words=out_words(p, pause)))


def test_freeze_with_no_continuation_extends_the_segment_past_the_phrase(ax):
    ed = Editor(ax)
    m = {**single("funny", 10.0, 14.0), "parts": [{"start_s": 10.0, "end_s": 14.0, "role": "payoff", "label": ""},
                                                   {"start_s": 50.0, "end_s": 52.0, "role": "reaction", "label": ""}]}
    out = ed.finalize(hold_plan((50.0, 52.0)), m, {}, {}, hold_prep())
    assert out["segments"][0]["src_end"] == pytest.approx(11.43) and out["segments"][0]["hold"] > 0  # phrase, THEN beat
    assert "pacing:freeze_in_phrase" not in ids(story_lint(out, words=out_words(out)))


def test_heuristic_plan_hold_never_lands_inside_a_phrase(ax):
    m = single("funny", 10.0, 14.0)
    ed = Editor(ax)
    prep = hold_prep()
    prep["ranges"] = [(10.0, 10.5), (10.5, 14.0)]  # the tight cut ends the first range inside "Fuck… you"
    plan = ed.heuristic_plan(m, {}, {}, prep)
    plan["segments"][0]["hold"] = 0.6  # force the bad beat; the heuristic's own placement must clear it
    assert "pacing:freeze_in_phrase" in ids(story_lint(plan, words=out_words(plan)))  # RED first (control)
    Editor._place_holds(plan, FUCK_YOU)
    assert "pacing:freeze_in_phrase" not in ids(story_lint(plan, words=out_words(plan)))


def test_phrase_around_is_a_positive_control():
    assert qc.phrase_around(FUCK_YOU, 10.5) == (10.0, 11.4)
    assert qc.phrase_around(FUCK_YOU, 10.2) == (10.0, 11.4)  # inside a word
    assert qc.phrase_around(FUCK_YOU, 11.43) is None and qc.phrase_around(FUCK_YOU, 12.0) is None  # after the line


def test_house_rule_and_cp1_numbers_reach_the_prompts():
    t = standards_text("tiktok", -14.0, 1080, 1920, 30)
    assert "sexual" in t.lower() and "nudity" in t.lower() and str(LAYOUT["hook_emphasis_min_px"]) in t
    assert HOUSE_RULES and LAYOUT["caption_min_cap_px"] >= 55 and LAYOUT["hook_setup_min_cap_px"] == 55
    assert LAYOUT["hook_emphasis_min_px"] == 200
    from noze.agency.roles.editor import STORY_TOOLS

    assert "sexual" in STORY_TOOLS.lower() and "FREEZE PLACEMENT" in STORY_TOOLS


# frame 0 too dark -----------------------------------------------------------------------------------------------------
def test_frame0_dark_issues_red_dark_and_flat_green_bright():
    assert [i["id"] for i in qc.frame0_dark_issues(12.0, 40.0)] == ["hook:frame0_dark"]  # near-black
    assert qc.frame0_dark_issues(120.0, 8.0)  # flat grey: nothing to stop the scroll
    assert qc.frame0_dark_issues(QC["frame0_min_luma"] - 1, 60.0)[0]["severity"] == "major"
    assert not qc.frame0_dark_issues(110.0, 55.0)


@needs_ffmpeg
def test_frame0_luma_on_synthetic_clips_dark_band_vs_bright_frame(tmp_path):
    def clip(name, src):
        f = tmp_path / name
        subprocess.run([ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i", src, "-t", "1", "-r", "10", "-pix_fmt", "yuv420p",
                        "-y", str(f)], check=True)
        return str(f)
    dark = clip("dark.mp4", "color=c=black:s=360x640")
    bright = clip("bright.mp4", "testsrc2=s=360x640")
    half = clip("half.mp4", "color=c=black:s=360x640,drawbox=x=0:y=0:w=360:h=320:color=white:t=fill")  # white cam, black game
    mean, std = qc.frame0_luma(dark, [], 360, 640)
    assert qc.frame0_dark_issues(mean, std)  # RED
    mean, std = qc.frame0_luma(bright, [], 360, 640)
    assert not qc.frame0_dark_issues(mean, std)  # GREEN (positive control)
    assert qc.frame0_luma(half, [], 360, 640)[0] > 100  # the whole frame looks fine ...
    mean, std = qc.frame0_luma(half, [(0.0, 1.0, 320, {})], 360, 640)
    assert qc.frame0_dark_issues(mean, std, stacked=True)  # ... but the gameplay band (below the seam) is black
    issues, m = qc.technical_qc(dark, width=360, height=640, fps=10, target_lufs=-14.0, min_s=0, max_s=60, platform="tiktok")
    assert "hook:frame0_dark" in ids(issues) and m["frame0"]["luma_mean"] < 5


# face box validation ------------------------------------------------------------------------------------------------------
def test_valid_face_box_rejects_the_chest_and_specks_but_keeps_heads():
    band = 576
    assert qc.valid_face_box((494, 150, 200, 200), band)  # a head in the upper part
    assert qc.valid_face_box((494, 305, 243, 243), band)  # real faces sit low in a tall cam band: still accepted
    assert not qc.valid_face_box((300, 400, 120, 120), band)  # starts in the bottom 45% = the chest (tattoo, CP1)
    assert not qc.valid_face_box((300, 100, 40, 40), band)  # a speck: < 10% of the band
    assert not qc.valid_face_box(None, band)


def test_measure_cam_faces_drops_the_chest_box_and_keeps_the_face(monkeypatch, tmp_path):
    for i in range(2):
        (tmp_path / f"cam_0_{i}.jpg").write_bytes(b"x")
    monkeypatch.setattr(qc.face_finder, "available", lambda: True)
    monkeypatch.setattr(qc, "yunet_faces", lambda frames, d=None: None)  # the Haar path
    boxes = iter([(300, 400, 120, 120), (494, 150, 200, 200)])  # the chest, then a real head
    monkeypatch.setattr(qc.face_finder, "faces_in_band", lambda frames: [next(boxes) for _ in frames])
    out = qc.measure_cam_faces("clip.mp4", [(0.0, 5.0, 576, {})], tmp_path, per_seg=2)
    assert out[0.0]["box"] == (494, 150, 200, 200) and out[0.0]["hits"] == 1 and out[0.0]["n"] == 2
    monkeypatch.setattr(qc.face_finder, "faces_in_band", lambda frames: [(300, 400, 120, 120)] * len(frames))
    assert qc.measure_cam_faces("clip.mp4", [(0.0, 5.0, 576, {})], tmp_path, per_seg=2)[0.0]["box"] is None  # only the chest


def test_yunet_download_failure_falls_back_without_crashing(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(qc.urllib.request, "urlopen", boom)
    qc._yunet_failed.discard(str(tmp_path))
    assert qc.yunet_model(tmp_path) is None and qc.yunet_faces([(tmp_path / "x.jpg", 576)], tmp_path) is None
    (tmp_path / qc.YUNET_FILE).write_bytes(b"0" * 60_000)  # already cached: no download attempted
    assert qc.yunet_model(tmp_path) == tmp_path / qc.YUNET_FILE


# vod_map (story packs) -----------------------------------------------------------------------------------------------------
PACK = {"start_s": 0.0, "end_s": 40.0, "structure": "arc", "emotion": "funny", "title": "Told you",
        "parts": [{"start_s": 0.0, "end_s": 12.0, "role": "setup", "label": ""},
                  {"start_s": 21.0, "end_s": 32.0, "role": "payoff", "label": ""}],
        "vod_map": [{"file_start": 0.0, "file_end": 20.0, "vod_start": 1000.0},
                    {"file_start": 20.0, "file_end": 40.0, "vod_start": 8200.0}]}


def test_vod_map_makes_the_time_card_say_the_stream_gap_not_the_file_gap(ax):
    ed, prep = prepared(ax, PACK, (0.0, 12.0), (21.0, 32.0))
    assert [p["label"] for p in prep["parts"]] == ["", "2 HOURS LATER"]  # stream time; the glued file would give ''
    plan = ed.heuristic_plan(PACK, {}, {}, prep)
    assert [o["text"] for o in plan["overlays"] if o["kind"] == "time_card"] == ["2 HOURS LATER"]
    out = ed.finalize(plan, PACK, {}, {}, prep)
    assert all(c["ok"] for c in card_expectations(out, story.moment_parts(PACK), PACK["vod_map"]))
    assert "story:label_mismatch" not in ids(story_lint(out, moment=PACK))
    plain = {k: v for k, v in PACK.items() if k != "vod_map"}
    assert "story:label_mismatch" in ids(story_lint(out, moment=plain))  # control: without the map the card "lies"


# CP1 type sizes: the emphasis word >= 200 px, the setup line >= 55 px CAP height ----------------------------------------------
@pytest.mark.parametrize("kind", ["hook_title", "punch_title"])
def test_cp1_title_sizes_red_and_green(monkeypatch, kind):
    from tests import test_agency_qc_v2 as v2

    plan = v2.plan_of([v2.ov(kind, v2.TWO_LINES, "center")])
    v2.force_sizes(monkeypatch, [140, 110])  # big enough for the old 110 floor, short of the 200 px emphasis
    bad = v2.ids(v2.lint(plan))
    assert f"layout:{kind}_emphasis_small" in bad
    v2.force_sizes(monkeypatch, [230, 60])  # the setup line's cap height (~42 px) is under 55
    bad = v2.lint(plan)
    assert f"layout:{kind}_setup_small" in v2.ids(bad) and v2.sev(bad, f"layout:{kind}_setup_small") == "major"
    assert f"layout:{kind}_emphasis_small" not in v2.ids(bad)
    v2.force_sizes(monkeypatch, [230, 110])  # GREEN: control
    ok = v2.ids(v2.lint(plan))
    assert not {f"layout:{kind}_emphasis_small", f"layout:{kind}_setup_small", f"layout:{kind}_small"} & ok


# -- reference research (24 Nov): peak teaser, loop, few cuts, length, title ----------------------------------------------
def w(t, word):
    return {"start": t, "end": round(t + 0.3, 2), "word": word}


def peak_prep(ax, moment, peak_at=None, blueprint=None):
    """A talking stretch with 'no way' at ``peak_at`` (None = no peak words at all)."""
    a, b = moment["start_s"], moment["end_s"]
    ws = words_in(a, peak_at - 0.5 if peak_at else b)
    if peak_at:
        ws += [w(peak_at, "no"), w(peak_at + 0.35, "way!")] + words_in(peak_at + 1.0, b)
    ed = Editor(ax)
    prep = ed.prepare({"id": 1, "campaign_id": None}, Path("missing.mp4"), moment, {"segments": [{"words": ws}]},
                      blueprint or {}, INFO)
    return ed, prep


def test_linear_clip_with_a_late_peak_opens_on_a_teaser_of_it(ax):
    m = single("funny", 100.0, 128.0)
    ed, prep = peak_prep(ax, m, peak_at=120.0)
    segs = ed.heuristic_plan(m, {}, {}, prep)["segments"]
    t = segs[0]
    assert t["role"] == "cold_open" and t["transition_in"] == "cut"
    assert 0.8 <= t["src_end"] - t["src_start"] <= 1.5 and t["src_start"] <= 120.0 <= t["src_end"]  # the face at the peak
    assert segs[1]["src_start"] < 102.0 and segs[1]["transition_in"] == "cut"  # then the clip plays from its start


def test_no_teaser_when_the_clip_already_starts_on_the_peak_or_has_none(ax):
    m = single("funny", 100.0, 128.0)
    ed, prep = peak_prep(ax, m, peak_at=101.0)  # control: peak inside the first 3 s
    assert all(s["role"] != "cold_open" for s in ed.heuristic_plan(m, {}, {}, prep)["segments"])
    ed, prep = peak_prep(ax, m, peak_at=None)  # no peak words
    assert all(s["role"] != "cold_open" for s in ed.heuristic_plan(m, {}, {}, prep)["segments"])
    mp = m | {"peak_s": 121.0}  # a peak measured upstream counts as the signal
    ed, prep = peak_prep(ax, mp, peak_at=None)
    assert ed.heuristic_plan(mp, {}, {}, prep)["segments"][0]["role"] == "cold_open"


def test_cold_open_and_funny_clips_end_on_a_held_reaction_without_a_fade(ax):
    ed, prep = prepared(ax, COLD, *COLD_RANGES)
    last = ed.heuristic_plan(COLD, {}, {}, prep)["segments"][-1]
    assert last["hold"] >= 0.6 and last["transition_in"] != "fade" and last["role"] == "payoff"
    m = single("hype")  # control: hype linear is not a loop clip
    ed, prep = prepared(ax, m, (100.0, 116.0))
    assert ed.heuristic_plan(m, {}, {}, prep)["segments"][-1]["hold"] == 0.0


def test_lint_no_loop_red_on_a_cold_open_that_ends_elsewhere_green_on_the_reaction():
    cold = {"structure": "cold_open"}
    bad = plan_of([seg(0, 4, role="cold_open"), seg(10, 20, role="setup")])
    assert "story:no_loop" in ids(story_lint(bad, moment=cold))
    assert "story:no_loop" not in ids(story_lint(plan_of([seg(0, 4, role="cold_open"), seg(10, 20, role="payoff")]), moment=cold))
    assert "story:no_loop" not in ids(story_lint(plan_of([seg(0, 4), seg(10, 20, role="setup", hold=0.7)]), moment=cold))
    assert "story:no_loop" not in ids(story_lint(bad, moment={"structure": "linear"}))  # only cold_open loops


def words_with_pauses(a, n, pause):
    """n bursts of 5 words (2 s) separated by ``pause`` seconds of silence."""
    out, t = [], a
    for _ in range(n):
        out += words_in(t, t + 2.0, 0.4)
        t += 2.0 + pause
    return out


def ranges_for(ax, words, mode):
    return Editor(ax).prepare({"id": 1, "campaign_id": None}, Path("missing.mp4"), single("hype", 100.0, 130.0),
                              {"segments": [{"words": words}]}, {"framing": {"mode": mode}}, INFO)["ranges"]


def test_gameplay_is_not_cut_on_short_pauses_but_long_ones_still_go(ax):
    short = words_with_pauses(100.0, 9, 0.7)  # a 0.7 s breath: over the talking-head 0.4 s rule, under the 0.9 s one
    stack, talk = ranges_for(ax, short, "stack"), ranges_for(ax, short, "fixed")
    assert len(talk) >= 5 and len(stack) < len(talk)  # control: the talking head IS cut there
    assert (len(stack) - 1) * 30.0 / sum(b - a for a, b in stack) <= 4.5  # ~4 cuts per 30 s at most
    assert max(b - a for a, b in stack) > 5.0  # a running stretch is not chopped into 2.8 s pieces
    longer = words_with_pauses(100.0, 7, 1.6)  # 1.6 s pauses are still cut on gameplay
    assert len(ranges_for(ax, longer, "stack")) >= 3


def test_lint_over_cut_red_on_chopped_green_on_calm_and_on_time_jumps():
    chopped = plan_of([seg(2 * i, 2 * i + 1) for i in range(20)])  # 19 cuts in 20 s
    assert "pacing:over_cut" in ids(story_lint(chopped))
    assert "pacing:over_cut" not in ids(story_lint(plan_of([seg(0, 7), seg(7, 14), seg(14, 21), seg(21, 28)])))
    jumped = plan_of([seg(0, 1)] + [seg(1000 * i, 1000 * i + 1, transition_in="rewind") for i in range(1, 12)])
    assert "pacing:over_cut" not in ids(story_lint(jumped))  # a time-jump story may cut fast


def test_lint_long_for_stream_only_on_a_long_linear_clip():
    long = plan_of([seg(0, 20), seg(20, 40)])  # 40 s
    assert "pacing:long_for_stream" in ids(story_lint(long))
    assert "pacing:long_for_stream" not in ids(story_lint(plan_of([seg(0, 14), seg(14, 28)])))
    assert "pacing:long_for_stream" not in ids(story_lint(long, moment={"structure": "arc"}))


def test_lint_title_long_and_the_heuristic_title_stays_inside_the_limit(ax):
    from noze.agency.roles.editor import cap_chars, short_hook

    def title(text):
        return plan_of([seg(0, 5)], overlays=[{"kind": "hook_title", "text": text, "start": 0.0, "end": 2.0}])
    wordy = "HE SAID THE FIRST STREAM WOULD NEVER END TODAY OK"  # 49 characters
    assert "hook:title_long" in ids(story_lint(title(wordy)))
    assert "hook:title_long" in ids(story_lint(title("ONE\nTWO\nTHREE")))  # 3 lines
    assert "hook:title_long" not in ids(story_lint(title("STREAM ALMOST ENDED IMMEDIATELY")))
    assert "hook:title_long" not in ids(story_lint(title("HE SAID\nIT IS EASY")))
    assert len(short_hook("extraordinarily unbelievable spectacularly ridiculous catastrophe")) <= 45
    assert len(cap_chars("a " * 40)) <= 45
    found = [i for i in story_lint(title(wordy)) if i["id"] == "hook:title_long"]
    fixed = Editor(ax).apply_fixes(conform(title(wordy), EDIT_PLAN), found, {"words": []}, {}, {})
    assert "hook:title_long" not in ids(story_lint(fixed))


def long_phrase(a, b):
    return [{"start": round(t, 2), "end": round(t + 0.35, 2), "word": f"p{n}"}
            for n, t in enumerate(x * 0.4 + a for x in range(int((b - a) / 0.4)))]


def hold_case(ax, seg_end, part_end, phrase=(20.0, 29.0), moment_a=10.0):
    ws = long_phrase(*phrase)  # one unbroken phrase (words 0.05 s apart)
    m = single("funny", moment_a, part_end)
    prep = hold_prep(ws) | {"ranges": [(moment_a, part_end)]}
    plan = plan_of([seg(17.6, seg_end, hold=0.75)])
    return Editor(ax).finalize(plan, m, {}, {}, prep)


def test_jaw_drop_never_cuts_more_footage_than_the_hold_is_long(ax):
    out = hold_case(ax, 26.05, 40.0)  # phrase 20-29 runs well past the segment: no safe spot
    s = out["segments"][0]
    assert s["src_end"] == pytest.approx(26.05) and s["hold"] == 0.0  # RED before: 17.6-19.98 and the payoff was gone
    assert any(f["issue_id"] == "pacing:freeze_in_phrase" for f in out["fixes"])
    # control: a phrase that starts just before the segment end may take the hold back to its start (<= hold long)
    ws = [{"word": "a", "start": 17.0, "end": 17.5}, {"word": "b", "start": 25.7, "end": 26.0},
          {"word": "c", "start": 26.05, "end": 26.5}, {"word": "d", "start": 26.55, "end": 29.5}]
    m = single("funny", 10.0, 40.0)
    ok = Editor(ax).finalize(plan_of([seg(17.6, 26.05, hold=0.75)]), m, {}, {}, hold_prep(ws) | {"ranges": [(10.0, 40.0)]})
    assert ok["segments"][0]["src_end"] >= 26.05 - 0.75 and ok["segments"][0]["hold"] == 0.75  # freeze BEFORE the line


def test_hold_extension_stays_inside_the_part_and_the_length_cap(ax):
    out = hold_case(ax, 30.75, 30.75, phrase=(29.0, 31.5))  # the phrase ends 0.75 s after the part does
    assert out["segments"][0]["src_end"] <= 30.75 + 1e-6  # RED before: 31.33 and too_long
    m = single("funny", 10.0, 40.0)  # control: room in the part -> the phrase is finished, then the beat
    ws = long_phrase(25.0, 27.0)
    ok = Editor(ax).finalize(plan_of([seg(17.6, 26.05, hold=0.75)]), m, {}, {}, hold_prep(ws) | {"ranges": [(10.0, 40.0)]})
    assert ok["segments"][0]["src_end"] > 26.05
    short = Editor(ax).finalize(plan_of([seg(17.6, 26.05, hold=0.75)]), m, {"clip_length": {"max_s": 9.0}}, {},
                                hold_prep(ws) | {"ranges": [(10.0, 40.0)]})
    assert Timeline(short["segments"]).duration <= 9.0 + 0.05  # the cap runs after the move


def test_caption_font_scale_never_goes_under_one(ax):
    m = single("funny", 100.0, 116.0)
    ed, prep = prepared(ax, m, (100.0, 116.0))
    plan = ed.heuristic_plan(m, {}, {}, prep)
    plan["captions"]["font_scale"] = 0.7
    assert ed.finalize(plan, m, {}, {}, prep)["captions"]["font_scale"] == 1.0
    plan["captions"]["font_scale"] = 1.3
    assert ed.finalize(plan, m, {}, {}, prep)["captions"]["font_scale"] == 1.3


def test_segment_labels_ride_the_first_segment_of_each_part(ax):
    ed, prep = prepared(ax, COLD, *COLD_RANGES)
    plan = ed.finalize(ed.heuristic_plan(COLD, {}, {}, prep), COLD, {}, {}, prep)
    labels = [(s["src_start"] >= 2500.0, s["label"]) for s in plan["segments"]]
    assert labels[0][1] == "" and [l for _, l in labels if l] == ["40 MIN EARLIER", "40 MIN LATER"]
    assert plan["segments"][1]["label"] == "40 MIN EARLIER"  # the first segment of the setup part (the rewind pill)
    h = ed.heuristic_plan(COLD, {}, {}, prep)
    assert [s["label"] for s in h["segments"] if s["label"]] == ["40 MIN EARLIER", "40 MIN LATER"]


def test_segments_are_cut_at_story_pack_seams(ax):
    vm = [{"file_start": 0, "file_end": 60, "vod_start": 3600}, {"file_start": 60, "file_end": 120, "vod_start": 10800}]
    m = {"start_s": 50.0, "end_s": 90.0, "emotion": "funny", "structure": "linear", "title": "T", "vod_map": vm}
    prep = hold_prep([]) | {"ranges": [(50.0, 90.0)]}
    out = Editor(ax).finalize(plan_of([seg(55, 70, hold=0.5)]), m, {}, {}, prep)
    # sanitize clamps 55 to the part slack (58.5); both pieces are real footage (>= 1 s) of their own parts, and the
    # jump between them is labelled + carded (review 24 Nov: never as continuous footage)
    assert [(s["src_start"], s["src_end"], s["label"]) for s in out["segments"]] == [(58.5, 60.0, ""),
                                                                                    (60.0, 70.0, "2 HOURS LATER")]
    assert out["segments"][0]["hold"] == 0.0 and out["segments"][1]["hold"] == 0.5
    assert any(o["kind"] == "time_card" and o["text"] == "2 HOURS LATER" for o in out["overlays"])
    # a sliver under 1 s of the other hour never flashes on screen; a piece already played by another segment never repeats
    short = Editor(ax).finalize(plan_of([seg(59.4, 70)]), m, {}, {}, prep)
    assert [(s["src_start"], s["src_end"]) for s in short["segments"]] == [(60.0, 70.0)]
    dup = Editor(ax).finalize(plan_of([seg(50, 61.2), seg(60, 85)]), m, {}, {}, prep)
    assert [(s["src_start"], s["src_end"]) for s in dup["segments"]] == [(50.0, 60.0), (60.0, 85.0)]
    # a plan whose first segment sits in part A and second in part B: the jump is labelled AND carded
    two = Editor(ax).finalize(plan_of([seg(52, 59.9), seg(60.5, 70)]), m, {}, {}, prep)
    assert [s["label"] for s in two["segments"]] == ["", "2 HOURS LATER"]
    cards = [o for o in two["overlays"] if o["kind"] == "time_card"]
    assert cards and cards[0]["text"] == "2 HOURS LATER" and abs(cards[0]["start"] - 7.9) < 0.7
    # control: no seam inside -> one segment
    one = Editor(ax).finalize(plan_of([seg(61, 70)]), m, {}, {}, prep)
    assert [(s["src_start"], s["src_end"]) for s in one["segments"]] == [(61.0, 70.0)]
    # a sliver across the seam (slack) is dropped, the part side stays
    sl = Editor(ax).finalize(plan_of([seg(59.9, 70)]), m, {}, {}, prep)
    assert [(s["src_start"], s["src_end"]) for s in sl["segments"]] == [(60.0, 70.0)]


def test_prompt_and_sop_carry_the_reference_rules():
    from noze.agency.roles.editor import STORY_TOOLS
    for needle in ("teaser", "LOOP", "0.9 s", "20-30 s", "<= 45 characters"):
        assert needle in STORY_TOOLS
    sop = (Path(__file__).parents[1] / "noze/agency/sop/editor.md").read_text(encoding="utf-8").lower()
    assert "apa kata data referensi" in sop


# -- mandor CP2 (24 Nov): cam leak, title on the face, dropped arc, voice, repeated ending -------------------------------
from noze.agency.media import qc as _qc  # noqa: E402
from noze.agency.media.qc import layout_lint  # noqa: E402
from noze.agency.media.transcribe import spread_words  # noqa: E402
from noze.agency.roles.editor import inset_box  # noqa: E402
from noze.agency.standards import voice_of  # noqa: E402

CP2_MP4 = Path(__file__).parents[1] / "noze-data/agency/review/clipper-r1/cp2/sampel1b_kai_v3.mp4"
CAM_OK = {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}


def _ids(issues):
    return {i["id"] for i in issues}


def _band(w=540, h=296, leak=()):
    """A synthetic webcam band: a smooth room gradient with a bright lamp at the left edge (natural, localised);
    ``leak`` paints foreign strips: ('top', px) a flat green strip, ('right', px) a flat tan one."""
    import numpy as np

    yy, xx = np.mgrid[0:h, 0:w]
    img = np.stack([90 + 60 * xx / w, 70 + 50 * yy / h, 120 + 40 * xx / w], axis=-1)
    img[h // 3: h // 2, :w // 12] = (250, 250, 230)  # a lamp on the edge: natural
    img = img + np.random.default_rng(1).normal(0, 3, img.shape)
    for edge, px in leak:
        if edge == "top":
            img[:px] = (30, 120, 40)
        if edge == "right":
            img[:, w - px:] = (190, 150, 90)
    return np.clip(img, 0, 255).astype("uint8")


def test_cam_edge_foreign_flags_a_leaked_strip_and_not_a_natural_edge():
    from noze.agency.media.qc import cam_edge_foreign

    assert cam_edge_foreign(_band()) == {}  # control: gradient + a lamp on the edge is the webcam's own picture
    hit = cam_edge_foreign(_band(leak=[("top", 30), ("right", 50)]))
    assert set(hit) == {"top", "right"} and abs(hit["top"] - 30) <= 3 and abs(hit["right"] - 50) <= 3
    assert set(cam_edge_foreign(_band(leak=[("top", 30)]))) == {"top"}


def test_cam_edge_on_the_real_cp2_render_red_raw_green_inset():
    cv2 = pytest.importorskip("cv2")
    if not CP2_MP4.exists():
        pytest.skip("cp2 render not on this machine")
    cap = cv2.VideoCapture(str(CP2_MP4))
    cap.set(cv2.CAP_PROP_POS_MSEC, 9730)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        pytest.skip("cannot decode the cp2 render")
    band = frame[:592]  # the cam band as rendered: leaf strip on top, wall on the right
    assert {"top", "right"} <= set(_qc.cam_edge_foreign(band))
    assert _qc.cam_edge_foreign(band[64:, :962]) == {}  # the same picture inset past the strips is clean


def test_cam_edge_samples_majority_and_issue(monkeypatch):
    import types

    leaky = _band(leak=[("top", 30)])
    clean = _band()
    frames = iter([leaky, leaky, clean, clean, clean, clean])  # seg 1: 2 of 3 leak; seg 2: none

    def fake_run(args, **k):
        return types.SimpleNamespace(stdout=next(frames).tobytes())

    monkeypatch.setattr(_qc, "run", fake_run)
    seams = [(0.0, 6.0, 296, {}), (6.0, 12.0, 296, {})]
    found = _qc.cam_edge_samples("x.mp4", seams, 540, per_seg=3)
    assert [bool(e) for _, _, e in found] == [True, False]
    iss = _qc.cam_edge_issues(found, 540)
    assert [i["id"] for i in iss] == ["framing:cam_edge_foreign"] and iss[0]["severity"] == "major"
    assert _qc.cam_edge_issues([(0.0, 296, {})]) == []  # control


def _stack_seg(cam, **kw):
    return {"src_start": 0.0, "src_end": 10.0, "speed": 1.0, "reframe": {"mode": "stack", "x": 0.5, "cam": cam},
            "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut", "note": "", **kw}


def test_finalize_insets_the_detector_cam_but_keeps_a_chosen_one(ax):
    det = {"x": 0.05, "y": 0.1, "w": 0.30, "h": 0.30}  # 1.9x magnification: no growth needed
    prep = {"source_info": INFO, "ranges": [(0.0, 10.0)], "moment_words": [], "words": [], "facecam": det,
            "facecam_face": {"x": 0.3, "y": 0.2, "w": 0.4, "h": 0.5}}
    moment = {"start_s": 0.0, "end_s": 10.0}

    def plan_with(cam):
        return conform({"segments": [_stack_seg(cam)], "captions": {"enabled": False}}, EDIT_PLAN)

    got = Editor(ax).finalize(plan_with(dict(det)), moment, {}, {}, prep)["segments"][0]["reframe"]["cam"]
    assert got == inset_box(det, LAYOUT["cam_inset"]) and got["x"] > det["x"] and got["w"] < det["w"]
    mine = {"x": 0.04, "y": 0.09, "w": 0.32, "h": 0.32}  # a model's / human's crop is a decision
    assert Editor(ax).finalize(plan_with(dict(mine)), moment, {}, {}, prep)["segments"][0]["reframe"]["cam"] == mine


def test_fix_library_insets_only_the_leaking_segment_in_real_coordinates(ax):
    ed = Editor(ax)
    cam = {"x": 0.0, "y": 0.4, "w": 0.225, "h": 0.22}  # 432x238 px of a 1920x1080 source -> band 592, scale 2.5
    mine = {"x": 0.5, "y": 0.1, "w": 0.3, "h": 0.3}  # a clean segment with another (model's) crop
    segs = [_stack_seg(cam), {**_stack_seg(mine), "src_start": 10.0, "src_end": 20.0}]
    plan = conform({"segments": segs, "captions": {"enabled": False}}, EDIT_PLAN)
    ev = {"edges": {"top": 59}, "band": 592, "width": 1080,
          "segments": [{"t": 0.0, "band": 592, "edges": {"top": 59, "right": 110, "bottom": 5}}]}
    issue = {"id": "framing:cam_edge_foreign", "timecode_s": 0.0, "evidence": ev}
    out = ed.apply_fixes(plan, [issue], {"words": [], "source_info": INFO}, {}, {})
    new = out["segments"][0]["reframe"]["cam"]
    k = max(1080 / (cam["w"] * 1920), 592 / (cam["h"] * 1080))  # output px per source px
    win_top = cam["y"] * 1080 + (cam["h"] * 1080 - 592 / k) / 2  # the band shows a centred window of the crop
    assert new["y"] * 1080 >= win_top + 59 / k - 0.5  # the strip is outside the new crop (source px, not band share)
    win_right = cam["x"] * 1920 + (cam["w"] * 1920 + 1080 / k) / 2
    assert (new["x"] + new["w"]) * 1920 <= win_right - 110 / k + 0.5
    assert (new["y"] + new["h"]) * 1080 < (cam["y"] + cam["h"]) * 1080 - 5 / k + 0.5  # the bottom line is cut too
    assert out["segments"][1]["reframe"]["cam"] == mine  # the clean segment is not touched
    assert any(f["issue_id"] == "framing:cam_edge_foreign" for f in out["fixes"])
    quiet = {**ev, "segments": [{"t": 0.0, "band": 592, "edges": {}}]}
    same = ed.apply_fixes(plan, [{**issue, "evidence": quiet}], {"words": [], "source_info": INFO}, {}, {})
    assert same["segments"][0]["reframe"]["cam"] == cam and not same["fixes"]  # control: nothing measured, nothing moved
    # the floor: a crop already near the magnification limit is not shrunk past it (and no fix is logged)
    tight = {"x": 0.0, "y": 0.4, "w": 0.17, "h": 0.17}
    p2 = conform({"segments": [_stack_seg(tight)], "captions": {"enabled": False}}, EDIT_PLAN)
    big = {**ev, "segments": [{"t": 0.0, "band": 592, "edges": {"top": 90, "right": 120}}]}
    o2 = ed.apply_fixes(p2, [{**issue, "evidence": big}], {"words": [], "source_info": INFO}, {}, {})
    assert o2["segments"][0]["reframe"]["cam"] == tight and not o2["fixes"]


def test_cam_edge_issue_reports_every_segment_and_the_bottom_edge_is_checked():
    found = [(0.0, 592, {"top": 60}), (6.0, 592, {}), (9.0, 592, {"right": 7})]
    iss = _qc.cam_edge_issues(found, 1080)[0]
    assert [r["t"] for r in iss["evidence"]["segments"]] == [0.0, 9.0] and iss["evidence"]["segments"][1]["edges"] == {"right": 7}
    from noze.agency.media.qc import cam_edge_foreign

    assert set(cam_edge_foreign(_band_bottom_leak())) == {"bottom"}  # the cyan line under the band (reviewer s1)
    assert cam_edge_foreign(_band()) == {}


def _band_bottom_leak():
    img = _band()
    img[-14:] = (0, 220, 220)
    return img


# -- title over the subject -------------------------------------------------------------------------------------------
def _stack_plan(overlays, voice=None, captions=None):
    s = _stack_seg(CAM_OK, **({"voice": voice} if voice else {}))
    return conform({"segments": [s], "captions": captions or {"enabled": False}, "overlays": overlays}, EDIT_PLAN)


def _title(pos="center"):
    return {"kind": "hook_title", "text": "WHY PEOPLE FAIL", "start": 0.0, "end": 2.5, "position": pos, "style": "pop"}


def _lint(plan, words=None, **kw):
    return layout_lint(plan, {}, words=words or [], width=1080, height=1920, platform="tiktok", src_size=(1920, 1080), **kw)


def test_title_over_subject_red_when_it_covers_a_head_green_elsewhere(monkeypatch):
    monkeypatch.setattr(_qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")
    plan = _stack_plan([_title()])
    dbg = {}
    _lint(plan, debug=dbg)
    x0, y0, x1, y1 = next(ly["box"] for ly in dbg["layers"] if ly["kind"] == "hook_title")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    on_face = [(1.0, (cx - 60, cy - 60, cx + 60, cy + 60))]
    hit = [i for i in _lint(plan, gameplay_faces=on_face) if i["id"] == "layout:title_over_subject"]
    assert hit and hit[0]["severity"] == "major" and 0.0 <= hit[0]["evidence"]["face_cy"] < 0.4
    low = [(1.0, (400, 1500, 600, 1700))]  # a head at the bottom of the band, clear of the title
    assert "layout:title_over_subject" not in _ids(_lint(plan, gameplay_faces=low))
    assert "layout:title_over_subject" not in _ids(_lint(plan, gameplay_faces=[(5.0, on_face[0][1])]))  # title gone by then
    assert "layout:title_over_subject" not in _ids(_lint(plan, gameplay_faces=[]))
    # the video path measures itself (detector stubbed)
    monkeypatch.setattr(_qc, "measure_gameplay_faces", lambda *a, **k: on_face)
    assert "layout:title_over_subject" in _ids(_lint(plan, video_path="x.mp4"))
    monkeypatch.setattr(_qc, "measure_gameplay_faces", lambda *a, **k: None)
    notes = []
    assert "layout:title_over_subject" not in _ids(_lint(plan, video_path="x.mp4", notes=notes)) and notes


def test_measure_gameplay_faces_finds_the_npc_head_in_the_real_render(tmp_path):
    pytest.importorskip("cv2")
    if not CP2_MP4.exists() or _qc.yunet_model() is None:
        pytest.skip("cp2 render or the YuNet model is not on this machine")
    got = _qc.measure_gameplay_faces(str(CP2_MP4), [(0.0, 20.0, 592, {})], [(9.0, 10.5)], tmp_path / "g")
    assert got and all(fy0 >= 592 for _, (_, fy0, _, _) in got)  # a head in the gameplay band (the NPC)


def test_editor_moves_the_title_off_a_subject_in_the_top_of_the_band(ax):
    def go(cy, position="center", subject=True):
        prep = {"source_info": INFO, "ranges": [(0.0, 10.0)], "moment_words": [], "words": [], "facecam": CAM_OK,
                "facecam_face": None}
        if subject:
            prep["game_subject"] = {"cx": 0.5, "cy": cy, "n": 3}
        out = Editor(ax).finalize(_stack_plan([_title(position)]), {"start_s": 0.0, "end_s": 10.0}, {}, {}, prep)
        return out["overlays"][0]["position"], out.get("fixes")

    pos, fixes = go(0.2)
    assert pos == "bottom" and fixes and fixes[-1]["issue_id"] == "layout:title_over_subject"
    assert go(0.7)[0] == "center"  # control: the subject is low, the top of the band is free
    assert go(0.2, "bottom")[0] == "bottom"
    assert go(0.2, subject=False)[0] == "center"  # control: no subject known, nothing moves


def test_fix_library_title_over_subject_picks_the_free_half(ax):
    for cy, want in ((0.15, "bottom"), (0.8, "center")):
        out = Editor(ax).apply_fixes(_stack_plan([_title("center")]), [{"id": "layout:title_over_subject",
                                     "timecode_s": 0.0, "evidence": {"face_cy": cy}}], {"words": []}, {}, {})
        assert out["overlays"][0]["position"] == want


# -- arc dropped --------------------------------------------------------------------------------------------------------
def _seg(a, b, **kw):
    return {"src_start": a, "src_end": b, "speed": 1.0, "reframe": {"mode": "center", "x": 0.5},
            "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut", "note": "", **kw}


def _plan(segs, overlays=None):
    return conform({"segments": segs, "captions": {"enabled": False}, "overlays": overlays or []}, EDIT_PLAN)


def test_arc_dropped_red_one_period_green_both_and_for_other_structures():
    one = _plan([_seg(100, 106), _seg(106, 112)])
    hit = [i for i in story_lint(one, moment=ARC) if i["id"] == "story:arc_dropped"]
    assert hit and hit[0]["severity"] == "major" and hit[0]["evidence"]["missing_parts"] == [1]
    both = _plan([_seg(100, 112), _seg(2500, 2506)])
    assert "story:arc_dropped" not in _ids(story_lint(both, moment=ARC))
    assert "story:arc_dropped" not in _ids(story_lint(one, moment={**ARC, "structure": "linear"}))
    close = {**ARC, "parts": [{"start_s": 100.0, "end_s": 112.0, "role": "setup", "label": ""},
                              {"start_s": 140.0, "end_s": 150.0, "role": "payoff", "label": ""}]}  # < 1 min apart: one period
    assert "story:arc_dropped" not in _ids(story_lint(_plan([_seg(100, 112)]), moment=close))


def test_finalize_logs_a_dropped_arc_part_without_adding_footage(ax):
    prep = {"source_info": INFO, "ranges": [(100.0, 112.0)], "moment_words": [], "words": []}
    out = Editor(ax).finalize(_plan([_seg(100, 112)]), ARC, {}, {}, prep)
    assert [(s["src_start"], s["src_end"]) for s in out["segments"]] == [(100.0, 112.0)]  # nothing added
    assert "not played" in out["rationale"] and not any(f["issue_id"] == "story:arc_dropped" for f in out.get("fixes") or [])
    again = Editor(ax).finalize(out, ARC, {}, {}, prep)
    assert again["rationale"].count("not played") == 1  # idempotent
    ok = Editor(ax).finalize(_plan([_seg(100, 112), _seg(2500, 2506)]), ARC, {}, {}, prep)
    assert "not played" not in ok["rationale"]  # control


def test_heuristic_plan_plays_every_arc_part(ax):
    ed, prep = prepared(ax, ARC, (100.0, 112.0), (2500.0, 2506.0))
    keep = [i for i, p in enumerate(prep["range_parts"]) if p == 0]  # a tight cut that lost the whole second part
    prep["ranges"], prep["range_parts"] = [prep["ranges"][i] for i in keep], [0] * len(keep)
    plan = ed.heuristic_plan(ARC, {}, {}, prep)
    assert any(s["src_start"] >= 2500.0 - 1 for s in plan["segments"])
    assert "story:arc_dropped" not in _ids(story_lint(ed.finalize(plan, ARC, {}, {}, prep), moment=ARC))


# -- voice --------------------------------------------------------------------------------------------------------------
def test_voice_of_game_dialogue_vs_streamer():
    assert voice_of("Welcome sir, the mission begins now") == "game"
    assert voice_of("You have reached the voicemail of Mister Lamar") == "game"  # phone / NPC line
    assert voice_of("Ladies and gentlemen welcome to Vice City") == "game"  # >= 2 formal NPC words
    assert voice_of('"you will pay for this" he says') == "game"
    assert voice_of("oh my god I can't believe it") == "streamer"  # first person
    assert voice_of("welcome to chat bro") == "streamer"  # streamer slang beats the formal word
    assert voice_of("what is that") == "streamer" and voice_of("") == "streamer"  # when unsure: streamer
    for line in ("Welcome back everybody", "please please please no", "Mission failed again, are you serious",
                 "Subscribe to the channel right now", "You are not going to believe this one",
                 "anjir mission nya susah banget"):  # reviewer #6: streamer talk that one formal word used to flip
        assert voice_of(line) == "streamer", line


def _talk(text, a, step=0.4):
    return [{"word": w, "start": round(a + i * step, 2), "end": round(a + i * step + 0.35, 2)}
            for i, w in enumerate(text.split())]


def test_heuristic_plan_marks_game_dialogue_segments(ax):
    moment = {"start_s": 100.0, "end_s": 124.0, "emotion": "funny", "structure": "linear", "title": "NPC roast"}
    words = _talk("Welcome sir the mission begins now please step this way", 100.0) + _talk(
        "oh my god I can't believe he said that to me", 112.0)
    ed = Editor(ax)
    prep = ed.prepare({"id": 1, "campaign_id": None}, Path("missing.mp4"), moment,
                      {"segments": [{"words": words}]}, {}, INFO)
    plan = ed.heuristic_plan(moment, {}, {}, prep)
    voice_at = {round(s["src_start"]): s["voice"] for s in plan["segments"]}
    assert "game" in voice_at.values() and "streamer" in voice_at.values()
    assert all(v == "game" for k, v in voice_at.items() if k < 110)
    assert all(v == "streamer" for k, v in voice_at.items() if k >= 112)


def test_speaker_style_lint_red_when_all_streamer_over_game_dialogue_green_when_marked():
    words = _talk("Welcome sir the mission begins now please step this way", 0.0) + _talk(
        "oh my god I can't believe he said that to me", 5.0)

    def segs(v1):
        return [_seg(0, 5, voice=v1), _seg(5, 10)]

    assert "captions:speaker_style" in _ids(story_lint(_plan(segs("streamer")), words=words))
    assert "captions:speaker_style" not in _ids(story_lint(_plan(segs("game")), words=words))
    only_streamer = _talk("oh my god I can't believe he said that to me", 0.0)
    assert "captions:speaker_style" not in _ids(story_lint(_plan([_seg(0, 5)]), words=only_streamer))
    fixed = Editor.__new__(Editor).apply_fixes(_plan(segs("streamer")), [{"id": "captions:speaker_style"}],
                                               {"words": words}, {}, {})
    assert [s["voice"] for s in fixed["segments"]] == ["game", "streamer"]


def test_layout_lint_measures_the_taller_game_pill(monkeypatch):
    monkeypatch.setattr(_qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")
    caps = {"enabled": True, "style": "bold_pop", "words_per_caption": 2, "position": "upper", "font_scale": 1.0}
    words = spread_words("why do most people fail at saving money", 0.0, 6.0)

    def height(voice):
        dbg = {}
        _lint(_stack_plan([], voice=voice, captions=caps), words=words, debug=dbg)
        c = next(ly for ly in dbg["layers"] if ly["kind"] == "caption")
        return c["box"][3] - c["box"][1]

    assert height("game") > height(None) + 14  # pill padding + the IN-GAME tag above it; no voice = the old box


# -- repeated ending ----------------------------------------------------------------------------------------------------
def test_repeat_line_red_on_a_thrice_repeated_ending_green_otherwise():
    plan = _plan([_seg(0, 20)])
    loop = _talk("fine then you're a professional you're a professional you're a professional", 14.0, 0.3)
    hit = [i for i in story_lint(plan, words=loop) if i["id"] == "pacing:repeat_line"]
    assert hit and hit[0]["severity"] == "minor"
    assert "pacing:repeat_line" in _ids(story_lint(plan, words=_talk("professional professional professional", 15.0)))
    twice = _talk("you're a professional you're a professional", 15.0)
    assert "pacing:repeat_line" not in _ids(story_lint(plan, words=twice))
    assert "pacing:repeat_line" not in _ids(story_lint(plan, words=_talk("no no no no", 16.0)))  # a short exclamation
    early = _talk("you're a professional you're a professional you're a professional", 1.0, 0.3)
    assert "pacing:repeat_line" not in _ids(story_lint(plan, words=early))  # outside the ending window


# -- CP2 reviewer sweep: no ping-pong, no regrowth, honest fixes ----------------------------------------------------------
def _title_prep(cy=0.2, cx=0.5, **kw):
    return {"source_info": INFO, "ranges": [(0.0, 10.0)], "moment_words": [], "words": [], "facecam": CAM_OK,
            "facecam_face": None, "game_subject": {"cx": cx, "cy": cy, "n": 3}, **kw}


def test_title_placement_is_idempotent_and_never_fights_a_fix_or_a_revision(ax):
    m = {"start_s": 0.0, "end_s": 10.0}
    ed = Editor(ax)
    first = ed.finalize(_stack_plan([_title()]), m, {}, {}, _title_prep())
    assert first["overlays"][0]["position"] == "bottom"
    assert ed.finalize(first, m, {}, {}, _title_prep())["overlays"][0]["position"] == "bottom"  # idempotent
    # the fix library puts the title back under the seam (the subject measured LOW): finalize must not undo it
    fixed = ed.apply_fixes(first, [{"id": "layout:title_over_subject", "timecode_s": 0.0, "evidence": {"face_cy": 0.8}}],
                           {"words": []}, {}, {})
    assert fixed["overlays"][0]["position"] == "center"
    assert ed.finalize(fixed, m, {}, {}, _title_prep())["overlays"][0]["position"] == "center"
    # a revision (fresh=False) and a title somebody already placed are left alone
    assert ed.finalize(_stack_plan([_title()]), m, {}, {}, _title_prep(), fresh=False)["overlays"][0]["position"] == "center"
    assert ed.finalize(_stack_plan([_title("lower")]), m, {}, {}, _title_prep())["overlays"][0]["position"] == "lower"
    assert ed.finalize(_stack_plan([_title("top")]), m, {}, {}, _title_prep())["overlays"][0]["position"] == "top"


def test_title_placement_ignores_a_head_outside_the_visible_gameplay_crop(ax):
    m = {"start_s": 0.0, "end_s": 10.0}
    # 1920x1080 source, band 1331 px tall: the visible crop is ~0.43 of the source width around x=0.5
    far = Editor(ax).finalize(_stack_plan([_title()]), m, {}, {}, _title_prep(cx=0.05))
    assert far["overlays"][0]["position"] == "center"  # a head at the far left is not on screen
    near = Editor(ax).finalize(_stack_plan([_title()]), m, {}, {}, _title_prep(cx=0.5))
    assert near["overlays"][0]["position"] == "bottom"  # control: the same head inside the crop


def test_small_detector_cam_stays_inside_the_inset_box_no_regrowth(ax):
    det = {"x": 0.30, "y": 0.30, "w": 0.18, "h": 0.18}  # 3.1x: the old fit_cam_upscale grew it past the detector box
    prep = {"source_info": INFO, "ranges": [(0.0, 10.0)], "moment_words": [], "words": [], "facecam": det,
            "facecam_face": {"x": 0.3, "y": 0.2, "w": 0.4, "h": 0.5}}
    plan = conform({"segments": [_stack_seg(dict(det))], "captions": {"enabled": False}}, EDIT_PLAN)
    got = Editor(ax).finalize(plan, {"start_s": 0.0, "end_s": 10.0}, {}, {}, prep)["segments"][0]["reframe"]["cam"]
    box = inset_box(det, LAYOUT["cam_inset"])
    from noze.agency.roles.editor import CAM_SOFT_MAX, cam_magnification
    if cam_magnification(box, INFO["width"], INFO["height"], 1080, 1920) <= CAM_SOFT_MAX:
        assert got == box and got["w"] < det["w"]
    elif cam_magnification(det, INFO["width"], INFO["height"], 1080, 1920) <= CAM_SOFT_MAX:
        assert got == det  # review CP2: the inset would push it past the soft max -> the inset is given back
    else:  # even the raw box is too small: it grows JUST enough (not the old 2.5x growth over the stream layout)
        assert det["w"] < got["w"] <= det["w"] * 1.08
    assert cam_magnification(got, INFO["width"], INFO["height"], 1080, 1920) <= 3.2


def test_fix_library_replays_a_dropped_arc_part_and_the_lint_then_passes(ax):
    one = _plan([_seg(100, 106), _seg(106, 112)])
    issue = next(i for i in story_lint(one, moment=ARC) if i["id"] == "story:arc_dropped")
    prep = {"source_info": INFO, "ranges": [(100.0, 112.0)], "moment_words": [], "words": []}
    out = Editor(ax).apply_fixes(one, [issue], prep, {}, {})
    assert any(s["src_start"] >= 2499.0 for s in out["segments"]) and any(f["issue_id"] == "story:arc_dropped" for f in out["fixes"])
    final = Editor(ax).finalize(out, ARC, {}, {}, prep, fresh=False)
    assert "story:arc_dropped" not in _ids(story_lint(final, moment=ARC))
    assert [s["label"] for s in final["segments"] if s["label"]] == ["40 MIN LATER"]  # and its time card follows
    # control: nothing missing = nothing added, nothing logged
    both = _plan([_seg(100, 112), _seg(2500, 2506)])
    same = Editor(ax).apply_fixes(both, [{**issue, "evidence": {"missing": [], "seg_parts": [0, 1]}}], prep, {}, {})
    assert len(same["segments"]) == 2 and not same["fixes"]


def test_title_over_subject_is_minor_when_faces_fill_both_halves(monkeypatch):
    monkeypatch.setattr(_qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")
    plan = _stack_plan([_title()])
    dbg = {}
    _lint(plan, debug=dbg)
    x0, y0, x1, y1 = next(ly["box"] for ly in dbg["layers"] if ly["kind"] == "hook_title")
    top_face = (1.0, (x0 + 10, y0, x0 + 200, y1))
    bottom_face = (1.5, (400, 1500, 600, 1750))
    one = [i for i in _lint(plan, gameplay_faces=[top_face]) if i["id"] == "layout:title_over_subject"]
    assert one and one[0]["severity"] == "major"  # control: a free half exists
    both = [i for i in _lint(plan, gameplay_faces=[top_face, bottom_face]) if i["id"] == "layout:title_over_subject"]
    assert both and both[0]["severity"] == "minor"  # nowhere to move it to
    tall = [i for i in _lint(plan, gameplay_faces=[(1.0, (x0 + 10, y0, x0 + 200, 1700))]) if i["id"] == "layout:title_over_subject"]
    assert tall and tall[0]["severity"] == "minor"  # one face spanning the middle of the band


def test_gameplay_face_cache_is_keyed_by_the_video_content(monkeypatch, tmp_path):
    monkeypatch.setattr(_qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")
    seen = []
    monkeypatch.setattr(_qc, "measure_gameplay_faces", lambda path, seams, wins, work, **k: seen.append(work) or [])
    vid = tmp_path / "r.mp4"
    vid.write_bytes(b"a" * 10)
    _lint(_stack_plan([_title()]), video_path=str(vid))
    vid.write_bytes(b"b" * 25)  # a re-render under the same name
    _lint(_stack_plan([_title()]), video_path=str(vid))
    assert len(seen) == 2 and seen[0] != seen[1] and "game_" in seen[0].name
