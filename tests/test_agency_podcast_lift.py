"""Podcast crops: reframe.scale/y lift the face above the caption band (16:9 → 9:16)."""
import re

from noze.agency.media.captions import plan_captions, title_holds
from noze.agency.media.qc import layout_lint
from noze.agency.media.render import Renderer, RenderSpec, reframe_filters
from noze.agency.schemas import EDIT_PLAN, conform

W, H = 1080, 1920


def _crop(f):
    w, h, x, y = map(int, re.search(r"crop=(\d+):(\d+):(\d+):(\d+)", f if isinstance(f, str) else f[0]).groups())
    return w, h, x, y


def test_default_is_unchanged_full_height():
    assert reframe_filters("fixed", 0.25, 1920, 1080, W, H) == [
        "crop=608:1080:176:0", "scale=1080:1920:flags=lanczos"]


def test_scale_and_y_lift_the_face():
    # face centre at 40 % of the source height, chin at 57 %
    w, h, x, y = _crop(reframe_filters("fixed", 0.25, 1920, 1080, W, H, 1.25, 0.58))
    assert (w, h) == (486, 864) and abs(w / h - W / H) < 0.01
    out = lambda sy: (sy * 1080 - y) * H / h  # source fraction → output px  # noqa: E731
    assert out(0.40) < 620  # face centre clearly in the upper third (was 768 at full height)
    assert out(0.57) < 1000  # chin well above the 'lower' caption anchor (~1128)
    assert abs((x + w / 2) - 0.25 * 1920) < 2  # horizontal aim kept


def test_y_without_scale_has_no_room_and_is_clamped():
    assert _crop(reframe_filters("fixed", 0.5, 1920, 1080, W, H, 1.0, 0.9))[1:] == (1080, 656, 0)
    w, h, x, y = _crop(reframe_filters("fixed", 0.5, 1920, 1080, W, H, 9.0, 1.0))
    assert h == 720 and y == 1080 - 720  # scale capped at 1.5, crop stays inside the source


def test_render_graph_passes_scale_and_y_from_the_plan():
    seg = {"src_start": 0, "src_end": 5, "speed": 1.0, "zoom": {"type": "none", "scale": 1.0},
           "reframe": {"mode": "fixed", "x": 0.25, "scale": 1.25, "y": 0.58}}
    graph, _ = Renderer(RenderSpec()).segment_graph(seg, 1.0, 5.0, "cut", "cut", 1920, 1080, True)
    assert _crop(graph)[:2] == (486, 864) and _crop(graph)[3] > 0


def test_schema_keeps_the_new_fields():
    plan = conform({"segments": [{"src_start": 1, "src_end": 2,
                                  "reframe": {"mode": "fixed", "x": 0.3, "scale": 1.2, "y": 0.6}}]}, EDIT_PLAN)
    rf = plan["segments"][0]["reframe"]
    assert rf["scale"] == 1.2 and rf["y"] == 0.6


WORDS = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate("so this is what happened to me".split())]
CAPS = {"enabled": True, "style": "bold_pop", "words_per_caption": 2, "position": "lower"}


def test_chest_title_pauses_the_captions():
    ovs = [{"kind": "hook_title", "text": "HE SAID IT", "start": 0, "end": 1.2, "position": "lower"},
           {"kind": "hook_title", "text": "TOP ONE", "start": 2.0, "end": 2.6, "position": "top"}]
    assert title_holds(ovs) == [(0.0, 1.2)]
    held = plan_captions(WORDS, CAPS, "tiktok", W, H, 90, 3.0, None, 0, title_holds(ovs))
    free = plan_captions(WORDS, CAPS, "tiktok", W, H, 90, 3.0)
    assert free[0].start < 1.2 and all(ev.start >= 1.0 for ev in held) and len(held) < len(free)


def test_a_chunk_straddling_the_title_edge_never_overlaps_it():
    for end in (0.9, 1.0, 1.1, 1.3, 1.7, 2.6):  # title edges that fall mid-chunk, not only in a gap
        ovs = [{"kind": "hook_title", "text": "X", "start": 0.0, "end": end, "position": "lower"},
               {"kind": "punch_title", "text": "Y", "start": 2.0, "end": 2.4, "position": "bottom"}]
        for ev in plan_captions(WORDS, CAPS, "tiktok", W, H, 90, 3.0, None, 0, title_holds(ovs)):
            for a, b in title_holds(ovs):
                assert ev.end <= a + 1e-6 or ev.start >= b - 1e-6, (end, ev.start, ev.end, a, b)


def test_a_caption_is_not_stretched_across_a_title_in_a_short_pause():
    # a caption is normally held until the next one when the gap is < 0.3 s; a title in that pause cuts it short
    words = [{"word": "one", "start": 0.0, "end": 1.0}, {"word": "two", "start": 1.38, "end": 2.0}]
    ovs = [{"kind": "punch_title", "text": "X", "start": 1.13, "end": 1.37, "position": "lower"}]
    evs = plan_captions(words, {**CAPS, "words_per_caption": 1}, "tiktok", W, H, 90, 3.0, None, 0, title_holds(ovs))
    assert len(evs) == 2 and evs[0].end <= 1.13 + 1e-6


def _lint(seg_extra, overlays=()):
    plan = {"segments": [{"src_start": 0, "src_end": 3, "speed": 1.0, **seg_extra}],
            "captions": CAPS, "overlays": list(overlays)}
    return {i["check"] if "check" in i else i.get("id") for i in
            layout_lint(plan, {}, words=WORDS, width=W, height=H, platform="tiktok", src_size=(1920, 1080))}


def test_lint_measures_crop_magnification():
    lifted = {"reframe": {"mode": "fixed", "x": 0.3, "scale": 1.25, "y": 0.58}, "zoom": {"type": "none", "scale": 1}}
    blown = {"reframe": {"mode": "fixed", "x": 0.3, "scale": 1.5, "y": 0.6}, "zoom": {"type": "punch", "scale": 1.3}}
    assert not any("crop_upscale" in str(c) for c in _lint(lifted))
    assert any("crop_upscale" in str(c) for c in _lint(blown))
    # a low-res source magnified by the full-height crop alone is not the editor's to fix (no endless loop)
    plan = {"segments": [{"src_start": 0, "src_end": 3, "speed": 1.0, "zoom": {"type": "none", "scale": 1},
                          "reframe": {"mode": "fixed", "x": 0.3}}], "captions": CAPS, "overlays": []}
    low = layout_lint(plan, {}, words=WORDS, width=W, height=H, platform="tiktok", src_size=(640, 360))
    assert not any("crop_upscale" in str(i) for i in low)


def test_lint_sees_no_caption_title_overlap_when_captions_pause():
    seg = {"reframe": {"mode": "fixed", "x": 0.3, "scale": 1.25, "y": 0.58}, "zoom": {"type": "none", "scale": 1}}
    for end in (1.0, 1.2, 2.6):  # 1.0 used to leave a straddling chunk on the title (retest 4 Nov)
        title = [{"kind": "hook_title", "text": "HE SAID IT", "emphasis": "IT", "start": 0, "end": end,
                  "position": "lower"}]
        assert not any("overlap" in str(c) and "caption" in str(c) for c in _lint(seg, title)), end


def test_declutter_keeps_a_chest_title_and_chest_captions_on_lifted_shots():
    # live run 4 Nov: the editor's 'lower' titles were moved to 'upper' (= the eyes) by the house declutter rule
    from noze.agency.roles.editor import Editor

    seg = {"src_start": 0, "src_end": 10, "reframe": {"mode": "fixed", "x": 0.3, "scale": 1.25, "y": 0.58}}
    plan = {"segments": [seg], "captions": {"enabled": True, "position": "lower", "words_per_caption": 3},
            "overlays": [{"kind": "hook_title", "text": "A", "start": 0, "end": 2, "position": "lower"},
                         {"kind": "punch_title", "text": "B", "start": 5, "end": 6, "position": "bottom"},
                         {"kind": "label", "text": "@mark", "start": 0, "end": 10, "position": "bottom"}]}
    Editor._declutter(plan, 10.0)
    assert [o["position"] for o in plan["overlays"]] == ["lower", "bottom", "bottom"]
    assert plan["captions"]["position"] == "lower" and plan["captions"]["words_per_caption"] == 2
