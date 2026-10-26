"""EditPlan (the editor's EDL) → finished vertical video, with one ffmpeg graph
plus a second pass for exact loudness.

Video, per segment: trim → speed → reframe (crop / blurred-fill) → zoom
(punch / push / pull / zoom-in transition) → shake → dip/whip transitions.
Then: concat → colour → ASS captions & motion text (+flashes) → progress bar.
Audio: segment audio → music bed (looped, faded, side-chain ducked under the
voice) → SFX at their cue times → limiter → two-pass loudnorm to target.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..standards import DELIVERY
from .analyze import loudness, loudnorm_measure
from .captions import AssDoc, add_flash, build_captions, build_overlays, caption_styles, overlay_styles, pick_font
from .ffmpeg import MediaError, esc_filter_value, probe, run
from .timeline import Timeline

log = logging.getLogger("noze.agency.render")

COLOR_FILTERS = {
    "none": "",
    "punchy": "eq=contrast=1.07:saturation=1.18:gamma=0.98",
    "warm": "colorbalance=rs=0.04:gs=0.01:bs=-0.05:rm=0.03:bm=-0.03,eq=saturation=1.06",
    "cool": "colorbalance=rs=-0.04:bs=0.05:rm=-0.02:bm=0.03,eq=saturation=1.04",
    "bw": "hue=s=0,eq=contrast=1.12",
    "cinematic": "colorbalance=rs=0.05:bs=-0.05:rh=-0.03:bh=0.05,eq=contrast=1.05:saturation=0.92",
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

    def as_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "duration": self.duration, "timeline": self.timeline,
                "captions": self.captions, "overlays": self.overlays, "sfx": self.sfx, "music": self.music,
                "loudness": self.loudness, "ass_path": self.ass_path, "font": self.font}


def _even(x: float) -> int:
    return max(2, int(round(x / 2.0)) * 2)


def reframe_filters(mode: str, x_frac: float, src_w: int, src_h: int, w: int, h: int) -> list[str]:
    """Filters that turn a source frame into a w×h frame (labels handled by caller)."""
    tgt = w / h
    src = src_w / src_h if src_h else tgt
    if mode == "fit_blur" and abs(src - tgt) > 0.02:
        return ["FIT_BLUR"]  # needs a split graph; built by the caller
    if abs(src - tgt) <= 0.02:
        return [f"scale={w}:{h}:flags=lanczos"]
    if src > tgt:  # wider than 9:16 → crop width
        cw = _even(src_h * tgt)
        xf = 0.5 if mode in ("center", "auto", "fill") else min(1.0, max(0.0, x_frac or 0.5))
        x = int(min(max(xf * src_w - cw / 2, 0), src_w - cw))
        return [f"crop={cw}:{src_h}:{x}:0", f"scale={w}:{h}:flags=lanczos"]
    ch = _even(src_w / tgt)  # taller → crop height, biased up (faces live in the upper half)
    y = int(min(max(0.42 * src_h - ch / 2, 0), src_h - ch))
    return [f"crop={src_w}:{ch}:0:{y}", f"scale={w}:{h}:flags=lanczos"]


def zoom_filters(kind: str, scale: float, transition_in: str, dur: float, w: int, h: int, fps: int) -> list[str]:
    scale = min(1.4, max(1.0, scale or 1.0))
    if transition_in == "zoom":  # zoom-in transition: start 25% in, settle in 0.3 s
        return [f"scale=w='2*trunc({w}*(1+0.25*max(0,1-t/0.3))/2)':h=-2:eval=frame:flags=bicubic",
                f"crop={w}:{h}:(iw-ow)/2:(ih-oh)/2"]
    if kind == "punch" and scale > 1.0:  # fast punch-in on the first word of the segment
        return [f"scale=w='2*trunc({w}*(1+{scale - 1:.3f}*min(t/0.15,1))/2)':h=-2:eval=frame:flags=bicubic",
                f"crop={w}:{h}:(iw-ow)/2:(ih-oh)/2"]
    if kind in ("push", "pull") and scale > 1.0:  # slow Ken Burns: zoompan on 2× upscale = no jitter
        frames = max(1, int(dur * fps))
        z = (f"1+{scale - 1:.3f}*min(on/{frames},1)" if kind == "push"
             else f"{scale:.3f}-{scale - 1:.3f}*min(on/{frames},1)")
        return [f"scale={w * 2}:{h * 2}:flags=lanczos",
                f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"]
    return []


def shake_filter(w: int, h: int, amp: int = 22) -> list[str]:
    a = amp
    return [f"crop=w=iw-{2 * a}:h=ih-{2 * a}:x='{a}+{a}*sin(2*PI*18*t)*lt(t,0.35)*exp(-8*t)'"
            f":y='{a}+{a}*cos(2*PI*14*t)*lt(t,0.35)*exp(-8*t)'",
            f"scale={w}:{h}:flags=bicubic"]


class Renderer:
    def __init__(self, spec: RenderSpec, fonts_dir: Path | None = None):
        self.spec = spec
        self.fonts_dir = fonts_dir

    def _render_segment(self, source: Path, seg: dict[str, Any], speed: float, dur: float, trans: str, nxt: str,
                        src_w: int, src_h: int, has_audio: bool, dest: Path) -> None:
        """One source range → a W×H intermediate (near-lossless video, PCM audio so
        concatenation stays sample-accurate). Seeking per segment keeps memory flat."""
        sp = self.spec
        W, H, FPS = sp.width, sp.height, sp.fps
        a, b = float(seg["src_start"]), float(seg["src_end"])
        chain = ["setpts=PTS-STARTPTS"]
        if abs(speed - 1.0) > 1e-3:
            chain.append(f"setpts=PTS/{speed:.4f}")
        reframe = seg.get("reframe") or {}
        rf = reframe_filters(reframe.get("mode") or "auto", float(reframe.get("x") or 0.5), src_w, src_h, W, H)
        zoom = seg.get("zoom") or {}
        post = zoom_filters(zoom.get("type") or "none", float(zoom.get("scale") or 1.0), trans, dur, W, H, FPS)
        if seg.get("shake"):
            post += shake_filter(W, H)
        if trans == "fade":
            post.append("fade=t=in:st=0:d=0.15")
        if nxt == "fade":
            post.append(f"fade=t=out:st={max(0.0, dur - 0.1):.3f}:d=0.1")
        if trans == "whip":
            post.append("avgblur=sizeX=48:sizeY=1:enable='lt(t,0.1)'")
        if nxt == "whip":
            post.append(f"avgblur=sizeX=48:sizeY=1:enable='gt(t,{max(0.0, dur - 0.08):.3f})'")
        post += [f"fps={FPS}", "format=yuv420p", "setsar=1"]
        if rf == ["FIT_BLUR"]:
            graph = (f"[0:v]{','.join(chain)},split=2[bg][fg];"
                     f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                     f"boxblur=26:2,eq=brightness=-0.07:saturation=0.85[b];"
                     f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos[f];"
                     f"[b][f]overlay=(W-w)/2:(H-h)/2,{','.join(post)}[v]")
        else:
            graph = f"[0:v]{','.join(chain + rf + post)}[v]"
        if has_audio:
            ach = ["asetpts=PTS-STARTPTS"]
            if abs(speed - 1.0) > 1e-3:
                ach.append(f"atempo={speed:.4f}")
            ach += ["aformat=sample_rates=48000:channel_layouts=stereo", "afade=t=in:d=0.012",
                    f"afade=t=out:st={max(0.0, dur - 0.012):.3f}:d=0.012", f"apad=whole_dur={dur:.3f}"]
            graph += f";[0:a]{','.join(ach)}[a]"
        else:
            graph += f";anullsrc=r=48000:cl=stereo,atrim=0:{dur:.3f}[a]"
        tmp = dest.with_suffix(".part.mkv")
        run(["-y", "-nostats", "-v", "error", "-threads", "4", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
             "-i", str(source), "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
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
        overlay_styles(doc, font)
        out_words = tl.map_words(words)
        n_caps = build_captions(doc, out_words, cap_spec, sp.platform, D) if cap_spec.get("enabled", True) else 0
        n_ovs = build_overlays(doc, plan.get("overlays") or [], sp.platform, D)
        for p in tl.placed[1:]:
            if (segs[p.index].get("transition_in") or "cut") == "flash":
                add_flash(doc, p.out_start)
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
            key = hashlib.sha1(json.dumps([str(source), src_stat.st_size, int(src_stat.st_mtime), W, H, FPS,
                                           seg.get("src_start"), seg.get("src_end"), p.speed, seg.get("reframe"),
                                           seg.get("zoom"), bool(seg.get("shake")), trans, nxt],
                                          sort_keys=True, default=str).encode()).hexdigest()[:16]
            dest = seg_dir / f"seg_{key}.mkv"
            if not dest.exists():
                self._render_segment(source, seg, p.speed, p.out_duration, trans, nxt, src_w, src_h, has_audio, dest)
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
        for cue in plan.get("sfx") or []:
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
        fonts = f":fontsdir='{esc_filter_value(str(self.fonts_dir))}'" if self.fonts_dir and self.fonts_dir.exists() else ""
        vf.append(f"ass=filename='{esc_filter_value(ass_path.name)}'{fonts}")
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
        music_gain = float((plan.get("music") or {}).get("gain_db") or -18.0)
        if music_idx is not None:
            g.append(f"[{music_idx}:a]atrim=0:{D:.3f},asetpts=PTS-STARTPTS,"
                     f"aformat=sample_rates=48000:channel_layouts=stereo,volume={music_gain:.1f}dB,"
                     f"afade=t=in:d=0.4,afade=t=out:st={max(0.0, D - 1.0):.3f}:d=1.0,{pad}[mus]")
            if (plan.get("music") or {}).get("duck", True) and has_audio:
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
                       "out_start": round(p.out_start, 3), "out_end": round(p.out_end, 3)} for p in tl.placed],
            captions=n_caps, overlays=n_ovs, sfx=sfx_used, music=str(music_path or ""),
            loudness=final_loud, ass_path=str(ass_path), font=font,
        )
        (work_dir / "render.json").write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
        return result
