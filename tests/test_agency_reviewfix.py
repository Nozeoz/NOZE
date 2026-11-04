"""Fixes from the review of the mandor package (3 Nov): measured faces are one real detection clipped to the
cam band, checks that would loop the editor are minor, replays never freeze or leave the source, the
disclosure clears the watermark pill, and the fix library only claims what it changed."""

from pathlib import Path

import pytest

from noze.agency.config import AgencySettings
from noze.agency.context import AgencyContext
from noze.agency.media import qc
from noze.agency.roles.editor import Editor
from noze.agency.schemas import EDIT_PLAN, conform
from noze.config import Settings

W, H = 1080, 1920


@pytest.fixture
def ax(tmp_path):
    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off", "NOZE_DATA_DIR": str(tmp_path)}
    a = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    yield a
    a.close()


def test_measured_face_is_one_real_detection_not_a_per_edge_median(monkeypatch, tmp_path):
    """Two detections of one head (494,305,243,243) and (544,344,126,126): the per-coordinate median of two
    samples is their max edges and spills below the seam; one detection never does."""
    for i in range(2):
        (tmp_path / f"cam_0_{i}.jpg").write_bytes(b"x")  # already extracted: no ffmpeg needed
    monkeypatch.setattr(qc.face_finder, "available", lambda: True)
    monkeypatch.setattr(qc.face_finder, "faces_in_band",
                        lambda frames: [(494, 305, 243, 243), (544, 344, 126, 126)])
    out = qc.measure_cam_faces("clip.mp4", [(0.0, 5.0, 576, {})], tmp_path, per_seg=2)
    box = out[0.0]["box"]
    assert box in ((494, 305, 243, 243), (544, 344, 126, 126)), box
    assert box[1] + box[3] <= 576


def _stack_plan(cam, captions_pos="upper"):
    return conform({"segments": [{"src_start": 0.0, "src_end": 10.0, "speed": 1.0,
                                  "reframe": {"mode": "stack", "x": 0.5, "cam": cam},
                                  "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut"}],
                    "captions": {"enabled": True, "style": "bold_pop", "words_per_caption": 1,
                                 "position": captions_pos, "font_scale": 1.0}, "overlays": []}, EDIT_PLAN)


def test_a_head_box_that_spills_past_the_chin_does_not_flag_the_seam_caption():
    from noze.agency.media.transcribe import spread_words

    cam = {"x": 0.0, "y": 0.0, "w": 0.215, "h": 0.215}
    words = spread_words("he went mid he actually went mid", 0.0, 5.0)
    dbg: dict = {}
    qc.layout_lint(_stack_plan(cam), {}, words=words, width=W, height=H, platform="tiktok", src_size=(1920, 1080),
                   debug=dbg)
    top = min(ly["box"][1] for ly in dbg["layers"] if ly["kind"] == "caption")  # where the seam caption starts

    def over_face(y, h):
        m = {0.0: {"box": (494, int(y), 243, int(h)), "hits": 5, "n": 5}}
        return "layout:over_face_caption" in {i["id"] for i in qc.layout_lint(
            _stack_plan(cam), {}, words=words, width=W, height=H, platform="tiktok", src_size=(1920, 1080),
            measured_faces=m)}
    # the live clip: the Haar box reaches 20 px past the caption's top, but only with the chin (last 15%)
    assert not over_face(top - 200, 220)
    # positive control: the face itself (its top 85%) runs into the caption
    assert over_face(top - 150, 200)


def test_face_small_is_silent_at_the_zoom_limit_and_minor_otherwise():
    tight = {"x": 0.0, "y": 0.0, "w": 0.215, "h": 0.215}  # 2.6x: already at the magnification limit
    loose = {"x": 0.0, "y": 0.0, "w": 0.35, "h": 0.35}
    small = {0.0: {"box": (500, 200, 120, 120), "hits": 5, "n": 5}}
    at_limit = qc.layout_lint(_stack_plan(tight), {}, words=[], width=W, height=H, platform="tiktok",
                              src_size=(1920, 1080), measured_faces=small)
    assert "layout:face_small" not in {i["id"] for i in at_limit}
    roomy = qc.layout_lint(_stack_plan(loose), {}, words=[], width=W, height=H, platform="tiktok",
                           src_size=(1920, 1080), measured_faces=small)
    hit = [i for i in roomy if i["id"] == "layout:face_small"]
    assert hit and hit[0]["severity"] == "minor"


def _prep(duration=60.0):
    return {"source_info": {"width": 1920, "height": 1080, "duration": duration}, "ranges": [(0.0, 10.0)],
            "moment_words": [], "words": [], "facecam": None, "facecam_face": None}


def test_band_src_outside_the_source_is_clamped_or_dropped(ax):
    plan = _stack_plan({"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35})
    plan["segments"][0]["band_src"] = {"start": 55.0, "end": 70.0, "speed": 0.75}
    out = Editor(ax).finalize(plan, {"start_s": 0.0, "end_s": 10.0}, {}, {}, _prep(60.0))
    assert out["segments"][0]["band_src"] == {"start": 55.0, "end": 60.0, "speed": 0.75}
    plan["segments"][0]["band_src"] = {"start": 80.0, "end": 90.0, "speed": 1.0}
    out = Editor(ax).finalize(plan, {"start_s": 0.0, "end_s": 10.0}, {}, {}, _prep(60.0))
    assert out["segments"][0]["band_src"] is None


def test_a_short_replay_slows_down_instead_of_freezing(ax):
    from noze.agency.media.render import Renderer, RenderSpec

    seg = {"src_start": 0.0, "src_end": 4.0, "speed": 1.0, "band_src": {"start": 10.0, "end": 11.0, "speed": 1.0},
           "reframe": {"mode": "stack", "x": 0.5, "cam": {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}},
           "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut"}
    r = Renderer(RenderSpec(width=W, height=H, fps=30))
    graph, _ = r.segment_graph(seg, 1.0, 4.0, "cut", "cut", 1920, 1080, True)
    assert "setpts=PTS/0.5000" in graph  # 1 s of replay covers 4 s at the 0.5x floor, then holds only the rest


def test_disclosure_moves_off_the_watermark_pill(ax):
    plan = conform({"segments": [], "overlays": []}, EDIT_PLAN)
    Editor(ax).enforce_compliance(plan, {"requirements": {"watermark": "twitch.tv/x", "disclosure": "#ad"}}, 20.0)
    disc = next(o for o in plan["overlays"] if o["text"] == "#ad")
    mark = next(o for o in plan["overlays"] if o["text"] == "twitch.tv/x")
    assert mark["position"] == "bottom" and disc["position"] == "lower"


def test_declutter_on_a_stack_returns_captions_to_the_seam_not_onto_the_titles():
    """Live run 3 Nov (#11 r2): the editor chose captions 'lower'; declutter moved them to 'center' — where the
    stacked hook and punch titles sit — and the reviewer read the editor's fix note as a lie."""
    from noze.agency.media.transcribe import spread_words

    plan = _stack_plan({"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}, captions_pos="lower")
    plan["captions"]["words_per_caption"] = 3
    plan["overlays"] = conform({"segments": [], "overlays": [
        {"kind": "label", "text": "twitch.tv/x", "start": 0.0, "end": 10.0, "position": "bottom", "align": "left",
         "box": True, "style": "fade"},
        {"kind": "hook_title", "text": "HIS UNBEATABLE DODGE STRAT", "emphasis": "DODGE STRAT", "start": 0.0,
         "end": 2.6, "position": "center", "style": "pop"}]}, EDIT_PLAN)["overlays"]
    Editor._declutter(plan, 10.0)
    assert plan["captions"]["position"] == "upper" and plan["captions"]["words_per_caption"] == 2
    assert any(f["issue_id"] == "house:declutter" for f in plan["fixes"])
    words = spread_words("oh you can't hit me with a ball bro", 0.0, 4.0)
    issues = qc.layout_lint(plan, {"requirements": {"watermark": "twitch.tv/x"}}, words=words, width=W, height=H,
                            platform="tiktok", src_size=(1920, 1080))
    assert not [i["id"] for i in issues if i["id"].startswith("layout:overlap_caption")]


def test_seam_captions_are_always_one_line_free_ones_may_take_two():
    """Live run 3 Nov: three re-cuts in a row lost a round to a two-line seam caption growing into the face."""
    from noze.agency.media.captions import plan_captions
    from noze.agency.media.transcribe import spread_words

    words = spread_words("he was bobbing around what am I saying always the left one bro", 0.0, 6.0)
    spec = {"enabled": True, "style": "bold_pop", "words_per_caption": 3, "position": "upper", "font_scale": 1.3}
    seam = plan_captions(words, spec, "tiktok", W, H, 90, 6.0, lambda t: 576)
    free = plan_captions(words, spec, "tiktok", W, H, 90, 6.0, None)
    assert max(len(e.lines) for e in seam) == 1
    assert max(len(e.lines) for e in free) == 2  # positive control: the same words do wrap off the seam
    assert " ".join(w for e in seam for ln in e.lines for w in ln) == " ".join(w["word"].upper() for w in words)


def test_the_fix_library_only_logs_changes_it_made(ax):
    plan = _stack_plan({"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35})
    issue = {"id": "layout:over_face_caption", "severity": "major", "description": "", "fix": ""}
    plan["captions"]["words_per_caption"] = 3
    out = Editor(ax).apply_fixes(plan, [issue], _prep(), {}, {})
    assert out["captions"]["words_per_caption"] == 2 and out["captions"]["position"] == "upper" and out["fixes"]
    # nothing movable: the watermark collides with a caption → no change, so no claim
    issue = {"id": "layout:overlap_caption_watermark", "severity": "major", "description": "", "fix": ""}
    plan["overlays"] = [{"kind": "label", "text": "twitch.tv/x", "start": 0.0, "end": 10.0, "position": "bottom",
                         "style": "fade", "align": "left", "box": True, "emphasis": ""}]
    out = Editor(ax).apply_fixes(plan, [issue], _prep(), {}, {"requirements": {"watermark": "twitch.tv/x"}})
    assert out["fixes"] == []
