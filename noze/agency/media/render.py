"""EditPlan (the editor's EDL) → finished vertical video, with one ffmpeg graph
plus a second pass for exact loudness.

Video, per segment: trim → speed → reframe (crop / blurred-fill) → zoom
(punch / push / pull toward a focus point / zoom-in transition) → shake → ``look`` (flashback / vhs / noir /
dream) → rewind or glitch transition → ``hold`` (freeze the last frame: zoom / polaroid / bw) → dip/whip fades.
Then: concat → colour grade → fx (vignette / grain / letterbox) → ASS captions & motion text (+flashes) →
progress bar. Audio: segment audio → music bed (looped, faded, side-chain ducked under the voice, cut out
just before ``music.drop_at``) → SFX at their cue times → limiter → two-pass loudnorm to target.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..standards import DELIVERY
from .analyze import loudness, loudnorm_measure
from .captions import (AssDoc, title_holds, add_flash, add_rewind_tag, box_pad, build_captions, build_overlays,
                       Meter, caption_styles, overlay_styles, pick_font, rides_seam)
from .ffmpeg import MediaError, probe, run
from .timeline import Timeline, clamp_hold

log = logging.getLogger("noze.agency.render")

COLOR_FILTERS = {
    "none": "",
    "punchy": "eq=contrast=1.07:saturation=1.18:gamma=0.98",
    "warm": "colorbalance=rs=0.04:gs=0.01:bs=-0.05:rm=0.03:bm=-0.03,eq=saturation=1.06",
    "cool": "colorbalance=rs=-0.04:bs=0.05:rm=-0.02:bm=0.03,eq=saturation=1.04",
    "bw": "hue=s=0,eq=contrast=1.12",
    "cinematic": "colorbalance=rs=0.05:bs=-0.05:rh=-0.03:bh=0.05,eq=contrast=1.05:saturation=0.92",
    # shadows pushed to teal, highlights to orange (the blockbuster split-tone)
    "teal_orange": ("colorbalance=rs=-0.09:gs=-0.02:bs=0.10:rm=0.04:bm=-0.04:rh=0.12:gh=0.03:bh=-0.11,"
                    "eq=contrast=1.08:saturation=1.10"),
    # night: dim, cool, a touch desaturated — for tense / eerie footage
    "night": ("eq=brightness=-0.05:contrast=1.10:saturation=0.78:gamma=0.93,"
              "colorbalance=rs=-0.05:bs=0.10:rm=-0.04:bm=0.08:rh=-0.03:bh=0.05"),
}

REWIND_S = 0.45  # the rewind transition occupies the first 0.45 s of the incoming segment
REWIND_SRC_S = 1.6  # … and shows this much of the previous segment's tail, played backwards at ~3.5x
GLITCH_S = 0.2  # glitch transition: jolt window on each side of the cut
HOLD_ZOOM = {"zoom": 0.08, "bw": 0.05}  # push-in over the frozen frame
POLAROID_W, POLAROID_TILT = 0.82, -4  # frozen frame card: share of the frame width, degrees

# looks: footage from another time (or another mood). dream is a graph fragment (glow = blur screened over the picture)
LOOK_CHAINS = {
    "flashback": ("eq=saturation=0.10:contrast=0.93:brightness=0.03,"
                  "colorbalance=rs=0.06:gs=0.025:bs=-0.07:rm=0.05:gm=0.015:bm=-0.05,gblur=sigma=0.9:steps=1,"
                  "noise=alls=15:allf=t+u,vignette=angle=PI/6"),
    "vhs": ("eq=saturation=1.12:contrast=1.06:gamma=1.05,chromashift=cbh=7:crh=-7,rgbashift=rh=-2:bh=2,"
            "gblur=sigma=0.8:steps=1,noise=alls=20:allf=t,{scan}"),
    "noir": "hue=s=0,eq=contrast=1.35:brightness=-0.05:gamma=0.95,noise=alls=7:allf=t,vignette=angle=PI/5",
}


@dataclass
class RenderSpec:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    platform: str = "tiktok"
    target_lufs: float = -14.0
    crf: int = 19
    preset: str = "medium"


@dataclass
class RenderResult:
    path: Path
    duration: float
    timeline: list[dict[str, Any]]
    captions: int = 0
    overlays: int = 0
    sfx: list[dict[str, Any]] = field(default_factory=list)
    music: str = ""
    loudness: dict[str, float] = field(default_factory=dict)
    ass_path: str = ""
    font: str = ""
    stamps: list[dict[str, Any]] = field(default_factory=list)  # {"kind": "hit", "at": s}: where each stamp lands

    def as_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "duration": self.duration, "timeline": self.timeline,
                "captions": self.captions, "overlays": self.overlays, "sfx": self.sfx, "music": self.music,
                "loudness": self.loudness, "ass_path": self.ass_path, "font": self.font, "stamps": self.stamps}


def _even(x: float) -> int:
    return max(2, int(round(x / 2.0)) * 2)


def _unit(v: Any, default: float | None = None) -> float | None:
    """0-1 focus coordinate, or ``default`` when unset / not a number."""
    try:
        return min(1.0, max(0.0, float(v)))
    except (TypeError, ValueError):
        return default


def reframe_filters(mode: str, x_frac: float, src_w: int, src_h: int, w: int, h: int,
                    scale: float = 1.0, y_frac: float | None = None) -> list[str]:
    """Filters that turn a source frame into a w×h frame (labels handled by caller).
    ``scale`` > 1 crops tighter than full height, which frees vertical room: ``y_frac`` (0-1) is then the
    vertical centre of the crop in the source — below the face lifts the face up the frame (podcast shots,
    where full-height crops put the chin exactly where the captions sit)."""
    tgt = w / h
    src = src_w / src_h if src_h else tgt
    if mode == "stack" and src > tgt:
        return ["STACK"]  # facecam over gameplay; built by the caller
    if mode in ("fit_blur", "stack") and abs(src - tgt) > 0.02:
        return ["FIT_BLUR"]  # needs a split graph; built by the caller
    if abs(src - tgt) <= 0.02:
        return [f"scale={w}:{h}:flags=lanczos"]
    if src > tgt:  # wider than 9:16 → crop width
        sc = min(1.5, max(1.0, scale or 1.0))
        ch = _even(src_h / sc)
        cw = _even(ch * tgt)
        xf = 0.5 if mode in ("center", "auto", "fill") else min(1.0, max(0.0, x_frac or 0.5))
        x = int(min(max(xf * src_w - cw / 2, 0), src_w - cw))
        yf = 0.5 if y_frac is None else min(1.0, max(0.0, y_frac))
        y = int(min(max(yf * src_h - ch / 2, 0), src_h - ch))
        return [f"crop={cw}:{ch}:{x}:{y}", f"scale={w}:{h}:flags=lanczos"]
    ch = _even(src_w / tgt)  # taller → crop height, biased up (faces live in the upper half)
    y = int(min(max(0.42 * src_h - ch / 2, 0), src_h - ch))
    return [f"crop={src_w}:{ch}:0:{y}", f"scale={w}:{h}:flags=lanczos"]


def _valid_cam(cam: Any) -> bool:
    if not isinstance(cam, dict):
        return False
    try:
        x, y, w, h = (float(cam[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= x < 1 and 0 <= y < 1 and 0.05 <= w <= 1 and 0.05 <= h <= 1


def stack_layout(cam: dict[str, Any], src_w: int, src_h: int, w: int, h: int) -> tuple[int, int]:
    """(cam band height, gameplay band height) of the stacked streamer layout."""
    cw = _even(min(float(cam["w"]) * src_w, src_w - int(float(cam["x"]) * src_w)))
    ch = _even(min(float(cam["h"]) * src_h, src_h - int(float(cam["y"]) * src_h)))
    top = _even(min(max(w * ch / max(cw, 1), h * 0.26), h * 0.45))  # cam band keeps the cam's shape
    return top, h - top


def stack_graph(cam: dict[str, Any], game_x: float, src_w: int, src_h: int, w: int, h: int,
                game_post: list[str] | None = None, scale: float = 1.0, game_y: float | None = None) -> str:
    """Graph body (inputs [c] and [g]) for the streamer layout: facecam band on top,
    gameplay crop below (``game_post`` = zoom filters for the gameplay band only).
    ``scale`` (1-1.5) zooms the gameplay crop tighter and ``game_y`` (0-1 of the source) sets its vertical centre —
    the player/action moves up, out from under the platform's bottom UI. Defaults = the full-height crop.
    Ends without an output label so the caller can append filters."""
    cx, cy = int(float(cam["x"]) * src_w), int(float(cam["y"]) * src_h)
    cw = _even(min(float(cam["w"]) * src_w, src_w - cx))
    ch = _even(min(float(cam["h"]) * src_h, src_h - cy))
    top, bottom = stack_layout(cam, src_w, src_h, w, h)
    sc = min(1.5, max(1.0, scale or 1.0))
    gh = src_h if sc <= 1.0 else min(src_h, _even(src_h / sc))
    gw = _even(min(gh * w / bottom, src_w))
    gx = int(min(max(game_x * src_w - gw / 2, 0), src_w - gw))
    gy = 0 if gh >= src_h else int(min(max((0.5 if game_y is None else game_y) * src_h - gh / 2, 0), src_h - gh))
    return (f"[c]crop={cw}:{ch}:{cx}:{cy},scale={w}:{top}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{top}[top];"
            f"[g]crop={gw}:{gh}:{gx}:{gy},scale={w}:{bottom}:flags=lanczos{''.join(',' + f for f in game_post or [])}[bot];"
            f"[top][bot]vstack=inputs=2")


def band_src_range(seg: dict[str, Any]) -> tuple[float, float, float] | None:
    """(start, end, speed) of a usable ``band_src`` (stack mode: the gameplay band's own source range), else None."""
    bs = seg.get("band_src")
    if not isinstance(bs, dict):
        return None
    try:
        a, b, s = float(bs.get("start")), float(bs.get("end")), float(bs.get("speed") or 1.0)
    except (TypeError, ValueError):
        return None
    return (a, b, min(4.0, max(0.25, s))) if a >= 0 and b - a >= 0.1 else None


def grow_filters(w: int, h: int, z: str, fx: float | None, fy: float | None) -> list[str]:
    """Scale the frame by the time-varying factor expression ``z`` and crop w×h back out of it so the point
    (fx, fy) keeps its place on screen (None = the centre). The crop offset is written in terms of ``z`` itself, NOT
    iw/ow: crop evaluates iw once at configure time, before the first scale step has grown the frame, so written
    with iw/ow every offset is 0 and the zoom grows from the top-left corner (what the old punch / zoom did)."""
    zw, zh = f"2*trunc({w}*{z}/2)", f"2*trunc({h}*{z}/2)"
    cx = f"({zw}-{w})/2" if fx is None else f"{fx:.3f}*({zw}-{w})"
    cy = f"({zh}-{h})/2" if fy is None else f"{fy:.3f}*({zh}-{h})"
    return [f"scale=w='{zw}':h='{zh}':eval=frame:flags=bicubic", f"crop={w}:{h}:x='{cx}':y='{cy}'"]


def zoom_filters(kind: str, scale: float, transition_in: str, dur: float, w: int, h: int, fps: int,
                 fx: float | None = None, fy: float | None = None) -> list[str]:
    """Zoom of one segment. ``fx``/``fy`` (0-1 of the output frame) = the point the zoom grows from: that point
    stays put on screen while the rest scales away from it (crop offset = f × the overshoot, so the window
    never leaves the frame); None = the centre."""
    scale = min(1.4, max(1.0, scale or 1.0))
    fx, fy = _unit(fx), _unit(fy)
    if transition_in == "zoom":  # zoom-in transition: start 25% in, settle in 0.3 s
        return grow_filters(w, h, "(1+0.25*max(0,1-t/0.3))", fx, fy)
    if kind == "punch" and scale > 1.0:  # fast punch-in on the first word of the segment
        return grow_filters(w, h, f"(1+{scale - 1:.3f}*min(t/0.15,1))", fx, fy)
    if kind in ("push", "pull") and scale > 1.0:  # slow Ken Burns: zoompan on 2× upscale = no jitter
        frames = max(1, int(dur * fps))
        z = (f"1+{scale - 1:.3f}*min(on/{frames},1)" if kind == "push"
             else f"{scale:.3f}-{scale - 1:.3f}*min(on/{frames},1)")
        zx = "iw/2-(iw/zoom/2)" if fx is None else f"(iw-iw/zoom)*{fx:.3f}"
        zy = "ih/2-(ih/zoom/2)" if fy is None else f"(ih-ih/zoom)*{fy:.3f}"
        return [f"scale={w * 2}:{h * 2}:flags=lanczos",
                f"zoompan=z='{z}':x='{zx}':y='{zy}':d=1:s={w}x{h}:fps={fps}"]
    return []


def shake_filter(w: int, h: int, amp: int = 22) -> list[str]:
    a = amp
    return [f"crop=w=iw-{2 * a}:h=ih-{2 * a}:x='{a}+{a}*sin(2*PI*18*t)*lt(t,0.35)*exp(-8*t)'"
            f":y='{a}+{a}*cos(2*PI*14*t)*lt(t,0.35)*exp(-8*t)'",
            f"scale={w}:{h}:flags=bicubic"]


def scanlines(h: int) -> str:
    """CRT / tape scanlines: a thin dark line every few pixels (period scales with the frame height)."""
    return f"drawgrid=w=iw:h={max(4, h // 240)}:t={max(1, h // 960)}:c=black@0.22"


def rewind_len(trans: str, prev: Any, play: float) -> float:
    """Seconds of rewind drawn over the head of a segment (0 = none): needs a previous segment to rewind and room
    for the rewind plus a moment of the segment itself."""
    return REWIND_S if trans == "rewind" and isinstance(prev, dict) and play >= REWIND_S + 0.3 else 0.0


def look_fragment(look: str, src: str, dst: str, h: int) -> str:
    """Graph text ``[src]…[dst]`` for a look ('' for none)."""
    if look in LOOK_CHAINS:
        return f"[{src}]{LOOK_CHAINS[look].format(scan=scanlines(h))}[{dst}]" if "{scan}" in LOOK_CHAINS[look] \
            else f"[{src}]{LOOK_CHAINS[look]}[{dst}]"
    if look == "dream":  # soft glow: a heavily blurred copy screened over the picture, blacks lifted, warm-pink cast
        return (f"[{src}]split=2[dr_a][dr_b];[dr_b]gblur=sigma={max(10, h // 80)},eq=brightness=0.04[dr_c];"
                f"[dr_a][dr_c]blend=all_mode=screen:all_opacity=0.5,eq=saturation=0.88:gamma=1.06,"
                f"colorbalance=rs=0.05:bs=0.05:rm=0.03:bm=0.03,curves=all='0/0.06 1/1'[{dst}]")
    return ""


def glitch_fragment(src: str, dst: str, windows: list[tuple[float, float]], w: int, h: int) -> str:
    """RGB split + horizontal jitter + noise + a brightness flicker, only while one of ``windows`` is on screen
    (a gated overlay of a damaged copy, so the picture outside the windows is untouched — no constant zoom)."""
    on = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in windows)
    ax, ay = max(8, w // 34), max(4, h // 90)
    return (f"[{src}]split=2[gl_a][gl_b];[gl_b]crop=w=iw-{2 * ax}:h=ih-{2 * ay}:x='{ax}+{ax}*(random(1)*2-1)'"
            f":y='{ay}+{ay}*(random(2)*2-1)',scale={w}:{h}:flags=bilinear,"
            f"rgbashift=rh=-{max(6, w // 60)}:bh={max(6, w // 60)}:gv={max(2, w // 200)}:edge=smear,"
            f"noise=alls=32:allf=t,eq=brightness='0.06*gt(random(3),0.5)':eval=frame[gl_c];"
            f"[gl_a][gl_c]overlay=0:0:enable='{on}'[{dst}]")


def hold_fragment(src: str, dst: str, play: float, hold: float, style: str, w: int, h: int, fps: int) -> str:
    """The moving picture for ``play`` seconds, then its LAST frame frozen for ``hold`` seconds, dressed per style.
    The frozen part is cut from a clone-padded copy so only ``hold × fps`` frames are ever processed."""
    freeze = (f"tpad=stop_mode=clone:stop_duration={hold + 0.2:.3f},trim=start={play - 0.5 / fps:.4f}:"
              f"duration={hold:.3f},setpts=PTS-STARTPTS")
    head = f"[{src}]split=2[h_p][h_q];[h_p]trim=duration={play:.3f},setpts=PTS-STARTPTS[h_play];"
    tail = f"[h_play][h_fz]concat=n=2:v=1:a=0[{dst}]"
    if style == "polaroid":
        cw = _even(w * POLAROID_W)
        b = max(8, int(w * 0.035))
        iw_ = cw - 2 * b
        a = POLAROID_TILT * 3.14159265 / 180
        card = (f"scale={iw_}:-2:flags=lanczos,pad=iw+{2 * b}:ih+{4 * b}:{b}:{b}:color=white,format=rgba,"
                f"rotate={a:.5f}:c=none:ow=rotw({a:.5f}):oh=roth({a:.5f})")
        return (head + f"[h_q]{freeze},split=2[h_b0][h_f0];"
                f"[h_b0]scale=iw/8:ih/8,boxblur=3:2,scale={w}:{h}:flags=bilinear,eq=brightness=-0.32:saturation=0.75[h_bg];"
                f"[h_f0]{card},split=2[h_c1][h_c2];"
                f"[h_c1]colorchannelmixer=rr=0:gg=0:bb=0:aa=0.55,gblur=sigma=16[h_sh];"
                f"[h_bg][h_sh]overlay=x=(W-w)/2+16:y=(H-h)/2+26:format=auto[h_o1];"
                f"[h_o1][h_c2]overlay=x=(W-w)/2:y=(H-h)/2:format=auto,format=yuv420p,setsar=1[h_fz];" + tail)
    k = HOLD_ZOOM.get(style, HOLD_ZOOM["zoom"])
    push = ",".join(grow_filters(w, h, f"(1+{k}*(1-pow(1-min(t/{hold:.3f},1),2)))", None, None))
    grade = "hue=s=0,eq=contrast=1.1," if style == "bw" else ""
    return head + f"[h_q]{freeze},{grade}{push},format=yuv420p,setsar=1[h_fz];" + tail


class Renderer:
    def __init__(self, spec: RenderSpec, fonts_dir: Path | None = None):
        self.spec = spec
        self.fonts_dir = fonts_dir

    def _fonts_arg(self, work_dir: Path) -> str:
        """fontsdir for the ass filter, as a path free of filtergraph metacharacters: a path
        relative to ffmpeg's cwd when that's clean, else a private copy of the fonts."""
        try:
            rel = os.path.relpath(self.fonts_dir, work_dir).replace(os.sep, "/")
        except ValueError:  # different drive on Windows
            rel = ""
        if rel and not re.search(r"[':,;\[\]\\]", rel):
            return rel
        local = work_dir / "fonts"
        local.mkdir(exist_ok=True)
        for f in self.fonts_dir.iterdir():
            if f.is_file() and not (local / f.name).exists():
                shutil.copyfile(f, local / f.name)
        return "fonts"

    def _tail_graph(self, prev: dict[str, Any], idx: int, src_w: int, src_h: int) -> str:
        """``[idx:v]`` (the previous segment's last stretch) → ``[rw_raw]``: reframed exactly like that segment
        was, at 20 fps so ``reverse`` has little to buffer."""
        W, H = self.spec.width, self.spec.height
        reframe = prev.get("reframe") or {}
        mode = reframe.get("mode") or "auto"
        if mode == "stack" and not _valid_cam(reframe.get("cam")):
            mode = "fit_blur"
        rf = reframe_filters(mode, float(reframe.get("x") or 0.5), src_w, src_h, W, H, float(reframe.get("scale") or 1.0),
                             None if reframe.get("y") is None else float(reframe["y"]))
        head = f"[{idx}:v]setpts=PTS-STARTPTS,fps=20"
        if rf == ["STACK"]:
            body = stack_graph(reframe["cam"], float(reframe.get("x") or 0.5), src_w, src_h, W, H,
                               scale=float(reframe.get("scale") or 1.0),
                               game_y=None if reframe.get("y") is None else float(reframe["y"]))
            for old, new in (("[c]", "[rw_c]"), ("[g]", "[rw_g]"), ("[top]", "[rw_top]"), ("[bot]", "[rw_bot]")):
                body = body.replace(old, new)
            return f"{head},split=2[rw_c][rw_g];{body}[rw_raw]"
        if rf == ["FIT_BLUR"]:
            return (f"{head},split=2[rw_bg][rw_fg];[rw_bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                    f"boxblur=26:2,eq=brightness=-0.07:saturation=0.85[rw_b];"
                    f"[rw_fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[rw_f];"
                    f"[rw_b][rw_f]overlay=(W-w)/2:(H-h)/2[rw_raw]")
        return f"{head},{','.join(rf)}[rw_raw]"

    def _rewind_fragment(self, idx: int, prev: dict[str, Any], src_w: int, src_h: int, rw: float) -> str:
        """VHS rewind: the previous segment's tail, reversed and sped up, with tape damage (chroma split, noise,
        scanlines, tracking bars), ending in a white blink as the segment itself takes over. → ``[rw_v]``."""
        W, H, FPS = self.spec.width, self.spec.height, self.spec.fps
        rate = REWIND_SRC_S / rw
        bars = ",".join(f"drawbox=x=0:y=ih*{y}:w=iw:h=ih*{hh}:color=white@0.30:t=fill:enable='between(t,{a},{b})'"
                        for y, hh, a, b in ((0.18, 0.035, 0.03, 0.15), (0.52, 0.05, 0.12, 0.26), (0.80, 0.03, 0.22, 0.36)))
        return (self._tail_graph(prev, idx, src_w, src_h) + ";"
                f"[rw_raw]reverse,setpts=PTS/{rate:.4f},fps={FPS},trim=duration={rw:.3f},setpts=PTS-STARTPTS,"
                f"eq=saturation=1.3:contrast=1.15:brightness=-0.02,gblur=sigma=1.6:steps=2,chromashift=cbh=10:crh=-10,"
                f"rgbashift=rh=-8:bh=8:gv=3:edge=smear,noise=alls=28:allf=t,{scanlines(H)},{bars},"
                f"fade=t=out:st={rw - 0.05:.3f}:d=0.05:color=white,format=yuv420p,setsar=1[rw_v]")

    def segment_graph(self, seg: dict[str, Any], speed: float, dur: float, trans: str, nxt: str,
                      src_w: int, src_h: int, has_audio: bool,
                      prev: dict[str, Any] | None = None) -> tuple[str, list[tuple[float, float]]]:
        """(filter graph, source ranges of the ffmpeg inputs). ``dur`` = the segment's output slot, hold included.
        Input 0 is the segment's own range (cam + audio); a stack segment with a valid ``band_src`` has the range the
        GAMEPLAY band shows instead as input 1; a ``rewind`` transition adds the tail of ``prev`` as the last input."""
        sp = self.spec
        W, H, FPS = sp.width, sp.height, sp.fps
        hold = clamp_hold(seg.get("hold"))
        if hold and dur - hold < 0.3:  # nothing left to play: no hold
            hold = 0.0
        play = dur - hold
        look = seg.get("look") or "none"
        rw = rewind_len(trans, prev, play)
        inputs = [(float(seg["src_start"]), float(seg["src_end"]))]
        chain = ["setpts=PTS-STARTPTS"]
        if abs(speed - 1.0) > 1e-3:
            chain.append(f"setpts=PTS/{speed:.4f}")
        reframe = seg.get("reframe") or {}
        mode = reframe.get("mode") or "auto"
        if mode == "stack" and not _valid_cam(reframe.get("cam")):
            mode = "fit_blur"  # no facecam rectangle: keep the whole frame visible instead
        rf = reframe_filters(mode, float(reframe.get("x") or 0.5), src_w, src_h, W, H,
                             float(reframe.get("scale") or 1.0),
                             None if reframe.get("y") is None else float(reframe["y"]))
        zoom = seg.get("zoom") or {}
        zkind, zscale = zoom.get("type") or "none", float(zoom.get("scale") or 1.0)
        zfx, zfy = zoom.get("fx"), zoom.get("fy")
        # on a stacked frame only the gameplay band zooms: the facecam must stay whole
        game_post = (zoom_filters(zkind, zscale, trans, play, W, stack_layout(reframe["cam"], src_w, src_h, W, H)[1],
                                  FPS, zfx, zfy) if rf == ["STACK"] else [])
        post = [] if rf == ["STACK"] else zoom_filters(zkind, zscale, trans, play, W, H, FPS, zfx, zfy)
        if seg.get("shake"):
            post += shake_filter(W, H)
        post += [f"fps={FPS}", "format=yuv420p", "setsar=1"]
        if rf == ["STACK"]:
            bs = band_src_range(seg)
            if bs:  # the gameplay band replays another range (muted); cam + audio keep this segment's own
                inputs.append((bs[0], bs[1]))
                # a replay shorter than the segment slows down to cover it (≥ 0.5×) instead of freezing on its
                # last frame — a held frame reads as an empty stage (QC visual:empty_band)
                bspeed = min(bs[2], max(0.5, (bs[1] - bs[0]) / max(play, 1e-3)))
                head = (f"[0:v]{','.join(chain)}[c];[1:v]setpts=PTS-STARTPTS,setpts=PTS/{bspeed:.4f},"
                        f"tpad=stop_mode=clone:stop_duration={play:.3f},trim=duration={play:.3f},setpts=PTS-STARTPTS[g];")
            else:
                head = f"[0:v]{','.join(chain)},split=2[c][g];"
            body = head + stack_graph(reframe["cam"], float(reframe.get("x") or 0.5), src_w, src_h, W, H, game_post,
                                      float(reframe.get("scale") or 1.0),
                                      None if reframe.get("y") is None else float(reframe["y"]))
            parts = [f"{body},{','.join(post)}[v0]"]
        elif rf == ["FIT_BLUR"]:
            parts = [f"[0:v]{','.join(chain)},split=2[bg][fg];"
                     f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                     f"boxblur=26:2,eq=brightness=-0.07:saturation=0.85[b];"
                     f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[f];"
                     f"[b][f]overlay=(W-w)/2:(H-h)/2,{','.join(post)}[v0]"]
        else:
            parts = [f"[0:v]{','.join(chain + rf + post)}[v0]"]
        cur = "v0"

        def stage(fragment: str, out: str) -> None:
            nonlocal cur
            if fragment:
                parts.append(fragment)
                cur = out

        stage(look_fragment(look, cur, "v_look", H), "v_look")
        if rw:
            idx = len(inputs)
            pa, pb = float(prev["src_start"]), float(prev["src_end"])
            inputs.append((max(pa, pb - REWIND_SRC_S), pb) if pb - pa >= REWIND_SRC_S else (pa, pb))
            parts.append(self._rewind_fragment(idx, prev, src_w, src_h, rw))
            parts.append(f"[{cur}][rw_v]overlay=0:0:eof_action=pass:enable='lt(t,{rw:.3f})'[v_rw]")
            cur = "v_rw"
        if hold:
            stage(hold_fragment(cur, "v_hold", play, hold, seg.get("hold_style") or "zoom", W, H, FPS), "v_hold")
        wins = []
        if trans == "glitch":
            wins.append((0.0, min(GLITCH_S, dur / 2)))
        if nxt == "glitch":
            wins.append((max(0.0, dur - GLITCH_S), dur))
        if wins:
            stage(glitch_fragment(cur, "v_gl", wins, W, H), "v_gl")
        fin = []
        if trans == "fade":
            fin.append("fade=t=in:st=0:d=0.15")
        if nxt == "fade":
            fin.append(f"fade=t=out:st={max(0.0, dur - 0.1):.3f}:d=0.1")
        if trans == "whip":
            fin.append("avgblur=sizeX=48:sizeY=1:enable='lt(t,0.1)'")
        if nxt == "whip":
            fin.append(f"avgblur=sizeX=48:sizeY=1:enable='gt(t,{max(0.0, dur - 0.08):.3f})'")
        parts.append(f"[{cur}]{','.join(fin + ['format=yuv420p', 'setsar=1'])}[v]")
        graph = ";".join(parts)
        if has_audio:
            ach = ["asetpts=PTS-STARTPTS"]
            if abs(speed - 1.0) > 1e-3:
                ach.append(f"atempo={speed:.4f}")
            ach.append("aformat=sample_rates=48000:channel_layouts=stereo")
            ach.append(f"afade=t=in:d={rw:.3f}" if rw else "afade=t=in:d=0.012")  # rewind: the voice swells in under the SFX
            ach += [f"afade=t=out:st={max(0.0, play - 0.012):.3f}:d=0.012", f"apad=whole_dur={dur:.3f}"]  # hold = silence
            graph += f";[0:a]{','.join(ach)}[a]"
        else:
            graph += f";anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[a]"
        return graph, inputs

    def _render_segment(self, source: Path, seg: dict[str, Any], speed: float, dur: float, trans: str, nxt: str,
                        src_w: int, src_h: int, has_audio: bool, dest: Path,
                        prev: dict[str, Any] | None = None) -> None:
        """One source range → a W×H intermediate (near-lossless video, PCM audio so
        concatenation stays sample-accurate). Seeking per segment keeps memory flat."""
        graph, inputs = self.segment_graph(seg, speed, dur, trans, nxt, src_w, src_h, has_audio, prev)
        tmp = dest.with_suffix(".part.mkv")
        ins: list[str] = []
        for a, b in inputs:
            ins += ["-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(source)]
        run(["-y", "-nostats", "-v", "error", "-threads", "4", *ins,
             "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p",
             "-c:a", "pcm_s16le", "-t", f"{dur:.3f}", str(tmp)], timeout=max(300, int(dur * 40)))
        tmp.replace(dest)

    def render(self, plan: dict[str, Any], source: Path, out_path: Path, work_dir: Path,
               words: list[dict[str, Any]], music_path: Path | None = None,
               sfx_paths: dict[str, Path] | None = None) -> RenderResult:
        sp = self.spec
        W, H, FPS = sp.width, sp.height, sp.fps
        work_dir.mkdir(parents=True, exist_ok=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        info = probe(source)
        if not info.get("has_video"):
            raise MediaError(f"{source} has no video stream")
        segs = plan["segments"]
        if not segs:
            raise MediaError("edit plan has no segments")
        tl = Timeline(segs)
        D = tl.duration
        src_w, src_h = int(info["width"]), int(info["height"])
        has_audio = bool(info.get("has_audio"))

        # -- captions / motion text / flashes (one ASS file) --------------------------------
        font = pick_font(self.fonts_dir, "")
        doc = AssDoc(W, H)
        cap_spec = plan.get("captions") or {}
        caption_styles(doc, font, cap_spec)
        title_font = pick_font(self.fonts_dir, "Anton")
        overlay_styles(doc, font, title_font)
        out_words = tl.map_words(words)
        for w in out_words:  # whose voice (streamer / game / other): the segment the word landed in decides
            w["voice"] = segs[tl.segment_at(w["start"]).index].get("voice") or "streamer"
        seams = [(p.out_start, p.out_end, stack_layout(segs[p.index]["reframe"]["cam"], src_w, src_h, W, H)[0])
                 for p in tl.placed if (segs[p.index].get("reframe") or {}).get("mode") == "stack"
                 and _valid_cam(segs[p.index]["reframe"].get("cam")) and src_w / max(src_h, 1) > W / H]

        def seam_at(t: float) -> int | None:  # stacked layout: captions ride the cam/gameplay seam
            return next((y for a, b, y in seams if a - 0.01 <= t < b), None)

        n_caps = (build_captions(doc, out_words, cap_spec, sp.platform, D, seam_at if seams else None,
                                 title_holds(plan.get("overlays"), title_font))
                  if cap_spec.get("enabled", True) else 0)
        seam_caps = seam_at if seams and n_caps and rides_seam(cap_spec) else None  # keep text off the seam caption
        cst = doc.styles["Caption"]
        stamps: list[dict[str, Any]] = []
        n_ovs = build_overlays(doc, plan.get("overlays") or [], sp.platform, D, seam_caps, cst.size, box_pad(cst),
                               cap_spec.get("highlight_color") or "", Meter(self.fonts_dir, title_font), stamps)
        for p in tl.placed[1:]:
            trans = segs[p.index].get("transition_in") or "cut"
            if trans == "flash":
                add_flash(doc, p.out_start)
            elif trans == "rewind":
                rw = rewind_len(trans, segs[p.index - 1], p.out_duration - p.hold)
                if rw:
                    add_rewind_tag(doc, p.out_start, rw, sp.platform, segs[p.index].get("label") or "",
                                   Meter(self.fonts_dir, font))
        ass_path = doc.write(work_dir / "captions.ass")

        # -- stage 1: each segment rendered (and cached) on its own ---------------------------------
        seg_dir = work_dir / "segments"
        seg_dir.mkdir(exist_ok=True)
        seg_files: list[Path] = []
        src_stat = source.stat()
        for i, seg in enumerate(segs):
            p = tl.placed[i]
            trans = (seg.get("transition_in") or "cut") if i > 0 else "cut"
            nxt = (segs[i + 1].get("transition_in") or "cut") if i + 1 < len(segs) else "cut"
            prev = segs[i - 1] if i > 0 and trans == "rewind" else None
            key = hashlib.sha1(json.dumps([str(source), src_stat.st_size, int(src_stat.st_mtime), W, H, FPS,
                                           seg.get("src_start"), seg.get("src_end"), p.speed, seg.get("reframe"),
                                           seg.get("zoom"), bool(seg.get("shake")), trans, nxt,
                                           seg.get("band_src"), p.hold, seg.get("hold_style"), seg.get("look"),
                                           [prev.get("src_start"), prev.get("src_end"), prev.get("reframe")] if prev else None,
                                           "fx2"],
                                          sort_keys=True, default=str).encode()).hexdigest()[:16]
            dest = seg_dir / f"seg_{key}.mkv"
            if not dest.exists():
                self._render_segment(source, seg, p.speed, p.out_duration, trans, nxt, src_w, src_h, has_audio, dest,
                                     prev)
            seg_files.append(dest)

        # -- stage 2: assemble, caption, mix --------------------------------------------------------
        args: list[str] = ["-y", "-nostats", "-v", "error"]
        for f in seg_files:
            args += ["-i", str(f)]
        n_in = len(seg_files)
        music_idx = None
        if music_path:
            args += ["-stream_loop", "-1", "-i", str(music_path)]
            music_idx = n_in
            n_in += 1
        sfx_cues: list[tuple[int, dict[str, Any]]] = []
        planned = list(plan.get("sfx") or [])
        if (sfx_paths or {}).get("hit"):  # a stamp lands with a hit unless the editor already put one there
            planned += [{"kind": "hit", "at": st["at"], "gain_db": -6.0} for st in stamps
                        if not any(c.get("kind") == "hit" and abs(float(c.get("at") or 0) - st["at"]) < 0.25
                                   for c in planned)]
        for cue in planned:
            path = (sfx_paths or {}).get(cue.get("kind") or "")
            at = float(cue.get("at") or 0.0)
            if path and 0 <= at < D:
                args += ["-i", str(path)]
                sfx_cues.append((n_in, cue))
                n_in += 1
        bar_idx = None
        if plan.get("progress_bar"):
            args += ["-f", "lavfi", "-i", f"color=c=white@0.85:s={W}x10:r={FPS}:d={D + 0.5:.3f}"]
            bar_idx = n_in
            n_in += 1
        g: list[str] = [f"{''.join(f'[{i}:v][{i}:a]' for i in range(len(seg_files)))}"
                        f"concat=n={len(seg_files)}:v=1:a=1[vcat][acat]"]

        # -- picture finishing ------------------------------------------------------------------------
        vf = []
        color = COLOR_FILTERS.get(plan.get("color") or "none", "")
        if color:
            vf.append(color)
        fx = plan.get("fx") or {}
        if fx.get("vignette"):
            vf.append("vignette=angle=PI/4.5")
        if fx.get("grain"):
            vf.append("noise=alls=9:allf=t+u")  # fine temporal grain: alive, not sparkly
        if fx.get("letterbox"):  # thin cinematic bars (3.5 % top and bottom)
            vf += ["drawbox=x=0:y=0:w=iw:h=ih*0.035:color=black:t=fill",
                   "drawbox=x=0:y=ih-ih*0.035:w=iw:h=ih*0.035:color=black:t=fill"]
        fonts = f":fontsdir='{self._fonts_arg(work_dir)}'" if self.fonts_dir and self.fonts_dir.exists() else ""
        vf.append(f"ass=filename='{ass_path.name}'{fonts}")
        g.append(f"[vcat]{','.join(vf)}[vass]")
        vout = "[vass]"
        if bar_idx is not None:
            g.append(f"[vass][{bar_idx}:v]overlay=x='-w+w*t/{D:.3f}':y=0:shortest=1[vbar]")
            vout = "[vbar]"

        # -- sound ------------------------------------------------------------------------------------
        # Every mix input is padded to the full length: amix drops the tail of the voice
        # when shorter inputs (SFX, music) end first, even with duration=first.
        pad = f"apad=whole_dur={D:.3f}"
        mix_inputs = ["[voice]"]
        music_cfg = plan.get("music") or {}
        music_gain = float(music_cfg.get("gain_db") or -18.0)
        if music_idx is not None:
            drop = ""
            try:
                at = float(music_cfg.get("drop_at") or 0.0)
            except (TypeError, ValueError):
                at = 0.0
            if 0.6 < at < D:  # riser → silence → payoff: the bed stops 0.35 s before the drop, returns ON it
                a0 = at - 0.35
                drop = (f"asetnsamples=n=240:p=0,volume='if(lt(t,{a0:.3f}),1,if(lt(t,{a0 + 0.04:.3f}),"
                        f"1-(t-{a0:.3f})/0.04,if(lt(t,{at:.3f}),0,if(lt(t,{at + 0.02:.3f}),(t-{at:.3f})/0.02,1))))':"
                        f"eval=frame,")
            g.append(f"[{music_idx}:a]atrim=0:{D:.3f},asetpts=PTS-STARTPTS,"
                     f"aformat=sample_rates=48000:channel_layouts=stereo,volume={music_gain:.1f}dB,"
                     f"afade=t=in:d=0.4,afade=t=out:st={max(0.0, D - 1.0):.3f}:d=1.0,{drop}{pad}[mus]")
            if music_cfg.get("duck", True) and has_audio:
                g.append(f"[acat]{pad},asplit=2[voice][sc]")
                g.append("[mus][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400:makeup=1[musd]")
            else:
                g.append(f"[acat]{pad}[voice]")
                g.append("[mus]anull[musd]")
            mix_inputs.append("[musd]")
        else:
            g.append(f"[acat]{pad}[voice]")
        sfx_used = []
        for j, (idx, cue) in enumerate(sfx_cues):
            ms = int(float(cue.get("at") or 0.0) * 1000)
            gain = float(cue.get("gain_db") if cue.get("gain_db") not in (None, "") else -8.0)
            g.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                     f"adelay=delays={ms}:all=1,volume={gain:.1f}dB,{pad}[sfx{j}]")
            mix_inputs.append(f"[sfx{j}]")
            sfx_used.append({"kind": cue.get("kind"), "at": cue.get("at"), "gain_db": gain})
        g.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=longest:dropout_transition=0:"
                 f"normalize=0,atrim=0:{D:.3f},alimiter=limit=0.89:level=0[aout]")

        graph = ";\n".join(g)
        (work_dir / "graph.txt").write_text(graph, encoding="utf-8")
        pre = work_dir / "pre_loudness.mp4"
        gop = max(1, FPS // 2)
        args += ["-filter_complex", graph, "-map", vout, "-map", "[aout]",
                 "-c:v", "libx264", "-preset", sp.preset, "-crf", str(sp.crf), "-profile:v", "high",
                 "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(gop), "-bf", "2",
                 "-maxrate", "12M", "-bufsize", "24M",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{D:.3f}", "-movflags", "+faststart",
                 str(pre)]
        run(args, cwd=work_dir, timeout=max(600, int(D * 60)))

        # -- loudness pass 2 (linear gain to target, true-peak safe) ------------------------------------
        target_tp = DELIVERY["true_peak_max"] - 0.5
        measured = loudnorm_measure(pre, sp.target_lufs, target_tp)
        if measured and measured.get("input_i") not in (None, "-inf"):
            ln = (f"loudnorm=I={sp.target_lufs}:TP={target_tp}:LRA=11:measured_I={measured['input_i']}:"
                  f"measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
                  f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true,"
                  f"aresample=48000")
            run(["-y", "-nostats", "-v", "error", "-i", str(pre), "-map", "0:v", "-map", "0:a", "-c:v", "copy",
                 "-af", ln, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out_path)],
                timeout=max(600, int(D * 20)))
        else:  # silent clip: nothing to normalise
            shutil.copyfile(pre, out_path)
        final_loud = loudness(out_path)
        result = RenderResult(
            path=out_path, duration=round(probe(out_path).get("duration") or D, 3),
            timeline=[{"index": p.index, "src_start": p.src_start, "src_end": p.src_end, "speed": p.speed,
                       "out_start": round(p.out_start, 3), "out_end": round(p.out_end, 3), "hold": p.hold}
                      for p in tl.placed],
            captions=n_caps, overlays=n_ovs, sfx=sfx_used, music=str(music_path or ""),
            loudness=final_loud, ass_path=str(ass_path), font=font, stamps=stamps,
        )
        (work_dir / "render.json").write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
        return result
