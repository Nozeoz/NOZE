"""Sound effects: your own files first (``agency/assets/sfx/<kind>*.wav|mp3``),
otherwise a built-in set synthesized with ffmpeg so the studio works out of the box
with zero licensing questions."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from .ffmpeg import run

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")

# aevalsrc expressions (t in seconds); each yields a short, clean, royalty-free cue.
# Every cue is peak-limited to 0.5 in ``synth_sfx`` (no clipping once mixed); the cues below shape their own
# attack/decay so the limiter only catches stray peaks.
RECIPES: dict[str, tuple[str, float, str]] = {
    # name: (expression, duration, extra filters)
    "whoosh": ("(random(0)*2-1)*sin(PI*t/0.55)", 0.55, "highpass=f=350,lowpass=f=5000,volume=1.6"),
    "swoosh": ("(random(0)*2-1)*sin(PI*t/0.3)", 0.3, "highpass=f=1500,lowpass=f=9000,volume=1.4"),
    "pop": ("sin(2*PI*(1100-5200*t)*t)*exp(-28*t)", 0.14, "volume=1.2"),
    "click": ("(random(0)*2-1)*exp(-350*t)", 0.04, "highpass=f=1800,volume=0.9"),
    "hit": ("sin(2*PI*(55+140*exp(-18*t))*t)*exp(-7*t)+0.25*(random(0)*2-1)*exp(-40*t)", 0.7, "volume=1.3"),
    "boom": ("sin(2*PI*(42+90*exp(-10*t))*t)*exp(-3.5*t)", 1.4, "lowpass=f=900,volume=1.5"),
    "riser": ("(0.6*sin(2*PI*(180+900*t*t)*t)+0.4*(random(0)*2-1))*min(1,t/1.3)", 1.5,
              "highpass=f=200,volume=0.8,afade=t=out:st=1.42:d=0.08"),
    "ding": ("(sin(2*PI*1320*t)+0.45*sin(2*PI*2640*t)+0.2*sin(2*PI*3960*t))*exp(-4.2*t)", 1.1, "volume=0.7"),
    "glitch": ("(random(0)*2-1)*lt(mod(t*37,1),0.5)*exp(-3*t)", 0.4, "highpass=f=600,volume=0.9"),
    # tape rewind: a whine sweeping UP (the spool spinning faster) over fluttering tape hiss, ends on a mechanical clack
    "rewind": ("(0.5*sin(2*PI*(500*t+2800*t*t))+0.22*sin(2*PI*(1000*t+5600*t*t))"
               "+0.3*(random(0)*2-1)*(0.65+0.35*sin(2*PI*38*t)))*min(1,t/0.05)"
               "+0.8*gte(t,0.45)*(random(0)*2-1)*exp(-260*(t-0.45))", 0.5,
               "highpass=f=250,lowpass=f=7500,volume=0.9"),
    # tape stop: pitch (and level) collapsing, 520 Hz → ~25 Hz over 0.6 s; three harmonics keep it reedy, not a sine beep
    "tape_stop": ("(0.6*sin(2*PI*94.5*(1-exp(-5.5*t)))+0.3*sin(4*PI*94.5*(1-exp(-5.5*t)))"
                  "+0.15*sin(6*PI*94.5*(1-exp(-5.5*t))))*max(0,1-t/0.6)", 0.6, "lowpass=f=4500,volume=1.1"),
    # heartbeat: "lub" at 0, softer "dub" at 0.32 s — two low thumps, nothing above 200 Hz
    "heartbeat": ("sin(2*PI*(52+34*exp(-30*t))*t)*exp(-13*t)"
                  "+0.7*gte(t,0.32)*sin(2*PI*(46+28*exp(-30*(t-0.32)))*(t-0.32))*exp(-15*(t-0.32))", 0.9,
                  "lowpass=f=200,volume=2.2"),
    # camera shutter: a bright click, then the mirror/blade clack 65 ms later
    "shutter": ("(random(0)*2-1)*exp(-420*t)*0.9+0.5*sin(2*PI*180*t)*exp(-90*t)"
                "+0.7*gte(t,0.065)*(random(0)*2-1)*exp(-380*(t-0.065))", 0.12,
                "highpass=f=900,lowpass=f=9000,volume=1.1"),
    # bass drop: a sub sweeping 120 Hz → 35 Hz, lightly saturated, long tail
    "bass_drop": ("clip(1.7*sin(2*PI*(35*t+21.25*(1-exp(-4*t)))),-1,1)*exp(-1.5*t)*min(1,t/0.012)", 1.2,
                  "lowpass=f=160,volume=1.6"),
    # sting: a tense minor-second stab (G + G#) with a slow tremolo over a low thud
    "sting": ("0.3*(sin(2*PI*392*t)+0.5*sin(4*PI*392*t)+0.3*sin(6*PI*392*t)+sin(2*PI*415.3*t)"
              "+0.5*sin(4*PI*415.3*t))*exp(-3.2*t)*(1+0.3*sin(2*PI*9*t))*min(1,t/0.01)"
              "+0.6*sin(2*PI*(60+80*exp(-20*t))*t)*exp(-9*t)", 0.8, "lowpass=f=6000,volume=1.0"),
}


def find_user_sfx(assets_dir: Path, kind: str) -> Path | None:
    folder = assets_dir / "sfx"
    if not folder.exists():
        return None
    matches = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXT and p.stem.lower().startswith(kind))
    return matches[0] if matches else None


def synth_sfx(kind: str, cache_dir: Path) -> Path:
    expr, dur, extra = RECIPES.get(kind, RECIPES["whoosh"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{kind}.wav"
    if not dest.exists():
        # render beside the cache under a name no other thread/process uses, then swap it in atomically: a
        # parallel tick never reads a half-written WAV (and two writers just replace each other with equal files)
        tmp = cache_dir / f"{kind}.{os.getpid()}.{threading.get_ident()}.tmp.wav"
        try:
            run(["-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={dur}",
                 "-af", f"{extra},alimiter=limit=0.5:level=0,aformat=sample_rates=48000:channel_layouts=stereo,"
                        f"afade=t=out:st={max(0.0, dur - 0.03):.3f}:d=0.03",
                 "-y", str(tmp)], timeout=60)
            try:
                os.replace(tmp, dest)
            except PermissionError:  # Windows: a reader holds dest; the other writer's identical file won
                if not dest.exists():
                    raise
        finally:
            tmp.unlink(missing_ok=True)
    return dest


def sfx_file(kind: str, assets_dir: Path, cache_dir: Path) -> Path:
    return find_user_sfx(assets_dir, kind) or synth_sfx(kind, cache_dir)
