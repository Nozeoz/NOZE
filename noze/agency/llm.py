"""Claude as the team's brain: one structured-output call per decision.

- every call returns JSON that matches a contract in ``schemas.py`` (``output_config.format``)
- SOP + playbook go in a cached system prompt; the volatile job data in the user turn
- spend is metered per call and capped per source video and per day
- server-side refusal fallbacks are on by default (``AGENCY_FALLBACKS=0`` to turn off)
- when Claude isn't configured (or the budget is spent) callers get ``None`` and
  fall back to their deterministic heuristics — the pipeline never stalls on the LLM
- two backends, same contract: the Anthropic API (``ANTHROPIC_API_KEY``) or the
  Claude Code CLI (``claude -p``, i.e. a Claude subscription — no API key needed)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import AgencySettings
from .schemas import conform
from .store import Store

log = logging.getLogger("noze.agency.llm")

# USD per million tokens: (input, output, cache read). Cache writes bill at 1.25× input.
PRICES = {
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}
FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


class LLMError(RuntimeError):
    pass


class BudgetExceeded(LLMError):
    pass


def image_block(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media,
                                        "data": base64.standard_b64encode(p.read_bytes()).decode("ascii")}}


def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int) -> float:
    pin, pout, pread = PRICES.get(model, PRICES["claude-opus-5-5"])
    return (input_tokens * pin + output_tokens * pout + cache_read * pread + cache_write * pin * 1.25) / 1e6


def _has_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    if os.environ.get("ANTHROPIC_PROFILE") or os.environ.get("ANTHROPIC_FEDERATION_RULE_ID"):
        return True
    return (Path.home() / ".config" / "anthropic").exists()  # `ant auth login` profile


def find_claude_cli(configured: str = "") -> str | None:
    """The Claude Code binary: AGENCY_CLAUDE_BIN, then PATH, then the native installer's spot."""
    for cand in (configured, shutil.which("claude"), str(Path.home() / ".local" / "bin" / "claude.exe"),
                 str(Path.home() / ".local" / "bin" / "claude")):
        if cand and Path(cand).is_file():
            return cand
    return None


def cli_logged_in(binary: str) -> tuple[bool, str]:
    try:
        r = subprocess.run([binary, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, stdin=subprocess.DEVNULL)
        status = json.loads(r.stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return False, f"claude CLI unusable ({exc})"
    if not status.get("loggedIn"):
        return False, "claude CLI is logged out — run `claude auth login` once"
    return True, ""


def _json_from_text(text: str) -> Any:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith(("{", "[")):
        start = text.find("{")
        text = text[start:] if start >= 0 else text
    return json.loads(text)


class LLM:
    def __init__(self, cfg: AgencySettings, store: Store):
        self.cfg = cfg
        self.store = store
        self._client = None
        self.reason = ""
        self.backend = ""  # "api" | "cli"
        self.cli = None
        if cfg.key("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = cfg.key("ANTHROPIC_API_KEY")  # from .env
        if cfg.llm == "off":
            self.available, self.reason = False, "AGENCY_LLM=off"
            return
        want_api = cfg.llm in ("api", "claude") or (cfg.llm == "auto" and _has_credentials())
        if want_api:
            try:
                import anthropic  # noqa: F401
            except ImportError:
                if cfg.llm != "auto":
                    self.available, self.reason = False, 'anthropic SDK not installed (pip install "noze[agency]")'
                    return
            else:
                self.available, self.backend = True, "api"
                return
        # no API credentials: a logged-in Claude Code CLI is the brain (subscription, no key)
        self.cli = find_claude_cli(cfg.claude_bin)
        if not self.cli:
            self.available, self.reason = False, ("no Anthropic credentials and no `claude` CLI "
                                                  "(set ANTHROPIC_API_KEY, or install Claude Code and log in)")
            return
        ok, why = cli_logged_in(self.cli)
        self.available, self.reason, self.backend = ok, why, "cli" if ok else ""

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(max_retries=3, timeout=600.0)
        return self._client

    # -- budget --------------------------------------------------------------------------
    def check_budget(self, budget_job_ids: list[int] | None) -> None:
        # ponytail: checked before the call, so parallel clip workers can overshoot by up to
        # AGENCY_PARALLEL calls; a reservation ledger if that ever matters more than a few cents.
        day_start = time.time() - 24 * 3600
        if self.store.spend(since=day_start) >= self.cfg.daily_budget_usd:
            raise BudgetExceeded(f"daily LLM budget ${self.cfg.daily_budget_usd:.2f} reached")
        if budget_job_ids and self.store.spend(job_ids=budget_job_ids) >= self.cfg.job_budget_usd:
            raise BudgetExceeded(f"per-source LLM budget ${self.cfg.job_budget_usd:.2f} reached")

    # -- the one call ----------------------------------------------------------------------
    def json(self, role: str, system: str, content: list[dict[str, Any]] | str, schema: dict[str, Any], *,
             job_id: int | None = None, budget_job_ids: list[int] | None = None,
             max_tokens: int = 16000) -> dict[str, Any]:
        if not self.available:
            raise LLMError(self.reason or "LLM unavailable")
        self.check_budget(budget_job_ids)
        model = self.cfg.model_for(role)
        blocks = [text_block(content)] if isinstance(content, str) else content
        if self.backend == "cli":
            return self._json_cli(role, model, system, blocks, schema, job_id)
        import anthropic

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": blocks}],
            "output_config": {"effort": self.cfg.effort_for(role),
                              "format": {"type": "json_schema", "schema": schema}},
        }
        use_fallbacks = self.cfg.fallbacks and model in FALLBACK_MODELS
        for attempt in (1, 2):
            try:
                if use_fallbacks:
                    if kwargs["max_tokens"] > 16000:
                        with self.client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"],
                                                              fallbacks="default", **kwargs) as stream:
                            resp = stream.get_final_message()
                    else:
                        resp = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                                fallbacks="default", **kwargs)
                elif kwargs["max_tokens"] > 16000:
                    with self.client.messages.stream(**kwargs) as stream:
                        resp = stream.get_final_message()
                else:
                    resp = self.client.messages.create(**kwargs)
            except anthropic.BadRequestError as exc:
                if use_fallbacks and "fallback" in str(exc).lower():
                    use_fallbacks = False  # platform without server-side fallbacks: retry plain
                    continue
                raise LLMError(f"bad request: {exc}") from exc
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
                self.available, self.reason = False, f"auth failed: {exc}"
                raise LLMError(self.reason) from exc
            except anthropic.RateLimitError as exc:
                raise LLMError(f"rate limited: {exc}") from exc
            except anthropic.APIStatusError as exc:
                raise LLMError(f"API error {exc.status_code}: {exc}") from exc
            except anthropic.APIConnectionError as exc:
                raise LLMError(f"network error: {exc}") from exc
            self._meter(resp, role, job_id)
            if resp.stop_reason == "refusal":
                raise LLMError("the model declined this request")
            if resp.stop_reason == "max_tokens" and attempt == 1:
                kwargs["max_tokens"] = max_tokens * 2
                continue
            text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
            try:
                data = json.loads(text)
            except ValueError as exc:
                if attempt == 1:
                    continue
                raise LLMError("model returned invalid JSON") from exc
            return conform(data, schema)
        raise LLMError("no usable answer after retry")

    # -- Claude Code CLI backend ---------------------------------------------------------------
    def _json_cli(self, role: str, model: str, system: str, blocks: list[dict[str, Any]],
                  schema: dict[str, Any], job_id: int | None) -> dict[str, Any]:
        """``claude -p`` with no tools, no MCP, no skills, from an empty folder: one structured answer.

        Images travel as content blocks over ``--input-format stream-json``; the system prompt goes
        through a file (SOP + playbook outgrow Windows' 32k command line).
        """
        message = {"type": "user", "message": {"role": "user", "content": blocks}}
        last = ""
        for attempt in (1, 2):
            # a killed CLI child can still hold the folder on Windows: never let cleanup mask the real error
            with tempfile.TemporaryDirectory(prefix="noze-claude-", ignore_cleanup_errors=True) as tmp:
                sp = Path(tmp) / "system.md"
                try:
                    sp.write_text(system, encoding="utf-8")
                except OSError as exc:
                    raise LLMError(f"could not stage the system prompt: {exc}") from exc
                cmd = [self.cli, "-p", "--model", model, "--effort", self.cfg.effort_for(role),
                       "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                       "--json-schema", json.dumps(schema), "--system-prompt-file", str(sp),
                       "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
                       "--setting-sources", "project", "--no-session-persistence"]
                if self.cfg.fallbacks and model != "claude-sonnet-5-5":
                    cmd += ["--fallback-model", "claude-sonnet-5-5"]
                env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "CLAUDECODE")}
                try:
                    r = subprocess.run(cmd, input=json.dumps(message) + "\n", capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=self.cfg.cli_timeout_s,
                                       cwd=tmp, env=env)
                except subprocess.TimeoutExpired as exc:
                    raise LLMError(f"claude CLI timed out after {self.cfg.cli_timeout_s:.0f}s") from exc
                except OSError as exc:
                    self.available, self.reason = False, f"claude CLI failed to start: {exc}"
                    raise LLMError(self.reason) from exc
            result = None
            for line in reversed((r.stdout or "").splitlines()):
                if line.startswith("{") and '"type":"result"' in line.replace(" ", ""):
                    try:
                        result = json.loads(line)
                    except ValueError:
                        continue
                    break
            if result is None:
                raise LLMError(f"claude CLI exit {r.returncode}: {(r.stderr or r.stdout or '')[-300:]}")
            self._meter_cli(result, role, model, job_id)
            text = str(result.get("result") or "")
            if result.get("is_error"):
                low = text.lower()
                if any(k in low for k in ("authenticat", "logged out", "not logged in", "oauth", "/login",
                                          "invalid api key", "unauthorized")):
                    self.available, self.reason = False, f"claude CLI auth: {text[:200]} — run `claude auth login`"
                    raise LLMError(self.reason)
                if "refus" in low or "declin" in low:
                    raise LLMError("the model declined this request")
                last = text[:300]
                continue
            data = result.get("structured_output")
            if data is None:
                try:
                    data = _json_from_text(text)
                except ValueError:
                    last = "model returned invalid JSON"
                    continue
            if isinstance(data, dict):
                return conform(data, schema)
            last = "model returned non-object JSON"
        raise LLMError(f"no usable answer after retry ({last})")

    def _meter_cli(self, result: dict[str, Any], role: str, model: str, job_id: int | None) -> None:
        mu = result.get("modelUsage") or {}
        inp = sum(int(v.get("inputTokens", 0)) for v in mu.values())
        out = sum(int(v.get("outputTokens", 0)) for v in mu.values())
        cr = sum(int(v.get("cacheReadInputTokens", 0)) for v in mu.values())
        cw = sum(int(v.get("cacheCreationInputTokens", 0)) for v in mu.values())
        used = ",".join(sorted(mu)) or model
        # the CLI reports what the call would cost at API prices; on a subscription it's quota, not money
        cost = float(result.get("total_cost_usd") or 0.0) or cost_usd(model, inp, out, cr, cw)
        if inp or out or cost:
            self.store.add_usage(job_id, role, used, inp, out, cr, cw, cost)

    def _meter(self, resp: Any, role: str, job_id: int | None) -> None:
        u = getattr(resp, "usage", None)
        if u is None:
            return
        model = getattr(resp, "model", "") or self.cfg.model_for(role)
        inp, out = int(u.input_tokens or 0), int(u.output_tokens or 0)
        cr = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        cw = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        self.store.add_usage(job_id, role, model, inp, out, cr, cw, cost_usd(model, inp, out, cr, cw))
