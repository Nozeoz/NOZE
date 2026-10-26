from __future__ import annotations

import json
import logging
from typing import Any

from ..context import AgencyContext
from ..learning import scopes_for
from ..llm import LLMError, image_block, text_block

log = logging.getLogger("noze.agency.roles")


def dump(value: Any, limit: int = 40000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=1, default=str)
    return text if len(text) <= limit else text[:limit] + "\n… (truncated)"


class Role:
    name = "role"

    def __init__(self, ax: AgencyContext):
        self.ax = ax
        self.store = ax.store

    def ask(self, job: dict[str, Any] | None, task: str, schema: dict[str, Any], *,
            images: list[str] | None = None, campaign: dict[str, Any] | None = None,
            max_tokens: int = 16000) -> dict[str, Any] | None:
        """One structured Claude call for this role, or None (caller uses its heuristic)."""
        if not self.ax.llm.available:
            return None
        canary = bool(job and job.get("canary"))
        system, shown = self.ax.system_prompt(self.name, scopes_for(campaign), canary)
        content = [image_block(p) for p in (images or [])] + [text_block(task)]
        budget_ids = None
        if job:
            root = job.get("parent_id") or job["id"]
            budget_ids = [root] + [c["id"] for c in self.store.list_jobs(parent_id=root, limit=500)]
        try:
            out = self.ax.llm.json(self.name, system, content, schema, job_id=job["id"] if job else None,
                                   budget_job_ids=budget_ids, max_tokens=max_tokens)
        except LLMError as exc:
            self.store.log(job["id"] if job else None, self.name, "llm_fallback", str(exc)[:500])
            log.warning("%s: Claude unavailable for this step (%s); using heuristics", self.name, exc)
            return None
        if "used_lessons" in out:
            out["used_lessons"] = self.ax.playbook.record_use(out.get("used_lessons") or [], shown,
                                                              job["id"] if job else None)
        return out

    def campaign_of(self, job: dict[str, Any]) -> dict[str, Any] | None:
        return self.store.get_campaign(job["campaign_id"]) if job.get("campaign_id") else None
