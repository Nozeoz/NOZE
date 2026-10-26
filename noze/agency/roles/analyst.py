"""Analyst: reference breakdowns → blueprint, and moment mining in the source."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from ..media.analyze import measure
from ..media.transcribe import all_words, for_prompt, speech_rate, transcribe
from ..schemas import BLUEPRINT, MOMENTS, REFERENCE_BREAKDOWN, conform, example
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
                 "unbelievable", "insane", "crazy", "takut", "nangis", "ketawa", "kaget", "marah", "keren", "gila")
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
                blueprint: dict[str, Any], n: int, min_s: float, max_s: float) -> list[dict[str, Any]]:
        words = all_words(transcript)
        found: list[dict[str, Any]] = []
        if words and self.ax.llm.available:
            found = self._llm_moments(job, transcript, brief, blueprint, n, min_s, max_s)
        if not found:
            found = self._heuristic_moments(words, facts, n * 3, min_s, max_s, transcript.get("language") or "en")
        snapped = []
        for m in found:
            s = snap_moment(m, words, min_s, max_s)
            if s:
                snapped.append(s)
        # dedupe: drop a moment overlapping >50% of an already kept, better one
        snapped.sort(key=lambda m: _overall(m), reverse=True)
        kept: list[dict[str, Any]] = []
        for m in snapped:
            d = m["end_s"] - m["start_s"]
            if any(min(m["end_s"], k["end_s"]) - max(m["start_s"], k["start_s"]) > 0.5 * d for k in kept):
                continue
            kept.append({**m, "overall": round(_overall(m), 2)})
        return kept

    def _llm_moments(self, job, transcript, brief, blueprint, n, min_s, max_s) -> list[dict[str, Any]]:
        lines = for_prompt(transcript, max_chars=10 ** 9).splitlines()
        chunks, cur, size = [], [], 0
        for ln in lines:
            if size + len(ln) > 40000 and cur:
                chunks.append(cur)
                cur, size = cur[-8:], sum(len(x) for x in cur[-8:])  # overlap so no moment is split
            cur.append(ln)
            size += len(ln) + 1
        if cur:
            chunks.append(cur)
        out: list[dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            task = (f"Find up to {max(2, n * 2 // max(1, len(chunks)) + 1)} clip moments in this part "
                    f"({i + 1}/{len(chunks)}) of the transcript. Each must run {min_s:.0f}-{max_s:.0f}s.\n"
                    f"Brief (niche/style/rules):\n{dump({k: brief.get(k) for k in ('niche', 'language', 'style', 'clip_length', 'platforms')}, 3000)}\n"
                    f"Blueprint hook formula: {blueprint.get('hook_formula')}\n\nTranscript:\n" + "\n".join(chunk))
            res = self.ask(job, task, MOMENTS, campaign=self.campaign_of(job))
            if res is None:
                return []
            out += res.get("moments") or []
        return out

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
                emotion = min(10.0, 3.0 + 1.5 * sum(text.count(e) for e in EMOTION_WORDS) + text.count("!"))
                flow = 6.0 + 2.0 * bool(re.search(r"[.!?]$", sents[j]["text"])) - 2.0 * (
                    sents[j]["text"].lower().rstrip(".!?").split()[-1:] in (["and"], ["but"], ["so"], ["dan"]))
                pace = nwords / max(1.0, d)
                trend = 4.0 + min(3.0, max(0.0, pace - 1.8) * 2)
                cands.append({
                    "start_s": s0["start"], "end_s": sents[j]["end"], "title": s0["text"][:70],
                    "hook_line": s0["text"][:120], "hook_type": "question" if "?" in s0["text"] else "bold_claim",
                    "summary": text[:200], "rationale": "heuristic: hook words, payoff punctuation, pace",
                    "scores": {"hook": min(10.0, hook), "flow": max(0.0, min(10.0, flow)), "value": value,
                               "trend": trend, "emotion": emotion},
                    "keywords": [],
                })
        cands.sort(key=_overall, reverse=True)
        return cands[: limit * 4]


def _overall(m: dict[str, Any]) -> float:
    s = m.get("scores") or {}
    return (0.35 * float(s.get("hook", 0)) + 0.2 * float(s.get("flow", 0)) + 0.25 * float(s.get("value", 0)) +
            0.1 * float(s.get("trend", 0)) + 0.1 * float(s.get("emotion", 0)))
