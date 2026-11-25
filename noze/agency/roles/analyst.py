"""Analyst: reference breakdowns → blueprint, and moment mining in the source."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any

from ..media.analyze import measure
from ..media.transcribe import all_words, for_prompt, speech_rate, transcribe
from ..schemas import BEAT_INDEX, BLUEPRINT, MOMENTS, REFERENCE_BREAKDOWN, conform, example
from ..story import envelope, label_parts, moment_parts, parts_duration
from .base import Role, dump

log = logging.getLogger("noze.agency.analyst")

HOOK_WORDS = {
    "en": ("why", "how", "never", "secret", "mistake", "nobody", "everyone", "stop", "truth", "worst", "best",
           "crazy", "insane", "actually", "wrong", "biggest", "only", "million", "money", "free", "hack",
           "warning", "don't", "dont", "won't", "impossible", "shocking", "real reason", "here's"),
    "id": ("kenapa", "gimana", "rahasia", "jangan", "ternyata", "gila", "banget", "parah", "salah", "terbesar",
           "cuma", "uang", "juta", "miliar", "nggak ada", "semua orang", "sebenarnya", "sumpah", "anjir", "fakta"),
}
VALUE_WORDS = ("because", "reason", "tip", "step", "how to", "the key", "lesson", "learned", "rule", "strategy",
               "%", "percent", "$", "karena", "caranya", "tips", "langkah", "kuncinya", "pelajaran", "strategi")
EMOTION_WORDS = ("love", "hate", "scared", "afraid", "cried", "laugh", "shocked", "angry", "amazing", "terrible",
                 "unbelievable", "insane", "crazy", "takut", "nangis", "ketawa", "kaget", "marah", "keren", "gila",
                 # live-stream reactions: what makes a gaming/IRL moment clippable
                 "what the", "no way", "let's go", "oh my god", "come on", "wtf", "fuck", "anjir", "astaga")
WEAK_OPENERS = ("and", "so", "but", "um", "uh", "like", "yeah", "okay", "terus", "jadi", "tapi", "nah", "dan", "ya")

DEFAULT_BLUEPRINT: dict[str, Any] = {
    "name": "house: talking-head short",
    "summary": "Fast, caption-led vertical clip: hook in the first second, jump cuts with alternating punch-ins, "
               "bold 1-3 word captions, light SFX on beats, payoff ending.",
    "hook_formula": "Open on the most provocative sentence of the moment; reinforce it with a ≤7-word hook title.",
    "hook_max_s": 1.5,
    "beats": [
        {"beat": "hook", "share": 0.1, "guidance": "the claim/question that makes them stay"},
        {"beat": "context", "share": 0.3, "guidance": "only the context needed to understand the payoff"},
        {"beat": "tension", "share": 0.3, "guidance": "build: the problem, the stakes, the twist"},
        {"beat": "payoff", "share": 0.3, "guidance": "the answer/punchline; end right after it"},
    ],
    "pacing": {"target_shot_s": 2.8, "max_static_s": 4.0, "remove_silences_over_s": 0.4, "cut_fillers": True},
    "captions": {"style": "bold_pop", "words_per_caption": 3, "position": "lower", "uppercase": True,
                 "highlight_color": "#FFE600"},
    "framing": {"mode": "auto", "notes": "keep the speaker's face in the upper-middle third"},
    "motion": {"punch_in_every_s": 3.0, "punch_scale": 1.12, "shake_on_impact": False,
               "transitions": ["cut", "flash"]},
    "sound": {"music_mood": "", "music_gain_db": -19.0, "sfx_density": "low", "sfx_palette": ["whoosh", "pop"]},
    "text_overlays": {"hook_title": True, "style": "pop", "cta_text": ""},
    "color": "punchy",
    "dos": ["start on a spoken word", "end on the payoff", "keep text inside the safe zone"],
    "donts": ["intros/greetings", "dead air", "music louder than the voice", "effects on every cut"],
    "used_lessons": [],
}


def sentences(words: list[dict[str, Any]], max_gap: float = 0.6) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    for w in words:
        if cur and w["start"] - cur[-1]["end"] > max_gap:
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", w["word"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"], "text": " ".join(w["word"] for w in s), "words": s}
            for s in out if s]


JUMP_CUT_SLACK = 1.15


def snap_moment(m: dict[str, Any], words: list[dict[str, Any]], min_s: float, max_s: float) -> dict[str, Any] | None:
    """Move a moment's edges to word/sentence boundaries; enforce the length window."""
    if not words:
        return m if m["end_s"] - m["start_s"] >= 3 else None
    sents = sentences(words)
    if not sents:
        return None
    start_sent = min(sents, key=lambda s: abs(s["start"] - m["start_s"]))
    i0 = sents.index(start_sent)
    target_end = m["end_s"]
    ends = [s for s in sents[i0:] if s["end"] > start_sent["start"]]
    if not ends:
        return None

    def span(s: dict[str, Any]) -> float:
        return s["end"] - start_sent["start"]

    # Jump cuts take pauses out, so aim ~15% above the minimum when the talk allows it.
    good = ([s for s in ends if min_s * JUMP_CUT_SLACK <= span(s) <= max_s]
            or [s for s in ends if min_s <= span(s) <= max_s])
    if not good:
        return None  # this stretch can't make a clip of the required length
    end_sent = min(good, key=lambda s: abs(s["end"] - target_end))
    prev_end = sents[i0 - 1]["end"] + 0.02 if i0 > 0 else 0.0
    j = sents.index(end_sent)
    next_start = sents[j + 1]["start"] if j + 1 < len(sents) else end_sent["end"] + 1.0
    start = max(prev_end, start_sent["start"] - 0.12)
    end = min(next_start - 0.02, end_sent["end"] + 0.25)
    if end - start < max(3.0, min_s):
        return None
    return {**m, "start_s": round(start, 3), "end_s": round(end, 3)}



# -- story mining: signals, arcs, honesty checks -------------------------------------------------------------------------
STORY_DIRECT = 60000  # transcript chars: below this one call reads the annotated transcript (no beat-index pass)
STORY_CHUNK = 40000
MIN_ARC_GAP_S = 45.0
STOPWORDS = frozenset("""that this with have from they them then than there their what when where which would could should
about because just like really very been were your you're i'm it's don't going gonna want know think said says okay
yeah right well also into over only even much more some will here those these being doing still never always""".split())
SETUP_RE = re.compile(r"\b(i bet|bet you|watch (?:me|this)|gonna|going to|never|i promise|promise|i swear|"
                      r"pasti|liat aja|lihat aja|jamin|awas|prediksi|bakal)\b", re.I)
# Dalvin: adult/sexual in-game scenes are skipped (FYP risk; clips are paid per view) -> big score penalty.
SEXUAL_RE = re.compile(
    r"\b(strip ?clubs?|strippers?|sex|sexual|sexy|seks|naked|nudes?|nudity|topless|lap ?dances?|freaky|porn|porno|"
    r"blow ?jobs?|orgasm|horny|boobs?|titties|tits|bokep|telanjang|bugil|mesum|ngentot|pelacur|stripteas\w*)\b", re.I)
SEXUAL_PENALTY = 3.0
ARC_GAP_BONUS = 2.0  # scan_arcs: a real cross-period arc outranks an equally good linear moment


def sexual_hits(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in SEXUAL_RE.finditer(text or "")})

# --- Referensi clipper 24 Nov (docs/REFERENSI-CLIPPER-2026-11.md): momen langka + emosi kuat yang meledak. All [D]. ---
# emotion = intensitas puncak, trend = kelangkaan; keyword (+ sinyal terukur) mengangkat skor LLM/heuristik.
INTENSE_RE = re.compile(
    r"\b(cry|cries|cried|crying|sobs?|sobbing|tears|weeping|nangis|menangis|rage|raging|furious|screams?|screaming|"
    r"screamed|ngamuk|marah banget|teriak|shocked|speechless|jaw dropped|kaget|syok|heartbroken)\b", re.I)
# kematian TOKOH CERITA saja ("bro I died" di gameplay bukan spoiler); kerabat: nama tokoh GTA VI + kata mati
_CHAR = r"(?:jason|lucia|main character|protagonist|tokoh utama|karakter utama)"
_DIE = r"(?:dies|died|dead|death|killed|mati|meninggal|tewas|kematian)"
STORY_DEATH = (rf"{_CHAR}\W+(?:\w+\W+){{0,2}}?{_DIE}|{_DIE}\W+(?:of\W+|nya\W+)?{_CHAR}|kills? off|funeral|pemakaman")
RARE_RE = re.compile(
    r"\b(first time|pertama kali|never seen|never before|belum pernah|turns out|ternyata|can actually|bisa begini|"
    rf"(?:the|game'?s?|story'?s?|gta'?s?) ending|final mission|end credits|credits roll|finale|plot twist|{STORY_DEATH})\b",
    re.I)
INTENSE_BOOST, INTENSE_CAP = 1.5, 3.0   # emotion points per keyword hit / max
SIGNAL_BOOST = 1.0                      # + when measured heat>=7, scream/laugh/chat spike or viewer clips agree
RARE_BOOST, RARE_CAP = 1.25, 2.5        # trend points per hit / max
# durasi: klip linear 18-32 dtk menang (Spearman -0,59); arc lintas periode bebas sampai 45 dtk
DUR_SWEET_S, DUR_BONUS = (18.0, 32.0), 0.8
LINEAR_SOFT_MAX_S, ARC_FREE_S, DUR_PENALTY_PER_S, DUR_PENALTY_CAP = 35.0, 45.0, 0.2, 2.5
# judul: [subjek dikenal] + [klaim ber-stakes], <=45 karakter
TITLE_MAX = 45
GENERIC_TITLE_RE = re.compile(r"^\W*(uh ?oh|oh no|wow|omg|their reactions?|reactions?|funny moment|crazy moment|"
                              r"best moment|moment at|peak at)\b", re.I)
# spoiler (ending/kematian tokoh/twist): paling ramai tapi risiko takedown Rockstar & dilarang banyak campaign
SPOILER_RE = re.compile(
    r"\b((?:the|game'?s?|story'?s?|gta'?s?) endings?|end of the game|final mission|last mission|end credits|credits roll|"
    r"finale|plot twist|spoilers?|tamat|"
    rf"akhir game|akhir cerita|{STORY_DEATH})\b", re.I)
SPOILER_PENALTY = 2.0  # brief melarang spoiler -> momen DITOLAK (spoiler_banned_by_brief), bukan penalti
_SPOIL_NO = re.compile(r"\b(?:no|without|zero)\W+(?:story\W+|plot\W+|major\W+)?spoil\w*|"
                       r"spoil\w*\W+(?:are\W+|is\W+)?(?:not\W+allowed|forbidden|banned|prohibited)|"
                       r"(?:do\W+not|don'?t|never|avoid)\W+(?:\w+\W+){0,2}spoil\w*|"
                       r"tanpa\W+spoil\w*|dilarang\W+(?:\w+\W+){0,1}spoil\w*|spoil\w*\W+dilarang|"
                       r"(?:jangan|tidak|tak|gak|ga|nggak|enggak|ngga)\W+(?:boleh\W+)?(?:ada\W+)?spoil\w*", re.I)
_SPOIL_OK = re.compile(r"spoil\w*\W+(?:are\W+|is\W+|boleh\W+)?(?:allowed|ok|okay|boleh|fine)|"
                       r"(?:allow|allowed|ok|okay|boleh)\W+(?:with\W+|ada\W+)?spoil\w*", re.I)


def spoiler_policy(brief: dict[str, Any] | None) -> str:
    """'banned' | 'allowed' | 'unknown' from brief.requirements.other + brief.style.notes (banned wins)."""
    b = brief or {}
    parts = list((b.get("requirements") or {}).get("other") or []) + [(b.get("style") or {}).get("notes") or ""]
    text = " ".join(str(x) for x in parts).lower()
    if _SPOIL_NO.search(text):
        return "banned"
    return "allowed" if _SPOIL_OK.search(text) else "unknown"


def short_title(subject: str, claim: str, limit: int = TITLE_MAX) -> str:
    """[subjek] + [klaim] cut on a word boundary to <= limit chars (no trailing punctuation)."""
    claim = re.sub(r"\s+", " ", (claim or "")).strip(" \"'")
    subject = re.sub(r"\s+", " ", (subject or "")).strip()
    text = f"{subject}: {claim}" if subject and claim else subject or claim
    if len(text) > limit:
        cut = text[:limit + 1]
        text = cut.rsplit(" ", 1)[0] if " " in cut[:limit] else cut[:limit]
    return text[:limit].rstrip(" ,.;:-!?") or text[:limit]


def duration_adjust(parts: list[dict[str, Any]], single: bool | None = None) -> float:
    """+bonus for a linear clip of 18-32 s; stepwise penalty above 35 s (multi-part arcs: free up to 45 s)."""
    dur = parts_duration(parts)
    if single is None:
        single = len(parts) == 1
    if single:
        if DUR_SWEET_S[0] <= dur <= DUR_SWEET_S[1]:
            return DUR_BONUS
        over = dur - LINEAR_SOFT_MAX_S
    else:
        over = dur - ARC_FREE_S
    return -min(DUR_PENALTY_CAP, DUR_PENALTY_PER_S * over) if over > 0 else 0.0


def arc_gap_s(parts: list[dict[str, Any]]) -> float:
    """Widest empty stretch of source between any two parts (either direction), seconds."""
    gap = 0.0
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            gap = max(gap, b["start_s"] - a["end_s"], a["start_s"] - b["end_s"])
    return gap


def fetch_plan(moments: list[dict[str, Any]], pad: float = 8.0, merge_gap: float = 30.0) -> list[tuple[float, float]]:
    """Source ranges to download for these moments: every part +-pad s, merged when closer than merge_gap s.
    Times are the parts' own (transcript/VOD) seconds; no LLM, no I/O."""
    spans = sorted((max(0.0, p["start_s"] - pad), p["end_s"] + pad) for m in moments for p in moment_parts(m))
    out: list[list[float]] = []
    for a, b in spans:
        if out and a - out[-1][1] < merge_gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in out]


class ArcScan(list):
    """scan_arcs result: the moments (a plain list) + ``ranges_to_fetch`` + ``rejected`` (why candidates were dropped)."""
    ranges_to_fetch: list[tuple[float, float]]
    rejected: list[dict[str, Any]]


_BASE_HEAT = {"heat": 0.0, "mean": 0.0, "laugh": 0.0, "chat": 0.0, "music": 0.0, "tags": [], "evidence": ""}


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) >= 4 and w not in STOPWORDS}


def heat_of(sig: dict[str, Any] | None, a: float, b: float) -> dict[str, Any]:
    """Measured excitement of a source range. Uses media.signals.heat_between when present, else a local reading of
    the same dict shape; no signals = all zeros (every caller must keep working then)."""
    if not sig:
        return dict(_BASE_HEAT)
    try:
        from ..media import signals as sg
        got = {**_BASE_HEAT, **sg.heat_between(sig, a, b)}
        return {**got, **{k: float(got[k] or 0) for k in ("heat", "mean", "laugh", "chat", "music")},
                "tags": list(got.get("tags") or []), "evidence": got.get("evidence") or ""}
    except Exception:  # noqa: BLE001 - module missing/older shape: read the bins ourselves
        pass
    step = float(sig.get("bin_s") or 2.0)
    bins = [x for x in sig.get("bins") or [] if x["t"] + step > a and x["t"] < b]
    out = dict(_BASE_HEAT)
    if bins:
        mus = [x["music"] for x in bins if x.get("music") is not None]
        out.update(heat=max(float(x.get("heat") or 0) for x in bins),
                   mean=sum(float(x.get("heat") or 0) for x in bins) / len(bins),
                   laugh=max(float(x.get("laugh") or 0) for x in bins),
                   chat=max(float(x.get("chat") or 0) for x in bins),
                   music=sum(mus) / len(mus) if mus else 0.0)
    peaks = [p for p in sig.get("peaks") or [] if p["end_s"] > a and p["start_s"] < b]
    out["tags"] = sorted({t for p in peaks for t in p.get("tags") or []})
    out["evidence"] = " · ".join(p.get("evidence", "") for p in peaks[:2] if p.get("evidence"))
    return out


def _timeline_text(sig: dict[str, Any] | None) -> str:
    if not sig:
        return ""
    try:
        from ..media import signals as sg
        return sg.prompt_timeline(sig, max_items=60)
    except Exception:  # noqa: BLE001
        return "\n".join(f"[{p['start_s']:.0f}-{p['end_s']:.0f}] heat {p.get('heat', 0):.1f} {p.get('evidence', '')}"
                         for p in (sig.get("peaks") or [])[:60])


def annotate(line: str, sig: dict[str, Any] | None) -> str:
    """Append the nearest measured signal to a transcript line, e.g. ``[🔥8.2 chat×45 KEKW]``, so the model sees what was loud."""
    m = re.match(r"\[([\d.]+)-([\d.]+)\] ", line)
    if not m or not sig:
        return line
    h = heat_of(sig, float(m.group(1)), float(m.group(2)))
    if h["heat"] < 3:
        return line
    bits = [f"🔥{h['heat']:.1f}"]
    if h["laugh"] >= 0.3:
        bits.append(f"laugh{h['laugh']:.1f}".replace("0.", "."))
    if h["evidence"]:
        bits.append(h["evidence"][:60])
    return f"{line}  [{' '.join(bits)}]"


def _speech_count(words: list[dict[str, Any]], a: float, b: float) -> int:
    return sum(1 for w in words if w["end"] > a and w["start"] < b)


def signal_beats(sig: dict[str, Any] | None, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Beats with no (or almost no) speech - game action, viewer clips - that the transcript alone would hide."""
    out: list[dict[str, Any]] = []
    for p in (sig or {}).get("peaks") or []:
        if _speech_count(words, p["start_s"], p["end_s"]) < 4:
            tags = p.get("tags") or []
            kind = "funny" if "funny" in tags else "shock" if "shock" in tags else "hype"
            out.append({"start_s": p["start_s"], "end_s": p["end_s"], "kind": kind, "heat": float(p.get("heat") or 0),
                        "summary": f"no speech: {p.get('evidence') or 'signal peak'}", "quote": "", "entities": []})
    for c in (sig or {}).get("clips") or []:
        out.append({"start_s": c["start_s"], "end_s": c["end_s"], "kind": "hype", "heat": 8.0, "quote": "",
                    "summary": f"viewers clipped this: {c.get('title', '')} ({c.get('views', '?')} views)",
                    "entities": []})
    return out


def beats_text(beats: list[dict[str, Any]]) -> str:
    rows = sorted(beats, key=lambda b: float(b.get("start_s") or 0))
    return "\n".join(f"#{i} [{b['start_s']:.0f}-{b['end_s']:.0f}] {b.get('kind', 'other')} h{float(b.get('heat') or 0):.0f}"
                     f" | {b.get('summary', '')} | \"{b.get('quote', '')}\" | {','.join(b.get('entities') or [])}"
                     for i, b in enumerate(rows))


def _tag_emotion(h: dict[str, Any]) -> str:
    tags = h.get("tags") or []
    if "funny" in tags or h.get("laugh", 0) >= 0.5:
        return "funny"
    return "shock" if "shock" in tags else "sad" if "sad" in tags else "hype"


def _quote_ok(quote: str, haystack: str) -> bool:
    """Fuzzy 'was this actually said': >= 60% of the quote's tokens occur in the part texts."""
    q = re.findall(r"[a-z0-9']+", (quote or "").lower())
    if not q:
        return True
    hay = set(re.findall(r"[a-z0-9']+", haystack.lower()))
    return sum(1 for t in q if t in hay) >= max(1, 0.6 * len(q))


def _snap_part(p: dict[str, Any], sents: list[dict[str, Any]], words: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Move one part to sentence boundaries. A part with no speech (pure gameplay) is kept as measured."""
    if not sents or not _speech_count(words, p["start_s"], p["end_s"]):
        return p
    s0 = min(sents, key=lambda s: abs(s["start"] - p["start_s"]))
    i0 = sents.index(s0)
    e0 = min(sents[i0:], key=lambda s: abs(s["end"] - p["end_s"]))
    j = sents.index(e0)
    prev_end = sents[i0 - 1]["end"] + 0.02 if i0 else 0.0
    next_start = sents[j + 1]["start"] if j + 1 < len(sents) else e0["end"] + 1.0
    start, end = max(prev_end, s0["start"] - 0.12), min(next_start - 0.02, e0["end"] + 0.25)
    return {**p, "start_s": round(start, 3), "end_s": round(end, 3)} if end - start >= 1.0 else None


def parts_overlap(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Seconds of source shared by two moments, counted per part (envelopes of arcs are hours wide and say nothing)."""
    pa, pb = moment_parts(a), moment_parts(b)
    return sum(max(0.0, min(x["end_s"], y["end_s"]) - max(x["start_s"], y["start_s"])) for x in pa for y in pb)


def _no(why: list[str] | None, reason: str) -> None:
    if why is not None:
        why.append(reason)
    return None


def build_moment(m: dict[str, Any], words: list[dict[str, Any]], sig: dict[str, Any] | None,
                 min_s: float, max_s: float, why: list[str] | None = None,
                 vod_map: list[dict[str, Any]] | None = None,
                 brief: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Turn a raw (model/heuristic) moment into a checked one, or None. Code decides, not the model: parts snapped to
    sentences, quotes and setup->payoff links verified against the transcript (C4), time-jump labels from real gaps,
    envelope, score with measured heat. ``vod_map`` (story pack: glued file -> stream time) drives the time-jump labels
    and rides on the moment so editor/QC label in stream time too. Sexual scenes are penalised (SEXUAL_PENALTY); spoilers per the brief's policy; rare + intense
    moments and 18-32 s linear clips are boosted (referensi clipper 24 Nov)."""
    raw = [p for p in (m.get("parts") or []) if isinstance(p, dict)]
    multi = len(raw) > 1
    parts = moment_parts(m)
    sents = sentences(words) if words else []
    if not multi:
        if words:
            s = snap_moment({"start_s": parts[0]["start_s"], "end_s": parts[0]["end_s"]}, words, min_s, max_s)
            if not s:
                return _no(why, "snap_failed: no sentence-aligned window of the required length")
            parts = [{**parts[0], "start_s": s["start_s"], "end_s": s["end_s"]}]
    else:
        parts = [_snap_part(p, sents, words) for p in parts]
        if any(p is None for p in parts):
            return _no(why, "part_snap_failed")
        if not (min_s <= parts_duration(parts) <= max_s * JUMP_CUT_SLACK):
            return _no(why, "duration_out_of_window")
    texts = [" ".join(w["word"] for w in words if w["end"] > p["start_s"] and w["start"] < p["end_s"]) for p in parts]
    heats = [heat_of(sig, p["start_s"], p["end_s"]) for p in parts]
    if words:
        if any(not t and h["heat"] < 4 for t, h in zip(texts, heats)):
            return _no(why, "part_without_speech_or_action")
        if not _quote_ok(m.get("hook_line") or "", " ".join(texts)):
            return _no(why, "quote_not_in_transcript")
    structure = m.get("structure") or "linear"
    if len(parts) == 1:
        structure = "linear"
    elif words and structure in ("arc", "cold_open", "montage"):
        grp: list[list[str]] = []  # seam-split pieces of one role = one part (else siblings "link" each other)
        for p, t in zip(parts, texts):
            if grp and grp[-1][0] == p["role"]:
                grp[-1][1] += " " + t
            else:
                grp.append([p["role"], t])
        texts_l = [g[1] for g in grp]
        sets = [_content_words(t) for t in texts_l]
        kws = {k.lower() for k in m.get("keywords") or []}
        linked = any(sets[i] & sets[j] for i in range(len(sets)) for j in range(i + 1, len(sets))) or (
            kws and sum(1 for t in texts_l if any(k in t.lower() for k in kws)) >= 2)
        if not linked:
            return _no(why, "setup_payoff_not_linked")
        setup = next((p["start_s"] for p in parts if p["role"] in ("setup", "foreshadow")), None)
        pay = next((p["start_s"] for p in reversed(parts) if p["role"] == "payoff"), None)
        if structure == "arc" and setup is not None and pay is not None and setup >= pay:
            return _no(why, "setup_after_payoff")
    n_groups = 1 + sum(1 for a, b in zip(parts, parts[1:]) if a["role"] != b["role"])
    parts = label_parts(parts, vod_map)
    if len(parts) != len(heats):  # label_parts split at a story-pack seam: re-read per final part
        heats = [heat_of(sig, p["start_s"], p["end_s"]) for p in parts]
    a, b = envelope(parts)
    dur = parts_duration(parts)
    h = {"heat": max((x["heat"] for x in heats), default=0.0), "tags": sorted({t for x in heats for t in x["tags"]}),
         "music": sum(x["music"] * (p["end_s"] - p["start_s"]) for x, p in zip(heats, parts)) / max(dur, 1e-6)}
    music_risk = h["music"] >= 0.6 or "music" in h["tags"]
    out = {**m, "start_s": round(a, 3), "end_s": round(b, 3), "parts": parts, "structure": structure,
           "vod_map": vod_map}
    adult = sexual_hits(" ".join(texts + [str(m.get(k) or "") for k in ("title", "summary", "story", "hook_line")]))
    out["scores"] = {**(m.get("scores") or {})}
    out["scores"].setdefault("story", 4.0 if len(parts) == 1 else 6.0)
    blob = " ".join(texts + [str(m.get(k) or "") for k in ("title", "summary", "story", "hook_line")])
    notes = []
    kw = len(INTENSE_RE.findall(blob))
    sig_hot = h["heat"] >= 7 or "scream" in h["tags"] or any(x.get("laugh", 0) >= 0.5 or x.get("chat", 0) >= 0.5
                                                           for x in heats)
    e_up = min(INTENSE_CAP, INTENSE_BOOST * kw) + (SIGNAL_BOOST if kw and sig_hot else 0.5 if sig_hot else 0.0)
    r_up = min(RARE_CAP, RARE_BOOST * len(RARE_RE.findall(blob)))
    if e_up:
        out["scores"]["emotion"] = min(10.0, float(out["scores"].get("emotion") or 0) + e_up)
        notes.append(f"emotion+{e_up:g}")
    if r_up:
        out["scores"]["trend"] = min(10.0, float(out["scores"].get("trend") or 0) + r_up)
        notes.append(f"rare+{r_up:g}")
    spoil = 0.0
    if SPOILER_RE.search(blob):
        policy = spoiler_policy(brief)
        out["spoiler"] = True
        if policy == "banned":
            return _no(why, "spoiler_banned_by_brief")
        spoil = 0.0 if policy == "allowed" else SPOILER_PENALTY
        notes.append(f"spoiler: policy {policy}, penalty -{spoil:g}")
    dadj = duration_adjust(parts, single=n_groups == 1)
    if dadj:
        notes.append(f"duration{dadj:+g}")
    title = str(m.get("title") or "")
    if m.get("title_auto") or not title or GENERIC_TITLE_RE.search(title):
        claim = title if m.get("title_auto") else (m.get("hook_line") or title)
        title = short_title(str((brief or {}).get("creator") or ""), claim)
    out["title"] = short_title("", title)
    out.pop("title_auto", None)
    if not out.get("emotion"):
        out["emotion"] = _tag_emotion(h) if h["heat"] >= 5 else ""
    if not out.get("signals"):
        out["signals"] = "; ".join(x["evidence"] for x in heats if x["evidence"])[:200]
    if not out.get("rationale"):
        out["rationale"] = f"{structure}: {out.get('story') or out.get('summary') or out.get('title') or 'moment'}"
    if music_risk:
        out["rationale"] += " [risk: dominant music, Content ID]"
    if adult:
        out["rationale"] += f" [penalty -{SEXUAL_PENALTY:g}: adult/sexual scene ({', '.join(adult[:3])})]"
        out["adult"] = True
    if notes:
        out["rationale"] += f" [{'; '.join(notes)}]"
    out["overall"] = round(_overall(out) + 0.2 * h["heat"] - (1.5 if music_risk else 0.0)
                           - (SEXUAL_PENALTY if adult else 0.0) - spoil + dadj, 2)
    return out


def _take(sents: list[dict[str, Any]], i: int, dur: float) -> tuple[float, float]:
    """Consecutive sentences from i until they cover ``dur`` seconds."""
    start, end = sents[i]["start"], sents[i]["end"]
    for s in sents[i + 1:]:
        if end - start >= dur:
            break
        end = s["end"]
    return start, end


def _heat_fn(sig: dict[str, Any] | None):
    """O(log n) max-heat-in-range over the bins (a heat_between call per sentence pair is minutes on a 6 h VOD)."""
    bins = sorted(((float(x["t"]), float(x.get("heat") or 0)) for x in (sig or {}).get("bins") or []))
    ts, hs = [t for t, _ in bins], [h for _, h in bins]
    step = float((sig or {}).get("bin_s") or 2.0)

    def heat(a: float, b: float) -> float:
        lo, hi = bisect_right(ts, a - step), bisect_left(ts, b)
        return max(hs[lo:hi], default=0.0)
    return heat


ARC_MAX_SETUPS = 200   # setups tried, best (most content words) first
ARC_MAX_PAYOFFS = 1500  # payoff sentences kept, strongest first


def heuristic_arcs(sents: list[dict[str, Any]], sig: dict[str, Any] | None, limit: int, min_s: float,
                   max_s: float, min_gap: float = MIN_ARC_GAP_S) -> list[dict[str, Any]]:
    """No-LLM story finder: a setup line (bet/promise/prediction) paired with a LATER high-heat or emotional payoff that
    shares real content words with it. Bounded: <= ARC_MAX_SETUPS x ARC_MAX_PAYOFFS cheap set tests, heat from a
    precomputed bin index."""
    target = min(max_s, max(min_s * JUMP_CUT_SLACK, (min_s + max_s) / 2))
    heat = _heat_fn(sig)
    wins = [_content_words(" ".join(s["text"] for s in sents[k:k + 2])) for k in range(len(sents))]
    pays: list[tuple[float, int]] = []
    for j, s in enumerate(sents):
        t = s["text"].lower()
        pay = heat(s["start"], s["end"]) + 1.5 * sum(t.count(e) for e in EMOTION_WORDS) + t.count("!")
        if pay >= 3 and wins[j]:
            pays.append((pay, j))
    pays = sorted(pays, reverse=True)[:ARC_MAX_PAYOFFS]
    setups = sorted((i for i, s in enumerate(sents) if SETUP_RE.search(s["text"]) and wins[i]),
                    key=lambda i: -len(wins[i]))[:ARC_MAX_SETUPS]
    found: list[tuple[float, int, int, float]] = []
    for i in setups:
        best = None
        for pay, j in pays:
            if sents[j]["start"] - sents[i]["end"] < min_gap:
                continue
            shared = len(wins[i] & wins[j])
            if shared and (best is None or pay + 1.5 * shared > best[0]):
                best = (pay + 1.5 * shared, i, j, pay)
        if best:
            found.append(best)
    out: list[dict[str, Any]] = []
    for _, i, j, pay in sorted(found, reverse=True)[:limit]:
        s = sents[i]
        s_a, s_b = _take(sents, i, 6.0)
        p_a, p_b = _take(sents, j, max(5.0, target - (s_b - s_a)))
        h = heat_of(sig, p_a, p_b)
        out.append({
            "start_s": s_a, "end_s": p_b, "structure": "arc", "emotion": _tag_emotion(h),
            "parts": [{"start_s": s_a, "end_s": s_b, "role": "setup", "label": ""},
                      {"start_s": p_a, "end_s": p_b, "role": "payoff", "label": ""}],
            "story": f"setup: {s['text'][:80]} -> payoff: {sents[j]['text'][:80]}",
            "title": sents[j]["text"][:70], "title_auto": True, "hook_line": s["text"][:120],
            "hook_type": "story",
            "summary": f"{s['text'][:100]} ... {sents[j]['text'][:100]}",
            "rationale": f"heuristic arc: bet/promise at {s_a:.0f}s pays off at {p_a:.0f}s (shared words, pay {pay:.1f})",
            "scores": {"hook": 5.0, "flow": 6.0, "value": 4.0, "trend": 5.0,
                       "emotion": min(10.0, 3.0 + pay / 2), "story": 8.0},
            "signals": h["evidence"], "keywords": sorted(wins[i] & wins[j])[:5]})
    return out


def peak_moments(sig: dict[str, Any] | None, limit: int, min_s: float, max_s: float) -> list[dict[str, Any]]:
    """No-LLM linear candidates centred on the loudest measured peaks (reaction first, then the aftermath)."""
    target = min(max_s, max(min_s * JUMP_CUT_SLACK, (min_s + max_s) / 2))
    dur = float((sig or {}).get("duration") or 0)
    out = []
    for p in sorted((sig or {}).get("peaks") or [], key=lambda p: -float(p.get("heat") or 0))[:limit]:
        a = max(0.0, p["start_s"] - 0.4 * target)
        b = a + target if not dur else min(dur, a + target)
        h = float(p.get("heat") or 0)
        out.append({"start_s": a, "end_s": b, "structure": "linear", "emotion": _tag_emotion(heat_of(sig, a, b)),
                    "title": f"Peak at {int(p['start_s'] // 60)}:{int(p['start_s'] % 60):02d}", "hook_line": "",
                    "hook_type": "visual", "summary": p.get("evidence", ""), "signals": p.get("evidence", ""),
                    "rationale": f"signal peak heat {h:.1f}: {p.get('evidence', '')}",
                    "scores": {"hook": 5.0, "flow": 5.0, "value": 3.0, "trend": 5.0, "emotion": min(10.0, h),
                               "story": 4.0}, "keywords": []})
    return out


class Analyst(Role):
    name = "analyst"

    # -- references ----------------------------------------------------------------------------
    def breakdown(self, job: dict[str, Any], ref: Path, why: str = "") -> dict[str, Any]:
        st = ref.stat()
        key = hashlib.sha1(f"{ref}:{st.st_size}:{int(st.st_mtime)}".encode()).hexdigest()[:16]
        cache_dir = self.ax.cfg.root / "cache" / "references"
        cache = cache_dir / f"{key}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        work = cache_dir / key
        stats = measure(ref, with_frames_dir=work / "frames")
        tr = transcribe(ref, self.ax.cfg.transcriber, self.ax.cfg.whisper_model, cache=work / "transcript.json")
        stats["speech_wpm"] = speech_rate(tr)
        facts = {k: stats.get(k) for k in ("shots", "loudness", "silence_share", "onsets", "energy_db", "speech_wpm")}
        facts["duration"] = stats["probe"].get("duration")
        facts["aspect"] = f"{stats['probe'].get('width')}x{stats['probe'].get('height')}"
        task = (f"Reference: {ref.name} (picked because: {why or 'n/a'})\n\nMeasured facts:\n{dump(facts, 6000)}\n\n"
                f"Transcript:\n{for_prompt(tr, max_chars=12000) or '(no speech / no transcript)'}\n\n"
                "The images are frame sheets of this reference, labelled with timestamps.")
        out = self.ask(job, task, REFERENCE_BREAKDOWN, images=stats.get("contact_sheets") or [],
                       campaign=self.campaign_of(job))
        if out is None:
            out = self._heuristic_breakdown(facts)
        result = {"ref": str(ref), "facts": facts, "breakdown": out}
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result

    def _heuristic_breakdown(self, facts: dict[str, Any]) -> dict[str, Any]:
        b = example(REFERENCE_BREAKDOWN)
        shots = facts.get("shots") or {}
        b["summary"] = (f"{facts.get('duration', 0):.0f}s reference, avg shot {shots.get('avg_shot_s', '?')}s, "
                        f"{shots.get('cuts_per_min', '?')} cuts/min, speech {facts.get('speech_wpm') or '?'} wpm.")
        b["captions"].update({"present": True, "style": "bold_pop", "words_per_caption": 3, "position": "lower",
                              "uppercase": True, "highlight_color": "#FFE600"})
        b["takeaways"] = [f"Aim for a visual change every ~{max(1.5, min(4.0, shots.get('avg_shot_s') or 2.8)):.1f}s."]
        return conform(b, REFERENCE_BREAKDOWN)

    def blueprint(self, job: dict[str, Any], breakdowns: list[dict[str, Any]], brief: dict[str, Any],
                  source_facts: dict[str, Any]) -> dict[str, Any]:
        task = (f"Brief:\n{dump(brief, 8000)}\n\nSource video facts:\n{dump(source_facts, 3000)}\n\n"
                f"Reference breakdowns ({len(breakdowns)}):\n{dump(breakdowns, 30000)}\n\n"
                f"House default blueprint (adapt, don't copy blindly):\n{dump(DEFAULT_BLUEPRINT, 4000)}")
        out = self.ask(job, task, BLUEPRINT, campaign=self.campaign_of(job))
        if out is None:
            out = json.loads(json.dumps(DEFAULT_BLUEPRINT))
            shots = [b["facts"].get("shots", {}).get("median_shot_s") for b in breakdowns if b.get("facts")]
            shots = [s for s in shots if s]
            if shots:
                out["pacing"]["target_shot_s"] = round(max(1.5, min(4.5, sorted(shots)[len(shots) // 2])), 2)
            style = (brief.get("style") or {}).get("caption_style", "").lower()
            for name in ("karaoke", "minimal", "boxed", "outline", "bold_pop"):
                if name.replace("_", " ") in style or name in style:
                    out["captions"]["style"] = name
            if (brief.get("requirements") or {}).get("cta"):
                out["text_overlays"]["cta_text"] = brief["requirements"]["cta"]
            out = conform(out, BLUEPRINT)
        out["pacing"]["max_static_s"] = min(float(out["pacing"].get("max_static_s") or 4.0), 5.0)
        if not out["captions"].get("words_per_caption"):
            out["captions"]["words_per_caption"] = 3
        return out

    # -- moments ---------------------------------------------------------------------------------
    def moments(self, job: dict[str, Any], transcript: dict[str, Any], facts: dict[str, Any], brief: dict[str, Any],
                blueprint: dict[str, Any], n: int, min_s: float, max_s: float,
                signals: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Candidate clips: single best moments AND stories stitched from different periods of the stream."""
        words = all_words(transcript)
        found: list[dict[str, Any]] = []
        self.last_rejected: list[dict[str, Any]] = []
        if words and self.ax.llm.available:
            found = self._llm_story(job, transcript, brief, blueprint, n, min_s, max_s, signals, words)

        vod_map = (facts or {}).get("vod_map")
        built = self._dedupe(self._build(found, words, signals, min_s, max_s, vod_map, brief))
        if len(built) < n:  # too few DISTINCT usable moments (after dedupe): top up from the measured heuristics
            extra = self._heuristic_moments(words, facts, n * 3, min_s, max_s, transcript.get("language") or "en")
            if words:
                extra += heuristic_arcs(sentences(words), signals, n * 2, min_s, max_s)
            built = self._dedupe(built + self._build(extra + peak_moments(signals, n * 2, min_s, max_s), words,
                                                     signals, min_s, max_s, vod_map, brief))
        return built

    def _build(self, raw, words, signals, min_s, max_s, vod_map, brief=None) -> list[dict[str, Any]]:
        ok = []
        for m in raw:
            why: list[str] = []
            b = build_moment(m, words, signals, min_s, max_s, why, vod_map, brief)
            if b:
                ok.append(b)
            else:
                self.last_rejected.append({"title": m.get("title", ""), "reason": why[0] if why else "invalid",
                                           "parts": moment_parts(m)})
        return ok

    def _dedupe(self, ms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Per part: drop a moment sharing >50% of its own length with an already kept, better one."""
        kept: list[dict[str, Any]] = []
        for m in sorted(ms, key=lambda m: m["overall"], reverse=True):
            if any(parts_overlap(m, k) > 0.5 * parts_duration(m["parts"]) for k in kept):
                self.last_rejected.append({"title": m.get("title", ""), "reason": "overlaps_better_moment",
                                           "parts": m["parts"]})
                continue
            kept.append(m)
        return kept

    def scan_arcs(self, job: dict[str, Any], transcript: dict[str, Any], signals: dict[str, Any] | None,
                  brief: dict[str, Any], n: int, min_s: float, max_s: float, gap_min_s: float = 600.0,
                  facts: dict[str, Any] | None = None, blueprint: dict[str, Any] | None = None) -> ArcScan:
        """Cross-period arcs from a LONG (hours) transcript, for the story-pack flow: pick clips, then download only
        ``ranges_to_fetch``. Part times are TRANSCRIPT seconds = stream/VOD seconds when the transcript is of the
        VOD (or audio-file seconds + the caller's offset: add it before calling, or pass ``facts["vod_map"]``).
        Priority: arc/cold_open/montage whose setup->payoff gap >= ``gap_min_s`` (+ARC_GAP_BONUS), best linear fills
        the rest. Every candidate goes through build_moment (quote said, setup/payoff linked). <= ~15 LLM calls for
        6 h (pass 1 chunks sized to <= 12 calls, pass 2 once). Returns the moments (best first) as a list with
        ``.ranges_to_fetch`` (fetch_plan of the picks) and ``.rejected``."""
        words = all_words(transcript)
        self.last_rejected = []
        vod_map = (facts or {}).get("vod_map")
        found: list[dict[str, Any]] = []
        if words and self.ax.llm.available:
            found = self._llm_story(job, transcript, brief, blueprint or {}, n, min_s, max_s, signals, words,
                                    gap_min_s=gap_min_s, max_chunks=12)
        built = self._build(found, words, signals, min_s, max_s, vod_map, brief)
        if words:
            extra = heuristic_arcs(sentences(words), signals, n * 2, min_s, max_s, min_gap=gap_min_s)
            extra += self._heuristic_moments(words, facts or {}, n * 3, min_s, max_s,
                                             transcript.get("language") or "en")
            built += self._build(extra + peak_moments(signals, n * 2, min_s, max_s), words, signals, min_s, max_s,
                                 vod_map, brief)
        for m in built:
            gap = arc_gap_s(m["parts"]) if len(m["parts"]) > 1 else 0.0
            m["arc_gap_s"] = round(gap, 1)
            if gap >= gap_min_s:
                m["overall"] = round(m["overall"] + ARC_GAP_BONUS, 2)
                m["rationale"] += f" [cross-period arc: {gap / 60:.0f} min between setup and payoff]"
        picked = self._dedupe(built)[:n]
        res = ArcScan(picked)
        res.ranges_to_fetch = fetch_plan(picked)
        res.rejected = list(self.last_rejected)
        return res

    def _llm_story(self, job, transcript, brief, blueprint, n, min_s, max_s, sig, words, gap_min_s=None,
                   max_chunks=None) -> list[dict[str, Any]]:
        """Pass 1 (long sources only): per-chunk beat index. Pass 2: ONE call composes the clips from the whole index."""
        lines = [annotate(ln, sig) for ln in for_prompt(transcript, max_chars=10 ** 9).splitlines()]
        camp = self.campaign_of(job)
        if sum(len(ln) + 1 for ln in lines) <= STORY_DIRECT:  # short VOD: the annotated transcript IS the index
            index = "Annotated transcript ([start-end] text  [measured signal]):\n" + "\n".join(lines)
        else:
            chunks, cur, size = [], [], 0
            total = sum(len(ln) + 1 for ln in lines)
            chunk_size = STORY_CHUNK if not max_chunks else max(STORY_CHUNK, total // max(1, max_chunks - 2))
            for ln in lines:
                if size + len(ln) > chunk_size and cur:
                    chunks.append(cur)
                    cur, size = cur[-8:], sum(len(x) for x in cur[-8:])
                cur.append(ln)
                size += len(ln) + 1
            chunks.append(cur)
            beats: list[dict[str, Any]] = []
            for i, chunk in enumerate(chunks):
                task = (f"Index the notable beats in part {i + 1}/{len(chunks)} of this stream transcript: funny, loud, "
                        "clutch/fail, shocking, emotional, rants, and especially SETUPS (predictions, promises, bets, "
                        "claims) and CALLBACKS/running gags another part of the stream could pay off. Short summaries "
                        "(<= 20 words), quote verbatim, name the entities. Lines tagged [🔥..] carry measured "
                        "excitement (chat/laughter/loudness): index those first. Do NOT index sexual/nudity scenes. "
                        + ("At most 25 beats for this part. " if max_chunks else "")
                        + "\n\nTranscript:\n" + "\n".join(chunk))
                res = self.ask(job, task, BEAT_INDEX, campaign=camp)
                if res is None:
                    return []
                beats += res.get("beats") or []
            index = "Beat index (#id [start-end] kind heat | summary | quote | entities):\n" + beats_text(beats)
        extra = signal_beats(sig, words)
        if extra:
            index += "\n\nBeats with no speech (action, viewer clips):\n" + beats_text(extra)
        timeline = _timeline_text(sig)
        task = (f"Compose up to {max(8, n * 3)} clip candidates (best first) of {min_s:.0f}-{max_s:.0f}s TOTAL each "
                f"(sum of parts; jump cuts later trim ~15%). Use structure linear / arc / cold_open / montage as the SOP "
                f"says; parts in PLAY order; role per part; the quote in hook_line must be said in the parts. Prefer "
                f"reactions and measured heat over plain talk; give every candidate a rationale. NEVER pick sexual/nudity "
                f"scenes (strip club, sex, naked...): pick reactions outside them.\n"
                f"SCORING (reference data): RARE + INTENSE beats funny-but-ordinary. scores.emotion = PEAK intensity "
                f"(crying/raging/huge shock = 9-10, ordinary laughing = 5-6, plain talk <= 3); scores.trend = RARITY "
                f"('first time', 'turns out the game can do this', ending, a character's death = 8-10; common banter "
                f"<= 4). The clip must OPEN on the peak or the strangest visual. Prefer 20-30 s linear clips (arcs may "
                f"run to ~45 s). `title` = [known subject: streamer/character] + [specific claim with stakes], "
                f"<= {TITLE_MAX} characters, no generic titles ('uh oh', 'their reactions'). Spoilers (ending, final "
                f"mission, credits, main character's death, plot twist) are penalised by code unless the brief allows.\n"
                + (f"PRIORITY: arc / cold_open / montage whose setup (prediction, promise, bet, running gag) and payoff are "
                   f">= {gap_min_s / 60:.0f} minutes apart, setup truly shown before the payoff and related to it; a few "
                   f"strong linear moments may fill the rest.\n" if gap_min_s else "")
                + f"Brief (niche/style/rules):\n{dump({k: brief.get(k) for k in ('niche', 'language', 'style', 'clip_length', 'platforms')}, 3000)}\n"
                f"Blueprint hook formula: {blueprint.get('hook_formula')}\n\n"
                + (f"Measured signal timeline:\n{timeline}\n\n" if timeline else "") + index)
        res = self.ask(job, task, MOMENTS, campaign=camp)
        return (res or {}).get("moments") or []


    def _heuristic_moments(self, words, facts, limit, min_s, max_s, lang) -> list[dict[str, Any]]:
        if not words:  # no transcript: use the loudest / busiest stretches
            dur = float((facts.get("probe") or {}).get("duration") or 0)
            target = min(max_s, max(min_s, 30.0))
            out, t = [], 0.0
            while t + target <= dur and len(out) < limit:
                out.append({"start_s": t, "end_s": t + target, "title": f"Moment at {int(t // 60)}:{int(t % 60):02d}",
                            "hook_line": "", "hook_type": "other", "summary": "", "rationale": "no transcript",
                            "scores": {"hook": 4, "flow": 5, "value": 4, "trend": 3, "emotion": 4}, "keywords": []})
                t += target
            return out
        sents = sentences(words)
        onsets = sorted(float(t) for t in facts.get("onsets") or [])  # loud reactions, hits, shouts
        hooks = HOOK_WORDS["id"] + HOOK_WORDS["en"] if lang.startswith("id") else HOOK_WORDS["en"] + HOOK_WORDS["id"]
        cands = []
        for i, s0 in enumerate(sents):
            first = s0["text"].lower()
            if first.split() and first.split()[0].strip(",.") in WEAK_OPENERS:
                continue
            hook = 3.0 + 2.5 * ("?" in s0["text"]) + 1.5 * bool(re.search(r"\d", first))
            hook += min(3.0, 1.0 * sum(1 for h in hooks if h in first))
            hook += 1.0 if len(s0["words"]) <= 14 else -0.5
            for j in range(i, len(sents)):
                d = sents[j]["end"] - s0["start"]
                if d > max_s:
                    break
                if d < min_s:
                    continue
                text = " ".join(s["text"] for s in sents[i:j + 1]).lower()
                nwords = sum(len(s["words"]) for s in sents[i:j + 1])
                value = min(10.0, 3.0 + 1.2 * sum(text.count(v) for v in VALUE_WORDS))
                hype = sum(1 for t in onsets if s0["start"] <= t <= sents[j]["end"])
                emotion = min(10.0, 3.0 + 1.5 * sum(text.count(e) for e in EMOTION_WORDS) + text.count("!")
                              + min(2.0, 0.25 * hype))
                flow = 6.0 + 2.0 * bool(re.search(r"[.!?]$", sents[j]["text"])) - 2.0 * (
                    sents[j]["text"].lower().rstrip(".!?").split()[-1:] in (["and"], ["but"], ["so"], ["dan"]))
                pace = nwords / max(1.0, d)
                trend = 4.0 + min(3.0, max(0.0, pace - 1.8) * 2)
                cands.append({
                    "start_s": s0["start"], "end_s": sents[j]["end"], "title": s0["text"][:70], "title_auto": True,
                    "hook_line": s0["text"][:120], "hook_type": "question" if "?" in s0["text"] else "bold_claim",
                    "summary": text[:200], "rationale": "heuristic: hook words, payoff punctuation, pace",
                    "scores": {"hook": min(10.0, hook), "flow": max(0.0, min(10.0, flow)), "value": value,
                               "trend": trend, "emotion": emotion},
                    "keywords": [],
                })
        cands.sort(key=_overall, reverse=True)
        # spread over the whole source: the best windows all overlap one dense stretch, so
        # suppress near-duplicates *before* cutting the list (or one hot minute fills it)
        kept: list[dict[str, Any]] = []
        for c in cands:
            d = c["end_s"] - c["start_s"]
            if all(min(c["end_s"], k["end_s"]) - max(c["start_s"], k["start_s"]) <= 0.5 * d for k in kept):
                kept.append(c)
            if len(kept) >= limit * 4:
                break
        return kept


def _overall(m: dict[str, Any]) -> float:
    # [D] 24 Nov (referensi clipper): momen langka + emosi kuat menentukan views, bukan edit/kata-hook.
    # dulu hook .30 flow .17 value .20 trend .08 emotion .12 story .13 -> kini emotion + trend naik.
    s = m.get("scores") or {}
    story = float(s["story"]) if s.get("story") is not None else float(s.get("flow", 0))
    return (0.25 * float(s.get("hook", 0)) + 0.12 * float(s.get("flow", 0)) + 0.10 * float(s.get("value", 0)) +
            0.15 * float(s.get("trend", 0)) + 0.23 * float(s.get("emotion", 0)) + 0.15 * story)
