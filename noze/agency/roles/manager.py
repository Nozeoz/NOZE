"""Manager / supervisor: leads → briefs → staffing → monitoring → final approval."""

from __future__ import annotations

import re
import time
from typing import Any

from ..schemas import APPROVAL, BRIEF, LEAD_QUALIFICATION, conform, example
from .base import Role, dump

RISK_WORDS = ("casino", "gambling", "betting", "onlyfans", "nsfw", "18+", "adult", "pay to join", "entry fee",
              "deposit", "buy views", "bot views", "forex", "signals", "airdrop", "guaranteed profit", "dm for price",
              "investment opportunity", "impersonat")
OFFER_WORDS = ("clipper", "clippers", "clipping", "clip my", "clips of", "content rewards", "per 1k", "per 1000",
               "cpm", "short form editor", "short-form editor", "shorts editor", "tiktok editor", "reels editor",
               "hiring", "[hiring]", "paid per view", "per view")
# strongest invitation first: the evidence quoted is the sentence with the best phrase
PERMISSION_PHRASES = ("clip my", "clip our", "clips of my", "clips of our", "looking for clippers", "hiring clippers",
                      "clippers wanted", "clipping campaign", "clip and post", "post clips", "use my content",
                      "use our content", "use the footage", "provided footage", "repost", "available content",
                      "content rewards", "clip the")


def _num(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def heuristic_brief(text: str, url: str = "", name: str = "") -> dict[str, Any]:
    t = text or ""
    low = t.lower()
    b = example(BRIEF)
    b["campaign_name"] = name or (t.strip().splitlines()[0][:80].strip() if t.strip() else "campaign")
    tags = list(dict.fromkeys(re.findall(r"(?<![\w/])#[\w]{2,40}", t)))
    b["requirements"]["hashtags"] = [x for x in tags if x.lower() not in ("#ad",)]
    b["requirements"]["mentions"] = list(dict.fromkeys(
        m.rstrip(".") for m in re.findall(r"(?<![\w/.])@[A-Za-z0-9_.]{2,30}", t)))[:5]
    if "#ad" in low or "disclos" in low or "paid partnership" in low:
        b["requirements"]["disclosure"] = "#ad"
    m = re.search(r"\$\s?(\d+(?:[.,]\d+)?)\s*(?:/|per)\s*(?:1k|1,?000|thousand|k)\b", low) or \
        re.search(r"\$\s?(\d+(?:[.,]\d+)?)\s*cpm", low) or re.search(r"(\d+(?:[.,]\d+)?)\s*\$?\s*cpm", low)
    if m:
        b["payout"].update({"model": "cpm", "rate_usd": _num(m.group(1)), "per": "1000 views"})
    else:
        m = re.search(r"\$\s?(\d+(?:[.,]\d+)?)\s*(?:/|per)\s*(?:clip|video|short|edit)", low)
        if m:
            b["payout"].update({"model": "flat", "rate_usd": _num(m.group(1)), "per": "clip"})
    m = re.search(r"budget[^$\n]{0,40}\$\s?([\d,]+(?:\.\d+)?)\s*(k)?", low)
    if m:
        v = _num(m.group(1))
        b["payout"]["budget_usd"] = v * 1000 if v and m.group(2) else v
    m = re.search(r"(\d{1,3})\s*(?:-|–|to)\s*(\d{1,3})\s*(?:s\b|sec|seconds)", low)
    if m:
        b["clip_length"] = {"min_s": float(m.group(1)), "max_s": float(m.group(2))}
    else:
        mn = re.search(r"(?:at least|min(?:imum)?|longer than|over|more than)\s*(\d{1,3})\s*(?:s\b|sec|seconds)", low)
        mx = re.search(r"(?:under|max(?:imum)?|less than|no longer than|up to)\s*(\d{1,3})\s*(?:s\b|sec|seconds)", low)
        b["clip_length"] = {"min_s": float(mn.group(1)) if mn else 0.0, "max_s": float(mx.group(1)) if mx else 0.0}
    plats = []
    for word, plat in (("tiktok", "tiktok"), ("reels", "reels"), ("instagram", "reels"), ("shorts", "shorts"),
                       ("youtube", "shorts"), ("twitter", "x"), (" x ", "x"), ("facebook", "facebook")):
        if word in f" {low} " and plat not in plats:
            plats.append(plat)
    b["platforms"] = plats
    links = re.findall(r"https?://[^\s)>\]]+", t)
    b["source_material"] = [u for u in links if any(h in u for h in ("drive.google", "dropbox", "mega.nz",
                                                                     "frame.io", "wetransfer", "box.com"))]
    b["submission"]["url"] = url or None
    hits = [p for p in PERMISSION_PHRASES if p in low]
    if hits:
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", t) if x.strip()]
        sent = next((x for x in sents if hits[0] in x.lower()), "")
        b["permission"] = {"granted": True, "evidence": sent[:400], "url": url or None}
    else:
        b["permission"] = {"granted": False, "evidence": "", "url": url or None}
    b["risks"] = [w for w in RISK_WORDS if w in low]
    if "no network" in low or "one account" in low:
        b["requirements"]["other"].append("No networks: post from a single personal account")
    if "only" in low and ("provided footage" in low or "provided content" in low):
        b["requirements"]["other"].append("Use only the provided footage")
    for m in re.finditer(r"include\s+(\S+)\s+in\s+(?:the|your|each)\s+(?:post\s+)?caption", t, re.I):
        if m.group(1).rstrip(".,") not in b["requirements"]["mentions"]:  # "include twitch.tv/x in the caption"
            b["requirements"]["mentions"].append(m.group(1).rstrip(".,"))
    # "caption" alone usually means the post text, not burned-in subtitles
    if re.search(r"subtitle|burn(?:ed)?[- ]in|on[- ]screen captions|(?:add|use|include) captions|captions? (?:are )?"
                 r"(?:required|mandatory|must)", low):
        b["requirements"]["other"].append("Burned-in captions required")
    m = re.search(r"\b(?:for|by)\s+(?:the\s+)?(?:streamer|creator|youtuber|podcaster)\s+@?([A-Za-z0-9_]{3,30})", t)
    if m:
        b["creator"] = m.group(1)
    b["creator_handles"] = list(dict.fromkeys(h.rstrip(".") for h in re.findall(
        r"(?:twitch\.tv|kick\.com|tiktok\.com|youtube\.com|instagram\.com)/@?[A-Za-z0-9_.]+", t)))[:5]
    for lang, code in (("english", "en"), ("indonesian", "id"), ("bahasa", "id"), ("spanish", "es")):
        if re.search(rf"\b{lang}\b(?: only| language)|only {lang}\b|in {lang}\b", low):
            b["language"] = code
            break
    m = re.search(r"\b([a-z]+)\s+niche\b", low)
    if m and m.group(1) not in ("the", "any", "a", "your", "same"):
        b["niche"] = m.group(1)
    if "facecam" in low or "face cam" in low:
        b["requirements"]["other"].append("Keep the streamer's facecam visible in every clip")
    m = re.search(r"((?:twitch\.tv|kick\.com|youtube\.com)/[A-Za-z0-9_@.]+)[^\n]{0,80}?(?:on[- ]screen|overlay|every clip)",
                  t, re.I) or re.search(r"(?:on[- ]screen|overlay)[^\n]{0,80}?((?:twitch\.tv|kick\.com|youtube\.com)/"
                                        r"[A-Za-z0-9_@.]+)", t, re.I)
    if m:
        b["requirements"]["watermark"] = m.group(1).rstrip(".,")
    if re.search(r"(do not|don'?t|never) (cover|drown)[^\n]{0,30}(voice|audio)[^\n]{0,20}music|no music", low):
        b["style"]["avoid"].append("music over the voice")
    b["deliverables"]["clips_per_source"] = 3
    return b


class Manager(Role):
    name = "manager"

    # -- leads ------------------------------------------------------------------------------
    def qualify_lead(self, lead: dict[str, Any]) -> dict[str, Any]:
        cfg = self.ax.cfg
        task = (f"Studio capabilities: languages {cfg.languages}, niches {cfg.niches or 'any'}, platforms "
                f"tiktok/reels/shorts, fully automated editing with human-quality review.\n\n"
                f"Lead source: {lead['source']}\nURL: {lead['url']}\nTitle: {lead['title']}\nPosted by: "
                f"{lead.get('creator')}\nPosted at: {lead.get('posted_at')}\n\nText:\n{lead.get('body', '')[:15000]}")
        out = self.ask(None, task, LEAD_QUALIFICATION)
        if out is None:
            out = self._heuristic_qualify(lead)
        out["brief"]["permission"]["url"] = out["brief"]["permission"].get("url") or lead["url"]
        return out

    def _heuristic_qualify(self, lead: dict[str, Any]) -> dict[str, Any]:
        text = f"{lead.get('title', '')}\n{lead.get('body', '')}"
        low = text.lower()
        brief = heuristic_brief(text, lead["url"], lead.get("title", "")[:80])
        offer = any(w in low for w in OFFER_WORDS) and ("clip" in low or "short" in low or "reel" in low)
        score = 0.0
        reasons = []
        if offer:
            score += 40
            reasons.append("mentions paid clipping / short-form editing")
        if brief["payout"]["rate_usd"]:
            score += 25
            reasons.append(f"payout stated ({brief['payout']['model']} ${brief['payout']['rate_usd']})")
        if brief["permission"]["granted"]:
            score += 15
            reasons.append("explicitly invites clipping of their content")
        if brief["source_material"]:
            score += 10
            reasons.append("raw footage link provided")
        if brief["requirements"]["hashtags"] or brief["clip_length"]["max_s"]:
            score += 5
            reasons.append("clear posting rules")
        risks = brief["risks"]
        score -= 30 * len(risks)
        score = max(0.0, min(100.0, score))
        decision = "reject" if (not offer or risks) else ("accept" if score >= 70 else "maybe")
        return conform({
            "is_clipping_offer": offer, "score": score, "decision": decision, "reasons": reasons, "risks": risks,
            "brief": brief,
            "outreach_draft": ("Hi! We run a small short-form studio (TikTok/Reels/Shorts) and would love to clip "
                               "your content for this campaign. We follow your brief exactly — captions, hashtags "
                               "and disclosure included — and can start today. Samples on request."),
        }, LEAD_QUALIFICATION)

    def brief_from_terms(self, text: str, url: str = "", name: str = "") -> dict[str, Any]:
        """Campaign terms pasted by the user (or fetched from an allowed page) → brief."""
        task = (f"Turn these campaign terms into the brief. Campaign name hint: {name or '(derive one)'}\n"
                f"Campaign URL: {url or '(none)'}\n\nTerms:\n{text[:30000]}")
        out = self.ask(None, task, BRIEF)
        brief = out if out is not None else heuristic_brief(text, url, name)
        if name:
            brief["campaign_name"] = name
        if url and not brief["permission"].get("url"):
            brief["permission"]["url"] = url
        return brief

    # -- staffing -----------------------------------------------------------------------------
    def select_moments(self, moments: list[dict[str, Any]], n: int, min_s: float, max_s: float) -> list[dict[str, Any]]:
        """Best non-overlapping moments that fit the length window."""
        def overall(m: dict[str, Any]) -> float:
            s = m.get("scores") or {}
            return float(m.get("overall") or (0.35 * s.get("hook", 0) + 0.2 * s.get("flow", 0) +
                                              0.25 * s.get("value", 0) + 0.1 * s.get("trend", 0) +
                                              0.1 * s.get("emotion", 0)))

        picked: list[dict[str, Any]] = []
        for m in sorted(moments, key=overall, reverse=True):
            d = m["end_s"] - m["start_s"]
            if d < max(3.0, min_s) or d > max_s * 1.4:
                continue
            if any(not (m["end_s"] <= p["start_s"] or m["start_s"] >= p["end_s"]) for p in picked):
                continue
            picked.append({**m, "overall": round(overall(m), 2)})
            if len(picked) >= n:
                break
        return picked

    # -- final gate -------------------------------------------------------------------------------
    def approve(self, job: dict[str, Any], packet: dict[str, Any], sheets: list[str],
                escalation: bool = False) -> dict[str, Any]:
        campaign = self.campaign_of(job)
        what = ("ESCALATION: editor and reviewer did not converge within the round limit. Decide approve "
                "(only if remaining issues are minor) or reject." if escalation else
                "Final approval of a clip the reviewer passed.")
        task = f"{what}\n\nEverything you need:\n{dump(packet)}"
        out = self.ask(job, task, APPROVAL, images=sheets, campaign=campaign)
        if out is None:
            out = self._heuristic_approve(packet, escalation)
        return out

    def _heuristic_approve(self, packet: dict[str, Any], escalation: bool) -> dict[str, Any]:
        review = packet.get("review") or {}
        issues = review.get("issues") or []
        blockers = [i for i in issues if i.get("severity") == "blocker"]
        majors = [i for i in issues if i.get("severity") == "major"]
        if escalation:
            decision = "approve" if not blockers and len(majors) <= 1 and (review.get("score") or 0) >= 6 else "reject"
        else:
            decision = "approve" if review.get("verdict") == "pass" and not blockers else "changes"
        post = packet.get("post") or {}
        return conform({"decision": decision,
                        "reasons": [f"review verdict {review.get('verdict')}, score {review.get('score')}, "
                                    f"{len(blockers)} blocker(s), {len(majors)} major issue(s)"],
                        "notes_for_editor": [] if decision != "changes" else issues[:5],
                        "post": {"title": packet.get("title", ""), "caption": post.get("caption", ""),
                                 "hashtags": post.get("hashtags", [])},
                        "risk_flags": []}, APPROVAL)

    # -- monitoring ---------------------------------------------------------------------------------
    def monitor(self, stale_after_s: float = 6 * 3600) -> list[dict[str, Any]]:
        """Alerts: stuck jobs, failures, budget pressure, campaigns without permission."""
        alerts: list[dict[str, Any]] = []
        now = time.time()
        for j in self.store.list_jobs(states=["failed"], limit=50):
            if now - (j.get("updated_at") or now) < 24 * 3600:
                alerts.append({"level": "error", "job": j["id"], "message": f"{j['kind']} job failed: {j['error'][:200]}"})
        active = [j for j in self.store.list_jobs(limit=500)
                  if j["state"] not in ("delivered", "rejected", "failed", "cancelled", "done")]
        for j in active:
            if now - (j.get("updated_at") or now) > stale_after_s and j["state"] != "awaiting_human":
                alerts.append({"level": "warn", "job": j["id"],
                               "message": f"{j['kind']} job stuck in '{j['state']}' for "
                                          f"{(now - j['updated_at']) / 3600:.1f}h"})
            if j["state"] == "awaiting_human":
                alerts.append({"level": "info", "job": j["id"], "message": "clip waiting for your approval"})
        spent = self.store.spend(since=now - 24 * 3600)
        if spent > 0.8 * self.ax.cfg.daily_budget_usd:
            alerts.append({"level": "warn", "job": None,
                           "message": f"LLM spend ${spent:.2f} in 24h (cap ${self.ax.cfg.daily_budget_usd:.2f})"})
        for c in self.store.list_campaigns("active"):
            if not (c.get("permission") or {}).get("granted"):
                alerts.append({"level": "warn", "job": None,
                               "message": f"campaign '{c['name']}' has no recorded clipping permission"})
        return alerts
