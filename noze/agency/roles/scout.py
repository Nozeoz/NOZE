"""Reference scout: gathers candidate references and picks the 1–3 worth dissecting."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..media.fetch import VIDEO_EXT, fetch_source
from ..media.ffmpeg import probe
from ..schemas import REFERENCE_PICK
from .base import Role, dump

log = logging.getLogger("noze.agency.scout")

MAX_PICKS = 3


class Scout(Role):
    name = "scout"

    def candidates(self, job: dict[str, Any], brief: dict[str, Any]) -> list[dict[str, Any]]:
        cfg = self.ax.cfg
        out: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(ref: str, origin: str, title: str = "", extra: dict[str, Any] | None = None) -> None:
            if ref and ref not in seen:
                seen.add(ref)
                out.append({"ref": ref, "origin": origin, "title": title or Path(ref).name, **(extra or {})})

        for r in (job.get("input") or {}).get("references") or []:
            add(str(r), "given with this job")
        for r in brief.get("reference_examples") or []:
            add(str(r), "creator's example in the brief")
        campaign = self.campaign_of(job)
        ref_root = cfg.assets_dir / "references"
        folders = [ref_root]
        if campaign:
            folders = [ref_root / campaign["name"], ref_root / (campaign.get("creator") or "_"), ref_root]
        for folder in folders:
            if folder.is_dir():
                for p in sorted(folder.iterdir()):
                    if p.suffix.lower() in VIDEO_EXT:
                        add(str(p), f"reference library ({folder.name})")
        # our own approved clips for this campaign, best first (real audience evidence)
        if campaign:
            mine = []
            for c in self.store.list_jobs(kind="clip", states=["delivered"], campaign_id=campaign["id"], limit=200):
                m = self.store.job_metrics(c["id"])
                path = (c.get("data") or {}).get("final_path")
                if path and Path(path).exists():
                    mine.append((m.get("views", 0.0), c, path, m))
            for views, c, path, m in sorted(mine, key=lambda x: x[0], reverse=True)[:5]:
                add(path, "our delivered clip", c.get("title", ""), {"views": views, "retention": m.get("retention")})
        # saved videos in the NOZE bank that match the niche
        bank = self.ax.bank
        if bank is not None and (brief.get("niche") or brief.get("style", {}).get("notes")):
            try:
                from ...db import Filters

                terms = (brief.get("niche") or brief["style"]["notes"]).split()[:6]
                hits = bank.db.fts_search(terms, Filters(kinds={"video"}, saved_only=True), limit=20)
                rows = bank.db.get_assets([h[0] for h in hits])
                for aid, _ in hits:
                    a = rows.get(aid)
                    if a and a.get("blob_key"):
                        add(f"noze:{aid}", "saved in NOZE bank", a.get("title", ""))
            except Exception as exc:  # pragma: no cover - bank is best effort
                log.info("bank lookup failed: %s", exc)
        return out

    def pick(self, job: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
        cands = self.candidates(job, brief)
        if len(cands) <= MAX_PICKS:
            return {"picks": [{"ref": c["ref"], "why": c["origin"], "learn": []} for c in cands],
                    "search_queries": [], "used_lessons": [], "candidates": len(cands)}
        task = (f"Brief:\n{dump(brief, 8000)}\n\nCandidate references (pick at most {MAX_PICKS}):\n{dump(cands, 12000)}")
        out = self.ask(job, task, REFERENCE_PICK, campaign=self.campaign_of(job))
        if out is None:
            order = {"creator's example in the brief": 0, "given with this job": 1, "our delivered clip": 2}
            ranked = sorted(cands, key=lambda c: (order.get(c["origin"], 3), -float(c.get("views") or 0)))
            out = {"picks": [{"ref": c["ref"], "why": c["origin"], "learn": []} for c in ranked[:MAX_PICKS]],
                   "search_queries": [], "used_lessons": []}
        valid = {c["ref"] for c in cands}
        out["picks"] = [p for p in out["picks"] if p["ref"] in valid][:MAX_PICKS]
        out["candidates"] = len(cands)
        return out

    def resolve(self, ref: str, dest: Path) -> Path | None:
        """Local file for a reference, or None if it can't (or may not) be fetched."""
        bank = self.ax.bank

        def bank_path(aid: str):
            if bank is None:
                return None
            a = bank.db.get_asset(aid)
            return bank.storage.local_path(a["blob_key"]) if a and a.get("blob_key") else None

        try:
            p = fetch_source(ref, dest, allow_download=self.ax.cfg.allow_download,
                             allow_private=self.ax.cfg.base.allow_private_fetch, max_mb=800, bank_path=bank_path)
            probe(p)
            return p
        except Exception as exc:  # references are optional; a bad one must not stop the job
            log.info("reference %s skipped: %s", ref, exc)
            return None
