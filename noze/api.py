"""HTTP API + web UI server (FastAPI)."""

from __future__ import annotations

import base64
import hmac
import logging
import re
import shutil
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings
from .context import Context
from .enrich import Enricher
from .exporter import export_board
from .harvest import Harvester
from .http import Http, SourceError
from .importers.web import ingest_file, ingest_url
from .lexicon import STARTER_TOPICS, parse_query
from .search import ACTION_WEIGHTS, Ranker, SearchRequest, describe_query, page_slice
from .worker import Worker

log = logging.getLogger("noze.api")
WEB_DIR = Path(__file__).parent / "web"
PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="3" viewBox="0 0 4 3">'
    '<rect width="4" height="3" fill="#8884"/></svg>'
)


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


class BoardIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class BoardPatch(BaseModel):
    name: str | None = None
    description: str | None = None


class BoardItemIn(BaseModel):
    asset_id: str
    note: str = ""


class SaveIn(BaseModel):
    asset_id: str
    board: str | None = None
    note: str = ""


class InteractionIn(BaseModel):
    asset_id: str
    action: str
    query: str = ""


class InterestIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    kinds: list[str] = []
    every_hours: float = 24
    max_pages: int = 5


class HarvestIn(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    kinds: list[str] = []
    sources: list[str] = []
    pages: int = Field(default=2, ge=1, le=20)


class IngestUrlIn(BaseModel):
    url: str
    page_url: str = ""
    title: str = ""
    note: str = ""
    tags: list[str] = []
    board: str | None = None


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    kind: str = "image"
    model: str | None = None


class State:
    ctx: Context
    http: Http
    harvester: Harvester
    enricher: Enricher
    ranker: Ranker
    worker: Worker | None = None
    _stats_cache: tuple[float, dict[str, Any]] | None = None


def create_app(settings: Settings | None = None, start_worker: bool | None = None) -> FastAPI:
    settings = settings or Settings.load()
    state = State()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state.ctx = Context(settings)
        state.http = Http(settings)
        state.harvester = Harvester(state.ctx, state.http)
        state.enricher = Enricher(state.ctx, state.http)
        state.ranker = Ranker(state.ctx)
        run_worker = settings.worker if start_worker is None else start_worker
        if run_worker:
            state.worker = Worker(state.ctx)
            state.worker.start()
        app.state.noze = state
        yield
        if state.worker:
            state.worker.stop()
        await state.http.aclose()

    app = FastAPI(title="NOZE asset bank", version="0.1.0", lifespan=lifespan)

    # -- security: optional password (HTTP Basic) + cross-site write protection --------------
    @app.middleware("http")
    async def guard(request: Request, call_next):
        if settings.password:
            header = request.headers.get("authorization", "")
            ok = False
            if header.lower().startswith("basic "):
                try:
                    _, _, pw = base64.b64decode(header[6:]).decode().partition(":")
                    ok = hmac.compare_digest(pw, settings.password)
                except Exception:
                    ok = False
            if not ok:
                return Response("NOZE: login required", status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="NOZE"'})
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin:
                o = re.sub(r"^https?://", "", origin).rstrip("/")
                if o != request.headers.get("host", ""):
                    return JSONResponse({"detail": "cross-site request blocked"}, status_code=403)
        return await call_next(request)

    def S() -> State:
        return app.state.noze

    def asset_or_404(asset_id: str) -> dict[str, Any]:
        a = S().ctx.db.get_asset(asset_id)
        if not a:
            raise HTTPException(404, "asset not found")
        return a

    def items_json(ids: list[str]) -> list[dict[str, Any]]:
        rows = S().ctx.db.get_assets(ids)
        return [S().ctx.asset_json(rows[i]) for i in ids if i in rows]

    # -- pages ------------------------------------------------------------------------------
    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/save", include_in_schema=False)
    async def save_page() -> FileResponse:
        return FileResponse(WEB_DIR / "save.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    # -- search & discovery ---------------------------------------------------------------------
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        ctx = S().ctx
        return {"ok": True, "embedder": ctx.embedder.name, "semantic": ctx.semantic, "vectors": len(ctx.index),
                "embedder_error": ctx.embedder_error,
                "worker": (S().worker.status if S().worker else {"state": "disabled"})}

    @app.get("/api/search")
    async def search(q: str = "", kinds: str = "", usage: str = "", sources: str = "", color: str = "",
                     page: int = 1, per_page: int = 40, live: bool = True, auto: bool = True) -> dict[str, Any]:
        st = S()
        page, per_page = max(1, page), max(1, min(per_page, 100))
        color = color if re.fullmatch(r"#?[0-9a-fA-F]{6}", color or "") else ""
        color = ("#" + color.lstrip("#")) if color else None
        req = SearchRequest(q=q, kinds=_csv(kinds), usages=_csv(usage), sources=_csv(sources), color=color,
                            page=page, per_page=per_page, live=live, auto_filters=auto)
        pq = parse_query(q)
        filters, applied = st.ranker.resolve_filters(req, pq)
        report = None
        if (pq.text or q.strip()) and live:
            src_page = 1 + (page - 1) // 4
            report = await st.harvester.search(pq, kinds=filters.kinds, only=filters.sources, page=src_page,
                                               timeout=settings.live_timeout)
        if pq.text or q.strip():
            ids = await run_in_threadpool(st.ranker.rank_query, pq, filters, color)
        else:
            ids = await run_in_threadpool(st.ranker.browse, filters, int(time.time() // 86400))
        page_ids = page_slice(ids, page, per_page)
        has_more = len(ids) > page * per_page or bool(report and not report.exhausted)
        return {"items": items_json(page_ids), "total": len(ids), "page": page, "has_more": has_more,
                "query": describe_query(pq, applied), "live": report.as_dict() if report else None}

    @app.get("/api/feed")
    async def feed(kinds: str = "", usage: str = "", sources: str = "", page: int = 1, per_page: int = 40,
                   seed: int = 0) -> dict[str, Any]:
        st = S()
        req = SearchRequest(kinds=_csv(kinds), usages=_csv(usage), sources=_csv(sources))
        filters, _ = st.ranker.resolve_filters(req, parse_query(""))
        ids = await run_in_threadpool(st.ranker.feed, filters, seed or int(time.time() // 86400))
        page_ids = page_slice(ids, page, per_page)
        return {"items": items_json(page_ids), "total": len(ids), "page": page, "has_more": len(ids) > page * per_page}

    @app.get("/api/vibes")
    async def vibes(q: str = "") -> dict[str, Any]:
        return describe_query(parse_query(q), {})

    # -- single asset ------------------------------------------------------------------------------
    @app.get("/api/assets/{asset_id:path}/related")
    async def related(asset_id: str, page: int = 1, per_page: int = 40, live: bool = True) -> dict[str, Any]:
        st = S()
        asset_or_404(asset_id)
        if live and page == 1:
            try:
                await st.harvester.related(asset_id)
            except Exception as exc:
                log.info("live related failed: %s", exc)
        ids = await run_in_threadpool(st.ranker.related, asset_id)
        page_ids = page_slice(ids, page, per_page)
        return {"items": items_json(page_ids), "total": len(ids), "page": page, "has_more": len(ids) > page * per_page}

    @app.post("/api/assets/{asset_id:path}/download")
    async def download(asset_id: str, wait: bool = False) -> dict[str, Any]:
        st = S()
        asset_or_404(asset_id)
        if wait:
            try:
                a = await st.harvester.download(asset_id)
            except SourceError as exc:
                raise HTTPException(502, str(exc))
            st.ctx.db.log_interaction(asset_id, "download", ACTION_WEIGHTS["download"])
            return {"ok": True, "asset": st.ctx.asset_json(a, full=True)}
        job = st.ctx.db.enqueue_job("download", {"asset_id": asset_id})
        st.ctx.db.log_interaction(asset_id, "download", ACTION_WEIGHTS["download"])
        return {"ok": True, "job_id": job}

    @app.get("/api/assets/{asset_id:path}/file")
    async def asset_file(asset_id: str, download: bool = False):
        st = S()
        a = asset_or_404(asset_id)
        key = a.get("blob_key")
        if not key:
            raise HTTPException(404, "not stored in the bank yet — press Download")
        storage = st.ctx.storage
        ext = Path(key.split("?")[0]).suffix
        name = (re.sub(r"[^A-Za-z0-9._ -]+", "", a.get("title") or "asset")[:80].strip() or "asset") + ext
        local = storage.local_path(key)
        disposition = "attachment" if download else "inline"
        if local is not None:
            return FileResponse(local, media_type=a.get("blob_mime") or None, filename=name,
                                content_disposition_type=disposition)
        url = storage.url(key)
        if url:
            return RedirectResponse(url)
        return StreamingResponse(storage.open(key), media_type=a.get("blob_mime") or "application/octet-stream")

    @app.post("/api/assets/{asset_id:path}/hide")
    async def hide(asset_id: str, hidden: bool = True) -> dict[str, Any]:
        st = S()
        asset_or_404(asset_id)
        st.ctx.db.update_asset(asset_id, hidden=1 if hidden else 0)
        if hidden:
            st.ctx.db.log_interaction(asset_id, "hide", ACTION_WEIGHTS["hide"])
        return {"ok": True}

    @app.get("/api/assets/{asset_id:path}")
    async def asset_detail(asset_id: str) -> dict[str, Any]:
        st = S()
        a = asset_or_404(asset_id)
        if not (a.get("extra") or {}).get("hydrated") and a["source"] in st.harvester.sources:
            a = await st.harvester.hydrate(asset_id) or a
        out = st.ctx.asset_json(a, full=True)
        out["boards"] = st.ctx.db.boards_for_asset(asset_id)
        src = st.harvester.sources.get(a["source"])
        out["source_credit"] = src.credit if src else ""
        return out

    @app.get("/api/thumb/{asset_id:path}")
    async def thumb(asset_id: str):
        st = S()
        a = st.ctx.db.get_asset(asset_id)
        if not a:
            raise HTTPException(404)
        headers = {"Cache-Control": "public, max-age=604800"}
        if a.get("thumb_path"):
            p = settings.thumbs_dir / a["thumb_path"]
            if p.exists():
                return FileResponse(p, media_type="image/svg+xml" if p.suffix == ".svg" else "image/webp",
                                    headers=headers)
        lost = bool(a.get("thumb_path")) and not (settings.thumbs_dir / a["thumb_path"]).exists()
        if (a.get("thumb_state") in (0, None) or lost) and (a.get("thumb_url") or a.get("blob_key")):
            p = await st.enricher.thumb_one(a)
            if p is not None and p.exists():
                return FileResponse(p, media_type="image/svg+xml" if p.suffix == ".svg" else "image/webp",
                                    headers=headers)
        if (a.get("thumb_url") or "").startswith("http"):
            return RedirectResponse(a["thumb_url"])
        return Response(PLACEHOLDER_SVG, media_type="image/svg+xml")

    @app.post("/api/interactions")
    async def interaction(body: InteractionIn) -> dict[str, Any]:
        if body.action not in ACTION_WEIGHTS:
            raise HTTPException(400, f"action must be one of {sorted(ACTION_WEIGHTS)}")
        S().ctx.db.log_interaction(body.asset_id, body.action, ACTION_WEIGHTS[body.action], body.query)
        return {"ok": True}

    # -- boards ------------------------------------------------------------------------------------
    def _save_side_effects(asset_id: str) -> None:
        db = S().ctx.db
        db.log_interaction(asset_id, "save", ACTION_WEIGHTS["save"])
        if settings.auto_download_on_save:
            db.enqueue_job("download", {"asset_id": asset_id})
        db.enqueue_job("expand", {"asset_id": asset_id})

    @app.get("/api/boards")
    async def boards() -> list[dict[str, Any]]:
        st = S()
        out = st.ctx.db.list_boards()
        covers = st.ctx.db.get_assets([c for b in out for c in b["cover_ids"]])
        for b in out:
            b["covers"] = [st.ctx.asset_json(covers[c]) for c in b.pop("cover_ids") if c in covers]
        return out

    @app.post("/api/boards")
    async def create_board(body: BoardIn) -> dict[str, Any]:
        bid = S().ctx.db.create_board(body.name, body.description)
        return S().ctx.db.get_board(bid)

    @app.get("/api/boards/{board_id}")
    async def board(board_id: int, page: int = 1, per_page: int = 60) -> dict[str, Any]:
        db = S().ctx.db
        b = db.get_board(board_id)
        if not b:
            raise HTTPException(404, "board not found")
        ids = db.board_item_ids(board_id)
        b["items"] = items_json(page_slice(ids, page, per_page))
        b["total"], b["page"], b["has_more"] = len(ids), page, len(ids) > page * per_page
        return b

    @app.patch("/api/boards/{board_id}")
    async def patch_board(board_id: int, body: BoardPatch) -> dict[str, Any]:
        S().ctx.db.update_board(board_id, body.name, body.description)
        return S().ctx.db.get_board(board_id) or {}

    @app.delete("/api/boards/{board_id}")
    async def delete_board(board_id: int) -> dict[str, Any]:
        S().ctx.db.delete_board(board_id)
        return {"ok": True}

    @app.post("/api/boards/{board_id}/items")
    async def add_item(board_id: int, body: BoardItemIn) -> dict[str, Any]:
        db = S().ctx.db
        if not db.get_board(board_id):
            raise HTTPException(404, "board not found")
        asset_or_404(body.asset_id)
        db.add_to_board(board_id, body.asset_id, body.note)
        _save_side_effects(body.asset_id)
        return {"ok": True}

    @app.delete("/api/boards/{board_id}/items/{asset_id:path}")
    async def remove_item(board_id: int, asset_id: str) -> dict[str, Any]:
        db = S().ctx.db
        db.remove_from_board(board_id, asset_id)
        db.log_interaction(asset_id, "unsave", ACTION_WEIGHTS["unsave"])
        return {"ok": True}

    @app.post("/api/save")
    async def quick_save(body: SaveIn) -> dict[str, Any]:
        db = S().ctx.db
        asset_or_404(body.asset_id)
        bid = db.create_board(body.board or "Saved")
        db.add_to_board(bid, body.asset_id, body.note)
        _save_side_effects(body.asset_id)
        return {"ok": True, "board_id": bid}

    @app.get("/api/boards/{board_id}/export")
    async def export(board_id: int):
        st = S()
        b = st.ctx.db.get_board(board_id)
        if not b:
            raise HTTPException(404, "board not found")
        out = settings.tmp_dir / f"export-{uuid.uuid4().hex}.zip"
        await run_in_threadpool(export_board, st.ctx, board_id, out)
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", b["name"]).strip("-") or "board"

        def cleanup_stream():
            try:
                with out.open("rb") as fh:
                    while chunk := fh.read(1 << 20):
                        yield chunk
            finally:
                out.unlink(missing_ok=True)

        return StreamingResponse(cleanup_stream(), media_type="application/zip",
                                 headers={"Content-Disposition": f'attachment; filename="noze-{name}.zip"'})

    # -- sources, interests, jobs ------------------------------------------------------------------------
    @app.get("/api/sources")
    async def sources() -> list[dict[str, Any]]:
        st = S()
        states = st.ctx.db.source_states()
        counts = st.ctx.db.stats()["by_source"]
        out = []
        for name, src in st.harvester.sources.items():
            info = src.info()
            s = states.get(name) or {}
            info.update({"items": counts.get(name, 0), "calls": s.get("calls", 0), "last_ok": s.get("last_ok"),
                         "last_error": s.get("last_error"), "last_error_at": s.get("last_error_at"),
                         "cooldown_until": s.get("cooldown_until")})
            out.append(info)
        return out

    @app.get("/api/interests")
    async def interests() -> list[dict[str, Any]]:
        return S().ctx.db.list_interests()

    @app.post("/api/interests")
    async def add_interest(body: InterestIn) -> dict[str, Any]:
        db = S().ctx.db
        iid = db.add_interest(body.query.strip(), ",".join(body.kinds), max(1.0, body.every_hours),
                              max(1, min(body.max_pages, 50)))
        db.enqueue_job("interest", {"interest_id": iid})
        return {"id": iid}

    @app.post("/api/interests/starter")
    async def starter() -> dict[str, Any]:
        db = S().ctx.db
        for topic in STARTER_TOPICS:
            iid = db.add_interest(topic, "", 72, 3)
            db.enqueue_job("interest", {"interest_id": iid})
        return {"added": len(STARTER_TOPICS)}

    @app.delete("/api/interests/{interest_id}")
    async def delete_interest(interest_id: int) -> dict[str, Any]:
        S().ctx.db.delete_interest(interest_id)
        return {"ok": True}

    @app.post("/api/harvest")
    async def harvest(body: HarvestIn) -> dict[str, Any]:
        job = S().ctx.db.enqueue_job("harvest", body.model_dump())
        return {"job_id": job}

    @app.get("/api/jobs")
    async def jobs(limit: int = 30) -> list[dict[str, Any]]:
        return S().ctx.db.list_jobs(min(limit, 200))

    @app.get("/api/jobs/{job_id}")
    async def job(job_id: int) -> dict[str, Any]:
        j = S().ctx.db.get_job(job_id)
        if not j:
            raise HTTPException(404, "job not found")
        return j

    # -- ingest -------------------------------------------------------------------------------------------------
    @app.post("/api/ingest/url")
    async def ingest(body: IngestUrlIn) -> dict[str, Any]:
        st = S()
        try:
            a = await ingest_url(st.ctx, st.http, body.url, body.page_url, body.title, body.note, body.tags, body.board)
        except (SourceError, ValueError) as exc:
            raise HTTPException(400, str(exc))
        st.ctx.db.log_interaction(a["id"], "save", ACTION_WEIGHTS["save"])
        return st.ctx.asset_json(a, full=True)

    @app.post("/api/ingest/upload")
    async def upload(file: UploadFile = File(...), tags: str = Form(""), board: str = Form(""),
                     note: str = Form("")) -> dict[str, Any]:
        st = S()
        max_bytes = settings.max_download_mb * 1024 * 1024
        with tempfile.NamedTemporaryFile(dir=settings.tmp_dir, delete=False) as tmp:
            size = 0
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > max_bytes:
                    Path(tmp.name).unlink(missing_ok=True)
                    raise HTTPException(413, "file too large (NOZE_MAX_DOWNLOAD_MB)")
                tmp.write(chunk)
        try:
            a = await run_in_threadpool(ingest_file, st.ctx, Path(tmp.name), file.filename or "upload",
                                        file.content_type or "", _csv(tags), board or None, note)
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        return st.ctx.asset_json(a, full=True)

    @app.post("/api/generate")
    async def generate_asset(body: GenerateIn) -> dict[str, Any]:
        if not settings.key("REPLICATE_API_TOKEN"):
            raise HTTPException(400, "Set REPLICATE_API_TOKEN to generate assets with AI (Seedance, FLUX…).")
        job = S().ctx.db.enqueue_job("generate", body.model_dump(), dedupe=False)
        return {"job_id": job}

    @app.get("/api/stats")
    async def stats() -> dict[str, Any]:
        st = S()
        cached = st._stats_cache
        if cached and time.time() - cached[0] < 30:
            return cached[1]
        data = st.ctx.db.stats()
        thumbs_bytes = await run_in_threadpool(
            lambda: sum(p.stat().st_size for p in settings.thumbs_dir.rglob("*") if p.is_file()))
        data.update({"thumbs_bytes": thumbs_bytes, "storage": st.ctx.storage.name, "data_dir": str(settings.data_dir),
                     "db_bytes": settings.db_path.stat().st_size if settings.db_path.exists() else 0,
                     "embedder": st.ctx.embedder.name, "semantic": st.ctx.semantic,
                     "disk_free": disk_free(settings.data_dir),
                     "generate": bool(settings.key("REPLICATE_API_TOKEN"))})
        st._stats_cache = (time.time(), data)
        return data

    return app


def disk_free(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0
