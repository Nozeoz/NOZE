"""QC v2 (design supervisor's first rejection, 3 Nov): checks that need no LLM and must go RED on the defect.

MF-1 title size / one size · MF-2 empty gameplay band (measured on a really rendered file) ·
MF-3 face measured on the OUTPUT beats the plan's guess · MF-4 watermark size + place.
Every check has a RED case and a GREEN case. Text sizes are injected through ``plan_overlays`` so these tests
do not depend on how the renderer sizes titles."""

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from noze.agency.media import faces, qc
from noze.agency.media.qc import empty_band_stretches, layout_lint, measure_cam_faces, stack_seams, technical_qc
from noze.agency.standards import LAYOUT, QC, standards_text
from noze.agency.media.ffmpeg import ffmpeg_bin

W, H = 1080, 1920
SRC = (1920, 1080)
CAM_OK = {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}  # band 708px = 37% of the frame
FACEBRIEF = {"requirements": {"other": ["Keep the streamer's facecam visible in every clip"]}}
MARK_BRIEF = {"requirements": {"watermark": "twitch.tv/x"}}
needs_ffmpeg = pytest.mark.skipif(not ffmpeg_bin(), reason="ffmpeg not installed")
REAL_FRAME = Path(__file__).resolve().parents[1] / "noze-data/agency/review/noze-studio-r1/final/debug_0000.20.jpg"


@pytest.fixture(autouse=True)
def estimated_font(monkeypatch):
    monkeypatch.setattr(qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")


def seg(a, b, mode="center", cam=None):
    return {"src_start": a, "src_end": b, "speed": 1.0, "reframe": {"mode": mode, "x": 0.5, "cam": cam},
            "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut", "note": ""}


def plan_of(overlays, segments=None, face=None):
    # built by hand (not conform()) so kinds the schema may not know yet (punch_title) survive
    p = {"segments": segments or [seg(0, 10)], "captions": {"enabled": False}, "overlays": overlays}
    if face:
        p["segments"][0]["reframe"]["face"] = face
    return p


def ov(kind, text, position="top", start=0.0, end=3.0):
    return {"kind": kind, "text": text, "start": start, "end": end, "position": position, "style": "pop"}


def lint(plan, brief=None, **kw):
    return layout_lint(plan, brief or {}, words=[], width=W, height=H, platform="tiktok", src_size=SRC, **kw)


def ids(issues):
    return {i["id"] for i in issues}


def sev(issues, iid):
    return next(i["severity"] for i in issues if i["id"] == iid)


_PLAN_OVERLAYS = qc.plan_overlays


def force_sizes(monkeypatch, sizes):
    """Every overlay event leaves plan_overlays with these font sizes per line (OvEvent.sizes contract; the last
    size repeats when the writer produced more lines)."""
    def patched(*a, **k):
        evs = _PLAN_OVERLAYS(*a, **k)
        for ev in evs:
            ev.sizes = (list(sizes) + [sizes[-1]] * len(ev.lines))[:len(ev.lines)]
        return evs
    monkeypatch.setattr(qc, "plan_overlays", patched)


TWO_LINES = "HUGE WIN HERE SO FAST"  # wraps to two lines in the title style


# MF-1 title size -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["hook_title", "punch_title"])
def test_small_title_is_red_and_a_big_one_green(monkeypatch, kind):
    force_sizes(monkeypatch, [38])  # the supervisor's ~35px "title": a caption in disguise
    bad = lint(plan_of([ov(kind, "WHY", "center")]))
    assert f"layout:{kind}_small" in ids(bad) and sev(bad, f"layout:{kind}_small") == "major"
    force_sizes(monkeypatch, [LAYOUT["hook_title_max_word_px"] + 20])
    assert f"layout:{kind}_small" not in ids(lint(plan_of([ov(kind, "WHY", "center")])))


@pytest.mark.parametrize("kind", ["hook_title", "punch_title"])
def test_two_lines_at_one_size_is_red_and_stepped_sizes_are_green(monkeypatch, kind):
    plan = plan_of([ov(kind, TWO_LINES, "center")])
    force_sizes(monkeypatch, [120, 120])
    bad = lint(plan)
    assert f"layout:{kind}_one_size" in ids(bad) and sev(bad, f"layout:{kind}_one_size") == "major"
    assert f"layout:{kind}_small" not in ids(bad)  # 120px is big enough; only the flat sizes are the defect
    force_sizes(monkeypatch, [130, 60])
    ok = ids(lint(plan))
    assert not {f"layout:{kind}_one_size", f"layout:{kind}_small"} & ok


def test_title_box_grows_with_its_per_line_sizes(monkeypatch):
    """The lint measures the boxes it judges collisions with from the real sizes, not the style's."""
    seen = {}
    for sizes in ([60, 60], [140, 60]):
        force_sizes(monkeypatch, sizes)
        dbg = {}
        lint(plan_of([ov("hook_title", TWO_LINES, "center")]), debug=dbg)
        box = next(ly["box"] for ly in dbg["layers"] if ly["kind"] == "hook_title")
        seen[tuple(sizes)] = box[3] - box[1]
    assert seen[(140, 60)] - seen[(60, 60)] == pytest.approx(80, abs=1)


# MF-4 watermark ------------------------------------------------------------------------------------------
def test_small_watermark_is_red_and_a_64px_one_green(monkeypatch):
    mark = plan_of([ov("label", "twitch.tv/x", "bottom", 0.0, 10.0)])
    force_sizes(monkeypatch, [40])
    bad = lint(mark, MARK_BRIEF)
    assert "layout:watermark_small" in ids(bad) and sev(bad, "layout:watermark_small") == "major"
    force_sizes(monkeypatch, [LAYOUT["watermark_min_px"]])
    assert "layout:watermark_small" not in ids(lint(mark, MARK_BRIEF))


def test_watermark_in_the_middle_of_the_action_is_red_bottom_or_top_green(monkeypatch):
    force_sizes(monkeypatch, [LAYOUT["watermark_min_px"]])
    mid = lint(plan_of([ov("label", "twitch.tv/x", "center", 0.0, 10.0)]), MARK_BRIEF)
    assert "layout:watermark_misplaced" in ids(mid) and sev(mid, "layout:watermark_misplaced") == "minor"
    for where in ("bottom", "top"):
        ok = lint(plan_of([ov("label", "twitch.tv/x", where, 0.0, 10.0)]), MARK_BRIEF)
        assert "layout:watermark_misplaced" not in ids(ok), where


# MF-3 measured face --------------------------------------------------------------------------------------
def stacked(face=None, brief_cam=CAM_OK):
    return plan_of([], [seg(0, 10, "stack", brief_cam)], face)


def band_of(plan):
    return stack_seams(plan, SRC, W, H)[0][2]


def frac(box, band):  # px box -> reframe.face (fractions of the cam band)
    return {"x": box[0] / W, "y": box[1] / band, "w": box[2] / W, "h": box[3] / band}


REAL_FACE = (440, 200, 260, 260)  # a head filling 37% of the 708px cam band, centred right of the chair
CHAIR = (260, 85, 280, 305)  # the plan's guess on the first approved clip: the empty chair


def measured(box, hits=5, n=5, at=0.0):
    return {round(at, 2): {"box": box, "hits": hits, "n": n}}


def test_plan_face_on_the_chair_disagrees_with_the_measured_face():
    p = stacked()
    band = band_of(p)
    p["segments"][0]["reframe"]["face"] = frac(CHAIR, band)
    bad = lint(p, measured_faces=measured(REAL_FACE))
    assert "layout:plan_face_mismatch" in ids(bad) and sev(bad, "layout:plan_face_mismatch") == "minor"  # renderer never reads reframe.face
    p["segments"][0]["reframe"]["face"] = frac(REAL_FACE, band)  # plan and frame agree
    assert "layout:plan_face_mismatch" not in ids(lint(p, measured_faces=measured(REAL_FACE)))


def test_the_measured_face_drives_the_face_checks_not_the_plan():
    p = stacked()
    band = band_of(p)
    tiny = (500, 300, 120, 100)  # a plan face this small is "face_small" …
    p["segments"][0]["reframe"]["face"] = frac(tiny, band)
    assert "layout:face_small" in ids(lint(p))  # no measurement: the plan's box is judged (old behaviour)
    # … but the face on the output is big and centred, and that is what counts
    assert "layout:face_small" not in ids(lint(p, measured_faces=measured(REAL_FACE)))
    # the other way round: a fine plan box, but the frame shows a face hugging the band edge
    p["segments"][0]["reframe"]["face"] = frac(REAL_FACE, band)
    edge = (960, 20, 100, 100)
    assert "layout:face_off_centre" in ids(lint(p, measured_faces=measured(edge)))
    assert "layout:face_off_centre" not in ids(lint(p))


def test_text_over_the_measured_face_is_caught_even_without_a_plan_face():
    p = stacked()  # no plan face at all
    p["overlays"] = [ov("label", "BEAT", "top", 1.0, 3.0)]
    on_face = lint(p, measured_faces=measured((300, 120, 300, 300)))
    assert any(i.startswith("layout:over_face_") for i in ids(on_face))


def test_brief_needs_the_facecam_but_no_face_is_found():
    p = stacked()
    red = lint(p, FACEBRIEF, measured_faces=measured(None, hits=1, n=5))
    assert "layout:face_not_found" in ids(red) and sev(red, "layout:face_not_found") == "major"
    assert "layout:face_not_found" not in ids(lint(p, FACEBRIEF, measured_faces=measured(REAL_FACE, hits=3, n=5)))
    assert "layout:face_not_found" not in ids(lint(p, {}, measured_faces=measured(None, hits=0, n=5)))  # no facecam asked
    assert "layout:face_not_found" not in ids(lint(p, FACEBRIEF))  # not measured (no OpenCV): plan stays the fallback


def test_iou():
    assert qc._iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert qc._iou((0, 0, 10, 10), (20, 20, 5, 5)) == 0.0
    assert qc._iou(CHAIR, REAL_FACE) < LAYOUT["face_iou_min"]


@pytest.mark.skipif(not faces.available() or not REAL_FRAME.exists(), reason="OpenCV Haar or the real frame missing")
def test_opencv_finds_the_real_face_not_the_chair():
    found = faces.faces_in_band([(REAL_FRAME, 580)])
    assert found and found[0], "no face detected on the real frame"
    x, y, w, h = found[0]
    cx, cy = x + w / 2, y + h / 2
    assert 540 <= cx <= 760 and 300 <= cy <= 520, found  # the supervisor's real face area
    assert qc._iou((x, y, w, h), CHAIR) < LAYOUT["face_iou_min"]  # not the plan's chair box
    assert y + h <= 580  # never reports the gameplay band


@needs_ffmpeg
@pytest.mark.skipif(not faces.available() or not REAL_FRAME.exists(), reason="OpenCV Haar or the real frame missing")
def test_measure_cam_faces_on_a_rendered_file_and_lint_flags_the_chair_plan(tmp_path):
    clip = tmp_path / "real.mp4"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-loop", "1", "-i", str(REAL_FRAME), "-t", "4", "-r", "10",
                    "-vf", "scale=1080:1920,format=yuv420p", "-y", str(clip)], check=True)
    p = stacked()
    seams = stack_seams(p, SRC, W, H)
    m = measure_cam_faces(str(clip), seams, tmp_path / "cam")
    assert m and m[0.0]["hits"] == m[0.0]["n"] >= 2
    assert 540 <= m[0.0]["box"][0] + m[0.0]["box"][2] / 2 <= 760
    p["segments"][0]["reframe"]["face"] = frac(CHAIR, seams[0][2])
    assert "layout:plan_face_mismatch" in ids(lint(p, FACEBRIEF, measured_faces=m))


def test_no_opencv_means_no_measurement_not_no_face(monkeypatch, tmp_path):
    monkeypatch.setattr(qc.face_finder, "available", lambda: False)
    assert measure_cam_faces("x.mp4", [(0.0, 5.0, 700, {})], tmp_path) is None


# MF-2 empty gameplay band --------------------------------------------------------------------------------
def make_clip(path, graph, seconds):
    subprocess.run([ffmpeg_bin(), "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=360x640:d={seconds}:r=10",
                    "-f", "lavfi", "-i", f"color=c=0x335577:s=360x640:d={seconds}:r=10", "-filter_complex", graph,
                    "-pix_fmt", "yuv420p", "-an", "-y", str(path)], check=True)
    return str(path)


@needs_ffmpeg
def test_flat_stretch_is_flagged_and_an_all_busy_clip_is_clean(tmp_path):
    # 3 s of busy test pattern, then 4 s of one flat colour
    clip = make_clip(tmp_path / "empty.mp4", "[0]trim=0:3,setpts=PTS-STARTPTS[a];[1]trim=0:4,setpts=PTS-STARTPTS[b];"
                     "[a][b]concat=n=2:v=1:a=0", 7)
    found = empty_band_stretches(clip, [], 360, 640, 7.0)
    assert len(found) == 1 and 2.5 <= found[0][0] <= 3.5 and found[0][1] >= 6.5, found
    busy = make_clip(tmp_path / "busy.mp4", "[0]trim=0:7,setpts=PTS-STARTPTS", 7)
    assert empty_band_stretches(busy, [], 360, 640, 7.0) == []
    # a flat stretch within the allowance (<= 2 s) is not an empty stage
    short = make_clip(tmp_path / "short.mp4", "[0]split[s0][s1];[s0]trim=0:3,setpts=PTS-STARTPTS[a];"
                      "[1]trim=0:1.5,setpts=PTS-STARTPTS[b];[s1]trim=3:6,setpts=PTS-STARTPTS[c];"
                      "[a][b][c]concat=n=3:v=1:a=0", 7)
    assert empty_band_stretches(short, [], 360, 640, 7.5) == []


REAL_CLIP = REAL_FRAME.parent / "00010_timmy-s-left-one-boss-strat.mp4"


@needs_ffmpeg
@pytest.mark.skipif(not REAL_CLIP.exists(), reason="the first approved clip is not on this machine")
def test_the_real_rejected_clip_has_its_empty_stage_flagged():
    """The supervisor's MF-2: ~9 s of one flat colour + a letterbox bar + a 70px square. A static bar alone puts
    28% of the band 'away from the median', so the bare-share rule alone says clean (measured: it did); the stillness
    rule is what catches it."""
    from noze.agency.media.ffmpeg import probe

    d = probe(str(REAL_CLIP))["duration"]
    found = empty_band_stretches(str(REAL_CLIP), [(0.0, d, 580, {})], 1080, 1920, d)
    assert found and found[-1][0] <= 28 and found[-1][1] >= d - 1.0 and found[-1][1] - found[-1][0] >= 6.0, found
    assert all(a > 20 for a, _, _ in found)  # the first 20 s (a chat-heavy but moving gameplay band) are not empty


@needs_ffmpeg
def test_only_the_gameplay_band_below_the_seam_counts(tmp_path):
    seam = 320
    seams = [(0.0, 7.0, seam, {})]
    # flat facecam on top, busy gameplay below -> fine (the cam being static is normal)
    ok = make_clip(tmp_path / "ok.mp4", "[1]crop=360:320:0:0[t];[0]crop=360:320:0:320[g];[t][g]vstack", 7)
    assert empty_band_stretches(ok, seams, 360, 640, 7.0) == []
    # busy facecam on top, flat gameplay below -> the stage is empty although the picture as a whole moves
    bad = make_clip(tmp_path / "bad.mp4", "[0]crop=360:320:0:0[t];[1]crop=360:320:0:320[g];[t][g]vstack", 7)
    found = empty_band_stretches(bad, seams, 360, 640, 7.0)
    assert found and found[0][1] - found[0][0] > QC["empty_band_max_s"]
    assert empty_band_stretches(bad, [], 360, 640, 7.0) == []  # judged as a whole frame it looks busy


@needs_ffmpeg
def test_technical_qc_reports_the_empty_stretch_with_timecodes(tmp_path):
    clip = make_clip(tmp_path / "empty.mp4", "[0]trim=0:3,setpts=PTS-STARTPTS[a];[1]trim=0:4,setpts=PTS-STARTPTS[b];"
                     "[a][b]concat=n=2:v=1:a=0", 7)
    issues, m = technical_qc(clip, width=360, height=640, fps=10, target_lufs=-14.0, min_s=5, max_s=60,
                             platform="tiktok")
    hit = next(i for i in issues if i["id"] == "visual:empty_band")
    assert hit["severity"] == "major" and 2.5 <= hit["timecode_s"] <= 3.5 and "-" in hit["description"]
    assert m["empty_band"] and hit["evidence"]["end"] >= 6.5
    busy = make_clip(tmp_path / "busy.mp4", "[0]trim=0:7,setpts=PTS-STARTPTS", 7)
    issues, m = technical_qc(busy, width=360, height=640, fps=10, target_lufs=-14.0, min_s=5, max_s=60,
                             platform="tiktok")
    assert "visual:empty_band" not in ids(issues) and m["empty_band"] == []


def test_a_still_band_is_minor_until_twice_the_allowance_and_a_bare_one_always_major():
    """Reviewer 3 Nov: a busy-but-static UI (board game, menu) is not a bare stage — only long stillness costs a round."""
    from noze.agency.media.qc import empty_band_issues

    sev = {name: empty_band_issues([s])[0]["severity"] for name, s in (
        ("still_short", (1.0, 4.0, False)), ("still_long", (1.0, 6.0, False)), ("bare_short", (1.0, 3.5, True)))}
    assert sev == {"still_short": "minor", "still_long": "major", "bare_short": "major"}


# the reviewer wires it all together, without an LLM -----------------------------------------------------------
@needs_ffmpeg
@pytest.mark.skipif(not faces.available() or not REAL_FRAME.exists(), reason="OpenCV Haar or the real frame missing")
def test_reviewer_catches_small_title_wrong_face_and_small_watermark_without_an_llm(tmp_path, monkeypatch):
    from noze.agency.config import AgencySettings
    from noze.agency.context import AgencyContext
    from noze.agency.roles.reviewer import Reviewer
    from noze.config import Settings

    clip = tmp_path / "real.mp4"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-loop", "1", "-i", str(REAL_FRAME), "-t", "4", "-r", "10",
                    "-vf", "scale=1080:1920,format=yuv420p", "-y", str(clip)], check=True)
    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off", "NOZE_DATA_DIR": str(tmp_path / "d")}
    ax = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    try:
        rv = Reviewer(ax)
        monkeypatch.setattr(Reviewer, "_source_size", lambda self, job: SRC)
        force_sizes(monkeypatch, [36])  # a 36px hook title and a 36px watermark, as in the rejected clip
        plan = plan_of([ov("hook_title", "WHY", "center", 0.0, 3.0), ov("label", "twitch.tv/x", "center", 0.0, 4.0)],
                       [seg(0, 4, "stack", CAM_OK)])
        plan["segments"][0]["reframe"]["face"] = frac(CHAIR, band_of(plan))
        brief = {"requirements": {"watermark": "twitch.tv/x", **FACEBRIEF["requirements"]}}
        out = rv.review({"parent_id": 1}, plan, {"path": str(clip)}, brief, {}, [], 1, [])
    finally:
        ax.close()
    got = {i["id"]: i for i in out["issues"]}
    assert not out["creative_review"] and out["verdict"] == "fail"
    for must in ("layout:hook_title_small", "layout:watermark_small", "layout:watermark_misplaced",
                 "layout:plan_face_mismatch"):
        assert must in got, (must, sorted(got))
    assert out["metrics"]["cam_faces"] and not any("OpenCV" in n for n in out["metrics"]["layout_notes"])


def test_the_standards_text_tells_the_editor_the_new_rules():
    t = standards_text("tiktok", -14.0, W, H, 30)
    assert str(LAYOUT["hook_title_max_word_px"]) in t and "empty stage" in t.lower() and "IoU" in t
    assert str(LAYOUT["watermark_min_px"]) in t and "bottom 25%" in t
