"""Background worker: jobs (downloads, harvests, AI generation), scheduled
"interests" that keep growing the bank, thumbnail caching and embeddings."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from .context import Context
from .enrich import Enricher
from .generate import generate
from .harvest import Harvester
from .http import Http
from .lexicon import parse_query
from .models import expand_kinds

log = logging.getLogger("noze.worker")


async def run_job(job: dict[str, Any], ctx: Context, harvester: Harvester, http: Http) -> Any:
    p = job.get("payload") or {}
    kind = job["type"]
    if kind == "download":
        a = await harvester.download(p["asset_id"])
        return {"asset_id": a["id"], "blob_size": a.get("blob_size")}
    if kind == "harvest":
        kinds = expand_kinds(p.get("kinds") or []) or None
        only = set(p.get("sources") or []) or None
        total = 0
        report = None
        for page in range(int(p.get("start_page") or 1), int(p.get("start_page") or 1) + int(p.get("pages") or 1)):
            report = await harvester.search(parse_query(p["query"]), kinds=kinds, only=only, page=page,
                                            force=bool(p.get("force")))
            total += report.new_items
            if report.exhausted:
                break
        return {"query": p["query"], "new_items": total, "last": report.as_dict() if report else None}
    if kind == "interest":
        interest = next((i for i in ctx.db.list_interests() if i["id"] == p["interest_id"]), None)
        if not interest:
            return None
        kinds = expand_kinds([k for k in (interest.get("kinds") or "").split(",") if k]) or None
        page = int(interest.get("next_page") or 1)
        report = await harvester.search(parse_query(interest["query"]), kinds=kinds, page=page, force=True)
        next_page = 1 if report.exhausted or page >= int(interest.get("max_pages") or 5) else page + 1
        ctx.db.mark_interest_run(interest["id"], next_page)
        return {"query": interest["query"], "page": page, "new_items": report.new_items}
    if kind == "related":
        return {"found": await harvester.related(p["asset_id"])}
    if kind == "expand":
        # after a save: pull more of the same vibe into the bank (Pinterest-style learning)
        a = ctx.db.get_asset(p["asset_id"])
        if not a:
            return None
        await harvester.related(a["id"])
        tags = [t for t in (a.get("tags") or []) if len(t) > 2][:3]
        if tags:
            await harvester.search(parse_query(" ".join(tags)), page=1)
        return {"expanded": a["id"]}
    if kind == "generate":
        a = await generate(ctx, http, p["prompt"], p.get("kind") or "image", p.get("model"), p.get("input"))
        return {"asset_id": a["id"]}
    raise ValueError(f"unknown job type {kind}")


class Worker(threading.Thread):
    def __init__(self, ctx: Context):
        super().__init__(name="noze-worker", daemon=True)
        self.ctx = ctx
        self.stop_event = threading.Event()
        self.status: dict[str, Any] = {"state": "starting"}

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        try:
            asyncio.run(self.main())
        except Exception:  # pragma: no cover - last-resort logging
            log.exception("worker crashed")

    async def main(self) -> None:
        ctx = self.ctx
        http = Http(ctx.settings)
        harvester = Harvester(ctx, http)
        enricher = Enricher(ctx, http)
        self.status["state"] = "loading embedder"
        await asyncio.to_thread(ctx.ensure_embedder)
        ctx.db.requeue_stale_jobs()
        last_interest_check = 0.0
        self.status["state"] = "running"
        try:
            while not self.stop_event.is_set():
                did = 0
                job = ctx.db.claim_job()
                if job:
                    did += 1
                    self.status["job"] = job["type"]
                    try:
                        result = await run_job(job, ctx, harvester, http)
                        ctx.db.finish_job(job["id"], result=result)
                    except Exception as exc:
                        log.warning("job %s (%s) failed: %s", job["id"], job["type"], exc)
                        ctx.db.finish_job(job["id"], error=str(exc)[:500])
                    self.status.pop("job", None)
                did += await enricher.thumbs_batch(24)
                did += await asyncio.to_thread(enricher.embed_batch, 48)
                if time.time() - last_interest_check > 300:
                    last_interest_check = time.time()
                    for interest in ctx.db.due_interests():
                        ctx.db.enqueue_job("interest", {"interest_id": interest["id"]})
                if not did:
                    await asyncio.sleep(2.0)
        finally:
            await http.aclose()
            self.status["state"] = "stopped"
