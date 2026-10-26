"""Finding creators who are hiring clippers — only through channels that allow it.

What the research found (Oct 2026) and therefore what this module does:

- **Whop Content Rewards / contentrewards.com, Vyro, ClipFarm …** (the big CPM
  campaign boards) have no listing API and their terms forbid scraping/automated
  access. → *manual*: paste the campaign URL + terms (``noze agency lead add``).
  The manager parses and qualifies them; nothing is fetched from those domains.
- **Whop Bounties API** (official, beta): open clipping bounties visible to your
  account → automated with ``WHOP_API_KEY`` (your own user token).
- **Reddit** (r/VideoEditors_forhire, r/HireAnEditor, r/forhire …): official OAuth API,
  only with already-approved credentials (``REDDIT_CLIENT_ID``/``SECRET``). Reddit stops
  new API access requests on 31 Oct 2026 and closes the public Data API in March 2027.
- **YouTube** search for "clipping campaign"/"clippers wanted" (``YOUTUBE_API_KEY``,
  its own 100-calls/day search bucket).
- **Any RSS/Atom feed** you trust (``AGENCY_LEAD_FEEDS``): newsletters, job boards.
- Discord servers and TikTok stay manual (no compliant automation).
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from ..http import check_public_url
from .config import DEFAULT_SUBREDDITS
from .context import AgencyContext
from .roles import Manager

log = logging.getLogger("noze.agency.leads")

# Their terms forbid automated access — we never fetch these; paste the terms instead.
NO_AUTOMATION_HOSTS = ("whop.com", "contentrewards.com", "vyro.com", "discord.com", "discord.gg", "tiktok.com")
UA = "python:noze-agency:0.1 (lead finder)"


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "div", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    p.feed(raw)
    text = html.unescape("".join(p.parts))
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def automation_forbidden(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in NO_AUTOMATION_HOSTS)


def fetch_page_text(url: str, allow_private: bool = False) -> str:
    if automation_forbidden(url):
        raise PermissionError(f"{urlparse(url).hostname} doesn't allow automated access — copy the campaign "
                              "terms from the page and pass them with --terms / --terms-file")
    asyncio.run(check_public_url(url, allow_private))
    with httpx.Client(follow_redirects=True, timeout=20.0, headers={"User-Agent": UA}) as client:
        r = client.get(url)
        r.raise_for_status()
        for hop in r.history:
            asyncio.run(check_public_url(str(hop.headers.get("location") or hop.url), allow_private))
        return html_to_text(r.text)[:30000] if "html" in r.headers.get("content-type", "") else r.text[:30000]


class LeadFinder:
    def __init__(self, ax: AgencyContext):
        self.ax = ax
        self.store = ax.store
        self.cfg = ax.cfg
        self.manager = Manager(ax)

    # -- sources ---------------------------------------------------------------------------------
    def from_reddit(self, client: httpx.Client) -> list[dict[str, Any]]:
        cid, secret = self.cfg.base.key("REDDIT_CLIENT_ID"), self.cfg.base.key("REDDIT_CLIENT_SECRET")
        if not (cid and secret):
            return []
        tok = client.post("https://www.reddit.com/api/v1/access_token", auth=(cid, secret),
                          data={"grant_type": "client_credentials"}, headers={"User-Agent": UA})
        tok.raise_for_status()
        headers = {"Authorization": f"bearer {tok.json()['access_token']}", "User-Agent": UA}
        subs = self.cfg.lead_subreddits or list(DEFAULT_SUBREDDITS)
        keys = [k.lower() for k in self.cfg.lead_keywords]
        out = []
        for sub in subs:
            r = client.get(f"https://oauth.reddit.com/r/{sub}/new", params={"limit": 100}, headers=headers)
            if r.status_code >= 400:
                log.info("r/%s: HTTP %s", sub, r.status_code)
                continue
            for child in (r.json().get("data") or {}).get("children") or []:
                d = child.get("data") or {}
                text = f"{d.get('title', '')}\n{d.get('selftext', '')}"
                low = text.lower()
                if "[for hire]" in low or "for hire" in (d.get("link_flair_text") or "").lower():
                    continue  # editors offering themselves, not clients
                if not any(k in low for k in keys):
                    continue
                out.append({"source": f"reddit:r/{sub}", "url": f"https://www.reddit.com{d.get('permalink', '')}",
                            "title": d.get("title", ""), "creator": f"u/{d.get('author', '')}",
                            "body": d.get("selftext", ""),
                            "posted_at": time.strftime("%Y-%m-%d %H:%M", time.gmtime(d.get("created_utc") or 0))})
            time.sleep(0.7)  # stay far below 100 QPM
        return out

    def from_whop(self, client: httpx.Client) -> list[dict[str, Any]]:
        key = self.cfg.key("WHOP_API_KEY")
        if not key:
            return []
        r = client.get("https://api.whop.com/api/v1/bounties",
                       params={"business_goal_type": "clipping", "status": "open"},
                       headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        payload = r.json()
        items = payload.get("data") if isinstance(payload, dict) else payload
        out = []
        for b in items or []:
            bid = b.get("id") or ""
            body = "\n".join(str(b.get(k) or "") for k in ("description", "requirements", "reward", "rules"))
            out.append({"source": "whop:bounties", "url": b.get("url") or f"https://whop.com/bounties/{bid}",
                        "title": b.get("title") or b.get("name") or f"Whop bounty {bid}",
                        "creator": (b.get("company") or {}).get("title", "") if isinstance(b.get("company"), dict) else "",
                        "body": body + "\n(Listed via Whop's official Bounties API: clipping bounty, open.)",
                        "posted_at": str(b.get("created_at") or "")})
        return out

    def from_youtube(self, client: httpx.Client) -> list[dict[str, Any]]:
        key = self.cfg.base.key("YOUTUBE_API_KEY")
        if not key:
            return []
        after = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7 * 86400))
        r = client.get("https://www.googleapis.com/youtube/v3/search",
                       params={"part": "snippet", "q": '"clipping campaign" OR "clippers wanted" OR "hiring clippers"',
                               "type": "video", "order": "date", "publishedAfter": after, "maxResults": 25, "key": key})
        r.raise_for_status()
        out = []
        for it in r.json().get("items") or []:
            sn = it.get("snippet") or {}
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                out.append({"source": "youtube", "url": f"https://www.youtube.com/watch?v={vid}",
                            "title": sn.get("title", ""), "creator": sn.get("channelTitle", ""),
                            "body": sn.get("description", ""), "posted_at": sn.get("publishedAt", "")})
        return out

    def from_feeds(self, client: httpx.Client) -> list[dict[str, Any]]:
        out = []
        keys = [k.lower() for k in self.cfg.lead_keywords]
        for url in self.cfg.lead_feeds:
            try:
                r = client.get(url, headers={"User-Agent": UA})
                r.raise_for_status()
                root = ET.fromstring(r.content)
            except (httpx.HTTPError, ET.ParseError) as exc:
                log.info("feed %s: %s", url, exc)
                continue
            for item in root.iter():
                tag = item.tag.split("}")[-1]
                if tag not in ("item", "entry"):
                    continue
                get = {c.tag.split("}")[-1]: (c.text or "") for c in item}
                link = get.get("link") or next((c.get("href") for c in item if c.tag.endswith("link")), "") or ""
                text = html_to_text(get.get("description") or get.get("summary") or get.get("content") or "")
                title = get.get("title", "")
                if link and any(k in f"{title} {text}".lower() for k in keys):
                    out.append({"source": f"feed:{urlparse(url).hostname}", "url": link.strip(), "title": title,
                                "creator": get.get("author", ""), "body": text,
                                "posted_at": get.get("pubDate") or get.get("updated") or ""})
        return out

    # -- the scouting round --------------------------------------------------------------------------
    def scout(self) -> dict[str, Any]:
        """Pull new leads from every configured source and qualify the new ones."""
        report: dict[str, Any] = {"sources": {}, "new": 0, "qualified": []}
        with httpx.Client(timeout=25.0) as client:
            for name, fn in (("whop", self.from_whop), ("reddit", self.from_reddit),
                             ("youtube", self.from_youtube), ("feeds", self.from_feeds)):
                try:
                    found = fn(client)
                    report["sources"][name] = len(found)
                except Exception as exc:
                    report["sources"][name] = f"error: {exc}"[:200]
                    continue
                for lead in found:
                    lid, new = self.store.upsert_lead(lead)
                    if new:
                        report["new"] += 1
                        report["qualified"].append(self.qualify(lid))
        self.store.log(None, "manager", "lead_scout", f"lead scouting: {report['new']} new lead(s)",
                       report["sources"])
        return report

    def add_manual(self, url: str, terms: str = "", title: str = "", creator: str = "") -> dict[str, Any]:
        if not terms:
            terms = fetch_page_text(url, self.cfg.base.allow_private_fetch)
        first_line = terms.strip().splitlines()[0] if terms.strip() else url
        lid, _ = self.store.upsert_lead({"source": "manual", "url": url, "title": title or first_line[:120],
                                         "creator": creator, "body": terms})
        return self.qualify(lid)

    def qualify(self, lead_id: int) -> dict[str, Any]:
        lead = self.store.get_lead(lead_id)
        q = self.manager.qualify_lead(lead)
        status = "rejected" if q["decision"] == "reject" else "qualified"
        self.store.update_lead(lead_id, score=q["score"], decision=q["decision"],
                               reasons=q["reasons"] + [f"risk: {r}" for r in q["risks"]], terms=q["brief"],
                               outreach=q["outreach_draft"], status=status)
        return {"id": lead_id, "title": lead["title"], "decision": q["decision"], "score": q["score"]}

    def accept(self, lead_id: int, name: str = "") -> int:
        """Turn a qualified lead into a campaign (its terms become the brief + permission record)."""
        from .pipeline import Agency

        lead = self.store.get_lead(lead_id)
        if not lead:
            raise ValueError(f"no lead {lead_id}")
        brief = lead.get("terms") or {}
        cname = name or brief.get("campaign_name") or lead["title"][:60] or f"lead-{lead_id}"
        if self.store.get_campaign(cname):
            cname = f"{cname} ({lead_id})"
        cid = Agency(self.ax).create_campaign(cname, terms=lead.get("body", ""), url=lead["url"], brief=brief or None,
                                              creator=lead.get("creator", ""), lead_id=lead_id)
        self.store.update_lead(lead_id, status="accepted")
        return cid
