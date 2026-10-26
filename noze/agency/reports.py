"""Reports the manager writes: per clip, per source batch, and the team report
(throughput, quality KPIs per role, recurring problems, spend, what the team learned)."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .context import AgencyContext
from .learning import TERMINAL


def _fmt_s(x: Any) -> str:
    try:
        return f"{float(x):.1f}s"
    except (TypeError, ValueError):
        return "—"


def clip_report(ax: AgencyContext, job: dict[str, Any]) -> Path:
    st = ax.store
    data = job.get("data") or {}
    moment = (job.get("input") or {}).get("moment") or {}
    plan = (st.artifact(job["id"], "plan") or {}).get("data") or {}
    render = (st.artifact(job["id"], "render") or {}).get("data") or {}
    approval = (st.artifact(job["id"], "approval") or {}).get("data") or {}
    reviews = st.reviews(job["id"])
    campaign = st.get_campaign(job["campaign_id"]) if job.get("campaign_id") else None
    spend = st.spend(job_ids=[job["id"]])
    loud = render.get("loudness") or {}
    lines = [
        f"# Clip #{job['id']} — {job.get('title')}",
        "",
        f"- **Campaign:** {campaign['name'] if campaign else 'own content'}",
        f"- **Status:** {job['state']} · review rounds: {job.get('round', 0)} · "
        f"first-pass: {'yes' if reviews and reviews[0]['verdict'] == 'pass' else 'no'}",
        f"- **Source moment:** {_fmt_s(moment.get('start_s'))} → {_fmt_s(moment.get('end_s'))} "
        f"(score {moment.get('overall', '—')})",
        f"- **Why this moment:** {moment.get('rationale') or moment.get('summary') or '—'}",
        f"- **Hook:** {moment.get('hook_line') or '—'}",
        f"- **Output:** {_fmt_s(render.get('duration'))}, {loud.get('integrated', '—')} LUFS, "
        f"true peak {loud.get('true_peak', '—')} dBTP, {render.get('captions', 0)} caption chunks, "
        f"{len(plan.get('sfx') or [])} SFX, music: {Path(render['music']).name if render.get('music') else 'none'}",
        f"- **Edit:** {len(plan.get('segments') or [])} segments · captions {plan.get('captions', {}).get('style')} · "
        f"colour {plan.get('color')} · text beats: "
        + ", ".join(f"{o['kind']} '{o['text']}'" for o in plan.get("overlays") or []),
        f"- **LLM cost:** ${spend:.3f}",
        "",
        "## Review history",
        "",
        "| round | by | verdict | score | issues |",
        "|---|---|---|---|---|",
    ]
    for r in reviews:
        top = "; ".join(f"[{i.get('severity')}] {i.get('description', '')[:80]}" for i in (r.get("issues") or [])[:4])
        lines.append(f"| {r['round']} | {r['reviewer']} | {r['verdict']} | {r['score'] if r['score'] is not None else '—'} "
                     f"| {top or '—'} |")
    fixes = [f for rnd in data.get("fix_log") or [] for f in rnd.get("fixes") or []]
    if fixes:
        lines += ["", "## Fixes the editor made", ""] + [f"- `{f['issue_id']}` → {f['change']}" for f in fixes]
    if approval:
        lines += ["", f"## Manager decision: {approval.get('decision', '').upper()}", ""]
        lines += [f"- {r}" for r in approval.get("reasons") or []]
    post = {**(plan.get("post") or {}), **{k: v for k, v in (data.get("post") or {}).items() if v}}
    lines += ["", "## Post copy", "", "```", (post.get("caption") or "").strip(),
              " ".join(post.get("hashtags") or []), "```"]
    delivery = data.get("delivery") or {}
    if delivery:
        lines += ["", "## Delivery", "", f"- File: `{delivery.get('video')}`",
                  f"- Targets: {', '.join(delivery.get('targets') or [])}"]
    learning = data.get("learning") or {}
    if learning:
        lines += ["", "## What the team learned", "",
                  f"- lessons tagged: {learning.get('tags', 0)}, new: {', '.join(learning.get('added') or []) or 'none'}, "
                  f"reinforced: {', '.join(learning.get('upvoted') or []) or 'none'}"]
    text = "\n".join(lines) + "\n"
    out = ax.cfg.reports_dir / "clips" / f"clip_{job['id']:05d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    if delivery.get("folder"):
        (Path(delivery["folder"]) / f"{job['id']:05d}_report.md").write_text(text, encoding="utf-8")
    return out


def source_report(ax: AgencyContext, job: dict[str, Any], kids: list[dict[str, Any]]) -> Path:
    st = ax.store
    moments = (st.artifact(job["id"], "moments") or {}).get("data") or {}
    bp = (st.artifact(job["id"], "blueprint") or {}).get("data") or {}
    refs = (st.artifact(job["id"], "references") or {}).get("data") or {}
    states = Counter(k["state"] for k in kids)
    spend = st.spend(job_ids=[job["id"]] + [k["id"] for k in kids])
    lines = [f"# Source #{job['id']} — {job.get('title')}", "",
             f"- clips: {len(kids)} ({', '.join(f'{v} {k}' for k, v in states.items())})",
             f"- candidate moments considered: {len(moments.get('candidates') or [])}",
             f"- references analysed: {len(refs.get('picks') or [])} · blueprint: {bp.get('name', '—')}",
             f"- LLM cost: ${spend:.3f}", "", "| clip | title | state | rounds |", "|---|---|---|---|"]
    lines += [f"| #{k['id']} | {k.get('title', '')[:60]} | {k['state']} | {k.get('round', 0)} |" for k in kids]
    out = ax.cfg.reports_dir / "sources" / f"source_{job['id']:05d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def team_metrics(ax: AgencyContext, days: float = 7.0, alerts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    st = ax.store
    alerts = _alerts(ax) if alerts is None else alerts
    since = time.time() - days * 86400
    clips = [j for j in st.list_jobs(kind="clip", limit=5000) if (j.get("created_at") or 0) >= since]
    done = [j for j in clips if j["state"] in TERMINAL]
    delivered = [j for j in done if j["state"] == "delivered"]
    reviews = {j["id"]: st.reviews(j["id"]) for j in clips}

    def first_review(jid: int) -> dict[str, Any] | None:
        return next((r for r in reviews[jid] if r["reviewer"] == "reviewer"), None)

    reviewed = [j for j in done if first_review(j["id"])]
    first_pass = [j for j in reviewed if first_review(j["id"])["verdict"] == "pass"]
    rounds = [int(j.get("round") or 0) for j in done if j.get("round")]
    escalated = [j for j in done if (j.get("data") or {}).get("escalated")]
    # reviewer misses: the reviewer passed it, then the manager or you sent it back / rejected it
    misses = [j for j in done if any(r["reviewer"] == "reviewer" and r["verdict"] == "pass" for r in reviews[j["id"]])
              and any(r["reviewer"] in ("manager", "human") and r["verdict"] != "pass" for r in reviews[j["id"]])]
    issue_counts: Counter = Counter()
    for j in clips:
        fr = first_review(j["id"])
        if fr:
            issue_counts.update(i.get("id") for i in fr.get("issues") or [])
    sources = [j for j in st.list_jobs(kind="source", limit=2000) if (j.get("created_at") or 0) >= since]
    spawned = sum(len(st.list_jobs(parent_id=s["id"], limit=500)) for s in sources)
    leads = [l for l in st.list_leads(limit=1000) if (l.get("found_at") or 0) >= since]
    views = [st.job_metrics(j["id"]).get("views") for j in delivered]
    views = [v for v in views if v is not None]
    lessons_all = st.lessons()
    recent_lessons = [l for l in lessons_all if l["created_at"] >= since]

    def pct(a: int, b: int) -> float | None:
        return round(100.0 * a / b, 1) if b else None

    return {
        "period_days": days,
        "throughput": {"sources": len(sources), "clips": len(clips), "delivered": len(delivered),
                       "rejected": sum(1 for j in done if j["state"] == "rejected"),
                       "failed": sum(1 for j in done if j["state"] == "failed"),
                       "in_progress": len(clips) - len(done)},
        "editor": {"first_pass_rate_pct": pct(len(first_pass), len(reviewed)),
                   "avg_review_rounds": round(sum(rounds) / len(rounds), 2) if rounds else None,
                   "escalation_rate_pct": pct(len(escalated), len(done))},
        "reviewer": {"issues_per_clip": round(sum(issue_counts.values()) / len(reviewed), 2) if reviewed else None,
                     "misses_caught_later": len(misses)},
        "analyst": {"moment_hit_rate_pct": pct(len(delivered), spawned)},
        "manager": {"approved": len(delivered), "leads_found": len(leads),
                    "leads_accepted": sum(1 for l in leads if l.get("decision") == "accept"),
                    "alerts": len(alerts)},
        "top_issues": issue_counts.most_common(8),
        "spend_usd": round(st.spend(since=since), 3),
        "spend_by_role": {k: round(v, 3) for k, v in st.spend_by_role(since).items()},
        "audience": {"clips_with_views": len(views), "avg_views": round(sum(views) / len(views)) if views else None,
                     "best_views": max(views) if views else None},
        "playbook": {"version": st.current_version(),
                     "active": sum(1 for l in lessons_all if l["status"] == "active"),
                     "candidates": sum(1 for l in lessons_all if l["status"] == "candidate"),
                     "quarantined": sum(1 for l in lessons_all if l["status"] == "quarantined"),
                     "new_this_period": len(recent_lessons)},
    }


def _alerts(ax: AgencyContext) -> list[dict[str, Any]]:
    from .roles import Manager

    return Manager(ax).monitor()


def team_report(ax: AgencyContext, days: float = 7.0) -> tuple[Path, dict[str, Any]]:
    alerts = _alerts(ax)
    m = team_metrics(ax, days, alerts)
    t, e, r = m["throughput"], m["editor"], m["reviewer"]

    def v(x: Any, unit: str = "") -> str:
        return "—" if x is None else f"{x}{unit}"

    lines = [
        f"# Team report — last {days:g} days ({time.strftime('%Y-%m-%d')})", "",
        "## Output", "",
        f"- sources processed: {t['sources']} · clips: {t['clips']} · delivered: {t['delivered']} · rejected: "
        f"{t['rejected']} · failed: {t['failed']} · in progress: {t['in_progress']}",
        f"- LLM spend: ${m['spend_usd']} ({', '.join(f'{k} ${v}' for k, v in m['spend_by_role'].items()) or 'none'})",
        "", "## How each role did", "",
        f"- **Editor** — first-pass approval {v(e['first_pass_rate_pct'], '%')}, avg review rounds "
        f"{v(e['avg_review_rounds'])}, escalations {v(e['escalation_rate_pct'], '%')}",
        f"- **Reviewer** — {v(r['issues_per_clip'])} issues flagged per clip, {r['misses_caught_later']} miss(es) "
        f"caught later by the manager/you",
        f"- **Analyst** — moment hit rate {v(m['analyst']['moment_hit_rate_pct'], '%')} (delivered / assigned)",
        f"- **Manager** — {m['manager']['approved']} approved, leads found {m['manager']['leads_found']} "
        f"({m['manager']['leads_accepted']} accepted)",
        "", "## Recurring problems (first-round review)", "",
    ]
    lines += [f"- `{iid}` × {n}" for iid, n in m["top_issues"]] or ["- none"]
    a = m["audience"]
    lines += ["", "## Audience", "",
              f"- clips with view data: {a['clips_with_views']} · avg views {v(a['avg_views'])} · best {v(a['best_views'])}",
              "", "## Playbook (what the team learned)", "",
              f"- version {m['playbook']['version']}: {m['playbook']['active']} active lessons, "
              f"{m['playbook']['candidates']} on trial, {m['playbook']['quarantined']} quarantined, "
              f"{m['playbook']['new_this_period']} new this period"]
    if alerts:
        lines += ["", "## Alerts", ""] + [f"- [{x['level']}] {x['message']}" for x in alerts[:20]]
    out_dir = ax.cfg.reports_dir / "team"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d")
    md = out_dir / f"team_{stamp}.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"team_{stamp}.json").write_text(json.dumps({**m, "alerts": alerts}, indent=2, default=str),
                                               encoding="utf-8")
    return md, m
