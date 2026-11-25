"""Captions and motion text as one ASS subtitle file (rendered by libass inside ffmpeg).

ASS gives us real motion-design primitives without a compositor: per-word
highlight, scale "pop" (\\t transforms), karaoke fills (\\kf), typewriter
reveals, slides (\\move), fades (\\fad) and vector shapes (\\p1) — which is how
the white flash transition is drawn too.
"""

from __future__ import annotations

import itertools
import logging
import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field, replace
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


# Words a caption page must never END on (EN + ID): the sentence is left hanging ("... AND" / "... YANG").
FUNCTION_WORDS = frozenset(
    "and or but so the a an to of in on at my your his her no oh like with for is was it's "
    "dan yang di ke dari sama terus jadi tapi".split())


def _core(word: str) -> str:
    return re.sub(r"[^\w']", "", word.lower().replace("’", "'"))


def is_function_word(word: str) -> bool:
    return _core(word) in FUNCTION_WORDS


def _sentence_end(word: str) -> bool:
    return bool(re.search(r"[.!?…]$", word))


def group_words(words: list[dict[str, Any]], max_words: int = 3, max_chars: int = 18,
                max_gap: float = 0.35) -> list[list[dict[str, Any]]]:
    """Caption pages: at most N words (N+1 after a carry), break on punctuation and on pauses, and a page
    never ENDS on a function word ("and", "no", "yang"): trailing ones move to the front of the next page
    (a sentence-final word and the very last page of the stream stay as they are)."""
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []

    def flush(final: bool = False) -> None:
        nonlocal cur
        carry: list[dict[str, Any]] = []
        # ``final`` = sentence end OR a pause: function words are never carried across either
        if not final and not _sentence_end(cur[-1]["word"]):
            while cur and is_function_word(cur[-1]["word"]):
                carry.insert(0, cur.pop())
        if cur:
            chunks.append(cur)
        cur = carry

    for w in words:
        text = clean_text(w["word"])
        if not text:
            continue
        w = {**w, "word": text}
        if cur:
            gap = w["start"] - cur[-1]["end"]
            chars = len(" ".join(x["word"] for x in cur + [w]))
            hanging = is_function_word(cur[-1]["word"]) and len(cur) <= max_words and gap <= max_gap
            if (len(cur) >= max_words and not hanging) or gap > max_gap or chars > max_chars * 2:
                # (a page ending on "the"/"and" takes one more word instead of cutting there; across a pause it stands alone)
                flush(final=gap > max_gap)
        cur.append(w)
        if _sentence_end(text):
            flush(final=True)
        elif re.search(r"[,;:]$", text) and len(cur) >= 2:
            flush()
    if cur:
        chunks.append(cur)
    return chunks


# -- builders -----------------------------------------------------------------------------------
CAP_RATIO = 0.574  # cap height / Fontsize (libass cell) of Anton and Montserrat, measured on the shipped files
TEXT_FLOOR = 98  # px at 1920 high: cap height >= 55 px (mandor MF-2/MF-3, raised twice) = 55 / CAP_RATIO (Anton 0.571)
CAPTION_FLOOR = TEXT_FLOOR
MAX_CPS = 20.0  # caption reading speed: characters per second a page may carry


def caption_styles(doc: AssDoc, font: str, spec: dict[str, Any]) -> None:
    h = doc.height
    scale = float(spec.get("font_scale") or 1.0)
    scale = min(1.6, max(0.6, scale))
    style = spec.get("style") or "bold_pop"
    hi = ass_color(spec.get("highlight_color") or "#FFE600")
    base = int(h * 0.05 * scale)
    floor = int(CAPTION_FLOOR * h / 1920) if scale >= 1.0 else 0  # mandor MF-2: cap height >= 55 px at 1920 high
    base = max(base, floor)
    if style == "karaoke":
        doc.styles["Caption"] = Style("Caption", font, base, primary=hi, secondary="&H00FFFFFF", outline=6, shadow=2)
    elif style == "minimal":
        doc.styles["Caption"] = Style("Caption", font, max(int(base * 0.82), floor), outline=0, shadow=3, back="&H64000000",
                                      bold=True)
    elif style == "boxed":
        doc.styles["Caption"] = Style("Caption", font, max(int(base * 0.9), floor), border_style=3, outline=14, shadow=0,
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
    voice: str = "streamer"  # streamer | game | other (SEGMENT.voice of the words on the page)
    tag: bool = False  # first page of a game block: carries the small "IN-GAME" label


GAME_PAD = 14  # px of padding the "game" pill carries (BorderStyle 3 outline = box thickness)
GAME_TAG = "IN-GAME"


def _voice(w: dict[str, Any]) -> str:
    v = w.get("voice")
    return v if v in ("game", "other") else "streamer"


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


def join_hyphenated(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Glue a word token that starts with '-' (or a word ending in '-') to its neighbour: 'AI' + '-inspired' is one
    word on screen, never a page that opens with a dangling hyphen."""
    out: list[dict[str, Any]] = []
    for w in words:
        t = str(w.get("word") or "")
        if out and (t.startswith("-") or str(out[-1].get("word") or "").endswith("-")) and t.strip("-"):
            prev = out[-1]
            out[-1] = {**prev, "word": str(prev.get("word") or "").rstrip("-") + "-" + t.lstrip("-"),
                       "end": max(float(prev.get("end") or 0), float(w.get("end") or 0))}
        else:
            out.append(w)
    return out


def plan_captions(words: list[dict[str, Any]], spec: dict[str, Any], platform: str, width: int, height: int,
                  size: int, duration: float, y_at: Callable[[float], int | None] | None = None,
                  pad: int = 0, holds: list[tuple[float, float]] | None = None) -> list[CapEvent]:
    """Where and when each caption chunk goes. ``holds`` = windows where a title sits in the caption band
    (``title_holds``): chunks spoken there are left out — the title is the text on screen then. ``y_at(t)`` may pin a chunk to a horizontal line instead
    (the seam of a stacked layout): one line straddles it and longer chunks grow upwards, away from
    whatever sits below the seam. Shared by the ASS writer and the layout lint: one source of truth."""
    if not spec.get("enabled", True) or not words:
        return []
    words = join_hyphenated(words)
    if not rides_seam(spec):
        y_at = None
    anc = anchors(width, height, platform)
    x, y = anc[spec.get("position") or "lower"] if (spec.get("position") or "lower") in anc else anc["lower"]
    style = spec.get("style") or "bold_pop"
    upper = bool(spec.get("uppercase", style in ("bold_pop", "outline", "karaoke")))
    n_words = min(4, max(1, int(spec.get("words_per_caption") or 3)))  # 2-4 words a page (+1 after a carry)
    max_chars = max(8, int(anc["max_width"] / (size * (0.62 if upper else 0.52))))

    clean = (lambda t: t) if spec.get("uncensored") else censor

    def tokens_of(chunk: list[dict[str, Any]]) -> list[str]:
        return [clean(w["word"].upper() if upper else (w["word"].lower() if style == "minimal" else w["word"]))
                for w in chunk]

    def split_tall(chunk: list[dict[str, Any]], limit: int) -> list[list[dict[str, Any]]]:
        if len(chunk) < 2 or len(wrap_words(tokens_of(chunk), max_chars)) <= limit:
            return [chunk]
        mid = len(chunk) // 2  # cut near the middle, but never right after a function word
        h = next((c for c in (mid, mid + 1, mid - 1) if 0 < c < len(chunk) and not is_function_word(chunk[c - 1]["word"])),
                 mid)
        return split_tall(chunk[:h], limit) + split_tall(chunk[h:], limit)

    # never more than 2 lines on screen; on the seam ONE line — a second line grows up into the facecam
    # (live run 3 Nov: three clips in a row lost a review round to a two-line seam caption over the face)
    # a page never mixes two voices: group each run of one voice on its own (no voice anywhere = one run, as before)
    chunks = [c for _, run in itertools.groupby(words, key=_voice)
              for ch in group_words(list(run), n_words, max_chars)
              for c in split_tall(ch, 1 if y_at and y_at(ch[0]["start"]) is not None else 2)]
    titles, tfont = getattr(holds, "titles", []), getattr(holds, "font", "")
    low = getattr(holds, "low", [])
    holds = [(a, b) for a, b in holds or [] if b > a]
    if y_at:  # captions ride the cam/gameplay seam: a title pauses them only where it MEASURABLY meets that strip
        # (review CP2: a title moved to the bottom of the gameplay band blanket-paused the spoken hook on the seam)
        holds = _squeezed_titles(titles + low, tfont, platform, width, height, size, pad, y_at) if titles or low else []
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
        voice = _voice(chunk[0])
        pd = max(pad, GAME_PAD) if voice == "game" else pad  # the game pill is a box even when the caption is not
        tag = voice == "game" and not (events and events[-1].voice == "game")
        events.append(CapEvent(chunk, start, end, lines, 2 if seam else 5, x,
                               seam + int(size * 0.55) if seam else fit_y(y, len(lines) * size + 2 * pd,
                                                                          platform, width, height),
                               voice, tag))
    return _reading_speed(events, duration, holds)


def page_chars(ev: CapEvent) -> int:
    return len(" ".join(" ".join(ln) for ln in ev.lines))


def _reading_speed(events: list[CapEvent], duration: float, holds: list[tuple[float, float]]) -> list[CapEvent]:
    """At most MAX_CPS characters per second on every page: a too-fast page first stays up longer (into the gap),
    then pushes the next page later (<= 0.6 s behind its first word) — text is never dropped."""
    for i, ev in enumerate(events):
        need = page_chars(ev) / MAX_CPS
        if ev.end - ev.start >= need:
            continue
        cap = min([duration] + [a for a, _ in holds if a > ev.start])
        ev.end = min(max(ev.end, ev.start + need), cap)
        nxt = events[i + 1] if i + 1 < len(events) else None
        if nxt and nxt.start < ev.end:
            if ev.end - nxt.chunk[0]["start"] <= 0.6:
                nxt.start = ev.end
                nxt.end = max(nxt.end, nxt.start + 0.35)
            else:
                ev.end = max(ev.start + 0.2, nxt.start)  # too far behind the speech: stay on the speech clock
    return events


def build_captions(doc: AssDoc, words: list[dict[str, Any]], spec: dict[str, Any], platform: str,
                   duration: float, y_at: Callable[[float], int | None] | None = None,
                   holds: list[tuple[float, float]] | None = None) -> int:
    """Add caption events for re-timed words. Returns how many caption chunks were placed."""
    style = spec.get("style") or "bold_pop"
    hi = ass_color(spec.get("highlight_color") or "#FFE600")
    cs = doc.styles["Caption"]
    events = plan_captions(words, spec, platform, doc.width, doc.height, cs.size, duration, y_at, box_pad(cs), holds)
    voices = {ev.voice for ev in events}
    if "game" in voices:  # dark semi-solid pill, white text, no highlight; a small grey tag marks the block
        box = "&H30141414"
        doc.styles["CaptionGame"] = Style("CaptionGame", cs.font, cs.size, border_style=3, outline=GAME_PAD, shadow=0,
                                          back=box, outline_color=box)
        doc.styles["CaptionTag"] = Style("CaptionTag", cs.font, round(32 * doc.height / 1920), primary="&H00BEBEBE",
                                         outline=3, shadow=0, alignment=2, spacing=2)
    if "other" in voices:  # plain white, no highlight
        doc.styles["CaptionOther"] = replace(cs, name="CaptionOther", primary="&H00FFFFFF", secondary="&H00FFFFFF")
    for ev in events:
        chunk, start, end, lines = ev.chunk, ev.start, ev.end, ev.lines
        pos = f"\\an{ev.an}\\pos({ev.x},{ev.y})"
        if ev.voice != "streamer":
            sty = "CaptionGame" if ev.voice == "game" else "CaptionOther"
            doc.add(1, start, end, sty, f"{{{pos}\\fad(60,60)}}" + "\\N".join(" ".join(ln) for ln in lines))
            if ev.tag:
                h = len(lines) * cs.size
                top = ev.y - h / 2 - GAME_PAD if ev.an == 5 else ev.y - h - GAME_PAD
                doc.add(2, start, end, "CaptionTag", f"{{\\an2\\pos({ev.x},{int(top) - 8})\\fad(60,60)}}{GAME_TAG}")
            continue
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
                a = start if k == 0 else max(start, w["start"])  # a page pushed later (reading speed) never starts early
                b = min(end, chunk[k + 1]["start"]) if k + 1 < len(chunk) else end
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
                intro = "\\fscx82\\fscy82\\t(0,90,0.5,\\fscx100\\fscy100)" if k == 0 else ""  # ease-out, not linear
                outro = "\\fad(0,60)" if k == len(chunk) - 1 else ""  # leaves in ~70 % of the 90 ms entry
                doc.add(1, a, b, "Caption", f"{{{pos}{intro}{outro}}}" + "\\N".join(rendered))
        else:  # minimal, boxed, outline: static chunk with a soft fade
            fade = "\\fad(60,60)" if style == "minimal" else ""
            doc.add(1, start, end, "Caption", f"{{{pos}{fade}}}" + "\\N".join(" ".join(ln) for ln in lines))
    return len(events)


TITLE_KINDS = ("hook_title", "punch_title")


class Holds(list):
    """``title_holds`` result: the (start, end) windows, plus the titles and their face so ``plan_captions`` can
    also pause captions under a title that is too tall for a stacked layout (it measures that title itself)."""
    titles: list[dict[str, Any]]
    font: str = ""


def title_holds(overlays: list[dict[str, Any]] | None, title_font: str = "") -> Holds:
    """(start, end) of titles placed in the caption band (``lower``/``bottom``, e.g. on the chest of a lifted
    talking head, where nothing fits above the head): captions pause there instead of colliding.
    ``title_font``: the face the renderer draws titles in (without it a wide face is assumed — the lint's worst case)."""
    h = Holds((float(o.get("start") or 0.0), float(o.get("end") or 0.0)) for o in overlays or []
              if o.get("kind") in TITLE_KINDS and o.get("position") in ("lower", "bottom"))
    h.titles = [o for o in overlays or [] if o.get("kind") in TITLE_KINDS and o.get("position") not in ("lower", "bottom")]
    h.low = [o for o in overlays or [] if o.get("kind") in TITLE_KINDS and o.get("position") in ("lower", "bottom")]
    h.font = title_font
    return h


def _squeezed_titles(titles: list[dict[str, Any]], font: str, platform: str, width: int, height: int, size: float,
                     pad: float, y_at: Callable[[float], int | None]) -> list[tuple[float, float]]:
    """Windows where a title, planned under the seam caption strip, still reaches up into the caption (it is too
    tall for the room under the strip: 4 lines of cap-floor setup + 200 px emphasis do not fit): the caption yields."""
    doc = AssDoc(width, height)
    overlay_styles(doc, font or "Arial", font or "Arial")
    out = []
    for ev in plan_overlays(doc, titles, platform, 1e9, y_at, size, pad):
        seam = y_at(ev.start)
        if seam is not None and ev.y - sum(ev.sizes) / 2 < seam + 0.3 * size:
            out.append((ev.start, ev.end))
    return out


KEY_SCALE = {"hook_title": 0.105, "punch_title": 0.115}  # emphasis font = share of the frame height (≈ 200 / 220 px at 1920)
KEY_FLOOR = {"hook_title": 150, "punch_title": 180}  # never smaller than this (px at 1920) even when the word is long
TITLE_TILT = -4  # degrees (\frz): hook / punch titles lean like a sticker, never dead level
STAMP_TILT = -8  # degrees: a stamp is struck crooked


def overlay_styles(doc: AssDoc, font: str, title_font: str = "") -> None:
    """``title_font``: the bold condensed face for hook/punch titles (render passes ``pick_font(.., "Anton")``)."""
    h = doc.height
    # setup line of a title: cap height >= 55 px (TEXT_FLOOR = 96 px at 1920 in the title face)
    tsize = max(int(h * 0.05), int(TEXT_FLOOR * h / 1920))
    doc.styles["Title"] = Style("Title", title_font or font, tsize, outline=5, shadow=8,
                                back="&H80000000", outline_color="&H00000000")
    # accent block behind the emphasis word: BorderStyle 3 = libass draws the opaque box around the glyph run itself
    doc.styles["TitleBlock"] = Style("TitleBlock", title_font or font, tsize, border_style=3, outline=22, shadow=0,
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


STORY_KINDS = ("time_card", "callout")  # set in the title face (Anton), measured like titles by the layout lint
CARD_DEFAULT_S = 1.1  # a time-jump card stays up 0.9-1.2 s
CARD_SCALE, CARD_FLOOR = 0.066, 110  # card font = share of the frame height (≈ 126 px at 1920); never below 110 px at 1920
CALLOUT_SCALE, CALLOUT_R = 0.042, 0.078  # label font (≈ 80 px at 1920) and ring radius (share of the frame WIDTH)


def card_lines(text: str, st: Style, doc: AssDoc, max_width: float) -> tuple[list[list[str]], list[int]]:
    """Time-jump card text: ONE big line when it fits (shrinking to the floor), else wrapped at the floor size."""
    adv = _adv(st.font)
    key = int(doc.height * CARD_SCALE)
    floor = int(CARD_FLOOR * doc.height / 1920)
    while key > floor and len(text) * adv * key > max_width:
        key = max(floor, key - 4)
    words = text.split()
    lines = [words] if len(text) * adv * key <= max_width else wrap_words(words, max(4, int(max_width / (key * adv))))
    return lines, [key] * len(lines)


def callout_label(text: str, ov: dict[str, Any], st: Style, doc: AssDoc, anc: dict[str, Any],
                  z: dict[str, Any]) -> tuple[list[list[str]], list[int], int, int]:
    """Label of a callout: sits on the far side of the pointed-at spot (below it when the target is in the upper
    half, above it otherwise), centred under/over the target but kept inside the safe zone."""
    W, H = doc.width, doc.height
    tx, ty = callout_target(ov, W, H)
    size = int(H * CALLOUT_SCALE)
    adv = _adv(st.font)
    lines = wrap_words(text.split(), max(6, int(anc["max_width"] * 0.8 / (size * adv))))
    half_w = max(len(" ".join(ln)) for ln in lines) * size * adv / 2
    block = size * len(lines)
    reach = CALLOUT_R * W + 0.10 * H  # ring radius + room for the arrow
    y = ty + reach + block / 2 if ty < H / 2 else ty - reach - block / 2
    lo, hi = z["left"] + half_w, W - z["right"] - half_w
    x = int(min(max(tx, lo), hi)) if lo <= hi else int(W / 2)
    return lines, [size] * len(lines), x, int(y)


def callout_target(ov: dict[str, Any], W: int, H: int) -> tuple[float, float]:
    """Pixel position a callout points at (at_x / at_y are 0-1 of the OUTPUT frame; unset = a bit above centre)."""
    def frac(v: Any, default: float) -> float:
        try:
            return min(0.95, max(0.05, float(v)))
        except (TypeError, ValueError):
            return default
    return frac(ov.get("at_x"), 0.5) * W, frac(ov.get("at_y"), 0.42) * H


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
        kind = ov.get("kind") or "text"
        a = max(0.0, float(ov.get("start") or 0.0))
        b = min(duration, float(ov.get("end") or a + (CARD_DEFAULT_S if kind == "time_card" else 2.5)))
        if b - a < 0.2:
            continue
        left = ov.get("align") == "left" and kind not in TITLE_KINDS + STORY_KINDS
        style = ("Title" if kind in TITLE_KINDS + STORY_KINDS else "CTA" if kind == "cta"
                 else "LabelBox" if ov.get("box") else "Label")
        where = ov.get("position") or ("top" if kind == "hook_title" else "center")
        if left and not ov.get("position"):
            where = "bottom"
        x, y = anc.get(where) or anc["top"]
        st = doc.styles[style]
        emph_at = None
        if kind in TITLE_KINDS:
            lines, sizes, emph_at = title_lines(text, ov.get("emphasis") or "", kind, st, doc, anc["max_width"])
        elif kind == "time_card":
            lines, sizes = card_lines(text.upper(), st, doc, anc["max_width"])
        elif kind == "callout":
            lines, sizes, x, y = callout_label(text.upper(), ov, st, doc, anc, z)
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
            y0, room_end, dropped = y, doc.height - z["bottom"], False
            while True:
                clash = [(pb, bot) for pa, pb, bot in pushed if pa < b and a < pb]
                top = max([seam + 0.6 * cap_size + cap_pad] + [bot for _, bot in clash])
                y = max(y0, int(math.ceil(top + gap + block / 2)))
                if y + block / 2 <= room_end or not clash or kind in TITLE_KINDS + STORY_KINDS:
                    break
                # no room left under a title that is on screen: a label / watermark waits until the title is gone
                a = max(pb for pb, _ in clash)
                if b - a < 0.2:
                    dropped = True
                    break
            if dropped:
                continue
            y = fit_y(y, block, platform, doc.width, doc.height)
            pushed.append((a, b, y + block / 2))
        y = fit_y(y, block, platform, doc.width, doc.height)
        events.append(OvEvent(ov, kind, style, a, b, lines, x, y, sizes, "left" if left else "center", emph_at))
    return events


def _tag_color(hex_color: str) -> str:
    return "&H" + ass_color(hex_color)[4:] + "&"  # override-tag form &HBBGGRR&


FPS_EV = 30  # per-frame helper events (eased slides, glitch layers) are cut at this rate
GLITCH_STEPS = [(-9, 3), (7, -4), (-5, 2), (8, 0), (-3, -2)]  # deterministic RGB-split offsets (dx, dy)


def _ease_out(p: float) -> float:
    return 1 - (1 - min(1.0, max(0.0, p))) ** 3


def _ease_in(p: float) -> float:
    return min(1.0, max(0.0, p)) ** 3


def _frames(a: float, d: float) -> list[tuple[float, float, float]]:
    """(start, end, progress 0-1 at the slice's middle) for ``d`` seconds from ``a``, one slice per 1/30 s."""
    n = max(1, int(round(d * FPS_EV)))
    return [(a + d * i / n, a + d * (i + 1) / n, (i + 0.5) / n) for i in range(n)]


def _plain(body: str) -> str:
    """The text with its per-line colour overrides removed (RGB-split layers set their own colour)."""
    return re.sub(r"\\1c&H[0-9A-Fa-f]{6}&", "", body)


def _rgb_layers(doc: AssDoc, layer: int, a: float, d: float, style: str, base: str, body: str, x: int, y: int) -> None:
    """Glitch: red + cyan ghosts of the text, jittering for ``d`` seconds from ``a`` (blinking: every third slice off)."""
    for i, (s, e, _) in enumerate(_frames(a, d)):
        if i % 3 == 2:
            continue
        dx, dy = GLITCH_STEPS[i % len(GLITCH_STEPS)]
        for col, sign in (("&H0000FF&", 1), ("&HFFFF00&", -1)):
            doc.add(layer - 1, s, e, style, f"{{{base}\\pos({x + sign * dx},{y + sign * dy})\\1c{col}\\bord0\\shad0"
                                            f"\\1a&H60&}}{_plain(body)}")


def _poly(points: list[list[tuple[float, float]]]) -> tuple[str, int, int]:
    """ASS drawing of closed polygons, translated so the union's top-left is (0, 0) → (path, x0, y0). The event
    then sits at ``\\an7\\pos(x0,y0)``: the same picture whether libass anchors at the drawing origin or its box."""
    xs = [p[0] for poly in points for p in poly]
    ys = [p[1] for poly in points for p in poly]
    x0, y0 = int(min(xs)), int(min(ys))
    parts = []
    for poly in points:
        pts = [f"{int(round(px - x0))} {int(round(py - y0))}" for px, py in poly]
        parts.append(f"m {pts[0]} l {' '.join(pts[1:])}")
    return " ".join(parts), x0, y0


def _rect_event(doc: AssDoc, layer: int, a: float, b: float, rect: tuple[int, int, int, int], color: str,
                alpha: str, extra: str = "") -> None:
    path, x0, y0 = _poly([[(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])]])
    doc.add(layer, a, b, "Shape", f"{{\\an7\\pos({x0},{y0})\\bord0\\shad0\\1c{color}\\1a{alpha}{extra}\\p1}}{path}{{\\p0}}")


def _build_time_card(doc: AssDoc, ev: Any, accent: str) -> None:
    """Big time-jump card: dark band across the frame with accent rules, the text sliding (or glitching) in on an
    ease-out in 220-280 ms and leaving ≈ 70 % as fast. Everything inside the card is the SAME box the lint measured."""
    ov, a, b, x, y, W, H = ev.ov, ev.start, ev.end, ev.x, ev.y, doc.width, doc.height
    if "Shape" not in doc.styles:
        doc.styles["Shape"] = Style("Shape", "Arial", 20, outline=0, shadow=0, alignment=7, margin_l=0, margin_r=0,
                                    margin_v=0)
    anim = ov.get("style") or "slide"
    d = b - a
    enter = min(0.22 if anim == "glitch" else 0.28, d / 3)
    leave = enter * 0.7
    block = sum(ev.sizes)
    pad = int(0.014 * H)
    y0, y1 = int(y - block / 2 - pad), int(y + block / 2 + pad)
    rule = max(3, int(0.003 * H))
    body = "\\N".join(f"{{\\fs{ev.sizes[i]}\\1c&HFFFFFF&}}{' '.join(ln)}" for i, ln in enumerate(ev.lines))

    # band: wipes in left→right (ease-out), wipes out to the right (ease-in)
    ms_in, ms_out = int(enter * 1000), int(leave * 1000)
    for s, e, tags in ((a, a + enter, f"\\clip(0,{y0},0,{y1})\\t(0,{ms_in},0.4,\\clip(0,{y0},{W},{y1}))"),
                       (a + enter, b - leave, ""),
                       (b - leave, b, f"\\clip(0,{y0},{W},{y1})\\t(0,{ms_out},2.2,\\clip({W},{y0},{W},{y1}))")):
        _rect_event(doc, 4, s, e, (0, y0, W, y1), "&H000000&", "&H40&", tags)
        for ry in (y0, y1 - rule):
            _rect_event(doc, 4, s, e, (0, ry, W, ry + rule), accent, "&H00&", tags)

    shad = "\\bord0\\shad5"
    if anim == "glitch":  # 3-frame RGB tear on arrival, then the text settles
        for s, e, p in _frames(a, enter):
            dx = int((1 - p) * 40 * (1 if int(p * 9) % 2 else -1))
            doc.add(5, s, e, "Title", f"{{\\an5\\pos({x + dx},{y})\\alpha&H{int(255 * (1 - _ease_out(p * 1.6)) // 1):02X}&{shad}}}{body}")
        _rgb_layers(doc, 5, a, enter, "Title", "\\an5", body, x, y)
    else:  # slide in from the left, ease-out; fast ease-in out to the right
        for s, e, p in _frames(a, enter):
            k = _ease_out(p)
            doc.add(5, s, e, "Title", f"{{\\an5\\pos({int(x - 340 * (1 - k))},{y})\\fscx{int(135 - 35 * k)}"
                                      f"\\blur{(1 - k) * 7:.1f}\\alpha&H{int(255 * (1 - min(1.0, k * 1.5))):02X}&{shad}}}{body}")
    doc.add(5, a + enter, b - leave, "Title", f"{{\\an5\\pos({x},{y}){shad}}}{body}")
    for s, e, p in _frames(b - leave, leave):
        k = _ease_in(p)
        doc.add(5, s, e, "Title", f"{{\\an5\\pos({int(x + 220 * k)},{y})\\fscx{int(100 + 30 * k)}"
                                  f"\\alpha&H{int(255 * k):02X}&{shad}}}{body}")


def _circle(r: int) -> str:
    k = int(r * 0.5523)
    return (f"m {2 * r} {r} b {2 * r} {r + k} {r + k} {2 * r} {r} {2 * r} b {r - k} {2 * r} 0 {r + k} 0 {r} "
            f"b 0 {r - k} {r - k} 0 {r} 0 b {r + k} 0 {2 * r} {r - k} {2 * r} {r}")


def _build_callout(doc: AssDoc, ev: Any, accent: str) -> None:
    """Hand-drawn-feeling callout: a ring pops onto the spot, an arrow draws itself from the label toward it
    (a clip that wipes along the shaft), and the label lands as a stamp / glitch / pop."""
    ov, a, b, x, y, W, H = ev.ov, ev.start, ev.end, ev.x, ev.y, doc.width, doc.height
    if "Shape" not in doc.styles:
        doc.styles["Shape"] = Style("Shape", "Arial", 20, outline=0, shadow=0, alignment=7, margin_l=0, margin_r=0,
                                    margin_v=0)
    anim = ov.get("style") or "pop"
    tx, ty = callout_target(ov, W, H)
    R = int(CALLOUT_R * W)
    block = sum(ev.sizes)
    # arrow: from the label edge nearest the target to just outside the ring
    sy = y - block / 2 - 12 if ty < y else y + block / 2 + 12
    sx = x + min(max(tx - x, -ev.sizes[0] * 2.0), ev.sizes[0] * 2.0)
    dx, dy = tx - sx, ty - sy
    dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / dist, dy / dist
    ex, ey = tx - ux * (R + 14), ty - uy * (R + 14)  # the tip
    nx, ny = -uy, ux
    shaft, head_len, head_w = max(7, int(0.0045 * H)), int(0.03 * H), int(0.028 * H)
    hx, hy = ex - ux * head_len, ey - uy * head_len
    arrow = [[(sx + nx * shaft / 2, sy + ny * shaft / 2), (hx + nx * shaft / 2, hy + ny * shaft / 2),
              (hx + nx * head_w / 2, hy + ny * head_w / 2), (ex, ey), (hx - nx * head_w / 2, hy - ny * head_w / 2),
              (hx - nx * shaft / 2, hy - ny * shaft / 2), (sx - nx * shaft / 2, sy - ny * shaft / 2)]]
    path, ax0, ay0 = _poly(arrow)

    # ring: dark halo under an accent stroke, popping in with an ease-out overshoot (stamp: from 160 %)
    start = {"stamp": "160", "glitch": "100"}.get(anim, "125")
    ms = 180 if anim == "stamp" else 220
    ring = _circle(R)
    for lay, bord, col, alpha in ((4, 17, "&H000000&", "&H70&"), (5, 8, accent, "&H00&")):
        doc.add(lay, a, b, "Shape", f"{{\\an5\\pos({int(tx)},{int(ty)})\\1a&HFF&\\3c{col}\\3a{alpha}\\bord{bord}\\shad0"
                                    f"\\fscx{start}\\fscy{start}\\t(0,{ms},0.4,\\fscx100\\fscy100)\\fad(60,140)\\p1}}{ring}{{\\p0}}")
    if anim == "glitch":
        for i, (s, e, _) in enumerate(_frames(a, 0.12)):
            if i % 3 != 2:
                gx, gy = GLITCH_STEPS[i % len(GLITCH_STEPS)]
                for col, sign in (("&H0000FF&", 1), ("&HFFFF00&", -1)):
                    doc.add(5, s, e, "Shape", f"{{\\an5\\pos({int(tx + sign * gx)},{int(ty + sign * gy)})\\1a&HFF&\\3c{col}"
                                              f"\\3a&H40&\\bord6\\shad0\\p1}}{ring}{{\\p0}}")

    # arrow: drawn along its shaft by an expanding clip (starts 100 ms after the ring), dark edge for contrast
    t0 = a + 0.10
    if b - t0 > 0.12:
        cx0, cy0, cx1, cy1 = (int(min(sx, ex)) - 40, int(min(sy, ey)) - 40, int(max(sx, ex)) + 40, int(max(sy, ey)) + 40)
        from_x, from_y = int(sx), int(sy)
        doc.add(5, t0, b, "Shape", f"{{\\an7\\pos({ax0},{ay0})\\1c{accent}\\3c&H000000&\\bord3\\shad0\\fad(0,140)"
                                    f"\\clip({from_x},{from_y},{from_x},{from_y})"
                                    f"\\t(0,260,0.4,\\clip({cx0},{cy0},{cx1},{cy1}))\\p1}}{path}{{\\p0}}")

    # label
    body = "\\N".join(f"{{\\fs{ev.sizes[i]}\\1c&HFFFFFF&}}{' '.join(ln)}" for i, ln in enumerate(ev.lines))
    la = a + 0.12
    if b - la < 0.12:
        return
    base = f"\\an5\\pos({x},{y})\\bord6\\shad6\\4c&H000000&\\4a&H60&"
    if anim == "stamp":  # slams down from 160 % with a slight rotation, then settles
        doc.add(5, la, b, "Title", f"{{{base}\\fscx160\\fscy160\\frz-9\\alpha&HFF&\\blur5\\t(0,180,0.5,"
                                   f"\\fscx100\\fscy100\\frz-3\\alpha&H00&\\blur0)\\fad(0,140)}}{body}")
    elif anim == "glitch":
        doc.add(5, la, b, "Title", f"{{{base}\\fad(0,140)}}{body}")
        _rgb_layers(doc, 5, la, 0.12, "Title", "\\an5", body, x, y)
    else:
        doc.add(5, la, b, "Title", f"{{{base}\\fscx75\\fscy75\\alpha&HFF&\\t(0,200,0.4,\\fscx100\\fscy100\\alpha&H00&)"
                                   f"\\fad(0,140)}}{body}")


STAMP_RED = "&H2B2BE8&"  # #E82B2B as an override colour (BGR)
STAMP_HIT_AT = 0.10  # s after the stamp appears: the moment it lands (the editor's `hit` SFX goes here)
STAMP_ENTER = 0.26  # s: scale-in + shake, then the stamp rests


def _text_w(meter: Any, font: str, text: str, size: float) -> float:
    """Width of ``text`` in px: the real face when the meter has it, else the conservative estimate."""
    if meter is not None and getattr(meter, "measured", False):
        return meter.width(text, size)
    return len(text) * size * _adv(font)


def _ink(hex_color: str) -> str:
    """Text colour (override form) that reads on an accent block: dark on light accents, white on dark ones."""
    h = ass_color(hex_color)[2:]  # AABBGGRR
    b, g, r = (int(h[i:i + 2], 16) for i in (2, 4, 6))
    return "&H141414&" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "&HFFFFFF&"


def is_stamp(ov: dict[str, Any]) -> bool:
    """punch_title and any text with style "stamp" are struck like a stamp; hook titles, cards and callouts have
    their own templates, typewriter stays a typewriter."""
    if ov.get("kind") in ("hook_title", "time_card", "callout") or ov.get("style") == "typewriter":
        return False
    return ov.get("kind") == "punch_title" or ov.get("style") == "stamp"


def _shape_style(doc: AssDoc) -> None:
    if "Shape" not in doc.styles:
        doc.styles["Shape"] = Style("Shape", "Arial", 20, outline=0, shadow=0, alignment=7, margin_l=0, margin_r=0,
                                    margin_v=0)


def _slam(p: float) -> int:
    """Emphasis word scale (%) over the entry: 125 → 95 (overshoot) → 100."""
    if p < 0.65:
        return int(round(125 - 30 * _ease_out(p / 0.65)))
    return int(round(95 + 5 * _ease_out((p - 0.65) / 0.35)))


def _build_hook_title(doc: AssDoc, ev: Any, hi: str, accent_hex: str) -> None:
    """Hook title template: small setup line(s) + ONE huge Anton emphasis word on a solid accent block, the whole
    thing tilted -4°, heavy shadow. Enters in ≈ 260 ms (eased drop-in, emphasis slams 125 % → 95 % → 100 %),
    leaves in ≈ 70 % of that. The block is the same glyph run drawn in BorderStyle 3 (libass sizes it exactly)."""
    ov, a, b, x, y, H = ev.ov, ev.start, ev.end, ev.x, ev.y, doc.height
    st = doc.styles["Title"]
    e0 = ev.emphasis_line or 0
    e1 = e0 + sum(1 for s in ev.sizes if s != st.size)
    ink, pad = _ink(accent_hex or "#FFE600"), max(10, int(0.012 * H))
    texts = [" ".join(ln) for ln in ev.lines]

    def layers(scale: int) -> tuple[str, str]:
        sc = f"\\fscx{scale}\\fscy{scale}"
        txt, blk = [], []
        for i, (t, sz) in enumerate(zip(texts, ev.sizes)):
            if e0 <= i < e1:
                txt.append(f"{{\\fs{sz}\\1c{ink}{sc}\\bord0\\shad0}}{t}")
                blk.append(f"{{\\fs{sz}{sc}\\1a&HFF&\\3a&H00&\\3c{hi}\\bord{pad}\\shad10\\4c&H000000&\\4a&H50&}}{t}")
            else:
                txt.append(f"{{\\fs{sz}\\1c&HFFFFFF&\\fscx100\\fscy100\\bord5\\shad10\\4c&H000000&\\4a&H50&}}{t}")
                blk.append(f"{{\\fs{sz}\\fscx100\\fscy100\\1a&HFF&\\3a&HFF&\\4a&HFF&\\bord0\\shad0}}{t}")
        return "\\N".join(txt), "\\N".join(blk)

    enter = min(0.26, (b - a) / 3)
    leave_ms = int(enter * 0.7 * 1000)
    tilt = f"\\frz{TITLE_TILT}"
    for s, e, p in _frames(a, enter):
        dy = -int(0.04 * H * (1 - _ease_out(p)))  # drops in from above, ease-out
        txt, blk = layers(_slam(p))
        pos = f"{{\\an5\\pos({x},{y + dy}){tilt}}}"
        doc.add(4, s, e, "TitleBlock", pos + blk)
        doc.add(5, s, e, "Title", pos + txt)
    txt, blk = layers(100)
    pos = f"{{\\an5\\pos({x},{y}){tilt}\\fad(0,{leave_ms})}}"
    doc.add(4, a + enter, b, "TitleBlock", pos + blk)
    doc.add(5, a + enter, b, "Title", pos + txt)


def _stamp_scale(t: float) -> float:
    """Stamp scale at ``t`` s after it appears: 1.4 → 0.94 in 100 ms (ease-out), back to 1.0 by 150 ms."""
    if t < STAMP_HIT_AT:
        return 1.4 - 0.46 * _ease_out(t / STAMP_HIT_AT)
    return 0.94 + 0.06 * min(1.0, (t - STAMP_HIT_AT) / 0.05)


SHAKE = [(6, -4), (-5, 5), (4, 3), (-6, -2), (3, -5), (-2, 3)]  # deterministic micro-shake (dx, dy), |.| ≤ 6 px


def _build_stamp(doc: AssDoc, ev: Any, meter: Any, cues: list[dict[str, Any]] | None) -> None:
    """A real stamp: thick red outline box + red lettering (white edge), struck at -8°, scale 1.4 → 0.94 → 1.0 in
    ≈ 120 ms, a 0.15 s micro-shake (±6 px) and a flickering ink alpha while it settles. The landing time goes
    into ``cues`` as a ``hit`` so the editor / renderer can put the SFX there."""
    _shape_style(doc)
    ov, a, b, x, y, H = ev.ov, ev.start, ev.end, ev.x, ev.y, doc.height
    st = doc.styles[ev.style]
    texts = [" ".join(ln) for ln in ev.lines]
    wtxt = max(_text_w(meter, st.font, t, sz) for t, sz in zip(texts, ev.sizes))
    padx, pady = int(0.024 * H), int(0.014 * H)
    bw, bh = int(wtxt + 2 * padx), int(sum(ev.sizes) + 2 * pady)
    th = max(8, int(0.0055 * H))  # ≥ 8 px frame
    frame = (f"m 0 0 l {bw} 0 {bw} {bh} 0 {bh} m {th} {th} l {th} {bh - th} {bw - th} {bh - th} {bw - th} {th}")
    body = "\\N".join(f"{{\\fs{sz}}}{t}" for t, sz in zip(texts, ev.sizes))
    tilt = f"\\frz{STAMP_TILT}"
    ink = f"\\1c{STAMP_RED}\\3c&HFFFFFF&\\bord4\\shad6\\4c&H000000&\\4a&H60&"
    ring = f"\\1c{STAMP_RED}\\bord0\\shad6\\4c&H000000&\\4a&H60&"
    enter = min(STAMP_ENTER, (b - a) / 2)
    for i, (s, e, _) in enumerate(_frames(a, enter)):
        t0, t1 = s - a, e - a
        sc0, sc1 = int(_stamp_scale(t0) * 100), int(_stamp_scale(t1) * 100)
        k = (t0 + t1) / 2 - 0.08  # shake runs 0.08-0.23 s and dies away
        dx, dy = ((int(SHAKE[i % len(SHAKE)][0] * (1 - k / 0.15)), int(SHAKE[i % len(SHAKE)][1] * (1 - k / 0.15)))
                  if 0 <= k < 0.15 else (0, 0))
        ms = max(1, int(round((e - s) * 1000)))
        grow = f"\\fscx{sc0}\\fscy{sc0}\\t(0,{ms},\\fscx{sc1}\\fscy{sc1})"
        ink_a = "\\alpha&H30&" if 0 <= k < 0.15 and i % 2 else ""  # ink skips a little while it settles
        pos = f"\\an5\\pos({x + dx},{y + dy}){tilt}{grow}"
        doc.add(4, s, e, "Shape", f"{{{pos}{ring}\\p1}}{frame}{{\\p0}}")
        doc.add(5, s, e, ev.style, f"{{{pos}{ink}{ink_a}}}{body}")
    pos = f"\\an5\\pos({x},{y}){tilt}\\fad(0,{int(enter * 0.7 * 1000)})"
    doc.add(4, a + enter, b, "Shape", f"{{{pos}{ring}\\p1}}{frame}{{\\p0}}")
    doc.add(5, a + enter, b, ev.style, f"{{{pos}{ink}}}{body}")
    if cues is not None:
        cues.append({"kind": "hit", "at": round(a + STAMP_HIT_AT, 3), "text": " ".join(texts)})


def build_overlays(doc: AssDoc, overlays: list[dict[str, Any]], platform: str, duration: float,
                   seam_at: Any = None, cap_size: float = 0.0, cap_pad: float = 0.0,
                   accent: str = "", meter: Any = None, cues: list[dict[str, Any]] | None = None) -> int:
    """``accent``: colour of the title emphasis (= captions.highlight_color, default yellow).
    ``meter``: a ``Meter`` of the title face (sizes the stamp frame; without it a conservative estimate).
    ``cues``: out-list; every stamp appends ``{"kind": "hit", "at": seconds}`` (when it lands)."""
    hi = _tag_color(accent or "#FFE600")
    n = 0
    for ev in plan_overlays(doc, overlays, platform, duration, seam_at, cap_size, cap_pad):
        ov, a, b, style, x, y, lines = ev.ov, ev.start, ev.end, ev.style, ev.x, ev.y, ev.lines
        if ev.kind == "hook_title" and (ov.get("style") or "pop") != "typewriter":
            _build_hook_title(doc, ev, hi, accent or "#FFE600")
            n += 1
            continue
        if is_stamp(ov):
            _build_stamp(doc, ev, meter, cues)
            n += 1
            continue
        if ev.kind == "time_card":
            _build_time_card(doc, ev, hi)
            n += 1
            continue
        if ev.kind == "callout":
            _build_callout(doc, ev, hi)
            n += 1
            continue
        title = ev.kind in TITLE_KINDS
        texts = [" ".join(ln) for ln in lines]
        anim = ov.get("style") or "pop"
        an = f"\\an{ev.an}"
        # title: tilted, drop shadow instead of a box; per-line \fs and the accent colour on the emphasis block
        tilt = f"\\frz{TITLE_TILT}" if title else ""
        look = f"{tilt}\\shad10\\4c&H000000&\\4a&H50&" if title else ""
        if anim == "typewriter":
            per = max(2, int(min(60, (b - a) * 100 * 0.5 / max(1, sum(len(t) for t in texts)))))
            texts = ["".join(f"{{\\k{per}}}{c}" if c != " " else " " for c in t) for t in texts]
        if title:
            e0 = ev.emphasis_line or 0
            e1 = e0 + sum(1 for s in ev.sizes if s != doc.styles[style].size)
            texts = [f"{{\\fs{ev.sizes[i]}\\1c{hi if e0 <= i < e1 else '&HFFFFFF&'}}}{t}" for i, t in enumerate(texts)]
        body = "\\N".join(texts)
        if anim == "slide":  # eased: one event per 1/30 s on an ease-out curve (ASS \move is linear)
            enter = min(0.24, (b - a) / 3)
            for s, e, p in _frames(a, enter):
                k = _ease_out(p)
                doc.add(5, s, e, style, f"{{{an}\\pos({int(x - 220 * (1 - k))},{y})\\alpha&H{int(255 * (1 - k)):02X}&{look}}}{body}")
            a, tags = a + enter, f"{an}\\pos({x},{y})\\fad(0,120)"
        elif anim == "fade":
            tags = f"{an}\\pos({x},{y})\\fad(220,220)"
        elif anim == "typewriter":
            tags = f"{an}\\pos({x},{y})\\2a&HFF&\\fad(0,150)"
        elif anim == "glitch":
            tags = f"{an}\\pos({x},{y})\\fad(0,150)"
            _rgb_layers(doc, 5, a, 0.12, style, an + tilt, body, x, y)
        else:  # pop: ease-out overshoot
            tags = (f"{an}\\pos({x},{y})\\fscx60\\fscy60\\t(0,140,0.5,\\fscx108\\fscy108)"
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


REWIND_PX = 92  # px at 1920: the label reads at a glance (≥ 90)
REWIND_MIN_S = 0.45


def rewind_label(label: str = "") -> str:
    """Text on the rewind pill: the part's time-jump label when it is short, else REWIND."""
    t = clean_text(label).upper()
    return t if 0 < len(t) <= 10 else "REWIND"


def add_rewind_tag(doc: AssDoc, at: float, dur: float, platform: str = "tiktok", label: str = "",
                   meter: Any = None) -> dict[str, int]:
    """Rewind label while the rewind transition runs: a dark pill top-left with a ◀◀ icon (blinking, drawn — no
    glyph needed) and REWIND / the time-jump label in ≥ 90 px. Slides in on an ease-out (≈ 200 ms), leaves in
    ≈ 70 % of that. Returns the pill rect {x0,y0,x1,y1} (the text inside it is ≥ 90 px)."""
    _shape_style(doc)
    W, H = doc.width, doc.height
    z = safe_zone(platform, W, H)
    size = int(REWIND_PX * H / 1920)
    font = doc.styles["Label"].font if "Label" in doc.styles else "Arial"
    text = rewind_label(label)
    padx, pady = int(0.42 * size), int(0.22 * size)
    icon_w, gap = int(0.95 * size), int(0.28 * size)
    tw = int(_text_w(meter, font, text, size) if getattr(meter, "measured", False) else len(text) * size * 0.64)
    x0, y0 = z["left"], z["top"] + int(0.02 * H)
    x1, y1 = min(x0 + padx + icon_w + gap + tw + padx, W - z["right"]), y0 + size + 2 * pady
    cy = (y0 + y1) // 2
    tri = int(0.5 * size)  # icon: two left-pointing triangles
    ix = x0 + padx

    def draw(s: float, e: float, dx: int, icon_on: bool, fade: str) -> None:
        doc.add(8, s, e, "Shape", f"{{\\an7\\pos({x0 + dx},{y0})\\1c&H000000&\\1a&H33&\\bord0\\shad0{fade}\\p1}}"
                                  f"m 0 0 l {x1 - x0} 0 {x1 - x0} {y1 - y0} 0 {y1 - y0}{{\\p0}}")
        if icon_on:
            tris = " ".join(f"m {j * tri * 0.95:.0f} {tri // 2} l {j * tri * 0.95 + tri:.0f} 0 {j * tri * 0.95 + tri:.0f} {tri}"
                            for j in (0, 1))
            doc.add(9, s, e, "Shape", f"{{\\an7\\pos({ix + dx},{cy - tri // 2})\\1c&H00E6FF&\\bord0\\shad0{fade}\\p1}}"
                                      f"{tris}{{\\p0}}")
        doc.add(9, s, e, "Label", f"{{\\an4\\pos({ix + icon_w + gap + dx},{cy})\\fs{size}\\1c&HFFFFFF&\\bord0\\shad0{fade}}}{text}")

    dur = max(dur, REWIND_MIN_S)
    enter = min(0.2, dur / 3)
    leave = enter * 0.7
    reach = x1  # slides in from (and out to) beyond the left edge
    for s, e, p in _frames(at, enter):  # ease-out in
        draw(s, e, -int(reach * (1 - _ease_out(p))), True, "")
    for i, (s, e, _) in enumerate(_frames(at + enter, dur - enter - leave)):  # icon blinks: 4 frames on, 4 off
        draw(s, e, 0, i // 4 % 2 == 0, "")
    for s, e, p in _frames(at + dur - leave, leave):  # ease-in out
        draw(s, e, -int(reach * _ease_in(p)), True, "")
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "size": size}


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
