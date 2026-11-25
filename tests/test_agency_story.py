"""Story mining: arcs from setup + payoff in different periods, honest quotes, per-part overlap, measured heat."""

from types import SimpleNamespace

from noze.agency.roles.analyst import (Analyst, build_moment, heuristic_arcs, peak_moments, sentences)
from noze.agency.roles.manager import Manager
from noze.agency.story import time_jump_label

MIN_S, MAX_S = 20.0, 40.0
PAYOFF = "Oh my god no way the car survived the jump!"


def make_words(extra: dict[int, str] | None = None, until: int = 3000):
    """A fake stream: a unique filler sentence every 6 s, plus the given sentences at their start second."""
    lines = {t: f"alpha{t} beta{t} gamma{t} delta{t} eps{t} zeta{t} eta{t} theta{t} iota{t} kappa{t}."
             for t in range(0, until, 6)}
    lines.update(extra or {})
    words = []
    for t, text in sorted(lines.items()):
        for k, w in enumerate(text.split()):
            words.append({"word": w, "start": t + 0.4 * k, "end": t + 0.4 * k + 0.35})
    return words


STORY = {100: "I bet you this car will never survive that jump.", 106: "Watch the car fly off the ramp right now.",
         2600: PAYOFF}


def make_sig(hot=(2598, 2620), music=None, until=3000):
    bins = []
    for t in range(0, until, 2):
        is_hot = hot and hot[0] <= t < hot[1]
        is_music = music and music[0] <= t < music[1]
        bins.append({"t": float(t), "heat": 9.0 if is_hot else 1.0, "loud": 0.5, "laugh": 0.7 if is_hot else 0.0,
                     "cheer": 0.0, "scream": 0.0, "music": 0.9 if is_music else None, "chat": 0.8 if is_hot else 0.1,
                     "chat_n": 45 if is_hot else 2, "chat_tags": {"funny": 0.5, "hype": 0.4, "shock": 0.0, "sad": 0.0},
                     "replay": None})
    peaks = [{"start_s": hot[0], "end_s": hot[1], "heat": 9.0, "tags": ["funny"], "evidence": "chat×45 KEKW"}] if hot else []
    return {"version": 1, "duration": float(until), "bin_s": 2.0, "bins": bins, "peaks": peaks, "clips": [],
            "sources": [], "notes": []}


def test_heuristic_arc_from_setup_and_payoff():
    words = make_words(STORY)
    arcs = heuristic_arcs(sentences(words), None, 3, MIN_S, MAX_S)  # no signals: emotion words carry the payoff
    assert arcs and arcs[0]["structure"] == "arc"
    setup, pay = arcs[0]["parts"]
    assert setup["role"] == "setup" and pay["role"] == "payoff" and setup["start_s"] < 120 < 2500 < pay["start_s"]
    m = build_moment(arcs[0], words, None, MIN_S, MAX_S)
    assert m and m["structure"] == "arc" and len(m["parts"]) == 2 and m["rationale"]
    assert m["parts"][0]["label"] == "" and m["parts"][1]["label"] == time_jump_label(m["parts"][0], m["parts"][1])
    assert m["parts"][1]["label"].endswith("MIN LATER")
    assert m["start_s"] == m["parts"][0]["start_s"] and m["end_s"] == m["parts"][1]["end_s"]


def test_cold_open_rewind_label_and_model_label_overwritten():
    words = make_words(STORY)
    raw = {"start_s": 100, "end_s": 2625, "structure": "cold_open", "keywords": ["jump"],
           "parts": [{"start_s": 2600, "end_s": 2612, "role": "cold_open", "label": "5 SECONDS LATER"},
                     {"start_s": 100, "end_s": 112, "role": "setup", "label": ""},
                     {"start_s": 2612, "end_s": 2625, "role": "payoff", "label": ""}],
           "scores": {"hook": 7, "flow": 6, "value": 5, "trend": 5, "emotion": 8}}
    m = build_moment(raw, words, None, MIN_S, MAX_S)
    assert m and m["structure"] == "cold_open"
    labels = [p["label"] for p in m["parts"]]
    assert labels[0] == "" and labels[1].endswith("MIN EARLIER") and labels[2].endswith("MIN LATER")


def test_unrelated_setup_is_dropped():
    words = make_words({100: "I bet you this banana will never melt.", 2600: "Oh my god the helicopter exploded!"})
    raw = {"start_s": 100, "end_s": 2625, "structure": "arc",
           "parts": [{"start_s": 100, "end_s": 112, "role": "setup", "label": ""},
                     {"start_s": 2600, "end_s": 2625, "role": "payoff", "label": ""}], "scores": {}}
    assert build_moment(raw, words, None, MIN_S, MAX_S) is None


def test_fake_quote_dropped_real_quote_kept():
    words = make_words(STORY)
    base = {"start_s": 2590, "end_s": 2625, "structure": "linear", "scores": {"hook": 6, "flow": 6}}
    real = build_moment({**base, "hook_line": PAYOFF}, words, None, MIN_S, MAX_S)
    fake = build_moment({**base, "hook_line": "completely invented sentence about dragons and lava"},
                        words, None, MIN_S, MAX_S)
    assert real is not None and real["parts"][0]["role"] == "build"  # positive control: a true quote survives
    assert fake is None


def test_select_moments_checks_overlap_per_part():
    def mk(parts, overall):
        ps = [{"start_s": a, "end_s": b, "role": "build", "label": ""} for a, b in parts]
        return {"start_s": min(a for a, _ in parts), "end_s": max(b for _, b in parts), "parts": ps,
                "structure": "arc", "emotion": "funny", "overall": overall}
    a = mk([(100, 120), (2000, 2020)], 8.0)
    b = mk([(110, 130), (3000, 3020)], 7.5)  # shares 10 s with a's first part
    c = mk([(500, 520), (1500, 1520)], 7.0)  # envelope sits INSIDE a's, but no part touches
    picked = Manager.select_moments(None, [a, b, c], 3, 30.0, 60.0)
    assert [p["overall"] for p in picked] == [8.0, 7.0]


def test_select_moments_prefers_variety():
    def lin(t, o):
        return {"start_s": t, "end_s": t + 30, "structure": "linear", "emotion": "hype", "overall": o}
    arc = {"start_s": 5000, "end_s": 9000, "structure": "arc", "emotion": "funny", "overall": 6.0,
           "parts": [{"start_s": 5000, "end_s": 5015, "role": "setup"}, {"start_s": 9000, "end_s": 9020, "role": "payoff"}]}
    picked = Manager.select_moments(None, [lin(0, 7.0), lin(100, 6.9), lin(200, 6.8), arc], 2, 30.0, 60.0)
    assert {p["structure"] for p in picked} == {"linear", "arc"}


def test_heat_bonus_reorders_and_music_penalised_and_none_works():
    words = make_words(STORY)
    sc = {"hook": 6, "flow": 6, "value": 5, "trend": 5, "emotion": 5}
    cold = {"start_s": 1000, "end_s": 1035, "scores": dict(sc)}
    hot = {"start_s": 2590, "end_s": 2625, "scores": dict(sc)}
    plain = [build_moment(m, words, None, MIN_S, MAX_S) for m in (cold, hot)]
    assert plain[0] and plain[1] and plain[0]["overall"] == plain[1]["overall"]  # no signals: tie, no crash
    sig = make_sig()
    c, h = (build_moment(m, words, sig, MIN_S, MAX_S) for m in (cold, hot))
    assert h["overall"] > c["overall"] and h["emotion"] == "funny" and h["signals"]
    songy = build_moment(cold, words, make_sig(hot=None, music=(990, 1050)), MIN_S, MAX_S)
    assert songy["overall"] < plain[0]["overall"] and "Content ID" in songy["rationale"]


def test_analyst_moments_without_llm_has_arc_candidates_and_rationales():
    words = make_words(STORY)
    tr = {"language": "en", "segments": [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]}
                                         for w in words]}
    a = Analyst.__new__(Analyst)
    a.ax = SimpleNamespace(llm=SimpleNamespace(available=False))
    for sig in (None, make_sig()):
        got = a.moments({}, tr, {}, {}, {}, 3, MIN_S, MAX_S, signals=sig)
        assert len(got) >= 8 and all(m["rationale"] and m["parts"] for m in got)
        assert any(m["structure"] == "arc" for m in got)
    assert peak_moments(make_sig(), 2, MIN_S, MAX_S)[0]["scores"]["emotion"] == 9.0


def test_all_llm_candidates_rejected_falls_back_to_heuristics_and_logs_reasons():
    words = make_words(STORY)
    tr = {"language": "en", "segments": [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]}
                                         for w in words]}
    a = Analyst.__new__(Analyst)
    a.ax = SimpleNamespace(llm=SimpleNamespace(available=True))
    fake = {"start_s": 2590, "end_s": 2625, "title": "invented", "hook_line": "dragons invented nothing said here",
            "scores": {}}
    a._llm_story = lambda *args, **kw: [fake]
    got = a.moments({}, tr, {}, {}, {}, 3, MIN_S, MAX_S)
    assert got and any(m["structure"] == "arc" for m in got)  # heuristics topped up the empty result
    assert a.last_rejected[0]["title"] == "invented" and a.last_rejected[0]["reason"] == "quote_not_in_transcript"


def test_heuristic_arcs_scales_to_a_six_hour_stream():
    import time
    until = 21600
    extra = {}
    for k in range(600):  # 600 setups in the first half, each paid off in the second half
        extra[6 * (1 + 3 * k)] = f"I bet topic{k} will never happen."
        extra[6 * (1900 + 2 * k)] = f"Oh my god no way topic{k} happened!"
    words = make_words(extra, until=until)
    sig = make_sig(until=until)
    t0 = time.time()
    arcs = heuristic_arcs(sentences(words), sig, 10, MIN_S, MAX_S)
    assert time.time() - t0 < 30 and len(arcs) == 10 and arcs[0]["structure"] == "arc"


def test_top_up_counts_distinct_moments_after_dedupe():
    """Round-2 review: 3 valid LLM picks of the SAME stretch dedupe to 1 — the heuristics must still top up to n."""
    words = make_words(STORY)
    tr = {"language": "en", "segments": [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]}
                                         for w in words]}
    a = Analyst.__new__(Analyst)
    a.ax = SimpleNamespace(llm=SimpleNamespace(available=True))
    base = Analyst.__new__(Analyst)
    base.ax = SimpleNamespace(llm=SimpleNamespace(available=False))
    one = base.moments({}, tr, {}, {}, {}, 3, MIN_S, MAX_S)[0]  # a moment the builder accepts
    a._llm_story = lambda *args, **kw: [dict(one), dict(one), dict(one)]
    got = a.moments({}, tr, {}, {}, {}, 3, MIN_S, MAX_S)
    assert len(got) >= 3  # control: without the post-dedupe top-up this was 1
    assert any(r["reason"] == "overlaps_better_moment" for r in a.last_rejected)


# -- cross-period scan (long streams, story pack) -------------------------------------------------------------------
from noze.agency.roles.analyst import fetch_plan, sexual_hits  # noqa: E402


def _tr(words):
    return {"language": "en", "segments": [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]}
                                           for w in words]}


def _analyst(llm=False):
    a = Analyst.__new__(Analyst)
    a.ax = SimpleNamespace(llm=SimpleNamespace(available=llm))
    return a


LONG = {1200: "I bet you this car will never survive that jump.", 1206: "Watch the car fly off the ramp right now.",
        7800: PAYOFF}


def test_scan_arcs_finds_promise_at_0_20_paid_off_at_2_10_and_plans_fetch():
    words = make_words(LONG, until=10800)  # 3 h stream
    res = _analyst().scan_arcs({}, _tr(words), None, {}, 3, MIN_S, MAX_S, gap_min_s=600)
    top = res[0]
    assert top["structure"] == "arc" and top["arc_gap_s"] >= 600 and "cross-period arc" in top["rationale"]
    assert top["parts"][0]["start_s"] < 1300 < 7700 < top["parts"][1]["start_s"]
    assert top["parts"][1]["label"].endswith("HOURS LATER") and top["parts"][0]["label"] == ""
    rng = res.ranges_to_fetch
    assert rng == fetch_plan(list(res)) and len(rng) <= 2 * len(res)
    assert any(a <= 1200 <= b for a, b in rng) and any(a <= 7800 <= b for a, b in rng)
    assert sum(b - a for a, b in rng) < 0.1 * 10800  # nowhere near the whole stream


def test_scan_arcs_gap_filter_is_a_control_short_gap_gets_no_bonus():
    words = make_words({100: "I bet you this car will never survive that jump.", 106: "Watch the car fly off the ramp.",
                        400: PAYOFF}, until=3000)
    res = _analyst().scan_arcs({}, _tr(words), None, {}, 3, MIN_S, MAX_S, gap_min_s=600)
    arcs = [m for m in res if m["structure"] == "arc"]
    assert all(m["arc_gap_s"] < 600 and "cross-period" not in m["rationale"] for m in arcs)


def test_fetch_plan_pads_merges_and_clamps():
    ms = [{"parts": [{"start_s": 100, "end_s": 110}, {"start_s": 120, "end_s": 130}]},  # 10 s apart: merge
          {"start_s": 500, "end_s": 510},                                              # single range moment
          {"parts": [{"start_s": 3, "end_s": 6}]},                                    # clamp at 0
          {"parts": [{"start_s": 540, "end_s": 550}]}]                                # 14 s gap after pad: merge
    assert fetch_plan(ms) == [(0.0, 14.0), (92.0, 138.0), (492.0, 558.0)]
    assert fetch_plan(ms, pad=8, merge_gap=5) == [(0.0, 14.0), (92.0, 138.0), (492.0, 518.0), (532.0, 558.0)]
    assert fetch_plan([]) == []


def test_sexual_scene_penalised_control_unchanged():
    base = {"start_s": 2590, "end_s": 2625, "structure": "linear", "scores": {"hook": 6, "flow": 6}}
    clean = build_moment(base, make_words({2600: "Oh my god no way the parking lot is crazy!"}), None, MIN_S, MAX_S)
    dirty = build_moment(base, make_words({2600: "Oh my god no way the strip club is crazy!"}), None, MIN_S, MAX_S)
    assert clean and dirty and "adult" not in clean and dirty["adult"]
    assert round(clean["overall"] - dirty["overall"], 2) == 3.0 and "penalty -3" in dirty["rationale"]
    assert sexual_hits("lap dance and a freaky nudes pic") == ["freaky", "lap dance", "nudes"]
    assert sexual_hits("Essex essentially sextant") == []
    other = {**clean, "start_s": 9000, "end_s": 9030, "parts": [{"start_s": 9000, "end_s": 9030, "role": "", "label": ""}]}
    kept = _analyst()
    kept.last_rejected = []
    assert kept._dedupe([dirty, other])[0] is other  # equal otherwise: the clean one ranks first
    assert [m["overall"] for m in kept._dedupe([dirty, other])] == sorted([dirty["overall"], other["overall"]], reverse=True)


def test_vod_map_rides_on_moment_and_labels_use_stream_time():
    vm = [{"file_start": 0, "file_end": 200, "vod_start": 1000}, {"file_start": 200, "file_end": 400, "vod_start": 20000}]
    words = make_words({100: "I bet you this car will never survive that jump.", 106: "Watch the car fly off the ramp.",
                        300: PAYOFF}, until=400)
    raw = {"start_s": 100, "end_s": 325, "structure": "arc", "keywords": ["jump"],
           "parts": [{"start_s": 100, "end_s": 112, "role": "setup", "label": ""},
                     {"start_s": 300, "end_s": 325, "role": "payoff", "label": ""}], "scores": {}}
    m = build_moment(raw, words, None, MIN_S, MAX_S, vod_map=vm)
    assert m["vod_map"] == vm and m["parts"][1]["label"] == time_jump_label(m["parts"][0], m["parts"][1], vm)
    assert m["parts"][1]["label"].endswith("HOURS LATER")  # stream gap ~5 h
    plain = build_moment(raw, words, None, MIN_S, MAX_S)  # control: file time says 3 minutes
    assert plain["vod_map"] is None and plain["parts"][1]["label"].endswith("MIN LATER")
    a = _analyst()
    got = a.moments({}, _tr(words), {"vod_map": vm}, {}, {}, 3, MIN_S, MAX_S)  # moments() forwards facts
    assert got and all(x["vod_map"] == vm for x in got)
    assert any(x["parts"][-1]["label"].endswith("HOURS LATER") for x in got if len(x["parts"]) > 1)


def test_scan_arcs_llm_budget_for_six_hours_and_prompt_rules():
    words = make_words({}, until=21600)
    for w in words:  # fatten to ~500k chars like a real 6 h transcript
        w["word"] = w["word"] + "xxxx"
    a = _analyst(llm=True)
    calls = []
    a.campaign_of = lambda job: None

    def ask(job, task, schema, **kw):
        calls.append(task)
        return {"beats": []} if task.startswith("Index") else {"moments": []}
    a.ask = ask
    res = a.scan_arcs({}, _tr(words), None, {}, 3, MIN_S, MAX_S, gap_min_s=600)
    print('LLM calls for 6 h:', len(calls))
    assert 3 <= len(calls) <= 15, len(calls)
    assert all("sexual" in c.lower() for c in calls) and "10 minutes apart" in calls[-1]
    assert isinstance(res.ranges_to_fetch, list)


# --- referensi clipper 24 Nov: rarity x intensity, durasi, judul, spoiler ---------------------------------------
from noze.agency.roles.analyst import _overall, duration_adjust, short_title, spoiler_policy  # noqa: E402

ALLOW = {"creator": "Kai Cenat", "requirements": {"other": ["Spoilers allowed for this campaign"]}}
BAN = {"creator": "Kai Cenat", "requirements": {"other": ["No spoilers!"]}}
SCORES = {"hook": 6, "flow": 6, "value": 5, "trend": 4, "emotion": 6}


def _lin(text, scores=None, dur=26, at=2600, brief=ALLOW, sig=None, **kw):
    raw = {"start_s": at - 2, "end_s": at + dur, "structure": "linear", "scores": dict(scores or SCORES),
           "title": "Kai Cenat moment", **kw}
    return build_moment(raw, make_words({at: text}, until=3000), sig, MIN_S, MAX_S, brief=brief)


def test_rare_intense_beats_funny_and_control_flips():
    funny_scores = {"hook": 7, "flow": 6, "value": 5, "trend": 4, "emotion": 6}  # raw LLM scores: funny leads
    cry = _lin("Kai cries at the ending and cannot speak.", SCORES)
    funny = _lin("Ha that funny club moment was so funny.", funny_scores)
    assert cry and funny and cry["overall"] > funny["overall"]
    assert _overall({"scores": funny_scores}) > _overall({"scores": SCORES})  # control: raw order, no boost
    neutral = _lin("Kai talks about the weather and lunch today.", SCORES)  # same scores, no keywords -> no boost
    assert neutral["scores"]["emotion"] == 6 and cry["scores"]["emotion"] > 6 and cry["scores"]["trend"] > 4
    assert neutral["overall"] < cry["overall"]


def test_signal_raises_emotion_only_with_measured_heat():
    text = "Kai screams and cries."
    hot = _lin(text, sig=make_sig())
    cold = _lin(text)
    assert hot["scores"]["emotion"] > cold["scores"]["emotion"] > 6


def test_duration_bonus_and_penalty():
    one = lambda a, b: [{"start_s": a, "end_s": b}]  # noqa: E731
    assert duration_adjust(one(0, 25)) > 0
    assert duration_adjust(one(0, 34)) == 0.0
    assert duration_adjust(one(0, 60)) < duration_adjust(one(0, 38)) < 0
    arc = [{"start_s": 0, "end_s": 20}, {"start_s": 900, "end_s": 925}]  # 45 s across periods: no penalty
    assert duration_adjust(arc) == 0.0 and duration_adjust(arc + one(2000, 2020)) < 0
    short = _lin("Oh my god no way the car survived!", dur=25)
    long_ = _lin("Oh my god no way the car survived!", dur=60)
    assert short and long_ and short["overall"] > long_["overall"]


def test_titles_are_short_and_not_generic():
    t = short_title("Kai Cenat", "cries at the ending of the whole game and cannot stop sobbing")
    assert len(t) <= 45 and t.startswith("Kai Cenat:")
    m = _lin("Kai cries at the ending and cannot speak.", title="Uh oh", hook_line="Kai cries at the ending")
    assert m["title"] == "Kai Cenat: Kai cries at the ending"
    long = _lin("Oh my god no way the car survived!", title="Kai " + "word " * 20)
    assert len(long["title"]) <= 45
    words = make_words(STORY)
    auto = heuristic_arcs(sentences(words), None, 3, MIN_S, MAX_S)[0]
    built = build_moment(auto, words, None, MIN_S, MAX_S, brief=ALLOW)
    assert built and len(built["title"]) <= 45 and built["title"].startswith("Kai Cenat")


def _lin_why(text, brief, why):
    raw = {"start_s": 2598, "end_s": 2626, "structure": "linear", "scores": dict(SCORES), "title": "x"}
    return build_moment(raw, make_words({2600: text}), None, MIN_S, MAX_S, why, brief=brief)


def test_spoiler_flag_penalty_allowed_and_banned_is_rejected():
    txt = "Kai cries at the ending and cannot speak."
    plain = _lin("Kai cries at the market and cannot speak.")
    unknown, allowed = _lin(txt, brief=None), _lin(txt)
    why: list[str] = []
    assert _lin_why(txt, BAN, why) is None and why == ["spoiler_banned_by_brief"]
    assert "spoiler" not in plain and unknown["spoiler"] and allowed["spoiler"]
    assert round(allowed["overall"] - unknown["overall"], 2) == 2.0
    assert "penalty -2" in unknown["rationale"] and "penalty -0" in allowed["rationale"]
    a = _analyst()  # the Analyst path records it in last_rejected
    a.last_rejected = []
    words = make_words({2600: txt})
    raw = {"start_s": 2598, "end_s": 2624, "structure": "linear", "scores": dict(SCORES), "title": "x"}
    assert a._build([raw], words, None, MIN_S, MAX_S, None, BAN) == []
    assert a.last_rejected[0]["reason"] == "spoiler_banned_by_brief"
    assert len(a._build([raw], words, None, MIN_S, MAX_S, None, ALLOW)) == 1
    assert spoiler_policy({"style": {"notes": "no spoilers"}}) == "banned"
    assert spoiler_policy({"requirements": {"other": ["spoilers not allowed"]}}) == "banned"
    assert spoiler_policy({"requirements": {"other": ["spoilers ok"]}}) == "allowed"
    assert spoiler_policy({"requirements": {"other": ["no spoilers allowed"]}}) == "banned"
    assert spoiler_policy({}) == "unknown"


def test_spoiler_only_for_story_character_death():
    assert "spoiler" not in _lin("Bro I died again in the car, I died so many times!", brief=None)
    for t in ("Jason dies in the final scene.", "Lucia is killed right here.", "The main character dies.",
              "the funeral scene wrecked me"):
        assert _lin(t, brief=None).get("spoiler"), t
    assert _lin("I died again lol", brief=None)["scores"]["trend"] == SCORES["trend"]  # no rarity boost either
    assert _lin("Jason dies here", brief=None)["scores"]["trend"] > SCORES["trend"]


def test_seam_split_siblings_do_not_fake_a_link():
    vm = [{"file_start": 0, "file_end": 200, "vod_start": 1000}, {"file_start": 200, "file_end": 400, "vod_start": 20000}]
    words = make_words({100: "I bet you this banana will never melt.", 190: "Oh my god the helicopter exploded!",
                        204: "Everybody saw it exploded again!"}, until=400)
    raw = {"start_s": 100, "end_s": 215, "structure": "arc", "keywords": ["exploded"],
           "parts": [{"start_s": 100, "end_s": 112, "role": "setup", "label": ""},
                     {"start_s": 190, "end_s": 215, "role": "payoff", "label": ""}], "scores": {}}
    why: list[str] = []
    assert build_moment(raw, words, None, MIN_S, MAX_S, why, vod_map=vm) is None and why == ["setup_payoff_not_linked"]
    words2 = make_words({100: "I bet you this helicopter will never explode.", 190: "Oh my god the helicopter exploded!"},
                        until=400)
    m = build_moment({**raw, "keywords": []}, words2, None, MIN_S, MAX_S, vod_map=vm)
    assert m and len(m["parts"]) == 3 and m["structure"] == "arc"  # split payoff = still one role, still linked
