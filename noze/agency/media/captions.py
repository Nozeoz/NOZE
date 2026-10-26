"""Captions and motion text as one ASS subtitle file (rendered by libass inside ffmpeg).

ASS gives us real motion-design primitives without a compositor: per-word
highlight, scale "pop" (\\t transforms), karaoke fills (\\kf), typewriter
reveals, slides (\\move), fades (\\fad) and vector shapes (\\p1) — which is how
the white flash transition is drawn too.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..standards import safe_zone

log = logging.getLogger("noze.agency.captions")

# Families tried in order; the first one installed (system or assets/fonts) wins.
FONT_PREFERENCES = ("Montserrat ExtraBold", "Montserrat Black", "Montserrat", "Poppins ExtraBold", "Poppins",
                    "Inter ExtraBold", "Inter Black", "Inter", "Arial Black", "Arial", "DejaVu Sans")

STYLE_COLORS = {"white": "#FFFFFF", "yellow": "#FFE600", "green": "#2BFF88", "red": "#FF3B3B", "cyan": "#29E7FF"}


def ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB (+ alpha 0=opaque..255=clear) → ASS &HAABBGGRR."""
    h = (hex_color or "#FFFFFF").strip().lstrip("#")
    if h.lower() in STYLE_COLORS:
        h = STYLE_COLORS[h.lower()].lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def clean_text(text: str) -> str:
    return re.sub(r"[{}\\]", "", text or "").replace("\n", " ").strip()


# -- fonts -----------------------------------------------------------------------------
def installed_families(fonts_dir: Path | None = None) -> set[str]:
    fams: set[str] = set()
    if shutil.which("fc-list"):
        try:
            out = subprocess.run(["fc-list", ":", "family", "style"], capture_output=True, text=True, timeout=20).stdout
            for line in out.splitlines():
                fam, _, style = line.partition(":")
                for f in fam.split(","):
                    fams.add(f.strip())
                    for s in style.replace("style=", "").split(","):
                        if s.strip():
                            fams.add(f"{f.strip()} {s.strip()}")
        except (OSError, subprocess.SubprocessError):
            pass
    if fonts_dir and fonts_dir.exists():
        try:
            from PIL import ImageFont

            for p in list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")):
                try:
                    fam, style = ImageFont.truetype(str(p), 12).getname()
                    fams.add(fam)
                    fams.add(f"{fam} {style}")
                except OSError:
                    continue
        except ImportError:
            pass
    return fams


def pick_font(fonts_dir: Path | None = None, preferred: str = "") -> str:
    fams = installed_families(fonts_dir)
    for name in ((preferred,) if preferred else ()) + FONT_PREFERENCES:
        if name and name in fams:
            return name
    return "DejaVu Sans" if "DejaVu Sans" in fams else (sorted(fams)[0] if fams else "Arial")


# -- document ---------------------------------------------------------------------------
@dataclass
class Style:
    name: str
    font: str
    size: int
    primary: str = "&H00FFFFFF"
    secondary: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    back: str = "&H80000000"
    bold: bool = True
    border_style: int = 1  # 1 outline+shadow, 3 opaque box
    outline: float = 6
    shadow: float = 2
    alignment: int = 5
    margin_l: int = 60
    margin_r: int = 60
    margin_v: int = 60
    spacing: float = 0

    def line(self) -> str:
        return (f"Style: {self.name},{self.font},{self.size},{self.primary},{self.secondary},{self.outline_color},"
                f"{self.back},{-1 if self.bold else 0},0,0,0,100,100,{self.spacing},0,{self.border_style},"
                f"{self.outline},{self.shadow},{self.alignment},{self.margin_l},{self.margin_r},{self.margin_v},1")


@dataclass
class AssDoc:
    width: int
    height: int
    styles: dict[str, Style] = field(default_factory=dict)
    events: list[tuple[int, float, float, str, str]] = field(default_factory=list)

    def add(self, layer: int, start: float, end: float, style: str, text: str) -> None:
        if end - start >= 0.02:
            self.events.append((layer, start, end, style, text))

    def text(self) -> str:
        head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {self.width}", f"PlayResY: {self.height}",
                "WrapStyle: 2", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
                "[V4+ Styles]",
                "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
                "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding"]
        head += [s.line() for s in self.styles.values()]
        head += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        body = [f"Dialogue: {layer},{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{text}"
                for layer, a, b, style, text in sorted(self.events, key=lambda e: (e[1], e[0]))]
        return "\n".join(head + body) + "\n"

    def write(self, path: Path) -> Path:
        path.write_text(self.text(), encoding="utf-8")
        return path


# -- layout -----------------------------------------------------------------------------------
def anchors(width: int, height: int, platform: str) -> dict[str, tuple[int, int]]:
    z = safe_zone(platform, width, height)
    cx = int((z["left"] + (width - z["right"])) / 2)
    usable_h = height - z["top"] - z["bottom"]
    return {
        "top": (cx, int(z["top"] + 0.07 * usable_h)),
        "upper": (cx, int(z["top"] + 0.22 * usable_h)),
        "center": (cx, int(z["top"] + 0.5 * usable_h)),
        "lower": (cx, int(height - z["bottom"] - 0.12 * usable_h)),
        "bottom": (cx, int(height - z["bottom"] - 0.03 * usable_h)),
        "max_width": width - z["left"] - z["right"] - 40,
    }


def wrap_words(words: list[str], max_chars: int) -> list[list[str]]:
    lines: list[list[str]] = [[]]
    for w in words:
        cur = lines[-1]
        if cur and len(" ".join(cur + [w])) > max_chars:
            lines.append([w])
        else:
            cur.append(w)
    return [ln for ln in lines if ln]


def group_words(words: list[dict[str, Any]], max_words: int = 3, max_chars: int = 18,
                max_gap: float = 0.35) -> list[list[dict[str, Any]]]:
    """Caption chunks: at most N words, break on punctuation and on pauses."""
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for w in words:
        text = clean_text(w["word"])
        if not text:
            continue
        w = {**w, "word": text}
        if cur:
            gap = w["start"] - cur[-1]["end"]
            chars = len(" ".join(x["word"] for x in cur + [w]))
            if len(cur) >= max_words or gap > max_gap or chars > max_chars * 2:
                chunks.append(cur)
                cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", text) or (re.search(r"[,;:]$", text) and len(cur) >= 2):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


# -- builders -----------------------------------------------------------------------------------
def caption_styles(doc: AssDoc, font: str, spec: dict[str, Any]) -> None:
    h = doc.height
    scale = float(spec.get("font_scale") or 1.0)
    scale = min(1.6, max(0.6, scale))
    style = spec.get("style") or "bold_pop"
    hi = ass_color(spec.get("highlight_color") or "#FFE600")
    base = int(h * 0.05 * scale)
    if style == "karaoke":
        doc.styles["Caption"] = Style("Caption", font, base, primary=hi, secondary="&H00FFFFFF", outline=6, shadow=2)
    elif style == "minimal":
        doc.styles["Caption"] = Style("Caption", font, int(base * 0.82), outline=0, shadow=3, back="&H64000000",
                                      bold=True)
    elif style == "boxed":
        doc.styles["Caption"] = Style("Caption", font, int(base * 0.9), border_style=3, outline=14, shadow=0,
                                      back="&H40000000", outline_color="&H40000000")
    else:  # bold_pop, outline
        doc.styles["Caption"] = Style("Caption", font, base, outline=7, shadow=3)


def build_captions(doc: AssDoc, words: list[dict[str, Any]], spec: dict[str, Any], platform: str,
                   duration: float) -> int:
    """Add caption events for re-timed words. Returns how many caption chunks were placed."""
    if not spec.get("enabled", True) or not words:
        return 0
    anc = anchors(doc.width, doc.height, platform)
    x, y = anc[spec.get("position") or "lower"] if (spec.get("position") or "lower") in anc else anc["lower"]
    style = spec.get("style") or "bold_pop"
    upper = bool(spec.get("uppercase", style in ("bold_pop", "outline", "karaoke")))
    n_words = int(spec.get("words_per_caption") or 3)
    n_words = min(6, max(1, n_words))
    size = doc.styles["Caption"].size
    max_chars = max(8, int(anc["max_width"] / (size * (0.62 if upper else 0.52))))
    hi = ass_color(spec.get("highlight_color") or "#FFE600")
    chunks = group_words(words, n_words, max_chars)
    pos = f"\\an5\\pos({x},{y})"
    for i, chunk in enumerate(chunks):
        start = chunk[0]["start"]
        nxt = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else duration
        end = max(chunk[-1]["end"] + 0.12, start + 0.35)
        if nxt - end < 0.3:
            end = nxt
        end = min(end, duration)
        tokens = [w["word"].upper() if upper else (w["word"].lower() if style == "minimal" else w["word"])
                  for w in chunk]
        lines = wrap_words(tokens, max_chars)
        if style == "karaoke":
            parts, k = [], 0
            for li, line in enumerate(lines):
                for wi, tok in enumerate(line):
                    w = chunk[k]
                    dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
                    parts.append(f"{{\\kf{dur_cs}}}{tok}" + (" " if wi < len(line) - 1 else ""))
                    k += 1
                if li < len(lines) - 1:
                    parts.append("\\N")
            lead_cs = max(0, int(round((chunk[0]["start"] - start) * 100)))
            doc.add(1, start, end, "Caption", f"{{{pos}\\k{lead_cs}}}" + "".join(parts))
        elif style in ("bold_pop",):
            for k, w in enumerate(chunk):
                a = start if k == 0 else w["start"]
                b = chunk[k + 1]["start"] if k + 1 < len(chunk) else end
                if b <= a:
                    continue
                rendered, idx = [], 0
                for line in lines:
                    toks = []
                    for tok in line:
                        if idx == k:
                            toks.append(f"{{\\1c{hi}\\fscx112\\fscy112}}{tok}{{\\r}}")
                        else:
                            toks.append(tok)
                        idx += 1
                    rendered.append(" ".join(toks))
                intro = "\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)" if k == 0 else ""
                doc.add(1, a, b, "Caption", f"{{{pos}{intro}}}" + "\\N".join(rendered))
        else:  # minimal, boxed, outline: static chunk with a soft fade
            fade = "\\fad(60,60)" if style == "minimal" else ""
            doc.add(1, start, end, "Caption", f"{{{pos}{fade}}}" + "\\N".join(" ".join(ln) for ln in lines))
    return len(chunks)


def overlay_styles(doc: AssDoc, font: str) -> None:
    h = doc.height
    doc.styles["Title"] = Style("Title", font, int(h * 0.036), border_style=3, outline=18, shadow=0,
                                back="&H1A000000", outline_color="&H1A000000")
    doc.styles["Label"] = Style("Label", font, int(h * 0.028), outline=5, shadow=2)
    doc.styles["CTA"] = Style("CTA", font, int(h * 0.034), primary="&H00000000", border_style=3, outline=18,
                              shadow=0, back="&H0000E6FF", outline_color="&H0000E6FF")


def build_overlays(doc: AssDoc, overlays: list[dict[str, Any]], platform: str, duration: float) -> int:
    anc = anchors(doc.width, doc.height, platform)
    n = 0
    for ov in overlays:
        text = clean_text(ov.get("text", ""))
        if not text:
            continue
        a = max(0.0, float(ov.get("start") or 0.0))
        b = min(duration, float(ov.get("end") or a + 2.5))
        if b - a < 0.2:
            continue
        kind = ov.get("kind") or "text"
        style = {"hook_title": "Title", "cta": "CTA"}.get(kind, "Label")
        where = ov.get("position") or ("top" if kind == "hook_title" else "center")
        x, y = anc.get(where) or anc["top"]
        size = doc.styles[style].size
        max_chars = max(8, int(anc["max_width"] / (size * 0.58)))
        lines = wrap_words(text.split(), max_chars)
        body = "\\N".join(" ".join(ln) for ln in lines)
        anim = ov.get("style") or "pop"
        if anim == "slide":
            tags = f"\\an5\\move({x - 220},{y},{x},{y},0,180)\\fad(0,120)"
        elif anim == "fade":
            tags = f"\\an5\\pos({x},{y})\\fad(220,220)"
        elif anim == "typewriter":
            per = max(2, int(min(60, (b - a) * 100 * 0.5 / max(1, len(body)))))
            chars = "".join(f"{{\\k{per}}}{c}" if c != " " else " " for c in body.replace("\\N", "\n"))
            body = chars.replace("\n", "\\N")
            tags = f"\\an5\\pos({x},{y})\\2a&HFF&\\fad(0,150)"
        else:  # pop
            tags = (f"\\an5\\pos({x},{y})\\fscx60\\fscy60\\t(0,140,\\fscx108\\fscy108)"
                    f"\\t(140,230,\\fscx100\\fscy100)\\fad(0,150)")
        doc.add(5, a, b, style, f"{{{tags}}}{body}")
        n += 1
    return n


def add_flash(doc: AssDoc, at: float, dur: float = 0.16) -> None:
    w, h = doc.width, doc.height
    shape = f"m 0 0 l {w} 0 {w} {h} 0 {h}"
    if "Shape" not in doc.styles:
        doc.styles["Shape"] = Style("Shape", "Arial", 20, outline=0, shadow=0, alignment=7, margin_l=0,
                                    margin_r=0, margin_v=0)
    doc.add(9, max(0.0, at - 0.02), at + dur, "Shape",
            f"{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&HFFFFFF&\\alpha&H20&\\t(0,{int(dur * 1000)},\\alpha&HFF&)\\p1}}"
            f"{shape}{{\\p0}}")
