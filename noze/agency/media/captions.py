"""Captions and motion text as one ASS subtitle file (rendered by libass inside ffmpeg).

ASS gives us real motion-design primitives without a compositor: per-word
highlight, scale "pop" (\\t transforms), karaoke fills (\\kf), typewriter
reveals, slides (\\move), fades (\\fad) and vector shapes (\\p1) — which is how
the white flash transition is drawn too.
"""

from __future__ import annotations

import logging
import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

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


def fit_y(y: int, block_h: float, platform: str, width: int, height: int) -> int:
    """Shift a vertically centred text block so it sits inside the platform's safe zone (when it fits at all)."""
    z = safe_zone(platform, width, height)
    lo, hi = math.ceil(z["top"] + block_h / 2), math.floor(height - z["bottom"] - block_h / 2)
    return min(max(y, lo), hi) if lo <= hi else y


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


@dataclass
class CapEvent:
    """One caption chunk exactly as the writer places it (the reviewer's layout lint measures the same objects)."""
    chunk: list[dict[str, Any]]
    start: float
    end: float
    lines: list[list[str]]  # wrapped display tokens
    an: int  # ASS alignment: 5 = centred on (x, y), 2 = bottom-centre (seam placement)
    x: int
    y: int


_PROFANE = re.compile(r"(mother)?f+u+c+k|\bsh+i+t|b+i+t+c+h|\bcunt|\bnigg|\bd+i+c+k(?:s|head)?\b|\bpuss+y\b|"
                      r"\bassh+o+le|\bbastard|\bcocks?\b|\bslut|\bwhore|\bfag(?:got)?s?\b|\bretard|"
                      r"\banjing|\bbangsat|\bbajingan|\bkontol|\bmemek|\bngentot", re.I)
_CLEAN_WORDS = {"shiitake", "shitake", "shiite", "shiites", "niggle", "niggles", "niggled", "niggling", "bitchute"}


def censor(token: str) -> str:
    """'BITCH!' → 'B***H!': platforms down-rank burned-in slurs; the first/last letters keep it readable."""
    if re.sub(r"\W", "", token).lower() in _CLEAN_WORDS:
        return token

    def mask(m: re.Match) -> str:
        s = m.group(0)
        return s if len(s) < 3 else s[0] + "*" * (len(s) - 2) + s[-1]
    return _PROFANE.sub(mask, token)


def rides_seam(spec: dict[str, Any]) -> bool:
    """On a stacked layout captions sit on the cam/gameplay seam — unless the editor chose the gameplay
    band on purpose (position "center"/"lower"); "upper" or unset means the seam."""
    return spec.get("position") not in ("center", "lower")


def plan_captions(words: list[dict[str, Any]], spec: dict[str, Any], platform: str, width: int, height: int,
                  size: int, duration: float, y_at: Callable[[float], int | None] | None = None,
                  pad: int = 0, holds: list[tuple[float, float]] | None = None) -> list[CapEvent]:
    """Where and when each caption chunk goes. ``holds`` = windows where a title sits in the caption band
    (``title_holds``): chunks spoken there are left out — the title is the text on screen then. ``y_at(t)`` may pin a chunk to a horizontal line instead
    (the seam of a stacked layout): one line straddles it and longer chunks grow upwards, away from
    whatever sits below the seam. Shared by the ASS writer and the layout lint: one source of truth."""
    if not spec.get("enabled", True) or not words:
        return []
    if not rides_seam(spec):
        y_at = None
    anc = anchors(width, height, platform)
    x, y = anc[spec.get("position") or "lower"] if (spec.get("position") or "lower") in anc else anc["lower"]
    style = spec.get("style") or "bold_pop"
    upper = bool(spec.get("uppercase", style in ("bold_pop", "outline", "karaoke")))
    n_words = min(6, max(1, int(spec.get("words_per_caption") or 3)))
    max_chars = max(8, int(anc["max_width"] / (size * (0.62 if upper else 0.52))))

    clean = (lambda t: t) if spec.get("uncensored") else censor

    def tokens_of(chunk: list[dict[str, Any]]) -> list[str]:
        return [clean(w["word"].upper() if upper else (w["word"].lower() if style == "minimal" else w["word"]))
                for w in chunk]

    def split_tall(chunk: list[dict[str, Any]], limit: int) -> list[list[dict[str, Any]]]:
        if len(chunk) < 2 or len(wrap_words(tokens_of(chunk), max_chars)) <= limit:
            return [chunk]
        h = len(chunk) // 2
        return split_tall(chunk[:h], limit) + split_tall(chunk[h:], limit)

    # never more than 2 lines on screen; on the seam ONE line — a second line grows up into the facecam
    # (live run 3 Nov: three clips in a row lost a review round to a two-line seam caption over the face)
    chunks = [c for ch in group_words(words, n_words, max_chars)
              for c in split_tall(ch, 1 if y_at and y_at(ch[0]["start"]) is not None else 2)]
    holds = [(a, b) for a, b in holds or [] if b > a]
    # any overlap counts (a chunk straddling the title's edge would still sit on it), tail included
    chunks = [c for c in chunks if not any(c[0]["start"] < b and c[-1]["end"] + 0.12 > a for a, b in holds)]
    events: list[CapEvent] = []
    for i, chunk in enumerate(chunks):
        start = chunk[0]["start"]
        seam = y_at(start) if y_at else None
        nxt = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else duration
        end = max(chunk[-1]["end"] + 0.12, start + 0.35)
        if nxt - end < 0.3:
            end = nxt
        end = min([end, duration] + [a for a, _ in holds if a > start])  # never run into a title
        lines = wrap_words(tokens_of(chunk), max_chars)
        events.append(CapEvent(chunk, start, end, lines, 2 if seam else 5, x,
                               seam + int(size * 0.55) if seam else fit_y(y, len(lines) * size + 2 * pad,
                                                                          platform, width, height)))
    return events


def build_captions(doc: AssDoc, words: list[dict[str, Any]], spec: dict[str, Any], platform: str,
                   duration: float, y_at: Callable[[float], int | None] | None = None,
                   holds: list[tuple[float, float]] | None = None) -> int:
    """Add caption events for re-timed words. Returns how many caption chunks were placed."""
    style = spec.get("style") or "bold_pop"
    hi = ass_color(spec.get("highlight_color") or "#FFE600")
    cs = doc.styles["Caption"]
    events = plan_captions(words, spec, platform, doc.width, doc.height, cs.size, duration, y_at, box_pad(cs), holds)
    for ev in events:
        chunk, start, end, lines = ev.chunk, ev.start, ev.end, ev.lines
        pos = f"\\an{ev.an}\\pos({ev.x},{ev.y})"
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
    return len(events)


TITLE_KINDS = ("hook_title", "punch_title")


def title_holds(overlays: list[dict[str, Any]] | None) -> list[tuple[float, float]]:
    """(start, end) of titles placed in the caption band (``lower``/``bottom``, e.g. on the chest of a lifted
    talking head, where nothing fits above the head): captions pause there instead of colliding."""
    return [(float(o.get("start") or 0.0), float(o.get("end") or 0.0)) for o in overlays or []
            if o.get("kind") in TITLE_KINDS and o.get("position") in ("lower", "bottom")]
KEY_SCALE = {"hook_title": 0.105, "punch_title": 0.115}  # emphasis font = share of the frame height (≈ 200 / 220 px at 1920)
KEY_FLOOR = {"hook_title": 150, "punch_title": 180}  # never smaller than this (px at 1920) even when the word is long
TITLE_TILT = -3  # degrees (\frz)


def overlay_styles(doc: AssDoc, font: str, title_font: str = "") -> None:
    """``title_font``: the bold condensed face for hook/punch titles (render passes ``pick_font(.., "Anton")``)."""
    h = doc.height
    doc.styles["Title"] = Style("Title", title_font or font, int(h * 0.034), outline=5, shadow=8,
                                back="&H80000000", outline_color="&H00000000")
    doc.styles["Label"] = Style("Label", font, int(h * 0.028), outline=5, shadow=2)
    # dark pill (BorderStyle 3, alpha 0x66 = 60 % opaque): watermark / mention. ≥ 64 px at 1920
    doc.styles["LabelBox"] = Style("LabelBox", font, int(h * 0.034), border_style=3, outline=16, shadow=0,
                                   back="&H66000000", outline_color="&H66000000")
    doc.styles["CTA"] = Style("CTA", font, int(h * 0.034), primary="&H00000000", border_style=3, outline=18,
                              shadow=0, back="&H0000E6FF", outline_color="&H0000E6FF")


@dataclass
class OvEvent:
    ov: dict[str, Any]
    kind: str
    style: str  # ASS style name: Title / CTA / Label / LabelBox
    start: float
    end: float
    lines: list[list[str]]
    x: int  # centre (align "center") or the LEFT edge of the text (align "left")
    y: int  # centre of the text block
    sizes: list[int] = field(default_factory=list)  # font px per line (same length as ``lines``)
    align: str = "center"
    emphasis_line: int | None = None  # index of the first accent-coloured line (titles only)

    @property
    def an(self) -> int:
        """ASS alignment the writer uses (and ``text_box`` expects): 5 = centred, 4 = left edge, vertically centred."""
        return 4 if self.align == "left" else 5


def box_pad(st: Style) -> int:
    """Visible padding around the text: only an opaque box (BorderStyle 3) counts, a stroke is cosmetic."""
    return int(st.outline) if st.border_style == 3 else 0


def _adv(font: str) -> float:
    """Conservative glyph advance / font size of an upper-case word (no font file at planning time)."""
    return 0.32 if "anton" in font.lower() else 0.62


def title_lines(text: str, emphasis: str, kind: str, st: Style, doc: AssDoc,
                max_width: float) -> tuple[list[list[str]], list[int], int]:
    """Mixed-scale title: small text (st.size) around ONE huge emphasis block, in reading order.
    No ``emphasis`` (or not found in the text) → the last word. Returns (lines, sizes, first emphasis line)."""
    words = text.split()
    norm = lambda ws: [re.sub(r"\W", "", w).lower() for w in ws]  # noqa: E731 — "ONE," matches "one"
    want = norm(clean_text(emphasis).split())
    at = next((i for i in range(len(words) - len(want) + 1) if norm(words[i:i + len(want)]) == want), -1) \
        if want else -1
    n = len(want) if at >= 0 else 1
    if at < 0:
        at = len(words) - 1
    emph = words[at:at + n]  # the text's own spelling (keeps its punctuation)
    before, after = words[:at], words[at + n:]
    adv = _adv(st.font)
    small_chars = max(8, int(max_width / (st.size * adv)))
    key = int(doc.height * KEY_SCALE[kind])
    floor = int(KEY_FLOOR[kind] * doc.height / 1920)
    elines = wrap_words(emph, max(4, int(max_width / (key * adv))))
    while key > floor and max(len(" ".join(ln)) for ln in elines) * adv * key > max_width:
        key = max(floor, key - 4)
        elines = wrap_words(emph, max(4, int(max_width / (key * adv))))
    pre, post = (wrap_words(part, small_chars) if part else [] for part in (before, after))
    return pre + elines + post, [st.size] * len(pre) + [key] * len(elines) + [st.size] * len(post), len(pre)


def plan_overlays(doc: AssDoc, overlays: list[dict[str, Any]], platform: str, duration: float,
                  seam_at: Any = None, cap_size: float = 0.0, cap_pad: float = 0.0) -> list[OvEvent]:
    """Motion-text placement (needs ``overlay_styles`` applied to ``doc`` for the sizes). Shared with the lint.

    ``seam_at(t)`` (stacked layout with captions on the seam): text that would sit on or just under the seam
    is pushed below the seam caption's strip, so a centred hook title never touches the caption.
    """
    anc = anchors(doc.width, doc.height, platform)
    z = safe_zone(platform, doc.width, doc.height)
    events: list[OvEvent] = []
    gap = 24 * doc.height / 1920
    pushed: list[tuple[float, float, float]] = []  # (start, end, bottom px) of texts already moved under the seam
    for ov in overlays:
        text = clean_text(ov.get("text", ""))
        if not text:
            continue
        a = max(0.0, float(ov.get("start") or 0.0))
        b = min(duration, float(ov.get("end") or a + 2.5))
        if b - a < 0.2:
            continue
        kind = ov.get("kind") or "text"
        left = ov.get("align") == "left" and kind not in TITLE_KINDS
        style = ("Title" if kind in TITLE_KINDS else "CTA" if kind == "cta"
                 else "LabelBox" if ov.get("box") else "Label")
        where = ov.get("position") or ("top" if kind == "hook_title" else "center")
        if left and not ov.get("position"):
            where = "bottom"
        x, y = anc.get(where) or anc["top"]
        st = doc.styles[style]
        emph_at = None
        if kind in TITLE_KINDS:
            lines, sizes, emph_at = title_lines(text, ov.get("emphasis") or "", kind, st, doc, anc["max_width"])
        else:
            max_chars = max(8, int((anc["max_width"] - (z["left"] if left else 0)) / (st.size * 0.58)))
            lines = wrap_words(text.split(), max_chars)
            sizes = [st.size] * len(lines)
        pad = box_pad(st)
        block = sum(sizes) + 2 * pad
        if left:
            x = z["left"] + pad  # the pill's own left edge sits on the safe-zone edge
            if where in ("bottom", "lower"):
                y = int(y - block / 2 + pad)  # the anchor is the BOTTOM of the text
        seam = seam_at(a) if seam_at else None
        if seam is not None and where not in ("bottom", "lower"):
            # one seam caption line straddles the seam (≈ 0.6 of its size below it) + the house 24 px gap;
            # texts pushed there earlier and on screen at the same time stack downwards, never on top of each other
            top = max([seam + 0.6 * cap_size + cap_pad] + [bot for pa, pb, bot in pushed if pa < b and a < pb])
            y = max(y, int(math.ceil(top + gap + block / 2)))
            y = fit_y(y, block, platform, doc.width, doc.height)
            pushed.append((a, b, y + block / 2))
        y = fit_y(y, block, platform, doc.width, doc.height)
        events.append(OvEvent(ov, kind, style, a, b, lines, x, y, sizes, "left" if left else "center", emph_at))
    return events


def _tag_color(hex_color: str) -> str:
    return "&H" + ass_color(hex_color)[4:] + "&"  # override-tag form &HBBGGRR&


def build_overlays(doc: AssDoc, overlays: list[dict[str, Any]], platform: str, duration: float,
                   seam_at: Any = None, cap_size: float = 0.0, cap_pad: float = 0.0,
                   accent: str = "") -> int:
    """``accent``: colour of the title emphasis (= captions.highlight_color, default yellow)."""
    hi = _tag_color(accent or "#FFE600")
    n = 0
    for ev in plan_overlays(doc, overlays, platform, duration, seam_at, cap_size, cap_pad):
        ov, a, b, style, x, y, lines = ev.ov, ev.start, ev.end, ev.style, ev.x, ev.y, ev.lines
        title = ev.kind in TITLE_KINDS
        texts = [" ".join(ln) for ln in lines]
        anim = ov.get("style") or "pop"
        an = f"\\an{ev.an}"
        # title: tilted, drop shadow instead of a box; per-line \fs and the accent colour on the emphasis block
        look = f"\\frz{TITLE_TILT}\\shad10\\4c&H000000&\\4a&H50&" if title else ""
        if anim == "typewriter":
            per = max(2, int(min(60, (b - a) * 100 * 0.5 / max(1, sum(len(t) for t in texts)))))
            texts = ["".join(f"{{\\k{per}}}{c}" if c != " " else " " for c in t) for t in texts]
        if title:
            e0 = ev.emphasis_line or 0
            e1 = e0 + sum(1 for s in ev.sizes if s != doc.styles[style].size)
            texts = [f"{{\\fs{ev.sizes[i]}\\1c{hi if e0 <= i < e1 else '&HFFFFFF&'}}}{t}" for i, t in enumerate(texts)]
        body = "\\N".join(texts)
        if anim == "slide":
            tags = f"{an}\\move({x - 220},{y},{x},{y},0,180)\\fad(0,120)"
        elif anim == "fade":
            tags = f"{an}\\pos({x},{y})\\fad(220,220)"
        elif anim == "typewriter":
            tags = f"{an}\\pos({x},{y})\\2a&HFF&\\fad(0,150)"
        else:  # pop
            tags = (f"{an}\\pos({x},{y})\\fscx60\\fscy60\\t(0,140,\\fscx108\\fscy108)"
                    f"\\t(140,230,\\fscx100\\fscy100)\\fad(0,150)")
        doc.add(5, a, b, style, f"{{{tags}{look}}}{body}")
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


# -- measuring (the reviewer's layout lint) --------------------------------------------------------
@lru_cache(maxsize=16)
def _face_metrics(fonts_dir: str, family: str) -> tuple[Any, float, float] | None:
    """(Pillow font at 1000px, cell height, cap height) of ``family`` — fonts_dir first, then the system."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    paths: list[str] = []
    d = Path(fonts_dir) if fonts_dir else None
    if d and d.exists():
        for p in sorted(list(d.glob("*.ttf")) + list(d.glob("*.otf"))):
            try:
                fam, style = ImageFont.truetype(str(p), 12).getname()
            except OSError:
                continue
            if family in (fam, f"{fam} {style}"):
                paths.append(str(p))
    paths += [family, family + ".ttf", family.replace(" ", "").lower() + ".ttf"]  # installed fonts, by name
    for path in paths:
        try:
            f = ImageFont.truetype(path, 1000)
            asc, desc = f.getmetrics()
            box = f.getbbox("H")
            return f, float(asc + desc), float(box[3] - box[1])
        except OSError:
            continue
    return None


class Meter:
    """Text extents as libass draws them: Fontsize is the cell height (ascent+descent), so glyph
    advance = Pillow advance × size / cell. Without the font file: a conservative per-char estimate."""

    def __init__(self, fonts_dir: Path | None, family: str):
        self.face = _face_metrics(str(fonts_dir or ""), family)
        self.measured = self.face is not None
        self.cap_ratio = (self.face[2] / self.face[1]) if self.face else 0.58

    def width(self, text: str, size: float) -> float:
        if self.face:
            return self.face[0].getlength(text) * size / self.face[1]
        return len(text) * size * (0.62 if text.isupper() else 0.55)


def text_box(lines: list[str], size: float | list[float], x: float, y: float, an: int, pad: float,
             meter: Meter) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of a text block anchored like the writer does: \\an5 = centre, \\an2 = bottom-centre,
    \\an4 = left edge (x is the text's LEFT edge) / vertically centred, \\an1 = bottom-left.
    ``size`` is one font px for every line, or a list with one per line (mixed-scale titles)."""
    if isinstance(size, (list, tuple)):
        w = max((meter.width(ln, s) for ln, s in zip(lines, size)), default=0.0)
        h = float(sum(size[:len(lines)]))
    else:
        w = max((meter.width(ln, size) for ln in lines), default=0.0)
        h = size * len(lines)
    top = y - h / 2 if an in (4, 5, 6) else (y if an in (7, 8, 9) else y - h)
    if an in (1, 4, 7):
        return x - pad, top - pad, x + w + pad, top + h + pad
    if an in (3, 6, 9):
        return x - w - pad, top - pad, x + pad, top + h + pad
    return x - w / 2 - pad, top - pad, x + w / 2 + pad, top + h + pad
