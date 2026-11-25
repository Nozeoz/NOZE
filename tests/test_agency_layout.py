"""Layout lint (media/qc.layout_lint) and the honest no-LLM review: every check has a bad plan that must go
RED and a good plan that must stay green, and a QC-only review can never be approved automatically.
Pure geometry tests need no ffmpeg; the pipeline test at the bottom does."""

import shutil

import pytest

from noze.agency.config import AgencySettings
from noze.agency.context import AgencyContext
from noze.agency.media import qc
from noze.agency.media.captions import Meter
from noze.agency.media.qc import layout_lint
from noze.agency.media.transcribe import spread_words
from noze.agency.roles.editor import Editor
from noze.agency.roles.manager import Manager
from noze.agency.schemas import EDIT_PLAN, conform
from noze.agency.standards import LAYOUT
from noze.config import Settings

W, H = 1080, 1920
SRC = (1920, 1080)
CAM_OK = {"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.35}  # band 709px = 37% of the frame
FACEBRIEF = {"requirements": {"other": ["Keep the streamer's facecam visible in every clip"]}}


@pytest.fixture(autouse=True)
def estimated_font(monkeypatch):
    """Deterministic on every machine: no font file → the conservative per-character estimate."""
    monkeypatch.setattr(qc, "pick_font", lambda *a, **k: "NoSuchFontForTests")


def seg(a, b, mode="center", cam=None, **kw):
    return {"src_start": a, "src_end": b, "speed": 1.0, "reframe": {"mode": mode, "x": 0.5, "cam": cam},
            "zoom": {"type": "none", "scale": 1.0}, "shake": False, "transition_in": "cut", "note": "", **kw}


def make_plan(segments=None, captions=None, overlays=None):
    return conform({"segments": segments or [seg(0, 10)], "captions": captions or {"enabled": False},
                    "overlays": overlays or []}, EDIT_PLAN)


def ov(kind, text, start=0.0, end=2.5, position=None):
    return {"kind": kind, "text": text, "start": start, "end": end, "position": position or "top", "style": "pop"}


def lint(plan, brief=None, words=None, src=SRC, notes=None, platform="tiktok"):
    return layout_lint(plan, brief or {}, words=words or [], width=W, height=H, platform=platform,
                       src_size=src, notes=notes)


def ids(issues):
    return {i["id"] for i in issues}


def sev(issues, iid):
    return next(i["severity"] for i in issues if i["id"] == iid)


WORDS = spread_words("why do most people fail at saving money", 0.0, 6.0)
CAPS = {"enabled": True, "style": "bold_pop", "words_per_caption": 2, "position": "lower", "font_scale": 1.0}


def good_plan():
    return make_plan(captions=CAPS, overlays=[ov("hook_title", "WHY PEOPLE FAIL", 0.0, 2.5, "top")])


def test_good_plan_is_clean():
    assert lint(good_plan(), words=WORDS) == []


# (a) frame / safe zone ------------------------------------------------------------------------------
def test_text_outside_the_frame_is_a_blocker():
    bad = make_plan(overlays=[ov("hook_title", "SUPERCALIFRAGILISTICEXPIALIDOCIOUSLYLONGWORD", position="top")])
    found = lint(bad)
    assert "layout:clipped_hook_title" in ids(found) and sev(found, "layout:clipped_hook_title") == "blocker"
    assert next(i for i in found if i["id"] == "layout:clipped_hook_title")["evidence"]["font_metrics"] == "estimated"
    assert not ids(lint(make_plan(overlays=[ov("hook_title", "SHORT HOOK")])))


def test_text_in_the_platform_ui_band_is_major():
    wide = "ABCDEFGHIJKLMNOPQRSTUVWXYZABCD"  # inside the frame, outside the left/right safe margins
    bad = lint(make_plan(overlays=[ov("label", wide, position="center")]))
    assert "layout:safe_zone_label" in ids(bad) and "layout:clipped_label" not in ids(bad)
    assert sev(bad, "layout:safe_zone_label") == "major"
    assert not ids(lint(make_plan(overlays=[ov("label", "ABCDEFGHIJ", position="center")])))


def test_two_line_title_is_pulled_back_inside_the_safe_zone():
    long_title = "STOP DOING THIS RIGHT NOW"  # wraps to 2 lines; centred on the 'top' anchor it poked out
    assert not ids(lint(make_plan(overlays=[ov("hook_title", long_title, position="top")])))


# (b) collisions -------------------------------------------------------------------------------------
def test_overlapping_layers_are_major_and_a_gap_is_minor():
    bad = lint(make_plan(overlays=[ov("hook_title", "ONE", 0, 2.5, "center"), ov("label", "TWO", 1.0, 3.0, "center")]))
    assert "layout:overlap_hook_title_label" in ids(bad) and sev(bad, "layout:overlap_hook_title_label") == "major"
    apart = lint(make_plan(overlays=[ov("hook_title", "ONE", 0, 2.5, "top"), ov("label", "TWO", 1.0, 3.0, "lower")]))
    assert not any(i.startswith("layout:overlap") or i.startswith("layout:gap") for i in ids(apart))
    sequential = lint(make_plan(overlays=[ov("hook_title", "ONE", 0, 2.0, "center"), ov("label", "TWO", 2.0, 4.0, "center")]))
    assert not ids(sequential)  # same place but never visible together


def wm(text, start=0.0, end=10.0):
    """The house watermark (Editor.enforce_compliance): bottom-left on a dark pill."""
    return {**ov("label", text, start, end, "bottom"), "align": "left", "box": True}


def test_watermark_on_the_caption_strip_is_caught_and_declutter_fixes_it():
    mark = wm("twitch.tv/x")
    plan = make_plan(captions={**CAPS, "words_per_caption": 3}, overlays=[mark])
    brief = {"requirements": {"watermark": "twitch.tv/x"}}
    bad = lint(plan, brief, WORDS)
    assert any(i.startswith("layout:overlap_") or i.startswith("layout:gap_") for i in ids(bad))
    Editor._declutter(plan, 10.0)
    assert plan["captions"]["position"] == "center"
    assert not ids(lint(plan, brief, WORDS))


# (c) stacked layout ---------------------------------------------------------------------------------
def stacked(cam=CAM_OK, overlays=None, captions=None, zoom=None, face=None):
    plan = make_plan([seg(0, 10, "stack", cam)], captions, overlays)
    # set after conform() so tests can use zoom values beyond the schema's range
    if face:
        plan["segments"][0]["reframe"]["face"] = face
    if zoom:
        plan["segments"][0]["zoom"] = zoom
    return plan


def test_facecam_band_share():
    assert not ids(lint(stacked()))
    thin = lint(stacked({"x": 0.6, "y": 0.0, "w": 0.4, "h": 0.1}))  # ultra-wide cam → band at the 26% floor
    assert "layout:cam_small" in ids(thin) and sev(thin, "layout:cam_small") == "major"
    warn = lint(stacked({"x": 0.7, "y": 0.0, "w": 0.3, "h": 0.3}))  # 31.6%: passes 30%, under the 33% aim
    assert ids(warn) == {"layout:cam_small_warn"} and sev(warn, "layout:cam_small_warn") == "minor"


def test_text_over_the_face_and_title_in_the_cam_band():
    bad = lint(stacked(overlays=[ov("label", "BEAT", 1, 3, "top")]))
    assert "layout:over_face_label" in ids(bad)
    assert not ids(lint(stacked(overlays=[ov("label", "BEAT", 1, 3, "lower")])))
    title = lint(stacked(overlays=[ov("hook_title", "WHY PEOPLE FAIL", 0, 2.5, "top")]))
    assert "layout:hook_in_cam_band" in ids(title) and sev(title, "layout:hook_in_cam_band") == "major"
    assert not ids(lint(stacked(overlays=[ov("hook_title", "WHY PEOPLE FAIL", 0, 2.5, "lower")])))


def test_captions_on_the_seam_stay_off_the_face_unless_the_chunk_grows_into_it():
    one_line = {**CAPS, "words_per_caption": 1, "position": "upper"}
    assert not ids(lint(stacked(captions=one_line), words=WORDS))
    # a tiny cam band with a face box that reaches the seam: the seam caption now lands on the face
    face = {"x": 0.3, "y": 0.55, "w": 0.4, "h": 0.6}  # the face itself (not just the chin) runs down to the seam
    assert "layout:over_face_caption" in ids(lint(stacked(captions=one_line, face=face), words=WORDS))


def test_face_box_checks_run_only_when_the_plan_has_one():
    notes: list[str] = []
    lint(stacked(), notes=notes)
    assert any("no face box" in n for n in notes)
    good = lint(stacked(face={"x": 0.35, "y": 0.35, "w": 0.3, "h": 0.5}))
    assert not ids(good)
    bad = lint(stacked(face={"x": 0.4, "y": 0.0, "w": 0.2, "h": 0.1}))
    assert {"layout:face_small", "layout:eye_line_high", "layout:face_off_centre"} <= ids(bad)


def test_upscale_checks_need_the_source_size():
    tiny_cam = {"x": 0.7, "y": 0.0, "w": 0.15, "h": 0.2}
    assert "layout:cam_upscale" in ids(lint(stacked(tiny_cam)))
    assert "layout:cam_upscale" not in ids(lint(stacked()))
    punch = lint(stacked(zoom={"type": "punch", "scale": 1.4}))  # 1.12x geometry × 1.4 zoom > 1.5x
    assert "layout:game_upscale" in ids(punch)
    notes: list[str] = []
    assert "layout:cam_upscale" not in ids(lint(stacked(tiny_cam), src=None, notes=notes))
    assert any("source size unknown" in n for n in notes)


# (d) facecam visible ----------------------------------------------------------------------------------
def test_required_facecam_must_be_visible_in_every_segment():
    hidden = lint(make_plan([seg(0, 5, "stack", CAM_OK), seg(5, 10, "fill")]), FACEBRIEF)
    assert "layout:facecam_hidden" in ids(hidden) and sev(hidden, "layout:facecam_hidden") == "blocker"
    assert not ids(lint(make_plan([seg(0, 5, "stack", CAM_OK), seg(5, 10, "fit_blur")]), FACEBRIEF))
    assert "layout:facecam_hidden" not in ids(lint(make_plan([seg(0, 10, "fill")])))  # brief doesn't ask for it
    assert not ids(lint(make_plan([seg(0, 10, "fill")]), FACEBRIEF, src=(1080, 1920)))  # vertical source: all visible


# captions / hook / watermark rules ----------------------------------------------------------------------
def test_caption_size_and_line_rules():
    small = lint(make_plan(captions={**CAPS, "font_scale": 0.7}), words=WORDS)
    assert "layout:caption_small" in ids(small) and sev(small, "layout:caption_small") == "major"
    assert "layout:caption_small" not in ids(lint(make_plan(captions=CAPS), words=WORDS))
    # the writer never lets a chunk take a third line, so the lint stays green however long the words are
    long_words = spread_words("EXTRAORDINARILY UNBELIEVABLY INCOMPREHENSIBLE WONDERFUL", 0.0, 6.0)
    assert "layout:caption_lines" not in ids(lint(make_plan(captions={**CAPS, "words_per_caption": 4}), words=long_words))


def test_hook_title_rules():
    late = lint(make_plan(overlays=[ov("hook_title", "WHY PEOPLE FAIL", 0.4, 3.0)]))
    assert "layout:hook_late" in ids(late)
    short = lint(make_plan(overlays=[ov("hook_title", "WHY PEOPLE FAIL", 0.0, 1.0)]))
    assert "layout:hook_short" in ids(short)
    long = lint(make_plan(overlays=[ov("hook_title", "ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT", 0.0, 2.5)]))
    assert "layout:hook_long" in ids(long) and sev(long, "layout:hook_long") == "minor"
    assert not ids(lint(make_plan(overlays=[ov("hook_title", "ONE TWO THREE", 0.0, 2.5)])))


def test_watermark_rules(monkeypatch):
    brief = {"requirements": {"watermark": "twitch.tv/x"}}
    long_mark = "twitch.tv/averylongstreamer1"
    fine = make_plan(overlays=[wm("twitch.tv/x")])
    assert not ids(lint(fine, brief))
    plain = make_plan(overlays=[ov("label", "twitch.tv/x", 0.0, 10.0, "bottom")])  # a plain 53 px label is too small
    assert "layout:watermark_small" in ids(lint(plain, brief))
    wide = make_plan(overlays=[ov("label", long_mark, 0.0, 10.0, "bottom")])
    assert "layout:watermark_column" in ids(lint(wide, {"requirements": {"watermark": long_mark}}))
    monkeypatch.setitem(LAYOUT, "watermark_min_px", 80)  # positive control for the size rule (the pill is 65px)
    assert "layout:watermark_small" in ids(lint(fine, brief))


def test_measured_font_beats_the_estimate():
    from pathlib import Path

    arial = Path("C:/Windows/Fonts/arial.ttf")
    if not arial.exists():
        pytest.skip("needs a real font file")
    m = Meter(arial.parent, "Arial")
    assert m.measured and 0.5 < m.cap_ratio < 0.75 and 0 < m.width("WHY", 100) < 300
    assert not Meter(None, "NoSuchFontForTests").measured


# honest review without an LLM ---------------------------------------------------------------------------
def test_qc_only_review_is_never_approved_automatically():
    qc_only = {"review": {"verdict": "pass", "score": 9.6, "issues": [], "creative_review": False}}
    reviewed = {"review": {"verdict": "pass", "score": 9.0, "issues": [], "creative_review": True}}
    assert Manager.needs_human(qc_only) == "no creative review (Claude unavailable) — needs your ACC"
    assert Manager.needs_human(reviewed) is None
    assert Manager.needs_human({"review": {}})  # a review without the flag (older code) proves no creative pass
    mgr = Manager.__new__(Manager)  # the heuristic needs no context
    for escalation in (False, True):
        assert mgr._heuristic_approve(qc_only, escalation)["decision"] != "approve"
    assert mgr._heuristic_approve(reviewed, False)["decision"] == "approve"  # positive control


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_heuristic_pipeline_parks_the_clip_for_a_human(tmp_path):
    from noze.agency.media.ffmpeg import run
    from noze.agency.pipeline import Agency

    video = tmp_path / "talk.mp4"
    run(["-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15:duration=30", "-f", "lavfi",
         "-i", "sine=frequency=200:duration=30:sample_rate=48000", "-af", "volume=0.4", "-c:v", "libx264",
         "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(video)])
    srt = []
    for i in range(8):
        srt.append(f"{i + 1}\n00:00:{1 + 2 * i:02d},000 --> 00:00:{2 + 2 * i:02d},500\nWords number {i} are spoken here!\n")
    (tmp_path / "talk.srt").write_text("\n".join(srt))
    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "NOZE_DATA_DIR": str(tmp_path / "bank"), "AGENCY_LLM": "off",
           "AGENCY_WIDTH": "360", "AGENCY_HEIGHT": "640", "AGENCY_FPS": "15", "AGENCY_MIN_CLIP_S": "8",
           "AGENCY_MAX_CLIP_S": "20", "AGENCY_CLIPS_PER_SOURCE": "1"}  # auto-approve stays ON (the default)
    ax = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    ag = Agency(ax)
    ag.submit(str(video), own_content=True)
    ag.run(once=True, idle_sleep=0)
    clip = next(j for j in ax.store.list_jobs(limit=50) if j["kind"] == "clip")
    rev = ax.store.artifact(clip["id"], "review")["data"]
    assert rev["creative_review"] is False and rev["summary"].startswith("QC-only, no creative review")
    assert clip["state"] == "awaiting_human", ax.store.events(clip["id"])
    assert "needs your ACC" in clip["data"]["hold_reason"]
    assert ag.decide(clip["id"], "approve") == "approved"  # the human gate still works
    ax.close()


# fixes from the first live run ------------------------------------------------------------------------
def test_centred_hook_title_clears_the_seam_caption(monkeypatch):
    """Live run 3 Nov: a 3-line hook title centred at y=750 touched the seam caption for 3 rounds."""
    caps = {**CAPS, "words_per_caption": 1, "position": "upper"}
    hook = [ov("hook_title", "I'M DOING THE RIGHT THING, YOU KNOW?", 0.0, 2.5, "center")]
    assert "layout:overlap_caption_hook_title" not in ids(lint(stacked(overlays=hook, captions=caps), words=WORDS))
    # live run 3 Nov #3: a label at "upper" and a centred title were both pushed under the seam onto one spot
    both = hook + [ov("label", "Twitch.tv/skiimasktimmy", 0.0, 10.0, "upper")]
    assert not {i for i in ids(lint(stacked(overlays=both, captions=caps), words=WORDS)) if "overlap" in i}
    # positive control: the same layout without the seam-aware placement does collide
    real = qc.plan_overlays
    monkeypatch.setattr(qc, "plan_overlays", lambda doc, o, p, d, *a, **k: real(doc, o, p, d))
    assert "layout:overlap_caption_hook_title" in ids(lint(stacked(overlays=hook, captions=caps), words=WORDS))


def test_detector_cam_is_widened_to_the_upscale_limit_and_the_face_follows():
    from noze.agency.media.render import stack_layout
    from noze.agency.roles.editor import fit_cam_upscale, reproject_box

    cam = {"x": 0.0, "y": 0.0, "w": 0.215, "h": 0.215}  # what the detector gives a 1080p streamer cam: 2.6x
    wide = fit_cam_upscale(cam, *SRC, W, H, LAYOUT["cam_max_upscale"])
    top, _ = stack_layout(wide, *SRC, W, H)
    assert max(W / (wide["w"] * SRC[0]), top / (wide["h"] * SRC[1])) <= LAYOUT["cam_max_upscale"]
    assert fit_cam_upscale(wide, *SRC, W, H, LAYOUT["cam_max_upscale"]) == wide  # idempotent
    face = {"x": 0.4, "y": 0.3, "w": 0.23, "h": 0.4}
    back = reproject_box(reproject_box(face, cam, wide), wide, cam)
    assert all(abs(back[k] - face[k]) < 0.01 for k in face)
    # a model that picks a 2x wider cam: the detector's face box must shrink with it, not be pasted as-is
    moved = reproject_box(face, {"x": 0.75, "y": 0.0, "w": 0.25, "h": 0.25}, {"x": 0.5, "y": 0.0, "w": 0.5, "h": 0.5})
    assert moved["h"] == pytest.approx(0.2, abs=0.01)


def test_finalize_widens_the_detector_cam_and_moves_its_face_box(tmp_path):
    """The wiring: a plan whose cam is the detector's guess (missing, or copied in as the heuristic plan and
    models do) leaves finalize widened to ≤ the upscale limit with the face box re-expressed in it; a
    model's own cam that cuts the detected face off gets no face box rather than a broken one."""
    from noze.agency.media.render import stack_layout

    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off", "NOZE_DATA_DIR": str(tmp_path)}
    ax = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    try:
        det_cam = {"x": 0.0, "y": 0.0, "w": 0.215, "h": 0.215}
        det_face = {"x": 0.4, "y": 0.3, "w": 0.23, "h": 0.4}
        prep = {"source_info": {"width": SRC[0], "height": SRC[1], "duration": 60.0}, "ranges": [(0.0, 10.0)],
                "moment_words": [], "words": [], "facecam": det_cam, "facecam_face": det_face}
        moment = {"start_s": 0.0, "end_s": 10.0}
        for cam in (None, dict(det_cam)):  # missing, then copied in (heuristic_plan writes the detector's box)
            plan = Editor(ax).finalize(make_plan([seg(0, 10, "stack", cam)]), moment, FACEBRIEF, {}, prep)
            rf = plan["segments"][0]["reframe"]
            top, _ = stack_layout(rf["cam"], *SRC, ax.cfg.width, ax.cfg.height)
            up = max(ax.cfg.width / (rf["cam"]["w"] * SRC[0]), top / (rf["cam"]["h"] * SRC[1]))
            # mandor CP2 / review: the detector's crop never grows past its own (inset) box — growing it pulled
            # leaves/walls/frames of the room into the band. A soft cam (upscale up to the 3.2x major line) is the
            # lesser evil; the lint calls it minor.
            assert up <= 3.2, (cam, rf["cam"], up)
            c = rf["cam"]
            assert c["x"] >= det_cam["x"] and c["y"] >= det_cam["y"] - 1e-9
            assert c["x"] + c["w"] <= det_cam["x"] + det_cam["w"] + 1e-9 and c["y"] + c["h"] <= det_cam["y"] + det_cam["h"] + 1e-9
            assert rf["face"] and rf["face"] != det_face and rf["face"]["w"] > 0.1  # re-expressed in the inset cam
        far = {"x": 0.75, "y": 0.0, "w": 0.25, "h": 0.25}  # a model's cam elsewhere in the frame
        plan = Editor(ax).finalize(make_plan([seg(0, 10, "stack", far)]), moment, FACEBRIEF, {}, prep)
        rf = plan["segments"][0]["reframe"]
        assert rf["cam"] == far and rf["face"] is None  # kept as chosen; no fake face box
        assert not {"layout:face_small", "layout:face_off_centre"} & ids(lint(plan, FACEBRIEF))
    finally:
        ax.close()


def test_captions_mask_profanity_unless_the_plan_allows_it():
    from noze.agency.media.captions import censor, plan_captions

    assert [censor(w) for w in ("BITCH!", "fucking", "Shit.", "dickens", "classic", "hello", "Shiitake", "niggling",
                                "cocktail", "Scunthorpe", "assess", "slut")] == [
        "B***H!", "f**king", "S**t.", "dickens", "classic", "hello", "Shiitake", "niggling",
        "cocktail", "Scunthorpe", "assess", "s**t"]
    words = spread_words("this is a bitch fight", 0.0, 3.0)
    text = lambda spec: " ".join(" ".join(ln) for ev in plan_captions(words, spec, "tiktok", W, H, 70, 3.0)  # noqa: E731
                                 for ln in ev.lines)
    assert "B***H" in text(CAPS) and "BITCH" not in text(CAPS)
    assert "BITCH" in text({**CAPS, "uncensored": True})  # positive control


def test_brief_watermark_is_the_on_screen_text_only():
    from noze.agency.roles.manager import clean_brief, clean_watermark

    assert clean_watermark("Twitch.tv/skiimasktimmy overlay, on screen for the whole clip") == "Twitch.tv/skiimasktimmy"
    assert clean_watermark("@kaicenat on screen") == "@kaicenat"
    assert clean_watermark("Twitch.tv/skiimasktimmy") == "Twitch.tv/skiimasktimmy"
    b = clean_brief({"requirements": {"watermark": "twitch.tv/xqc watermark throughout"}})
    assert b["requirements"]["watermark"] == "twitch.tv/xqc"
    for real in ("Kai Cenat (Twitch)", "Full stream: twitch.tv/x", "Clipped by Timmy, follow for more"):
        assert clean_watermark(real) == real  # real text survives whole
    for dirty in ('"Brand" overlay', "twitch.tv/x on screen for the whole clip"):
        once = clean_watermark(dirty)
        assert clean_watermark(once) == once  # idempotent


def test_stored_dirty_briefs_are_healed_on_read(tmp_path):
    """Campaigns saved before the watermark fix: every reader goes through Agency._brief, which cleans."""
    from noze.agency.pipeline import Agency
    from noze.agency.schemas import BRIEF, example

    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off", "NOZE_DATA_DIR": str(tmp_path)}
    ax = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    try:
        brief = example(BRIEF)
        brief["requirements"]["watermark"] = "Twitch.tv/skiimasktimmy overlay, on screen for the whole clip"
        cid = ax.store.create_campaign("old", brief, {"granted": True})  # bypasses create_campaign's cleaning
        assert Agency(ax)._brief({"campaign_id": cid})["requirements"]["watermark"] == "Twitch.tv/skiimasktimmy"
    finally:
        ax.close()


def test_a_chosen_cam_is_respected_and_explicit_caption_band_is_honoured(tmp_path):
    from noze.agency.media.captions import rides_seam

    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off", "NOZE_DATA_DIR": str(tmp_path)}
    ax = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    try:
        tight = {"x": 0.0, "y": 0.06, "w": 0.2, "h": 0.2}  # editor cropped below the chat ticker on purpose
        prep = {"source_info": {"width": SRC[0], "height": SRC[1], "duration": 60.0}, "ranges": [(0.0, 10.0)],
                "moment_words": [], "words": [], "facecam": {"x": 0.0, "y": 0.0, "w": 0.215, "h": 0.215},
                "facecam_face": None}
        plan = Editor(ax).finalize(make_plan([seg(0, 10, "stack", tight)]), {"start_s": 0.0, "end_s": 10.0},
                                   FACEBRIEF, {}, prep)
        assert plan["segments"][0]["reframe"]["cam"] == tight
    finally:
        ax.close()
    assert rides_seam({"position": "upper"}) and rides_seam({}) and not rides_seam({"position": "lower"})
    from noze.agency.media.captions import plan_captions

    def first_y(position):
        return plan_captions(WORDS, {**CAPS, "position": position}, "tiktok", W, H, 70, 6.0, lambda t: 640)[0].y
    assert abs(first_y("upper") - 640) < 60  # rides the seam …
    assert first_y("lower") > 1000  # … unless the editor put the captions on the gameplay band on purpose


def test_stretched_clip_keeps_one_watermark(tmp_path):
    """Live run 3 Nov: extending a clip left the old watermark short, so a second one was stacked on it."""
    env = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0", "AGENCY_LLM": "off", "NOZE_DATA_DIR": str(tmp_path)}
    ax = AgencyContext(AgencySettings.load(Settings.load(env=env, dotenv=False), env=env, dotenv=False))
    try:
        plan = make_plan(overlays=[{"kind": "label", "text": "Twitch.tv/skiimasktimmy", "start": 0.0, "end": 12.4,
                                    "position": "bottom", "style": "fade"}])
        Editor(ax).enforce_compliance(plan, {"requirements": {"watermark": "Twitch.tv/skiimasktimmy"}}, 21.0)
        marks = [o for o in plan["overlays"] if "skiimasktimmy" in o["text"].lower()]
        assert len(marks) == 1 and marks[0]["start"] == 0.0 and marks[0]["end"] == 21.0
        # live run 3 Nov #2: an instruction-text copy listed first must not be the one that survives
        plan = make_plan(overlays=[
            {"kind": "label", "text": "Twitch.tv/skiimasktimmy overlay, on screen for the whole clip", "start": 0.0,
             "end": 20.0, "position": "center", "style": "fade"},
            {"kind": "label", "text": "Twitch.tv/skiimasktimmy", "start": 0.0, "end": 20.0, "position": "bottom",
             "style": "fade"}])
        Editor(ax).enforce_compliance(plan, {"requirements": {"watermark": "Twitch.tv/skiimasktimmy"}}, 20.0)
        assert [(o["text"], o["position"]) for o in plan["overlays"]] == [("Twitch.tv/skiimasktimmy", "bottom")]
        # a CTA or title that names the handle is its own text, not a watermark copy
        cta = {"kind": "cta", "text": "Follow twitch.tv/skiimasktimmy for more", "start": 17.0, "end": 20.0,
               "position": "center", "style": "pop"}
        plan = make_plan(overlays=[dict(cta)])
        Editor(ax).enforce_compliance(plan, {"requirements": {"watermark": "Twitch.tv/skiimasktimmy"}}, 20.0)
        assert {k: plan["overlays"][0][k] for k in cta} == cta
        assert plan["overlays"][1]["text"] == "Twitch.tv/skiimasktimmy" and plan["overlays"][1]["box"] is True
        # exact duplicates never reach the screen
        hook = ov("hook_title", "WHY", 0.0, 2.5, "center")
        out = Editor(ax).finalize(make_plan(overlays=[dict(hook), dict(hook)]), {"start_s": 0.0, "end_s": 10.0},
                                  {}, {}, {"source_info": {"duration": 60.0}, "ranges": [(0.0, 10.0)],
                                           "moment_words": [], "words": []})
        assert [o["kind"] for o in out["overlays"]].count("hook_title") == 1
    finally:
        ax.close()


def test_fallback_escalation_never_ships_an_open_major():
    # live run 4 Nov: the LLM budget ran out at the verdict and the fallback approved a clip with a major open
    mgr = Manager.__new__(Manager)
    one_major = {"review": {"verdict": "fail", "score": 6.8, "creative_review": True,
                            "issues": [{"severity": "major"}, {"severity": "minor"}]}}
    minors = {"review": {"verdict": "fail", "score": 6.8, "creative_review": True, "issues": [{"severity": "minor"}]}}
    assert mgr._heuristic_approve(one_major, True)["decision"] == "reject"
    assert mgr._heuristic_approve(minors, True)["decision"] == "approve"  # positive control
