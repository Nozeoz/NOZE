"""Shared state for one agency process: settings, store, Claude, playbooks and
(lazily) the NOZE asset bank used for references, music and SFX."""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import Any

from ..config import Settings
from .config import AgencySettings
from .learning import Learner, Playbook
from .llm import LLM
from .standards import standards_text
from .store import Store

log = logging.getLogger("noze.agency")

SOP_DIR = Path(__file__).parent / "sop"


def load_sop(name: str) -> str:
    p = SOP_DIR / f"{name}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


class AgencyContext:
    def __init__(self, cfg: AgencySettings, llm: LLM | None = None):
        cfg.ensure_dirs()
        self.cfg = cfg
        self.store = Store(cfg.db_path)
        self.llm = llm or LLM(cfg, self.store)
        self.playbook = Playbook(self.store)
        self.learner = Learner(cfg, self.store, self.llm, sop_text=load_sop("_shared"))

    @classmethod
    def load(cls, data_dir: str | Path | None = None, env: dict[str, str] | None = None) -> "AgencyContext":
        base = Settings.load(data_dir=data_dir, env=env, dotenv=env is None)
        return cls(AgencySettings.load(base, env=env, dotenv=env is None))

    @cached_property
    def bank(self) -> Any | None:
        """The NOZE asset bank (same data dir). None if it can't be opened."""
        try:
            from ..context import Context

            return Context(self.cfg.base)
        except Exception as exc:  # pragma: no cover - bank is optional
            log.warning("NOZE bank unavailable: %s", exc)
            return None

    def standards(self) -> str:
        c = self.cfg
        return standards_text(c.platform, c.target_lufs, c.width, c.height, c.fps)

    def system_prompt(self, role: str, scopes: list[str], canary: bool) -> tuple[str, list[str]]:
        playbook, shown = self.playbook.render(role, scopes, canary)
        parts = [load_sop("_shared"), "## House standards\n" + self.standards(), load_sop(role)]
        if playbook:
            parts.append(playbook)
        return "\n\n".join(p for p in parts if p), shown

    def job_dir(self, job: dict[str, Any]) -> Path:
        root = job.get("parent_id") or job["id"]
        d = self.cfg.work_dir / f"source_{root}"
        if job.get("parent_id"):
            d = d / f"clip_{job['id']}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def close(self) -> None:
        self.store.close()
        if "bank" in self.__dict__ and self.__dict__["bank"] is not None:
            self.__dict__["bank"].db.close()
