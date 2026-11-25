"""Render v2 (design-supervisor fixes): the mixed-scale accented hook/punch title, the left-aligned pill
watermark, and ``band_src`` (the gameplay band replays another source range). Every feature has a case that
goes red when the feature is removed. The ASS/geometry/graph tests need no ffmpeg; the last two render for real
at 360x640@15."""

import re
import shutil

import pytest

from noze.agency.media.captions import (AssDoc, Meter, box_pad, build_overlays, caption_styles, overlay_styles,
                                        plan_overlays, text_box)
from noze.agency.media.ffmpeg import probe, run
from noze.agency.media.render import Renderer, RenderSpec, band_src_range
from noze.agency.schemas import EDIT_PLAN, SEGMENT, conform

W, H = 1080, 1920
YELLOW, WHITE = "&H00E6FF&", "&HFFFFFF&"  # #FFE600 / white as ASS override colours (BGR)
SRC = (640, 360)
CAM = {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}


def make_doc(w=W, h=H):
    doc = AssDoc(w, h)
    caption_styles(doc, "Anton", {})
    overlay_styles(doc, "Anton", "Anton")
    return doc


def ov(kind, text, start=0.0, end=2.5, **kw):
    return {"kind": kind, "text": text, "start": start, "end": end, "style": "pop", **kw}


def dialogue(doc, style):
    return next(t for _, _, _, s, t in doc.events if s == style)


def fs_of(text):
    """[(font px, text)] of each \\N-separated line of an ASS body."""
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"\\fs(\d+)[^}]*\}([^\\{]*)", text)]


# -- (MF-1) two-tier accented hook title ------------------------------------------------------------
def test_hook_title_is_two_tier_accented_tilted_with_a_shadow_not_a_box():
    doc = make_doc()
    assert build_overlays(doc, [ov("hook_title", "Why this clip is INSANE", emphasis="INSANE")], "tiktok", 10) == 1
    body = dialogue(doc, "Title")
    small, key = fs_of(body)
    assert small[0] >= 60 and key[0] >= 150 and key[1] == "INSANE" and small[1] == "Why this clip is"
    assert key[0] * 0.571 >= 105  # Anton cap ratio 0.571 of the font px: the key word's cap is ≥ 105 px
    block = dialogue(doc, "TitleBlock")  # CP1: the accent is a solid block behind the key word, dark ink on top
    assert f"\\fs{key[0]}\\1c&H141414&" in body and f"\\fs{small[0]}\\1c{WHITE}" in body
    assert block.count(f"\\3c{YELLOW}") == 1 and f"\\fs{key[0]}" in block  # accent only on the key word's block
    assert "\\frz-4" in body and "\\shad" in body and "\\4c" in body
    assert doc.styles["Title"].border_style == 1 and box_pad(doc.styles["Title"]) == 0  # the text itself has no box
    assert doc.styles["TitleBlock"].border_style == 3
    assert doc.styles["Title"].font == "Anton"


def test_title_accent_follows_the_caption_highlight_colour():
    doc = make_doc()
    build_overlays(doc, [ov("hook_title", "ONE WORD")], "tiktok", 10, accent="#FF3B3B")
    assert "\\3c&H3B3BFF&" in dialogue(doc, "TitleBlock")  # #FF3B3B → BGR, on the block behind the key word


def test_hook_title_without_emphasis_makes_the_last_word_the_emphasis():
    doc = make_doc()
    (ev,) = plan_overlays(doc, [ov("hook_title", "THE ONE MONEY RULE")], "tiktok", 10)
    assert [" ".join(ln) for ln in ev.lines] == ["THE ONE MONEY", "RULE"]
    assert ev.sizes[0] >= 60 and ev.sizes[1] >= 150 and len(ev.sizes) == len(ev.lines)
    (solo,) = plan_overlays(doc, [ov("hook_title", "WOW")], "tiktok", 10)
    assert solo.lines == [["WOW"]] and solo.sizes[0] >= 150  # emphasis alone when it is the whole text


def test_punch_title_example_left_one_vs_right_one():
    doc = make_doc()
    (ev,) = plan_overlays(doc, [ov("punch_title", "LEFT ONE > right one", 5, 7, emphasis="LEFT ONE",
                                   position="center")], "tiktok", 12)
    assert ev.kind == "punch_title" and ev.style == "Title"
    assert [" ".join(ln) for ln in ev.lines] == ["LEFT ONE", "> right one"]  # reading order: big first, small after
    assert ev.sizes[0] >= 180 and ev.sizes[1] >= 64
    build_overlays(doc, [ov("punch_title", "LEFT ONE > right one", 5, 7, emphasis="LEFT ONE")], "tiktok", 12)
    body = dialogue(doc, "Title")  # a punch title is a stamp (red, -8°), not the hook's yellow block
    assert "\\frz-8" in body and "&H2B2BE8&" in body and not any(e[3] == "TitleBlock" for e in doc.events)


def test_long_emphasis_shrinks_but_never_below_the_floor():
    doc = make_doc()
    (ev,) = plan_overlays(doc, [ov("hook_title", "Honestly UNBELIEVABLEFOOTAGEFROMTHEMATCH", emphasis="UNBELIEVABLEFOOTAGEFROMTHEMATCH")],
                          "tiktok", 10)
    assert 150 <= max(ev.sizes) < 201


def test_title_keeps_clear_of_the_seam_caption():
    doc = make_doc()
    (ev,) = plan_overlays(doc, [ov("hook_title", "SEAM TEST HERE", position="top")], "tiktok", 10,
                          seam_at=lambda t: 709, cap_size=96, cap_pad=0)
    x0, y0, x1, y1 = text_box([" ".join(ln) for ln in ev.lines], ev.sizes, ev.x, ev.y, ev.an, 0, Meter(None, "X"))
    assert y0 >= 709 + 0.6 * 96  # pushed under the caption strip: the seam logic still runs with mixed sizes


# -- text_box -----------------------------------------------------------------------------------------
def test_text_box_per_line_sizes_and_the_int_path_is_unchanged():
    m = Meter(None, "NoSuchFont")
    lines = ["SMALL", "HUGE"]
    x0, y0, x1, y1 = text_box(lines, [60, 200], 500, 700, 5, 0, m)
    assert (y1 - y0) == 260  # sum of the line heights, not 2 * max
    assert (x1 - x0) == pytest.approx(max(m.width("SMALL", 60), m.width("HUGE", 200)))
    assert text_box(lines, 60, 500, 700, 5, 4, m) == (500 - m.width("SMALL", 60) / 2 - 4, 700 - 60 - 4,
                                                     500 + m.width("SMALL", 60) / 2 + 4, 700 + 60 + 4)
    assert text_box(lines, 60, 500, 700, 2, 0, m)[1] == 700 - 120  # \an2 still bottom-anchored


# -- (MF-4) left-aligned pill watermark ----------------------------------------------------------------
def test_left_aligned_pill_label_sits_on_the_safe_zone_edge_bottom_anchored():
    doc = make_doc()
    wm = ov("label", "Twitch.tv/skiimask", 0, 9, position="bottom", align="left", box=True)
    (ev,) = plan_overlays(doc, [wm], "tiktok", 10)
    st = doc.styles[ev.style]
    assert ev.align == "left" and ev.an == 4 and ev.style == "LabelBox"
    assert st.size >= 64 and st.size * Meter(None, "X").cap_ratio >= 36
    assert st.border_style == 3 and st.back.startswith("&H66") and st.outline_color.startswith("&H66")  # 60 % pill
    x0, y0, x1, y1 = text_box([" ".join(ln) for ln in ev.lines], ev.sizes, ev.x, ev.y, ev.an, box_pad(st), Meter(None, "X"))
    assert x0 == 120  # tiktok safe-zone left edge: the PILL starts there, not the text
    assert 1240 - 20 <= y1 <= 1240 + 20  # bottom anchor ≈ y 1240 on 1920
    build_overlays(doc, [wm], "tiktok", 10)
    assert "\\an4\\pos(" in dialogue(doc, "LabelBox")


def test_plain_label_is_still_centred_and_unboxed():
    doc = make_doc()
    (ev,) = plan_overlays(doc, [ov("label", "plain", position="center")], "tiktok", 10)
    assert ev.align == "center" and ev.an == 5 and ev.style == "Label" and ev.sizes == [doc.styles["Label"].size]


# -- schema --------------------------------------------------------------------------------------------
def test_schema_carries_the_new_fields_with_safe_defaults():
    plan = conform({"segments": [{"src_start": 0, "src_end": 2}],
                    "overlays": [{"kind": "punch_title", "text": "X"}]}, EDIT_PLAN)
    o = plan["overlays"][0]
    assert o["kind"] == "punch_title" and o["emphasis"] == "" and o["align"] == "center" and o["box"] is False
    assert plan["segments"][0]["band_src"] is None
    kept = conform({"band_src": {"start": 2, "end": 4, "speed": 0.75}}, SEGMENT)["band_src"]
    assert kept == {"start": 2.0, "end": 4.0, "speed": 0.75}
    assert conform({"align": "diagonal"}, EDIT_PLAN["properties"]["overlays"]["items"])["align"] == "center"


# -- (MF-2a) band_src: the filter graph (no ffmpeg) ------------------------------------------------------
def stack_seg(**kw):
    return {"src_start": 0.0, "src_end": 2.0, "speed": 1.0, "zoom": {"type": "none", "scale": 1.0}, "shake": False,
            "transition_in": "cut", "reframe": {"mode": "stack", "x": 0.4, "cam": CAM, "face": None}, **kw}


def graph_of(seg, speed=1.0, dur=2.0):
    r = Renderer(RenderSpec(width=360, height=640, fps=15))
    return r.segment_graph(seg, speed, dur, "cut", "cut", SRC[0], SRC[1], False)


def test_band_src_makes_two_trims_and_a_separate_gameplay_input():
    graph, inputs = graph_of(stack_seg(band_src={"start": 5.0, "end": 8.0, "speed": 0.75}))
    assert inputs == [(0.0, 2.0), (5.0, 8.0)]
    assert "[0:v]" in graph and "[1:v]" in graph and "[1:a]" not in graph  # replay is muted: audio stays input 0
    assert "setpts=PTS/0.7500" in graph and "tpad=stop_mode=clone" in graph and "trim=duration=2.000" in graph
    assert "[c]crop=" in graph and "[g]crop=" in graph and "split=2" not in graph  # the band no longer shares input 0


def test_without_band_src_or_outside_stack_mode_there_is_one_input():
    g, ins = graph_of(stack_seg())
    assert ins == [(0.0, 2.0)] and "[1:v]" not in g and "split=2[c][g]" in g
    plain = stack_seg(band_src={"start": 5, "end": 8, "speed": 1})
    plain["reframe"] = {"mode": "center", "x": 0.5, "cam": None, "face": None}
    assert graph_of(plain)[1] == [(0.0, 2.0)]
    for bad in ({"start": 5, "end": 5, "speed": 1}, {"start": -1, "end": 3, "speed": 1}, {"start": "x", "end": 3}, "no"):
        assert band_src_range({"band_src": bad}) is None
    assert band_src_range({"band_src": {"start": 1, "end": 3, "speed": 0}})[2] == 1.0  # speed 0 → normal


# -- (MF-2a) band_src: a real render ---------------------------------------------------------------------
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")


@pytest.fixture(scope="module")
def three_colours(tmp_path_factory):
    """640x360 source: red 0-2 s, blue 2-3 s, green 3-4 s."""
    out = tmp_path_factory.mktemp("bandsrc") / "src.mp4"
    inputs = []
    for colour, dur in (("red", 2), ("blue", 1), ("green", 1)):
        inputs += ["-f", "lavfi", "-i", f"color=c={colour}:s=640x360:r=15:d={dur}"]
    run(["-v", "error", "-y", *inputs, "-filter_complex", "concat=n=3:v=1:a=0", "-c:v", "libx264", "-preset",
         "ultrafast", "-pix_fmt", "yuv420p", str(out)])
    return out


def colour_at(video, t, x, y):
    px = run(["-v", "error", "-ss", f"{t}", "-i", str(video), "-frames:v", "1", "-vf", f"format=rgb24,crop=1:1:{x}:{y}",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]).stdout
    r, g, b = px[0], px[1], px[2]
    return "red" if r > 150 > max(g, b) else "blue" if b > 150 > max(r, g) else "green" if g > 100 > r and g > b + 40 else f"?{r, g, b}"


def render_seg(src, seg, tmp_path, name):
    r = Renderer(RenderSpec(width=360, height=640, fps=15))
    dest = tmp_path / f"{name}.mkv"
    r._render_segment(src, seg, 1.0, 2.0, "cut", "cut", SRC[0], SRC[1], False, dest)
    return dest


@needs_ffmpeg
def test_real_render_gameplay_band_replays_another_range_while_the_cam_band_keeps_its_own(three_colours, tmp_path):
    cam_y, band_y, x = 20, 500, 180  # 360x640: cam band is the top ~166 px, gameplay below it
    plain = render_seg(three_colours, stack_seg(), tmp_path, "plain")
    assert colour_at(plain, 0.3, x, band_y) == "red" and colour_at(plain, 1.7, x, band_y) == "red"  # control: own range
    replay = render_seg(three_colours, stack_seg(band_src={"start": 2.0, "end": 4.0, "speed": 1.0}), tmp_path, "replay")
    assert colour_at(replay, 0.3, x, band_y) == "blue" and colour_at(replay, 1.7, x, band_y) == "green"
    assert colour_at(replay, 0.3, x, cam_y) == "red" and colour_at(replay, 1.7, x, cam_y) == "red"  # cam band untouched


@needs_ffmpeg
def test_real_render_band_src_shorter_than_the_segment_holds_its_last_frame(three_colours, tmp_path):
    held = render_seg(three_colours, stack_seg(band_src={"start": 2.0, "end": 3.0, "speed": 1.0}), tmp_path, "held")
    assert probe(held)["duration"] >= 1.9  # the band does not end the segment early
    assert colour_at(held, 0.3, 180, 500) == "blue" and colour_at(held, 1.8, 180, 500) == "blue"  # held, not black
    slow = render_seg(three_colours, stack_seg(band_src={"start": 2.0, "end": 4.0, "speed": 0.5}), tmp_path, "slow")
    assert colour_at(slow, 1.7, 180, 500) == "blue"  # half speed: at 1.7 s the replay is at source 2.85 s (blue); at full speed it would be green
