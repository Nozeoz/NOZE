"""Render FX upgrade (23 Nov): hold / rewind / glitch / look / zoom focus / fx / music drop / time_card / callout /
new SFX recipes. Every feature has a case that goes red when the feature is removed (positive controls: the same
check run on the un-treated segment must FAIL). Graph / ASS / timeline tests need no ffmpeg; the real renders run at
360x640@15."""

import array
import io
import math
import re
import shutil
import wave

import pytest

from noze.agency.media import qc
from noze.agency.media.captions import (AssDoc, Meter, box_pad, build_overlays, caption_styles, overlay_styles,
                                        plan_overlays, text_box)
from noze.agency.media.ffmpeg import probe, run
from noze.agency.media.render import (Renderer, RenderSpec, rewind_len, stack_graph, stack_layout, zoom_filters)
from noze.agency.media.sfx import RECIPES, synth_sfx
from noze.agency.media.timeline import Timeline, remove_output_range, sanitize_segments
from noze.agency.schemas import EDIT_PLAN, SEGMENT, conform

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
W, H, FPS = 360, 640, 15
SRC = (640, 360)


def seg(a, b, **kw):
    d = {"src_start": a, "src_end": b, "speed": 1.0,
         "reframe": {"mode": "center", "x": 0.5, "scale": None, "y": None, "cam": None, "face": None},
         "zoom": {"type": "none", "scale": 1.0, "fx": None, "fy": None}, "shake": False, "transition_in": "cut",
         "look": "none", "hold": 0.0, "hold_style": "zoom"}
    d.update(kw)
    return d


# -- timeline: hold -------------------------------------------------------------------------------------
def test_hold_lengthens_the_slot_and_words_never_land_in_it():
    segs = [seg(10, 14, hold=1.0), seg(20, 22, speed=2.0)]
    tl = Timeline(segs)
    p0, p1 = tl.placed
    assert (p0.out_start, p0.out_end, p0.hold, p0.play_end) == (0.0, 5.0, 1.0, 4.0)
    assert (p1.out_start, p1.out_end) == (5.0, 6.0) and tl.duration == 6.0  # transitions + hold = a plain running sum
    assert tl.to_source(4.6) == 14.0 and tl.to_source(5.5) == 21.0  # inside the hold = the frozen last frame
    words = [{"word": "late", "start": 13.7, "end": 14.3}, {"word": "next", "start": 20.2, "end": 20.6}]
    out = tl.map_words(words)
    assert out[0]["end"] <= p0.play_end + 1e-6  # the word that overruns the segment stops where the picture freezes
    assert not any(p0.play_end < w["start"] < p0.out_end for w in out)  # nothing is said during the hold
    assert out[1]["start"] == pytest.approx(5.1)  # the next segment starts AFTER the hold
    # control: without the hold the second segment would start at 4.0
    assert Timeline([seg(10, 14), seg(20, 22, speed=2.0)]).placed[1].out_start == 4.0
    assert Timeline([seg(0, 2, hold=9)]).duration == pytest.approx(3.2)  # clamped to 1.2


def test_remove_output_range_ignores_the_hold_and_moves_it_to_the_tail_piece():
    out = remove_output_range([seg(0, 10, hold=1.0)], 4.0, 5.0)
    assert [(s["src_start"], s["src_end"], s["hold"]) for s in out] == [(0, 4.0, 0.0), (5.0, 10, 1.0)]
    assert Timeline(out).duration == pytest.approx(10.0)  # 9 s played + 1 s hold
    assert remove_output_range([seg(0, 10, hold=1.0)], 10.2, 10.9)[0]["hold"] == 1.0  # a cut inside the hold: untouched


# -- timeline: sanitize with several bounds ----------------------------------------------------------------
def test_sanitize_segments_clamps_into_the_best_bound_and_keeps_the_editors_order():
    bounds = [(100, 110), (10, 20)]  # the story plays the LATE part first (cold open), then rewinds
    segs = [seg(99, 112, hold=5), seg(12, 15), seg(50, 53), seg(18, 40)]
    out = sanitize_segments(segs, source_duration=200, bounds=bounds)
    assert [(s["src_start"], s["src_end"]) for s in out] == [(99.0, 111.5), (12, 15), (18, 21.5)]  # 50-53 dropped
    assert out[0]["hold"] == 1.2  # hold clamped to 0-1.2
    assert out[1]["hold"] == 0.0
    # a single tuple / None behave as before; control: the late bound alone would drop the early segments
    assert [s["src_start"] for s in sanitize_segments(segs, 200, (100, 110))] == [99.0]
    assert sanitize_segments([seg(5, 9)], 200, None)[0]["src_end"] == 9
    capped = sanitize_segments([seg(0, 5, hold=1.0), seg(10, 15, hold=1.0)], 200, None, max_total=8.0)
    assert Timeline(capped).duration == pytest.approx(8.0) and sum(c["hold"] for c in capped) == 0  # holds go first


def test_schema_carries_the_fx_fields():
    s = conform({"zoom": {"type": "punch", "scale": 1.2, "fx": 0.3}, "hold": 0.8, "hold_style": "polaroid",
                 "look": "flashback", "transition_in": "rewind"}, SEGMENT)
    assert s["zoom"]["fx"] == 0.3 and s["zoom"]["fy"] is None and s["look"] == "flashback" and s["hold"] == 0.8
    plan = conform({"segments": [], "fx": {"vignette": True}, "music": {"drop_at": 7}, "color": "night"}, EDIT_PLAN)
    assert plan["fx"]["vignette"] is True and plan["music"]["drop_at"] == 7.0 and plan["color"] == "night"


# -- zoom focus / stack reframe ---------------------------------------------------------------------------
def test_zoom_grows_from_the_focus_point_not_the_centre():
    centre = zoom_filters("punch", 1.3, "cut", 3.0, W, H, FPS)
    zw = f"2*trunc({W}*(1+0.300*min(t/0.15,1))/2)"  # the grown width, written out (crop's iw is frozen at configure time)
    zh = zw.replace(str(W), str(H))
    assert f"x='({zw}-{W})/2':y='({zh}-{H})/2'" in centre[1]  # default: centred
    focus = zoom_filters("punch", 1.3, "cut", 3.0, W, H, FPS, 0.2, 0.3)
    assert f"x='0.200*({zw}-{W})':y='0.300*({zh}-{H})'" in focus[1]  # offset = fraction x overshoot: the focus stays put
    assert "iw" not in focus[1] and "ow" not in focus[1].replace("pow", "")
    clamped = zoom_filters("punch", 1.3, "cut", 3.0, W, H, FPS, -4, 9)[1]
    assert "x='0.000*(" in clamped and "y='1.000*(" in clamped  # clamped inside the frame
    push = zoom_filters("push", 1.2, "cut", 3.0, W, H, FPS, 0.8, None)
    assert "x='(iw-iw/zoom)*0.800'" in push[1] and "y='ih/2-(ih/zoom/2)'" in push[1]
    assert zoom_filters("none", 1.3, "cut", 3.0, W, H, FPS, 0.2, 0.3) == []


def test_stack_gameplay_band_zoom_and_position():
    cam = {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}
    src_w, src_h, w, h = 1920, 1080, 1080, 1920
    plain = stack_graph(cam, 0.5, src_w, src_h, w, h)
    _, bottom = stack_layout(cam, src_w, src_h, w, h)
    assert f"[g]crop={_even(src_h * w / bottom)}:{src_h}:" in plain and plain.count(":0,scale=") >= 1  # full height, y 0
    zoomed = stack_graph(cam, 0.5, src_w, src_h, w, h, scale=1.5, game_y=0.6)
    gh = _even(src_h / 1.5)
    m = re.search(r"\[g\]crop=(\d+):(\d+):(\d+):(\d+)", zoomed)
    assert int(m.group(2)) == gh and int(m.group(1)) == _even(gh * w / bottom)  # tighter crop, same aspect
    assert int(m.group(4)) == int(0.6 * src_h - gh / 2)  # centred on the requested height
    low = re.search(r"\[g\]crop=(\d+):(\d+):(\d+):(\d+)", stack_graph(cam, 0.5, src_w, src_h, w, h, scale=1.5, game_y=1.0))
    assert int(low.group(4)) == src_h - gh  # clamped inside the source
    assert plain != zoomed


def _even(x):
    return max(2, int(round(x / 2.0)) * 2)


# -- segment graph ------------------------------------------------------------------------------------------
def graph_of(s, dur=3.0, trans="cut", nxt="cut", prev=None, audio=True):
    r = Renderer(RenderSpec(width=W, height=H, fps=FPS))
    return r.segment_graph(s, 1.0, dur, trans, nxt, SRC[0], SRC[1], audio, prev)


def test_graph_hold_pads_the_audio_with_silence_and_freezes_the_picture():
    g, ins = graph_of(seg(0, 2.2, hold=0.8, hold_style="polaroid"), dur=3.0)
    assert "tpad=stop_mode=clone" in g and "concat=n=2:v=1:a=0" in g and "rotate=" in g  # polaroid card
    assert "trim=duration=2.200" in g  # the moving part is exactly the play time
    assert "afade=t=out:st=2.188:d=0.012" in g and "apad=whole_dur=3.000" in g  # voice ends at play end, hold = silence
    plain, _ = graph_of(seg(0, 3.0), dur=3.0)
    assert "tpad" not in plain and "concat=n=2" not in plain  # control: no hold, no freeze
    assert "pow(1-min(t/0.800" in graph_of(seg(0, 2.2, hold=0.8, hold_style="zoom"))[0]
    assert "hue=s=0" in graph_of(seg(0, 2.2, hold=0.8, hold_style="bw"))[0]
    nohold, _ = graph_of(seg(0, 0.4, hold=0.8), dur=1.2)  # no room to play: the hold is dropped rather than eating the clip
    assert "tpad" not in graph_of(seg(0, 0.2, hold=0.8), dur=1.0)[0] and nohold


def test_graph_rewind_adds_the_previous_tail_as_a_reversed_input():
    prev = seg(5, 8)
    g, ins = graph_of(seg(20, 23, transition_in="rewind"), trans="rewind", prev=prev)
    assert ins == [(20.0, 23.0), (6.4, 8.0)] and g.count("reverse") == 1  # last 1.6 s of the PREVIOUS segment, backwards
    assert "[2:v]" not in g and "[1:v]setpts" in g and "overlay=0:0:eof_action=pass:enable='lt(t,0.450)'" in g
    assert "afade=t=in:d=0.450" in g  # the incoming voice swells in under the SFX
    assert rewind_len("rewind", prev, 3.0) == 0.45 and rewind_len("rewind", None, 3.0) == 0.0
    assert rewind_len("rewind", prev, 0.6) == 0.0 and rewind_len("cut", prev, 3.0) == 0.0  # too short / not a rewind
    g2, ins2 = graph_of(seg(20, 23), trans="cut", prev=prev)
    assert len(ins2) == 1 and "reverse" not in g2  # control: no rewind transition, no extra input
    stacked = seg(5, 8, reframe={"mode": "stack", "x": 0.5, "cam": {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}})
    g3, _ = graph_of(seg(20, 23), trans="rewind", prev=stacked)
    assert "[rw_c]crop=" in g3 and "[rw_top]" in g3  # the rewound tail keeps the stacked layout, labels don't clash


def test_graph_glitch_is_gated_to_a_window_at_the_cut():
    g, _ = graph_of(seg(0, 3), trans="glitch", nxt="glitch")
    assert "between(t,0.000,0.200)" in g and "between(t,2.800,3.000)" in g and "rgbashift" in g
    assert "enable=" in g and "gl_c" in g
    assert "rgbashift" not in graph_of(seg(0, 3))[0]  # control


@pytest.mark.parametrize("look,needle", [("flashback", "vignette"), ("vhs", "chromashift"), ("noir", "hue=s=0"),
                                         ("dream", "blend=all_mode=screen")])
def test_graph_look_chains(look, needle):
    assert needle in graph_of(seg(0, 3, look=look))[0]
    assert needle not in graph_of(seg(0, 3))[0] or look == "noir"  # control (noir's hue=s=0 is also in bw hold only)


# -- ASS: time_card / callout / stamp / glitch -------------------------------------------------------------
def make_doc(w=1080, h=1920, font="Anton"):
    doc = AssDoc(w, h)
    caption_styles(doc, font, {})
    overlay_styles(doc, font, font)
    return doc


def ov(kind, text, start=1.0, end=2.1, **kw):
    return {"kind": kind, "text": text, "start": start, "end": end, "style": "slide", "position": "center", **kw}


def test_time_card_is_big_banded_and_eased_in_and_out():
    doc = make_doc()
    assert build_overlays(doc, [ov("time_card", "40 min earlier")], "tiktok", 10) == 1
    ev = doc.events
    titles = [e for e in ev if e[3] == "Title"]
    sizes = {int(m) for e in titles for m in re.findall(r"\\fs(\d+)", e[4])}
    assert sizes and min(sizes) >= 110  # the card text is ≥ 110 px at 1920
    assert any("\\p1" in e[4] and "\\clip" in e[4] and "\\t(0,280,0.4" in e[4] for e in ev)  # band wipes in, ease-out (accel 0.4)
    entry = [e for e in titles if e[1] < 1.0 + 0.3 and e[2] - e[1] < 0.1]  # the per-frame slices, not the static hold
    assert len(entry) >= 6 and max(e[2] for e in entry) - 1.0 <= 0.35  # slide-in = per-frame eased events, ≤ 350 ms
    xs = [int(re.search(r"\\pos\((-?\d+),", e[4]).group(1)) for e in sorted(entry, key=lambda e: e[1])]
    steps = [b - a for a, b in zip(xs, xs[1:])]
    assert all(s >= 0 for s in steps) and steps[0] > steps[-1] > -1  # fast first, slow last = ease-out, never linear
    leave = [e for e in titles if e[1] >= 2.1 - 0.2 - 1e-6]
    assert leave and 2.1 - min(e[1] for e in leave) <= 0.28 * 0.7 + 0.05  # exit ≈ 70 % of the entry
    (plan,) = plan_overlays(make_doc(font="Arial"), [ov("time_card", "40 min earlier")], "tiktok", 10)
    x0, y0, x1, y1 = text_box([" ".join(ln) for ln in plan.lines], plan.sizes, plan.x, plan.y, plan.an, 0, Meter(None, "X"))
    assert 0 <= x0 and x1 <= 1080 and 0 <= y0 and y1 <= 1920  # measured by the same geometry the lint uses
    assert min(plan.sizes) >= 110
    glitch = make_doc()
    build_overlays(glitch, [ov("time_card", "Back to now", style="glitch")], "tiktok", 10)
    assert any("&H0000FF&" in e[4] for e in glitch.events) and not any("&H0000FF&" in e[4] for e in doc.events)


def test_callout_draws_a_ring_and_a_self_drawing_arrow_to_the_target():
    doc = make_doc(font="Arial")  # a wide face: the planner's width estimate and the Meter below agree
    c = ov("callout", "look here", start=2.0, end=3.5, style="stamp", at_x=0.7, at_y=0.35)
    assert build_overlays(doc, [c], "tiktok", 10) == 1
    shapes = [e for e in doc.events if e[3] == "Shape"]
    assert any("\\bord8" in e[4] and "\\1a&HFF&" in e[4] and " b " in e[4] for e in shapes)  # bezier ring, no fill
    arrow = next(e for e in shapes if "\\3c&H000000&\\bord3" in e[4])
    assert "\\clip(" in arrow[4] and "\\t(0,260,0.4,\\clip(" in arrow[4]  # the line draws itself, ease-out
    label = next(e for e in doc.events if e[3] == "Title")
    assert "\\fscx160" in label[4] and "\\frz-9" in label[4] and "\\t(0,180,0.5" in label[4]  # stamp: 160 % → 100 %, rotated
    (plan,) = plan_overlays(doc, [c], "tiktok", 10)
    tx, ty = 0.7 * 1080, 0.35 * 1920
    assert plan.y > ty and min(plan.sizes) >= 64  # the label sits BELOW a target in the upper half
    x0, y0, x1, y1 = text_box([" ".join(ln) for ln in plan.lines], plan.sizes, plan.x, plan.y, plan.an, 0, Meter(None, "X"))
    assert 120 - 1 <= x0 and x1 <= 1080 - 120 + 1 and y1 <= 1920  # inside the safe zone, like every other text
    low = plan_overlays(doc, [ov("callout", "up here", at_x=0.3, at_y=0.8)], "tiktok", 10)[0]
    assert low.y < 0.8 * 1920  # a target in the lower half puts the label ABOVE it
    glitch = make_doc()
    build_overlays(glitch, [dict(c, style="glitch")], "tiktok", 10)
    assert any("&HFFFF00&" in e[4] for e in glitch.events) and not any("&HFFFF00&" in e[4] for e in doc.events)


def test_stamp_and_glitch_styles_work_on_ordinary_overlays():
    doc = make_doc()
    build_overlays(doc, [ov("text", "BOOM", style="stamp")], "tiktok", 10)
    bodies = [e[4] for e in doc.events if e[3] == "Label"]
    assert bodies and all("\\frz-8" in b for b in bodies)  # struck at -8°
    assert "\\fscx140" in bodies[0] and "\\t(0," in bodies[0]  # 1.4 → 1.0, animated (see test_stamp_is_a_real_stamp)
    glitch = make_doc()
    build_overlays(glitch, [ov("text", "NOPE", style="glitch")], "tiktok", 10)
    assert sum("&H0000FF&" in e[4] for e in glitch.events) >= 2  # RGB ghosts jittering for ~120 ms
    slide = make_doc()
    build_overlays(slide, [ov("text", "SLID", style="slide")], "tiktok", 10)
    assert not any("\\move" in e[4] for e in slide.events) and len(slide.events) > 4  # eased frames, no linear \move


def test_text_sizes_meet_the_mandor_floors():
    doc = make_doc()
    assert doc.styles["Caption"].size >= 75  # default font_scale 1.0
    (t,) = plan_overlays(doc, [ov("hook_title", "Why this clip is INSANE", style="pop", emphasis="INSANE")], "tiktok", 10)
    assert min(t.sizes) >= 55 and max(t.sizes) >= 110  # setup line ≥ 55, emphasis ≥ 110
    small = AssDoc(1080, 1920)
    caption_styles(small, "Anton", {"font_scale": 1.0, "style": "minimal"})
    assert small.styles["Caption"].size >= 75


def test_layout_lint_measures_the_new_overlays(monkeypatch):
    monkeypatch.setattr(qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")
    plan = conform({"segments": [seg(0, 10)], "captions": {"enabled": False},
                    "overlays": [ov("time_card", "40 min earlier", start=1, end=2.1),
                                 ov("callout", "look here", start=4, end=5.5, at_x=0.7, at_y=0.35)]}, EDIT_PLAN)
    debug = {}
    issues = qc.layout_lint(plan, {}, words=[], width=1080, height=1920, platform="tiktok", debug=debug)
    assert {ly["kind"] for ly in debug["layers"]} == {"time_card", "callout"}  # both are measured layers
    assert not [i for i in issues if i.get("severity") == "blocker"]
    wide = conform({"segments": [seg(0, 10)], "captions": {"enabled": False}, "overlays": [
        ov("time_card", "an extremely long time jump label that cannot possibly fit on one line at all", start=1, end=2.1)]},
        EDIT_PLAN)
    wide_layers = {}
    qc.layout_lint(wide, {}, words=[], width=1080, height=1920, platform="tiktok", debug=wide_layers)
    box = wide_layers["layers"][0]["box"]
    assert box[0] >= -1 and box[2] <= 1081  # a long label wraps instead of running off the frame


# -- SFX ------------------------------------------------------------------------------------------------------
NEW_SFX = {"rewind": 0.5, "tape_stop": 0.6, "heartbeat": 0.9, "shutter": 0.12, "bass_drop": 1.2, "sting": 0.8}


def samples(path):
    w = wave.open(str(path))
    a = array.array("h", w.readframes(w.getnframes()))
    return a[::2], w.getframerate()  # left channel


def zcr(a, lo, hi):
    seg_ = a[lo:hi]
    return sum(1 for x, y in zip(seg_, seg_[1:]) if (x < 0) != (y < 0)) / max(1, len(seg_))


@needs_ffmpeg
def test_new_sfx_recipes_are_clean_and_shaped_right(tmp_path):
    assert set(NEW_SFX) <= set(RECIPES)
    out = {}
    for kind, dur in NEW_SFX.items():
        a, sr = samples(synth_sfx(kind, tmp_path))
        out[kind] = a
        assert len(a) / sr == pytest.approx(dur, abs=0.02)
        peak = max(abs(x) for x in a) / 32768
        assert 0.1 < peak < 0.95, kind  # audible, never clipping
        assert abs(a[0]) < 3000 and abs(a[-1]) < 600, kind  # starts and ends without a click
    n = 48000 // 10
    assert zcr(out["tape_stop"], 0, n) > 2.5 * zcr(out["tape_stop"], len(out["tape_stop"]) - 4 * n, len(out["tape_stop"]) - 3 * n)
    assert zcr(out["rewind"], 0, n) < zcr(out["rewind"], 3 * n, 4 * n)  # the whine climbs
    assert zcr(out["bass_drop"], 0, len(out["bass_drop"])) < 0.01  # a sub, not noise
    assert zcr(out["heartbeat"], 0, len(out["heartbeat"])) < 0.01
    hb = out["heartbeat"]  # two thumps: energy at 0 and ~0.32 s, quiet in between and after
    e = lambda t0, t1: max(abs(x) for x in hb[int(t0 * 48000):int(t1 * 48000)])  # noqa: E731
    assert e(0, 0.1) > 2 * e(0.2, 0.3) and e(0.32, 0.42) > 2 * e(0.6, 0.9)
    sh = out["shutter"]
    assert max(abs(x) for x in sh[int(0.065 * 48000):int(0.1 * 48000)]) > 0.1 * 32768 * 0.5  # the second clack


# -- real renders ---------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def source(tmp_path_factory):
    """640x360@15, 12 s: moving testsrc2 (saturated colours) + a tone."""
    out = tmp_path_factory.mktemp("fx") / "src.mp4"
    run(["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=15:d=12", "-f", "lavfi", "-i", "sine=f=330:d=12",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)])
    return out


def frame(video, t):
    from PIL import Image
    raw = run(["-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-"]).stdout
    return Image.frombytes("RGB", (W, H), raw)


def count_px(im, pred):
    return sum(1 for r, g, b in zip(*[iter(im.convert("RGB").tobytes())] * 3) if pred(r, g, b))


def diff(a, b):
    from PIL import ImageChops, ImageStat
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def saturation(im):
    from PIL import ImageStat
    return ImageStat.Stat(im.convert("HSV")).mean[1] / 255


def render_seg(src, s, tmp_path, name, trans="cut", nxt="cut", prev=None, dur=2.5):
    r = Renderer(RenderSpec(width=W, height=H, fps=FPS))
    dest = tmp_path / f"{name}.mkv"
    r._render_segment(src, s, 1.0, dur, trans, nxt, SRC[0], SRC[1], True, dest, prev)
    return dest


@needs_ffmpeg
def test_real_segment_hold_freezes_polaroid_still_and_zoom_pushes(source, tmp_path):
    play, hold = 1.5, 1.0
    for style, frozen in (("polaroid", True), ("zoom", False)):
        v = render_seg(source, seg(1.0, 1.0 + play, hold=hold, hold_style=style), tmp_path, style, dur=play + hold)
        assert probe(v)["duration"] == pytest.approx(play + hold, abs=0.1)
        a, b = frame(v, play + 0.15), frame(v, play + 0.85)
        moving = diff(frame(v, 0.2), frame(v, 1.0))
        assert moving > 4  # control: the segment itself moves
        if frozen:
            assert diff(a, b) < 1.0  # the card does not move: frozen
            assert saturation(a) < saturation(frame(v, 0.5))  # dressed: dark blurred backdrop + white border
        else:
            assert 1.0 < diff(a, b)  # the slow push is visible
    plain = render_seg(source, seg(1.0, 2.5), tmp_path, "nohold", dur=1.5)
    assert diff(frame(plain, 0.8), frame(plain, 1.4)) > 4  # control: with no hold the last frames still move
    assert Timeline([seg(1.0, 2.5, hold=1.0)]).duration == pytest.approx(2.5)


@needs_ffmpeg
def test_real_segment_rewind_replaces_the_head_and_glitch_is_gated(source, tmp_path):
    prev = seg(3.0, 6.0)
    base = seg(8.0, 10.5)
    cut = render_seg(source, base, tmp_path, "cut")
    rew = render_seg(source, dict(base, transition_in="rewind"), tmp_path, "rew", trans="rewind", prev=prev)
    assert probe(rew)["duration"] == pytest.approx(probe(cut)["duration"], abs=0.1)  # a rewind never changes the length
    assert diff(frame(cut, 0.2), frame(rew, 0.2)) > 8  # the head is the rewound tail, not the segment
    assert diff(frame(cut, 1.2), frame(rew, 1.2)) < 4  # after 0.45 s the segment itself takes over
    gl = render_seg(source, dict(base, transition_in="glitch"), tmp_path, "gl", trans="glitch")
    assert diff(frame(cut, 0.1), frame(gl, 0.1)) > 8  # RGB split + jitter inside the 0.2 s window
    assert diff(frame(cut, 1.2), frame(gl, 1.2)) < 4  # …and nothing outside it (no constant zoom)
    again = render_seg(source, base, tmp_path, "cut2")
    assert diff(frame(cut, 0.1), frame(again, 0.1)) < 1  # control: two plain renders match, so the diffs above are the effect


@needs_ffmpeg
def test_real_segment_looks_are_clearly_different_from_the_present(source, tmp_path):
    plain = render_seg(source, seg(1.0, 3.0), tmp_path, "plain", dur=2.0)
    base_sat = saturation(frame(plain, 1.0))
    assert base_sat > 0.5  # the control footage is vivid
    sat_ok = lambda im: saturation(im) < 0.30  # noqa: E731 — the flashback check
    assert not sat_ok(frame(plain, 1.0))  # positive control: an un-treated segment FAILS the flashback check
    for look, limit in (("flashback", 0.30), ("noir", 0.05)):
        v = render_seg(source, seg(1.0, 3.0, look=look), tmp_path, look, dur=2.0)
        assert saturation(frame(v, 1.0)) < limit, look
    vhs = render_seg(source, seg(1.0, 3.0, look="vhs"), tmp_path, "vhs", dur=2.0)
    assert diff(frame(vhs, 1.0), frame(plain, 1.0)) > 8
    dream = render_seg(source, seg(1.0, 3.0, look="dream"), tmp_path, "dream", dur=2.0)
    assert diff(frame(dream, 1.0), frame(plain, 1.0)) > 8


@needs_ffmpeg
def test_real_segment_zoom_focus_moves_the_crop(source, tmp_path):
    def zs(fx):
        return seg(1.0, 3.0, zoom={"type": "punch", "scale": 1.4, "fx": fx, "fy": None})
    left = frame(render_seg(source, zs(0.0), tmp_path, "zl", dur=2.0), 1.0)
    right = frame(render_seg(source, zs(1.0), tmp_path, "zr", dur=2.0), 1.0)
    centre = frame(render_seg(source, zs(None), tmp_path, "zc", dur=2.0), 1.0)
    assert diff(left, right) > 10  # different parts of the frame stay in view
    assert diff(left, centre) > 4 and diff(right, centre) > 4


@needs_ffmpeg
def test_real_render_everything_together(source, tmp_path):
    segs = [seg(0.0, 3.0),
            seg(6.0, 8.5, transition_in="rewind", look="flashback", hold=0.8, hold_style="polaroid",
                zoom={"type": "punch", "scale": 1.3, "fx": 0.2, "fy": 0.3}),
            seg(3.0, 5.0, transition_in="glitch", look="vhs"),
            seg(8.5, 10.0, look="dream", hold=0.5, hold_style="zoom")]
    tl = Timeline(segs)
    plan = {"segments": segs, "captions": {"enabled": False},
            "overlays": [ov("time_card", "40 min earlier", start=3.0, end=4.1),
                         ov("callout", "look here", start=7.0, end=8.2, style="stamp", at_x=0.7, at_y=0.35),
                         ov("hook_title", "She turned down 5 BANDS", start=0.0, end=1.3, emphasis="5 BANDS", position="top"),
                         ov("punch_title", "DENIED", start=1.4, end=2.6)],
            "color": "teal_orange", "music": {"enabled": True, "gain_db": -14, "duck": True, "drop_at": 6.0},
            "sfx": [{"kind": "rewind", "at": 3.0, "gain_db": -8}]}
    sfx = {"rewind": synth_sfx("rewind", tmp_path / "sfx"), "hit": synth_sfx("hit", tmp_path / "sfx")}
    music = tmp_path / "music.wav"
    run(["-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=15", str(music)])
    res = Renderer(RenderSpec(width=W, height=H, fps=FPS, preset="ultrafast")).render(plan, source, tmp_path / "out.mp4",
                                                                                      tmp_path / "work", [], music, sfx)
    info = probe(res.path)
    assert info["has_video"] and info["has_audio"] and (info["width"], info["height"]) == (W, H)
    assert abs(info["duration"] - tl.duration) <= 1 / FPS + 0.02  # = Timeline.duration ± 1 frame
    assert res.overlays == 4 and res.timeline[1]["hold"] == 0.8
    assert res.stamps == [{"kind": "hit", "at": 1.5, "text": "DENIED"}]  # the stamp lands → a hit SFX is mixed there
    assert [c["at"] for c in res.sfx if c["kind"] == "hit"] == [1.5]
    assert count_px(frame(res.path, 2.0), lambda r, g, b: r > 180 and g < 90 and b < 90) > 60  # the red stamp, drawn by libass
    assert count_px(frame(res.path, 1.0), lambda r, g, b: r > 180 and g < 90 and b < 90) < 20  # control: no red before it lands
    ass = open(res.ass_path, encoding="utf-8").read()
    assert ass.count("Dialogue:") > 20 and "40 MIN" in ass.replace("\\N", " ") and "LOOK HERE" in ass and "REWIND" in ass
    p1 = tl.placed[1]  # hold polaroid: out 3.0+1.7 .. 3.0+2.5 = 4.7..5.5? (play 2.5 + hold 0.8 → 3.0 + 3.3)
    a, b = frame(res.path, p1.play_end + 0.15), frame(res.path, p1.out_end - 0.3)
    assert diff(a, b) < 1.5  # the frozen card, through the whole pipeline
    assert saturation(frame(res.path, 1.0)) > saturation(frame(res.path, p1.out_start + 1.0))  # flashback is paler than now
    # the color preset is applied on top: teal_orange moves the blue/red balance of the untreated segment
    from PIL import ImageStat
    r_, g_, b_ = ImageStat.Stat(frame(res.path, 1.0)).mean
    assert abs(r_ - b_) > 5


@needs_ffmpeg
def test_real_render_fx_and_music_drop(tmp_path):
    silent = tmp_path / "silent.mp4"  # no audio track: the music is the only sound, so the cut is measurable
    run(["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=15:d=8", "-c:v", "libx264", "-preset",
         "ultrafast", "-pix_fmt", "yuv420p", str(silent)])
    music = tmp_path / "m.wav"
    run(["-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=12", str(music)])

    def go(name, drop, fx):
        plan = {"segments": [seg(0.0, 8.0)], "captions": {"enabled": False}, "overlays": [], "fx": fx, "color": "night",
                "music": {"enabled": True, "gain_db": -10, "duck": False, "drop_at": drop}}
        return Renderer(RenderSpec(width=W, height=H, fps=FPS, preset="ultrafast")).render(
            plan, silent, tmp_path / f"{name}.mp4", tmp_path / name, [], music, {}).path

    def rms(path, t0, t1):
        raw = run(["-v", "error", "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000",
                   "-"]).stdout
        a = array.array("h", raw)
        return math.sqrt(sum(x * x for x in a) / max(1, len(a))) / 32768

    dropped = go("drop", 4.0, {"vignette": True, "grain": True, "letterbox": True})
    held = go("nodrop", None, {})
    assert rms(dropped, 3.0, 3.5) > 0.01  # music plays before the dip
    assert rms(dropped, 3.72, 3.98) < rms(dropped, 3.0, 3.5) * 0.05  # the bed is OUT in the 0.35 s before the drop
    assert rms(dropped, 4.1, 4.6) > rms(dropped, 3.0, 3.5) * 0.5  # …and back ON the drop
    assert rms(held, 3.72, 3.98) > rms(held, 3.0, 3.5) * 0.5  # control: with no drop_at nothing is cut
    # fx: letterbox bars are black top and bottom, the vignette darkens the corners, only when asked for
    f_on, f_off = frame(dropped, 2.0), frame(held, 2.0)
    from PIL import ImageStat
    bar = lambda im: ImageStat.Stat(im.crop((0, 0, W, 10))).mean[0]  # noqa: E731
    assert bar(f_on) < 12 < bar(f_off)
    corner = lambda im: ImageStat.Stat(im.crop((0, 40, 30, 70))).mean[0]  # noqa: E731
    centre = lambda im: ImageStat.Stat(im.crop((W // 2 - 15, H // 2 - 15, W // 2 + 15, H // 2 + 15))).mean[0]  # noqa: E731
    assert corner(f_on) / max(centre(f_on), 1) < corner(f_off) / max(centre(f_off), 1) * 0.9


# -- review fixes: dead-air cut keeps the hold, cap protects the payoff, SFX cache is race-free ---------------------
def test_dead_air_cut_before_a_hold_keeps_the_hold_on_the_head():
    out = remove_output_range([seg(0, 10, hold=0.75)], 9.0, 10.0)  # silence from 1 s before the end: tail < minimum
    assert len(out) == 1 and out[0]["src_end"] == 9.0 and out[0]["hold"] == 0.75
    assert Timeline(out).duration == pytest.approx(9.75)
    both = remove_output_range([seg(0, 10, hold=0.75)], 4.0, 5.0)  # control: a tail exists -> it carries the hold
    assert [s["hold"] for s in both] == [0.0, 0.75]
    assert remove_output_range([seg(0, 3, hold=0.75)], 0.0, 3.0) == []  # swallowing the whole segment drops it


def test_cap_shrinks_holds_then_setup_and_keeps_the_payoff():
    segs = [seg(0, 6, role="payoff"), seg(10, 18, role="setup", hold=0.5), seg(20, 24, role="reaction", hold=1.0)]
    out = sanitize_segments(segs, 100, None, max_total=14.0)  # 6 + 8.5 + 5 = 19.5 -> 5.5 too long
    assert [s["role"] for s in out] == ["payoff", "setup", "reaction"]  # order kept, nothing dropped
    assert out[0]["src_end"] - out[0]["src_start"] == 6 and out[2]["src_end"] - out[2]["src_start"] == 4
    assert out[2]["hold"] == 0 and out[1]["hold"] == 0  # holds went first
    assert Timeline(out).duration == pytest.approx(14.0)
    assert out[1]["src_end"] - out[1]["src_start"] == pytest.approx(4.0)  # control: the old rule cut the LAST segment
    tight = sanitize_segments(segs, 100, None, max_total=11.0)
    assert Timeline(tight).duration == pytest.approx(11.0) and len(tight) == 3


@needs_ffmpeg
def test_sfx_synth_is_safe_when_threads_race(tmp_path):
    import threading
    errs, paths = [], []

    def go():
        try:
            paths.append(synth_sfx("shutter", tmp_path))
        except Exception as exc:  # noqa: BLE001
            errs.append(exc)
    ts = [threading.Thread(target=go) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs and len(set(paths)) == 1
    a, sr = samples(paths[0])
    assert len(a) / sr == pytest.approx(0.12, abs=0.02)  # a complete, valid WAV
    assert [q.name for q in tmp_path.iterdir()] == ["shutter.wav"]  # no temp files left behind


# -- CP1 typography templates (23 Nov): hook title / stamp / rewind label / caption pages --------------------
from pathlib import Path  # noqa: E402

from noze.agency.media import captions as caps_mod  # noqa: E402
from noze.agency.media.captions import (CAP_RATIO, add_rewind_tag, group_words, is_function_word,  # noqa: E402
                                        plan_captions)

FONTS = Path(__file__).resolve().parents[1] / "noze-data" / "agency" / "assets" / "fonts"


def cap_px(size, family="Anton"):
    return size * Meter(FONTS, family).cap_ratio  # measured on the shipped face when present, else 0.58


def test_hook_title_is_a_template_big_emphasis_on_a_tilted_accent_block():
    doc = make_doc()
    c = ov("hook_title", "She turned down 5 BANDS", start=0.0, end=3.0, emphasis="5 BANDS", style="pop", position="top")
    (plan,) = plan_overlays(doc, [c], "tiktok", 10)
    setup, emph = plan.sizes[0], max(plan.sizes)
    assert cap_px(setup) >= 55 and emph >= 200  # measured cap height of the setup line, emphasis ≥ 200 px
    assert int(1920 * 0.034) * CAP_RATIO < 55  # control: the old setup size (65 px) was under the floor
    assert build_overlays(doc, [c], "tiktok", 10) == 1
    block = [e for e in doc.events if e[3] == "TitleBlock"]
    text = [e for e in doc.events if e[3] == "Title"]
    assert block and doc.styles["TitleBlock"].border_style == 3  # solid accent block behind the emphasis word
    assert all("\\frz-4" in e[4] for e in block + text)
    assert any("\\3c&H00E6FF&" in e[4] and "\\1a&HFF&" in e[4] for e in block)  # accent colour, glyphs hidden in this layer
    assert any("\\1c&H141414&" in e[4] for e in text)  # dark ink on the light block
    frames = sorted((e for e in text if e[2] - e[1] < 0.05), key=lambda e: e[1])
    enter = frames[-1][2] - frames[0][1]
    assert 0.2 <= enter <= 0.35  # enters in 200-350 ms
    scales = [int(re.search(rf"\\fs{emph}\\1c[^\\]*\\fscx(\d+)", e[4]).group(1)) for e in frames]
    assert 112 <= scales[0] <= 125 and min(scales) < 100 and scales[-1] >= 99  # slam 1.25 → overshoot → 1.0
    ys = [int(re.search(r"\\pos\(\d+,(-?\d+)\)", e[4]).group(1)) for e in frames]
    steps = [b - a for a, b in zip(ys, ys[1:])]
    assert ys[0] < ys[-1] and steps[0] > steps[-1] >= 0  # drops in on an ease-out
    hold = max(text, key=lambda e: e[2] - e[1])
    fade = int(re.search(r"\\fad\(0,(\d+)\)", hold[4]).group(1))
    assert 0.5 * enter * 1000 <= fade <= 0.9 * enter * 1000  # leaves in ~70 % of the entry
    red = make_doc()
    build_overlays(red, [c], "tiktok", 10, accent="#FF3B3B")
    assert any("\\3c&H3B3BFF&" in e[4] for e in red.events if e[3] == "TitleBlock")
    long_ = plan_overlays(doc, [ov("hook_title", "Look UNBELIEVABLEFOOTAGEFROMTHEMATCH", emphasis="UNBELIEVABLEFOOTAGEFROMTHEMATCH")],
                          "tiktok", 10)[0]
    assert max(long_.sizes) >= 140  # a long word shrinks, but not below 140
    x0, y0, x1, y1 = text_box([" ".join(ln) for ln in plan.lines], plan.sizes, plan.x, plan.y, plan.an, 0, Meter(FONTS, "Anton"))
    assert 120 <= x0 and x1 <= 1080 - 120 and y0 >= 0  # still measured by the lint's geometry, inside the safe zone


def test_stamp_is_a_real_stamp_with_a_hit_cue():
    doc, cues = make_doc(), []
    c = ov("punch_title", "DENIED", start=1.0, end=3.0, style="pop")  # punch_title is a stamp whatever style the editor sent
    assert build_overlays(doc, [c], "tiktok", 10, cues=cues) == 1
    assert cues == [{"kind": "hit", "at": 1.1, "text": "DENIED"}]  # lands 0.1 s in: the SFX goes here
    frame_ = [e for e in doc.events if e[3] == "Shape"]
    assert frame_ and all("\\frz-8" in e[4] for e in frame_)
    path = frame_[0][4].split("\\p1}")[1]
    outer, inner = path.split(" m ")[0], path.split(" m ")[1]
    thick = int(inner.split()[0])
    assert outer.count("l") == 1 and thick >= 8 and inner.startswith(f"{thick} {thick} ")  # hollow frame ≥ 8 px thick
    ents = sorted((e for e in doc.events if e[3] == "Title" and e[2] - e[1] < 0.05), key=lambda e: e[1])
    sc0 = [int(re.search(r"\\fscx(\d+)", e[4]).group(1)) for e in ents]
    assert sc0[0] == 140 and "\\t(0," in ents[0][4]  # 1.4 → ... animated per slice
    ends = [int(re.search(r"\\t\(0,\d+,\\fscx(\d+)", e[4]).group(1)) for e in ents]
    assert min(ends) < 100 and ents[0][1] == 1.0  # overshoot below 1.0 …
    settle = next(e for e in ents if int(re.search(r"\\t\(0,\d+,\\fscx(\d+)", e[4]).group(1)) >= 100)
    assert settle[2] - 1.0 <= 0.16  # … and back at 1.0 within ~150 ms
    pos = [tuple(map(int, re.search(r"\\pos\((-?\d+),(-?\d+)\)", e[4]).groups())) for e in ents]
    cx, cy = pos[0][0], pos[0][1]
    off = [(abs(px - cx), abs(py - cy)) for px, py in pos]
    assert max(max(o) for o in off) <= 6 and any(o != (0, 0) for o in off)  # micro-shake within ±6 px
    shaking = [e for e, o in zip(ents, off) if o != (0, 0)]
    assert shaking[-1][2] - shaking[0][1] <= 0.2  # lasts ~0.15 s
    # controls: an ordinary pop text is no stamp, and typewriter punch stays a typewriter
    plain, cues2 = make_doc(), []
    build_overlays(plain, [ov("text", "hello", style="pop")], "tiktok", 10, cues=cues2)
    assert cues2 == [] and not [e for e in plain.events if e[3] == "Shape"]


def words_at(text, step=0.3, t0=0.0):
    return [{"word": w, "start": t0 + i * step, "end": t0 + i * step + step * 0.8} for i, w in enumerate(text.split())]


def old_group(words, max_words=3):
    """The pre-CP1 chunker (control): cuts wherever the count says."""
    chunks, cur = [], []
    for w in words:
        if len(cur) >= max_words:
            chunks.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", w["word"]) or (re.search(r"[,;:]$", w["word"]) and len(cur) >= 2):
            chunks.append(cur)
            cur = []
    return chunks + ([cur] if cur else [])


def test_caption_pages_never_end_on_a_function_word_and_keep_every_word():
    text = ("NO, OH, my god and then he said to the guy yang tadi dan terus jadi kita pergi ke rumah sama dia but so "
            "the end is near and I like it a lot")
    words = words_at(text)
    pages = group_words(words, 3)
    assert [w["word"] for p in pages for w in p] == text.split()  # nothing lost, order kept
    assert all(len(p) <= 4 for p in pages)  # 2-4 words (the odd 1 is a sentence of one word)
    for p in pages[:-1]:  # the last page of a stream may trail off
        assert not is_function_word(p[-1]["word"]) or re.search(r"[.!?…]$", p[-1]["word"]), [w["word"] for w in p]
    # control: the old chunker ended pages on "OH," / "and" / "the" for this very input
    assert any(is_function_word(p[-1]["word"]) for p in old_group(words)[:-1])
    assert [w["word"] for w in pages[0]] == ["NO,", "OH,", "my", "god"]  # "NO, OH," no longer ends a page
    ev = plan_captions(words, {"words_per_caption": 3, "position": "lower"}, "tiktok", 1080, 1920, 96, 20.0)
    for e in ev[:-1]:
        assert not is_function_word(e.chunk[-1]["word"]) or re.search(r"[.!?…]$", e.chunk[-1]["word"])


def test_function_word_carry_never_crosses_a_pause():
    def w(t, s, e):
        return {"word": t, "start": s, "end": e}

    words = [w("oh", 0.0, 0.2), w("no", 0.2, 0.4), w("that", 3.4, 3.6), w("guy", 3.6, 3.9), w("again", 3.9, 4.2)]
    pages = group_words(words, 3)
    assert [[x["word"] for x in p] for p in pages] == [["oh", "no"], ["that", "guy", "again"]]  # "oh no" stands alone
    for p in pages:  # a page never starts before its first word is spoken: no word shown seconds early
        assert p[0]["start"] == min(x["start"] for x in p)
    # control: a carry inside a pause-free run still works ("... and" moves to the next page)
    run_ = [w("we", 0.0, 0.2), w("saw", 0.2, 0.4), w("the", 0.4, 0.6), w("guy", 0.6, 0.8), w("and", 0.8, 0.9), w("ran", 0.9, 1.1)]
    assert any(p[0]["word"] == "and" for p in group_words(run_, 3)) or all(
        not is_function_word(p[-1]["word"]) for p in group_words(run_, 3)[:-1])


def test_caption_reading_speed_is_at_most_20_cps_without_dropping_text(monkeypatch):
    fast = words_at("BRO THIS IS INSANE LOOK AT THAT RIGHT NOW WOW CRAZY STUFF", step=0.2)
    spec = {"words_per_caption": 4, "position": "lower"}
    ev = plan_captions(fast, spec, "tiktok", 1080, 1920, 96, 30.0)
    assert [w["word"] for e in ev for w in e.chunk] == [w["word"] for w in fast]  # every word still on screen
    for e in ev:
        assert caps_mod.page_chars(e) / (e.end - e.start) <= 20.01
    assert all(a.end <= b.start + 1e-6 for a, b in zip(ev, ev[1:]))  # pages never overlap
    monkeypatch.setattr(caps_mod, "_reading_speed", lambda events, d, h: events)  # control: without the pass it is faster
    raw = plan_captions(fast, spec, "tiktok", 1080, 1920, 96, 30.0)
    assert max(caps_mod.page_chars(e) / (e.end - e.start) for e in raw) > 20


def test_caption_cap_height_is_at_least_55_px_at_default_scale():
    for style in ("bold_pop", "karaoke", "minimal", "boxed", "outline"):
        doc = AssDoc(1080, 1920)
        caption_styles(doc, "Anton", {"style": style, "font_scale": 1.0})
        assert cap_px(doc.styles["Caption"].size) >= 55, style
    small = AssDoc(1080, 1920)
    caption_styles(small, "Anton", {"style": "bold_pop", "font_scale": 0.6})
    assert cap_px(small.styles["Caption"].size) < 55  # control: the floor only binds at the default scale


def test_rewind_label_is_big_dark_pill_with_icon_and_eases():
    doc = AssDoc(1080, 1920)
    caption_styles(doc, "Anton", {})
    overlay_styles(doc, "Anton", "Anton")
    rect = add_rewind_tag(doc, 2.0, 0.8, "tiktok", "")
    assert rect["size"] >= 90 and 120 <= rect["x0"] and rect["x1"] <= 1080  # ≥ 90 px, inside the safe zone
    labels = [e for e in doc.events if e[3] == "Label"]
    assert labels and all(f"\\fs{rect['size']}" in e[4] and e[4].endswith("REWIND") for e in labels)
    shapes = [e[4] for e in doc.events if e[3] == "Shape"]
    assert any("\\1a&H33&" in s for s in shapes) and any("\\1c&H00E6FF&" in s for s in shapes)  # dark pill + ◀◀ icon
    xs = [int(re.search(r"\\an4\\pos\((-?\d+),", e[4]).group(1)) for e in sorted(labels, key=lambda e: e[1])]
    ent = [b - a for a, b in zip(xs, xs[1:]) if b != a][:3]
    assert xs[0] < 0 and ent[0] > ent[-1] > 0  # slides in fast-then-slow (ease-out), never linear
    assert min(e[1] for e in labels) == 2.0 and max(e[2] for e in labels) == pytest.approx(2.8, abs=0.02)
    short = AssDoc(1080, 1920)
    overlay_styles(short, "Anton", "Anton")
    add_rewind_tag(short, 0.0, 0.8, "tiktok", "1 HR AGO")
    assert any(e[4].endswith("1 HR AGO") for e in short.events if e[3] == "Label")  # the part's time-jump label
    long_ = AssDoc(1080, 1920)
    overlay_styles(long_, "Anton", "Anton")
    add_rewind_tag(long_, 0.0, 0.8, "tiktok", "THREE MONTHS EARLIER")
    assert all(e[4].endswith("REWIND") for e in long_.events if e[3] == "Label")  # too long for the pill → REWIND
    assert int(1920 * 0.034) < 90  # control: the old "<< REW" tag was 65 px


def test_stack_title_squeezed_under_the_seam_pauses_captions_and_a_label_waits():
    doc = make_doc(font="Arial")  # a wide face: the long setup wraps to 3-4 lines and the band under the seam runs out
    seam = lambda t: 709  # noqa: E731
    hook = ov("hook_title", "I'M DOING THE RIGHT THING, YOU KNOW?", 0.0, 2.5, position="center")
    label = ov("label", "Twitch.tv/skiimasktimmy", 0.0, 10.0, position="upper")
    evs = plan_overlays(doc, [hook, label], "tiktok", 10, seam_at=seam, cap_size=98, cap_pad=0)
    title, wm = next(e for e in evs if e.kind == "hook_title"), next(e for e in evs if e.kind == "label")
    assert wm.start >= title.end - 1e-6  # no room under the title: the watermark appears when the title is gone
    assert not any(e.kind == "label" and e.start < title.end for e in evs)
    tall = ov("hook_title", "HIS UNBEATABLE DODGE STRAT", 0.0, 2.6, emphasis="DODGE STRAT", position="center")
    words = words_at("oh you can't hit me with a ball bro", step=0.4)
    spec = {"words_per_caption": 2, "position": "upper"}
    held = plan_captions(words, spec, "tiktok", 1080, 1920, 98, 10.0, seam, 0, caps_mod.title_holds([tall], "Arial"))
    assert held and all(e.start >= 2.6 or e.end <= 0.0 for e in held)  # captions yield for the whole title
    free = plan_captions(words, spec, "tiktok", 1080, 1920, 98, 10.0, seam, 0, caps_mod.title_holds([], "Arial"))
    assert any(e.start < 2.6 for e in free)  # control: without the hold they run under the title
    fit = ov("hook_title", "WHY PEOPLE FAIL", 0.0, 2.6, position="center")  # a short title fits: captions keep running
    keep = plan_captions(words, spec, "tiktok", 1080, 1920, 98, 10.0, seam, 0, caps_mod.title_holds([fit], "Arial"))
    assert any(e.start < 2.6 for e in keep)


# -- voice: game / NPC / ad audio is captioned differently from the streamer ----------------------------------
def voiced(words, voice):
    return [{**w, "voice": voice} for w in words]


def test_caption_voices_never_share_a_page_and_game_gets_its_own_pill_and_tag():
    st = voiced(words_at("I CANNOT BELIEVE THIS GAME NOW", t0=0.0), "streamer")
    gm = voiced(words_at("WE BELIEVE YOU'RE A PROFESSIONAL SOCIAL WORKER", t0=2.5), "game")
    st2 = voiced(words_at("BRO WHAT", t0=6.0), "streamer")
    gm2 = voiced(words_at("CALL ENDED", t0=7.0), "game")
    allw = st + gm + st2 + gm2
    spec = {"enabled": True, "style": "bold_pop", "words_per_caption": 4, "position": "lower"}
    ev = plan_captions(allw, spec, "tiktok", 1080, 1920, 98, 10.0)
    assert all(len({w["voice"] for w in e.chunk}) == 1 and e.voice == e.chunk[0]["voice"] for e in ev)
    assert [w["word"] for e in ev for w in e.chunk] == [w["word"] for w in allw]  # nothing dropped
    game_ev = [e for e in ev if e.voice == "game"]
    assert sum(e.tag for e in ev) == 2 and game_ev[0].tag and not game_ev[1].tag  # once per game BLOCK, first page
    doc = AssDoc(1080, 1920)
    caption_styles(doc, "Anton", spec)
    n = caps_mod.build_captions(doc, allw, spec, "tiktok", 10.0)
    assert n == len(ev)
    g, c, t = doc.styles["CaptionGame"], doc.styles["Caption"], doc.styles["CaptionTag"]
    assert g.border_style == 3 and c.border_style == 1 and cap_px(g.size) >= 55 and g.primary == "&H00FFFFFF"
    assert t.size == 32 and t.size < g.size
    games = [e for e in doc.events if e[3] == "CaptionGame"]
    assert games and not any("\\1c" in e[4] for e in games)  # no per-word yellow highlight on game lines
    assert any("\\1c" in e[4] for e in doc.events if e[3] == "Caption")  # control: the streamer still pops yellow
    tags = [e for e in doc.events if e[3] == "CaptionTag"]
    assert len(tags) == 2 and all(e[4].endswith("IN-GAME") for e in tags)
    assert max(caps_mod.page_chars(e) / (e.end - e.start) for e in ev) <= 20.01
    # "other": plain white, no highlight, no tag
    oth = AssDoc(1080, 1920)
    caption_styles(oth, "Anton", spec)
    caps_mod.build_captions(oth, voiced(words_at("HELLO THERE"), "other"), spec, "tiktok", 5.0)
    assert [e[3] for e in oth.events] == ["CaptionOther"] and "\\1c" not in oth.events[0][4]
    assert "CaptionTag" not in oth.styles


def test_caption_without_voice_is_unchanged():
    words = words_at("NO VOICE KEY ON THESE WORDS AT ALL OK", t0=0.0)
    spec = {"enabled": True, "style": "bold_pop", "words_per_caption": 3, "position": "lower"}
    a, b = AssDoc(1080, 1920), AssDoc(1080, 1920)
    caption_styles(a, "Anton", spec)
    caption_styles(b, "Anton", spec)
    caps_mod.build_captions(a, words, spec, "tiktok", 6.0)
    caps_mod.build_captions(b, voiced(words, "streamer"), spec, "tiktok", 6.0)  # explicit streamer = same as absent
    assert a.text() == b.text() and set(a.styles) == {"Caption"}
    assert all(e.voice == "streamer" and not e.tag for e in plan_captions(words, spec, "tiktok", 1080, 1920, 98, 6.0))


@needs_ffmpeg
def test_real_render_game_voice_looks_different(source, tmp_path):
    segs = [seg(0.0, 3.0), seg(3.0, 6.0, voice="game")]
    words = words_at("LOOK AT THIS GUY HERE", t0=0.2) + words_at("WE BELIEVE YOU ARE PRO", t0=3.2)
    plan = {"segments": segs, "captions": {"enabled": True, "style": "bold_pop", "position": "lower"}, "overlays": []}
    res = Renderer(RenderSpec(width=W, height=H, fps=FPS, preset="ultrafast")).render(plan, source, tmp_path / "v.mp4",
                                                                                       tmp_path / "w", words)
    ass = open(res.ass_path, encoding="utf-8").read()
    assert "CaptionGame" in ass and "IN-GAME" in ass
    yellow = lambda r, g, b: r > 245 and 215 < g < 245 and b < 25  # noqa: E731
    bare = Renderer(RenderSpec(width=W, height=H, fps=FPS, preset="ultrafast")).render(  # the picture alone (testsrc2 has yellow)
        {**plan, "captions": {"enabled": False}}, source, tmp_path / "b.mp4", tmp_path / "wb", words)
    base = lambda t: count_px(frame(bare.path, t), yellow)  # noqa: E731
    assert count_px(frame(res.path, 0.9), yellow) > base(0.9) + 20  # streamer: yellow pop word
    assert count_px(frame(res.path, 3.9), yellow) <= base(3.9) + 5  # game: no yellow added
