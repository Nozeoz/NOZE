"""The contracts between roles (JSON Schema), plus ``conform`` which makes any
payload — from Claude, a heuristic fallback or a human — fit its contract.

Every hand-off in the pipeline is one of these documents (MetaGPT-style
structured artifacts instead of free-form chat), so a role can be swapped,
retried or run without an LLM and the next role still gets what it expects.

Only the JSON Schema subset Claude's structured outputs accept is used here:
no numeric/string length constraints (ranges are enforced by the code that
consumes the value), nullable values via ``anyOf``.
"""

from __future__ import annotations

import copy
from typing import Any


# -- tiny schema builders ---------------------------------------------------------------
def S(desc: str = "") -> dict[str, Any]:
    return {"type": "string", **({"description": desc} if desc else {})}


def N(desc: str = "") -> dict[str, Any]:
    return {"type": "number", **({"description": desc} if desc else {})}


def I(desc: str = "") -> dict[str, Any]:  # noqa: E743 - reads like the other builders
    return {"type": "integer", **({"description": desc} if desc else {})}


def B(desc: str = "") -> dict[str, Any]:
    return {"type": "boolean", **({"description": desc} if desc else {})}


def E(values: list[str], desc: str = "") -> dict[str, Any]:
    return {"type": "string", "enum": list(values), **({"description": desc} if desc else {})}


def A(items: dict[str, Any], desc: str = "") -> dict[str, Any]:
    return {"type": "array", "items": items, **({"description": desc} if desc else {})}


def O(props: dict[str, Any], desc: str = "") -> dict[str, Any]:  # noqa: E743
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False,
            **({"description": desc} if desc else {})}


def Null(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


# -- shared vocab --------------------------------------------------------------------------
PLATFORMS = ["tiktok", "reels", "shorts", "x", "facebook", "other"]
SEVERITIES = ["blocker", "major", "minor"]
ISSUE_CATEGORIES = ["hook", "pacing", "captions", "framing", "audio", "text", "compliance", "story", "technical",
                    "visual", "other"]
CAPTION_STYLES = ["bold_pop", "karaoke", "minimal", "boxed", "outline"]
CAPTION_POSITIONS = ["upper", "center", "lower"]
REFRAME_MODES = ["auto", "center", "fixed", "fit_blur", "fill", "stack"]
ZOOM_TYPES = ["none", "punch", "push", "pull"]
TRANSITIONS = ["cut", "flash", "fade", "whip", "zoom"]
OVERLAY_STYLES = ["pop", "slide", "fade", "typewriter"]
OVERLAY_KINDS = ["hook_title", "text", "cta", "label"]
SFX_KINDS = ["whoosh", "pop", "hit", "riser", "click", "ding", "swoosh", "boom", "glitch"]
COLOR_PRESETS = ["none", "punchy", "warm", "cool", "bw", "cinematic"]
HOOK_TYPES = ["question", "bold_claim", "story", "visual", "controversy", "number", "secret", "challenge", "other"]
BEATS = ["hook", "setup", "context", "tension", "payoff", "cta", "other"]

# -- Manager: lead qualification & brief ---------------------------------------------------
PAYOUT = O({
    "model": E(["cpm", "flat", "rev_share", "unknown"]),
    "rate_usd": Null(N("USD per `per` unit, e.g. 1.5 for $1.5 per 1k views")),
    "per": S("unit for the rate, e.g. '1000 views', 'clip'"),
    "budget_usd": Null(N()),
    "min_views": Null(I("views needed before payout, if stated")),
    "notes": S(),
})

BRIEF = O({
    "campaign_name": S(),
    "creator": S("creator/brand that owns the content"),
    "creator_handles": A(S()),
    "niche": S(),
    "language": S("ISO code of the spoken language, e.g. en, id"),
    "platforms": A(E(PLATFORMS)),
    "payout": PAYOUT,
    "clip_length": O({"min_s": N(), "max_s": N()}),
    "style": O({
        "notes": S("tone/style the creator asked for"),
        "caption_style": S(),
        "must_include": A(S()),
        "avoid": A(S()),
    }),
    "requirements": O({
        "hashtags": A(S()),
        "mentions": A(S()),
        "disclosure": Null(S("e.g. '#ad' or 'clip from @creator'")),
        "watermark": Null(S()),
        "cta": Null(S()),
        "banned": A(S("things the clips must not contain")),
        "other": A(S()),
    }),
    "source_material": A(S("links/paths of long-form content we may clip")),
    "reference_examples": A(S("example clips the creator likes")),
    "submission": O({"method": S(), "url": Null(S()), "deadline": Null(S())}),
    "permission": O({
        "granted": B("true only if the text explicitly invites clipping/reposting of this content"),
        "evidence": S("verbatim sentence(s) that grant permission"),
        "url": Null(S()),
    }),
    "deliverables": O({"clips_per_source": I()}),
    "risks": A(S()),
})

LEAD_QUALIFICATION = O({
    "is_clipping_offer": B("the post offers paid clipping/short-form editing work"),
    "score": N("0-100 overall attractiveness for our studio"),
    "decision": E(["accept", "maybe", "reject"]),
    "reasons": A(S()),
    "risks": A(S()),
    "brief": BRIEF,
    "outreach_draft": S("short, honest message we could send to apply (never auto-sent)"),
})

# -- Scout -----------------------------------------------------------------------------------
REFERENCE_PICK = O({
    "picks": A(O({
        "ref": S("the id/path/url exactly as given"),
        "why": S(),
        "learn": A(S("what the analyst should study in it")),
    })),
    "search_queries": A(S("queries to find more references later")),
    "used_lessons": A(S()),
})

# -- Analyst ---------------------------------------------------------------------------------
REFERENCE_BREAKDOWN = O({
    "summary": S(),
    "hook": O({"type": E(HOOK_TYPES), "text": S(), "duration_s": N(), "why_it_works": S()}),
    "script_structure": A(O({"beat": E(BEATS), "start_s": N(), "end_s": N(), "purpose": S()})),
    "visual": O({"framing": S(), "b_roll": S(), "color_grade": S(), "text_overlays": S()}),
    "captions": O({
        "present": B(), "style": E(CAPTION_STYLES), "words_per_caption": I(), "position": E(CAPTION_POSITIONS),
        "uppercase": B(), "highlight_color": S("hex like #FFE600 or empty"), "animation": S(), "font_guess": S(),
    }),
    "motion": O({"zooms": S(), "transitions": S(), "graphics": S()}),
    "sound": O({"music": S(), "sfx": S(), "ducking": S()}),
    "retention_devices": A(S()),
    "cta": S(),
    "takeaways": A(S("concrete, reusable instruction for our editor")),
})

BLUEPRINT = O({
    "name": S(),
    "summary": S(),
    "hook_formula": S(),
    "hook_max_s": N("the hook must land within this many seconds"),
    "beats": A(O({"beat": E(BEATS), "share": N("0-1 share of the clip"), "guidance": S()})),
    "pacing": O({
        "target_shot_s": N("average seconds between visual changes"),
        "max_static_s": N("never hold an unchanged frame longer than this"),
        "remove_silences_over_s": N(),
        "cut_fillers": B(),
    }),
    "captions": O({
        "style": E(CAPTION_STYLES), "words_per_caption": I(), "position": E(CAPTION_POSITIONS),
        "uppercase": B(), "highlight_color": S(),
    }),
    "framing": O({"mode": E(REFRAME_MODES), "notes": S()}),
    "motion": O({
        "punch_in_every_s": N(), "punch_scale": N("e.g. 1.12"), "shake_on_impact": B(),
        "transitions": A(E(TRANSITIONS)),
    }),
    "sound": O({
        "music_mood": S("search words for background music, empty = none"),
        "music_gain_db": N(), "sfx_density": E(["none", "low", "medium", "high"]), "sfx_palette": A(E(SFX_KINDS)),
    }),
    "text_overlays": O({"hook_title": B(), "style": E(OVERLAY_STYLES), "cta_text": S()}),
    "color": E(COLOR_PRESETS),
    "dos": A(S()),
    "donts": A(S()),
    "used_lessons": A(S()),
})

MOMENTS = O({
    "moments": A(O({
        "start_s": N(), "end_s": N(), "title": S(), "hook_line": S("first words the viewer hears/reads"),
        "hook_type": E(HOOK_TYPES), "summary": S(),
        "scores": O({"hook": N("0-10"), "flow": N("0-10"), "value": N("0-10"), "trend": N("0-10"),
                     "emotion": N("0-10")}),
        "rationale": S(), "keywords": A(S()),
    })),
    "used_lessons": A(S()),
})

# -- Editor ------------------------------------------------------------------------------------
SEGMENT = O({
    "src_start": N("seconds in the source video"),
    "src_end": N(),
    "speed": N("1.0 normal; 0.8-1.25 sensible"),
    "reframe": O({
        "mode": E(REFRAME_MODES, "stack = streamer facecam on top, gameplay below (needs cam)"),
        "x": N("0-1 horizontal center of the subject (fixed mode) or of the gameplay (stack mode)"),
        "cam": Null(O({"x": N("left edge 0-1"), "y": N("top edge 0-1"), "w": N("width 0-1"), "h": N("height 0-1")},
                      "facecam rectangle in the source frame, as fractions")),
    }),
    "zoom": O({"type": E(ZOOM_TYPES), "scale": N("1.0-1.35")}),
    "shake": B(),
    "transition_in": E(TRANSITIONS),
    "note": S(),
})

EDIT_PLAN = O({
    "title": S("working title of the clip"),
    "segments": A(SEGMENT),
    "captions": O({
        "enabled": B(), "style": E(CAPTION_STYLES), "words_per_caption": I(), "position": E(CAPTION_POSITIONS),
        "uppercase": B(), "highlight_color": S(), "font_scale": N("1.0 default"),
    }),
    "overlays": A(O({
        "kind": E(OVERLAY_KINDS), "text": S(), "start": N("output seconds"), "end": N(),
        "position": E(["top", "upper", "center", "lower", "bottom"]), "style": E(OVERLAY_STYLES),
    })),
    "sfx": A(O({"kind": E(SFX_KINDS), "at": N("output seconds"), "gain_db": N()})),
    "music": O({"enabled": B(), "mood": S(), "asset": S("NOZE asset id or file path; empty = pick by mood"),
                "gain_db": N(), "duck": B()}),
    "color": E(COLOR_PRESETS),
    "progress_bar": B(),
    "post": O({"caption": S(), "hashtags": A(S())}),
    "fixes": A(O({"issue_id": S(), "change": S()})),
    "used_lessons": A(S()),
    "rationale": S(),
})

# -- Reviewer / Manager -------------------------------------------------------------------------
ISSUE = O({
    "category": E(ISSUE_CATEGORIES),
    "severity": E(SEVERITIES),
    "timecode_s": Null(N()),
    "description": S(),
    "fix": S("exact, actionable instruction for the editor"),
})

CREATIVE_REVIEW = O({
    "scores": O({"hook": N("0-10"), "pacing": N(), "captions": N(), "framing": N(), "audio": N(),
                 "compliance": N(), "overall": N()}),
    "issues": A(ISSUE),
    "resolved_previous": A(O({"issue_id": S(), "resolved": B(), "note": S()})),
    "summary": S(),
    "used_lessons": A(S()),
})

APPROVAL = O({
    "decision": E(["approve", "changes", "reject"]),
    "reasons": A(S()),
    "notes_for_editor": A(ISSUE),
    "post": O({"title": S(), "caption": S(), "hashtags": A(S())}),
    "risk_flags": A(S()),
    "used_lessons": A(S()),
})

# -- Learning ---------------------------------------------------------------------------------------
REFLECTION = O({
    "bullet_tags": A(O({"id": S(), "tag": E(["helpful", "harmful", "neutral"]), "why": S()})),
    "new_lessons": A(O({
        "role": E(["manager", "scout", "analyst", "editor", "reviewer"]),
        "section": S("short topic, e.g. hook, captions, pacing, audio, framing, brief, qc"),
        "scope": E(["global", "campaign", "creator"]),
        "text": S("one concrete, reusable instruction (imperative, <= 220 chars)"),
        "evidence": S("what in this job shows it"),
    })),
    "root_causes": A(S()),
    "summary": S(),
})

RETRO = O({
    "summary": S(),
    "wins": A(S()),
    "problems": A(S()),
    "new_lessons": REFLECTION["properties"]["new_lessons"],
    "retire": A(O({"id": S(), "why": S()})),
})


# -- conform ----------------------------------------------------------------------------------------
def _default(schema: dict[str, Any]) -> Any:
    if "anyOf" in schema:
        return None
    t = schema.get("type")
    if t == "object":
        return {k: _default(v) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return []
    if t == "string":
        return schema["enum"][0] if "enum" in schema else ""
    if t in ("number", "integer"):
        return 0
    if t == "boolean":
        return False
    return None


def conform(value: Any, schema: dict[str, Any]) -> Any:
    """Coerce ``value`` into ``schema``: fill missing keys with defaults, drop unknown keys,
    cast scalars, snap bad enum values to the first option. Never raises."""
    if "anyOf" in schema:
        if value is None:
            return None
        inner = next((s for s in schema["anyOf"] if s.get("type") != "null"), {})
        return conform(value, inner)
    t = schema.get("type")
    if t == "object":
        src = value if isinstance(value, dict) else {}
        return {k: conform(src.get(k), sub) if k in src else _default(sub)
                for k, sub in schema.get("properties", {}).items()}
    if t == "array":
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            value = [value]
        return [conform(v, schema.get("items", {})) for v in value]
    if t == "string":
        s = "" if value is None else (value if isinstance(value, str) else str(value))
        if "enum" in schema and s not in schema["enum"]:
            low = s.strip().lower()
            match = next((e for e in schema["enum"] if e.lower() == low), None)
            return match if match is not None else schema["enum"][0]
        return s
    if t == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    if t == "integer":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if t == "boolean":
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "y", "on")
        return bool(value)
    return copy.deepcopy(value)


def example(schema: dict[str, Any]) -> Any:
    """A schema-shaped skeleton (used by heuristics as a starting point)."""
    return _default(schema)
