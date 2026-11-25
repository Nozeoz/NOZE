"""Agency settings (``AGENCY_*`` environment variables / .env), layered on NOZE's Settings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Settings, _bool, _parse_env_file

ROLES = ("manager", "scout", "analyst", "editor", "reviewer")

# where creators post "[Hiring] short-form editor / clippers" (official Reddit API only)
DEFAULT_SUBREDDITS = ("VideoEditors_forhire", "HireAnEditor", "VideoEditor_forhire", "VideoEditingRequests",
                      "CreatorServices", "forhire")

# Effort per role: judgement-heavy roles think harder, routine ones stay cheap.
DEFAULT_EFFORT = {
    "manager": "medium",
    "scout": "low",
    "analyst": "high",
    "editor": "high",
    "reviewer": "high",
    "reflector": "medium",
    "approver": "low",
}

# Model per role when AGENCY_MODEL_<ROLE> isn't set. Judgement that is expensive to get wrong
# (the editor's cut, the reviewer's verdict, the manager's ACC) gets Opus; scouting, measured
# breakdowns and reflection score the same on Sonnet at a fraction of the quota.
DEFAULT_ROLE_MODELS = {
    "manager": "claude-opus-5-5",
    "editor": "claude-opus-5-5",
    "reviewer": "claude-opus-5-5",
    "analyst": "claude-sonnet-5-5",
    "scout": "claude-sonnet-5-5",
    "reflector": "claude-sonnet-5-5",
    # the manager's ACC on a clip the (Opus, vision) reviewer already passed: brief/post/risk check on text,
    # no frames — re-judging the same frames on Opus paid twice for one verdict (arena 30 Sep: re-verifying
    # managers cost 2.8-4.2x, no score gain). Escalations still go to the manager on Opus with frames.
    "approver": "claude-sonnet-5-5",
}

AGENCY_KEYS = (
    "ANTHROPIC_API_KEY",
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
    "TIKTOK_ACCESS_TOKEN",
    "AGENCY_WEBHOOK_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "WHOP_API_KEY",
)


@dataclass
class AgencySettings:
    base: Settings
    llm: str = "auto"  # auto (API key → API, else a logged-in `claude` CLI) | api | cli | off
    model: str = ""  # one model for every role; empty = DEFAULT_ROLE_MODELS
    claude_bin: str = ""  # path to the Claude Code CLI (default: PATH, then ~/.local/bin)
    cli_timeout_s: float = 900.0
    role_models: dict[str, str] = field(default_factory=dict)
    role_effort: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_EFFORT))
    fallbacks: bool = True  # server-side refusal fallbacks on Claude
    job_budget_usd: float = 4.0  # LLM spend cap per source video (all its clips)
    daily_budget_usd: float = 40.0
    max_rounds: int = 3  # editor↔reviewer loops before the manager steps in
    clips_per_source: int = 3
    parallel: int = 3  # clip jobs advanced at the same time (LLM calls + ffmpeg); sources stay one by one
    min_clip_s: float = 15.0
    max_clip_s: float = 60.0
    platform: str = "tiktok"  # tiktok | reels | shorts — drives safe zones & specs
    target_lufs: float = -14.0
    width: int = 1080
    height: int = 1920
    fps: int = 30
    transcriber: str = "auto"  # auto | faster-whisper | sidecar | none
    whisper_model: str = "auto"  # auto = large-v3 on a CUDA GPU, small on CPU
    allow_download: bool = False  # yt-dlp for platform URLs (only for content you have rights to)
    auto_publish: bool = False  # push approved clips to platforms without a human click
    publish_targets: list[str] = field(default_factory=lambda: ["folder"])
    auto_approve: bool = True  # manager may approve on its own; off = every clip waits for you
    canary_share: float = 0.2  # share of jobs that try candidate (not yet proven) lessons
    lead_subreddits: list[str] = field(default_factory=lambda: list(DEFAULT_SUBREDDITS))
    lead_feeds: list[str] = field(default_factory=list)
    lead_keywords: list[str] = field(default_factory=lambda: ["clipper", "clippers", "clipping", "short form editor",
                                                              "shorts editor", "tiktok editor", "reels editor"])
    niches: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=lambda: ["en", "id"])
    rclone_remote: str = ""
    lead_scout_every_h: float = 12.0  # while `run --forever` / autorun: look for new campaigns
    report_every_h: float = 24.0  # … and write (and send, if a webhook is set) the team report
    keys: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, base: Settings | None = None, env: dict[str, str] | None = None,
             dotenv: bool = True) -> "AgencySettings":
        base = base or Settings.load(env=env, dotenv=dotenv)
        merged: dict[str, str] = {}
        if dotenv:
            merged.update(_parse_env_file(Path.cwd() / ".env"))
            merged.update(_parse_env_file(base.data_dir / ".env"))
        merged.update(dict(os.environ) if env is None else dict(env))

        def get(name: str, default: str = "") -> str:
            return merged.get(name, default) or default

        def num(name: str, default: float) -> float:
            try:
                return float(get(name, str(default)))
            except ValueError:
                return default

        role_models = {r: merged[f"AGENCY_MODEL_{r.upper()}"] for r in (*ROLES, "reflector", "approver")
                       if merged.get(f"AGENCY_MODEL_{r.upper()}")}
        role_effort = dict(DEFAULT_EFFORT)
        for r in role_effort:
            if merged.get(f"AGENCY_EFFORT_{r.upper()}"):
                role_effort[r] = merged[f"AGENCY_EFFORT_{r.upper()}"].lower()
        keys = {k: merged[k] for k in AGENCY_KEYS if merged.get(k)}
        if env is None:  # media/transcribe.py reads these from the process env; let .env set them too
            for k in ("AGENCY_WHISPER_DEVICE", "AGENCY_CUDA_DLL_DIRS"):
                if merged.get(k) and not os.environ.get(k):
                    os.environ[k] = merged[k]

        def lst(name: str, default: list[str]) -> list[str]:
            raw = merged.get(name)
            if raw is None or raw == "":
                return list(default)
            return [v.strip() for v in raw.split(",") if v.strip()]

        return cls(
            base=base,
            llm=get("AGENCY_LLM", "auto").lower(),
            model=get("AGENCY_MODEL", ""),
            claude_bin=get("AGENCY_CLAUDE_BIN", ""),
            cli_timeout_s=num("AGENCY_CLI_TIMEOUT_S", 900.0),
            role_models=role_models,
            role_effort=role_effort,
            fallbacks=_bool(merged.get("AGENCY_FALLBACKS"), True),
            job_budget_usd=num("AGENCY_JOB_BUDGET_USD", 4.0),
            daily_budget_usd=num("AGENCY_DAILY_BUDGET_USD", 40.0),
            max_rounds=int(num("AGENCY_MAX_ROUNDS", 3)),
            clips_per_source=int(num("AGENCY_CLIPS_PER_SOURCE", 3)),
            parallel=max(1, int(num("AGENCY_PARALLEL", 3))),
            min_clip_s=num("AGENCY_MIN_CLIP_S", 15.0),
            max_clip_s=num("AGENCY_MAX_CLIP_S", 60.0),
            platform=get("AGENCY_PLATFORM", "tiktok").lower(),
            target_lufs=num("AGENCY_TARGET_LUFS", -14.0),
            width=int(num("AGENCY_WIDTH", 1080)),
            height=int(num("AGENCY_HEIGHT", 1920)),
            fps=int(num("AGENCY_FPS", 30)),
            transcriber=get("AGENCY_TRANSCRIBER", "auto").lower(),
            whisper_model=get("AGENCY_WHISPER_MODEL", "auto"),
            allow_download=_bool(merged.get("AGENCY_ALLOW_DOWNLOAD"), False),
            auto_publish=_bool(merged.get("AGENCY_AUTO_PUBLISH"), False),
            publish_targets=lst("AGENCY_PUBLISH_TARGETS", ["folder"]),
            auto_approve=_bool(merged.get("AGENCY_AUTO_APPROVE"), True),
            canary_share=min(1.0, max(0.0, num("AGENCY_CANARY_SHARE", 0.2))),
            lead_subreddits=lst("AGENCY_LEAD_SUBREDDITS", list(DEFAULT_SUBREDDITS)),
            lead_feeds=lst("AGENCY_LEAD_FEEDS", []),
            lead_keywords=lst("AGENCY_LEAD_KEYWORDS", ["clipper", "clippers", "clipping", "short form editor",
                                                       "shorts editor", "tiktok editor", "reels editor"]),
            niches=lst("AGENCY_NICHES", []),
            languages=lst("AGENCY_LANGUAGES", ["en", "id"]),
            rclone_remote=get("AGENCY_RCLONE_REMOTE"),
            lead_scout_every_h=num("AGENCY_LEAD_SCOUT_EVERY_H", 12.0),
            report_every_h=num("AGENCY_REPORT_EVERY_H", 24.0),
            keys=keys,
        )

    # -- helpers ----------------------------------------------------------------
    def key(self, name: str) -> str:
        return self.keys.get(name) or self.base.key(name)

    def model_for(self, role: str) -> str:
        return self.role_models.get(role) or self.model or DEFAULT_ROLE_MODELS.get(role, "claude-opus-5-5")

    def models_label(self) -> str:
        """``manager=claude-opus-5-5, scout=claude-sonnet-5-5 …`` collapsed to one name when all agree."""
        per = {r: self.model_for(r) for r in (*ROLES, "reflector", "approver")}
        if len(set(per.values())) == 1:
            return next(iter(per.values()))
        return ", ".join(f"{r}={m.removeprefix('claude-')}" for r, m in per.items())

    def effort_for(self, role: str) -> str:
        return self.role_effort.get(role, "medium")

    # -- paths ------------------------------------------------------------------
    @property
    def root(self) -> Path:
        return self.base.data_dir / "agency"

    @property
    def db_path(self) -> Path:
        return self.root / "agency.db"

    @property
    def work_dir(self) -> Path:
        return self.root / "work"

    @property
    def deliveries_dir(self) -> Path:
        return self.root / "deliveries"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def assets_dir(self) -> Path:
        """Your own SFX/music/fonts/LUTs/logos: ``assets/{sfx,music,fonts,luts,overlays}``."""
        return self.root / "assets"

    @property
    def fonts_dir(self) -> Path:
        return self.assets_dir / "fonts"

    @property
    def inbox_dir(self) -> Path:
        """Drop source videos here (``inbox/<campaign>/video.mp4``) and the manager picks them up."""
        return self.root / "inbox"

    def ensure_dirs(self) -> None:
        for d in (self.root, self.work_dir, self.deliveries_dir, self.reports_dir, self.inbox_dir,
                  self.assets_dir / "sfx", self.assets_dir / "music", self.fonts_dir, self.assets_dir / "luts",
                  self.assets_dir / "overlays", self.assets_dir / "references"):
            d.mkdir(parents=True, exist_ok=True)
