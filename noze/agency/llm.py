"""Claude as the team's brain: one structured-output call per decision.

- every call returns JSON that matches a contract in ``schemas.py`` (``output_config.format``)
- SOP + playbook go in a cached system prompt; the volatile job data in the user turn
- spend is metered per call and capped per source video and per day
- server-side refusal fallbacks are on by default (``AGENCY_FALLBACKS=0`` to turn off)
- when Claude isn't configured (or the budget is spent) callers get ``None`` and
  fall back to their deterministic heuristics — the pipeline never stalls on the LLM
"""

from __future__ import annotations

import base64
import json
import logging
import os
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


class LLM:
    def __init__(self, cfg: AgencySettings, store: Store):
        self.cfg = cfg
        self.store = store
        self._client = None
        self.reason = ""
        if cfg.key("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = cfg.key("ANTHROPIC_API_KEY")  # from .env
        if cfg.llm == "off":
            self.available, self.reason = False, "AGENCY_LLM=off"
            return
        try:
            import anthropic  # noqa: F401
        except ImportError:
            self.available, self.reason = False, 'anthropic SDK not installed (pip install "noze[agency]")'
            return
        if cfg.llm == "auto" and not _has_credentials():
            self.available, self.reason = False, "no Anthropic credentials (set ANTHROPIC_API_KEY or `ant auth login`)"
            return
        self.available = True

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(max_retries=3, timeout=600.0)
        return self._client

    # -- budget --------------------------------------------------------------------------
    def check_budget(self, budget_job_ids: list[int] | None) -> None:
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
        import anthropic

        model = self.cfg.model_for(role)
        blocks = [text_block(content)] if isinstance(content, str) else content
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

    def _meter(self, resp: Any, role: str, job_id: int | None) -> None:
        u = getattr(resp, "usage", None)
        if u is None:
            return
        model = getattr(resp, "model", "") or self.cfg.model_for(role)
        inp, out = int(u.input_tokens or 0), int(u.output_tokens or 0)
        cr = int(getattr(u, "cache_read_input_tokens", 0) or 0)
        cw = int(getattr(u, "cache_creation_input_tokens", 0) or 0)
        self.store.add_usage(job_id, role, model, inp, out, cr, cw, cost_usd(model, inp, out, cr, cw))
