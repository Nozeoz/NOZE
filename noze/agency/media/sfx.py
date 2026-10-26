"""Sound effects: your own files first (``agency/assets/sfx/<kind>*.wav|mp3``),
otherwise a built-in set synthesized with ffmpeg so the studio works out of the box
with zero licensing questions."""

from __future__ import annotations

from pathlib import Path

from .ffmpeg import run

AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac")

# aevalsrc expressions (t in seconds); each yields a short, clean, royalty-free cue.
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
        run(["-v", "error", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=48000:d={dur}",
             "-af", f"{extra},alimiter=limit=0.5:level=0,aformat=sample_rates=48000:channel_layouts=stereo,"
                    f"afade=t=out:st={max(0.0, dur - 0.03):.3f}:d=0.03",
             "-y", str(dest)], timeout=60)
    return dest


def sfx_file(kind: str, assets_dir: Path, cache_dir: Path) -> Path:
    return find_user_sfx(assets_dir, kind) or synth_sfx(kind, cache_dir)
