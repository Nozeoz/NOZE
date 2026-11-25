"""Story pack path (review CP2): VOD<->file time, --moments loading, scan-picked moments used as-is."""

import json
from types import SimpleNamespace

import pytest

from noze.agency.media.captions import join_hyphenated
from noze.agency.pipeline import Agency
from noze.agency.story import to_file, to_vod

VM = [{"file_start": 0.0, "file_end": 40.0, "vod_start": 1000.0},
      {"file_start": 40.0, "file_end": 80.0, "vod_start": 4000.0}]


def test_to_file_inverts_to_vod_and_rejects_outside_the_pack():
    for t in (5.0, 39.0, 41.0, 79.0):
        assert to_file(to_vod(t, VM), VM) == pytest.approx(t)
    assert to_file(2500.0, VM) is None  # between the pieces: not in the pack
    assert to_file(123.0, None) == 123.0  # no map: file time is stream time


def test_load_moments_accepts_scan_files_and_refuses_unknown_shapes(tmp_path):
    from noze.agency.cli import _load_moments

    good = tmp_path / "pack.moments.json"
    good.write_text(json.dumps({"picks": [{"start_s": 1, "end_s": 2}]}), encoding="utf-8")
    assert _load_moments(str(good)) == [{"start_s": 1, "end_s": 2}]
    bad = tmp_path / "x.json"
    bad.write_text(json.dumps({"something": 1}), encoding="utf-8")
    with pytest.raises(SystemExit):
        _load_moments(str(bad))
    assert _load_moments(None) is None


def _words(spans):
    out = []
    for start, text in spans:
        t = start
        for w in text.split():
            out.append({"word": w, "start": t, "end": t + 0.35})
            t += 0.4
    return out


def _fake_agency():
    logs = []
    fake = SimpleNamespace(store=SimpleNamespace(log=lambda *a, **k: logs.append(a)), _signals=lambda job: None)
    return fake, logs


def test_scan_moments_map_to_the_pack_keep_the_scan_score_and_put_arcs_first():
    setup = "I need a necklace and new clothes for Lucia tonight so she is impressed by me."
    payoff = "I do not even know what to wear for Lucia now man this is terrible honestly."
    filler = "We drive around the city and look at the cars for a while right now okay."
    words = _words([(2.0, setup), (12.0, filler), (44.0, payoff), (56.0, filler)])
    tr = {"language": "en", "segments": [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]}
                                         for w in words]}
    arc = {"start_s": 1002.0, "end_s": 4020.0, "structure": "arc", "emotion": "funny", "overall": 9.0,
           "title": "Kai can't pick a fit for Lucia", "hook_line": "I need a necklace and new clothes for Lucia",
           "story": "errands for Lucia, then outfit panic", "keywords": ["Lucia"],
           "parts": [{"start_s": 1002.0, "end_s": 1009.0, "role": "setup"},
                     {"start_s": 4004.0, "end_s": 4012.0, "role": "payoff"}],
           "scores": {"hook": 8, "flow": 7, "value": 5, "trend": 7, "emotion": 8, "story": 9}}
    linear = {"start_s": 1012.0, "end_s": 1020.0, "structure": "linear", "emotion": "hype", "overall": 9.9,
              "title": "drive", "hook_line": "We drive around the city",
              "scores": {"hook": 9, "flow": 9, "value": 9, "trend": 9, "emotion": 9, "story": 5}}
    outside = {**linear, "title": "elsewhere", "start_s": 2500.0, "end_s": 2510.0}
    fake, logs = _fake_agency()
    job = {"id": 1, "input": {"moments": [linear, arc, outside]}}
    got = Agency._scan_moments(fake, job, tr, {"vod_map": VM}, {}, 5.0, 60.0)
    assert [m["title"] for m in got] == ["Kai can't pick a fit for Lucia", "drive"]  # the arc leads, despite the score
    a = got[0]
    assert a["overall"] == 9.0 and a["from_scan"]  # the scan's own score stands (no double boost)
    assert [round(p["start_s"]) for p in a["parts"]] == [2, 44]  # mapped onto the pack file
    assert a["parts"][1]["label"].endswith("LATER")  # labelled in stream time (~50 min), not the 32 s file gap
    assert any("dropped" in str(l) and "elsewhere" in str(l) for l in logs)  # outside the pack: dropped WITH a reason


def test_scan_moments_without_a_vod_map_use_the_plain_offset():
    words = _words([(3.0, "This is the craziest thing I have ever seen in this game for real.")])
    tr = {"language": "en", "segments": [{"start": w["start"], "end": w["end"], "text": w["word"], "words": [w]}
                                         for w in words]}
    m = {"start_s": 503.0, "end_s": 509.5, "structure": "linear", "title": "crazy", "overall": 7.0,
         "hook_line": "This is the craziest thing", "scores": {"hook": 7, "flow": 7, "value": 5, "trend": 5,
                                                               "emotion": 7, "story": 5}}
    fake, _ = _fake_agency()
    got = Agency._scan_moments(fake, {"id": 2, "input": {"moments": [m], "offset_s": 500.0}}, tr,
                               {"probe": {"duration": 60}}, {}, 3.0, 60.0)
    assert got and round(got[0]["parts"][0]["start_s"]) == 3


def test_join_hyphenated_keeps_compound_words_on_one_page():
    w = [{"word": "AI", "start": 0, "end": 0.3}, {"word": "-inspired", "start": 0.3, "end": 0.8},
         {"word": "services", "start": 0.8, "end": 1.2}]
    assert [x["word"] for x in join_hyphenated(w)] == ["AI-inspired", "services"]
    assert [x["word"] for x in join_hyphenated([{"word": "a", "start": 0, "end": 1}])] == ["a"]  # control
