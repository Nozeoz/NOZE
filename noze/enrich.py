"""Background enrichment: cache thumbnails, extract palettes + perceptual
hashes, and compute vibe vectors for everything in the bank."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .context import Context
from .embeddings import EmbedInput, HashEmbedder, to_blob
from .http import Http, check_public_url
from .imaging import color_hist, process_image, render_font_specimen
from .models import Kind
from .sources import build_sources

log = logging.getLogger("noze.enrich")

THUMB_OK, THUMB_NONE, THUMB_FAILED = 1, 2, 3


def asset_text(a: dict[str, Any]) -> str:
    tags = " ".join((a.get("tags") or [])[:20])
    desc = (a.get("description") or "")[:240]
    return f"{a.get('title') or ''}. {tags}. {a.get('kind')}. {desc}".strip()


def video_frame(path: Path, at: float = 1.0) -> bytes | None:
    """Grab one frame with ffmpeg (if installed) for video thumbnails."""
    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    for ts in (at, 0.0):
        try:
            out = subprocess.run(
                [ffmpeg, "-v", "error", "-ss", str(ts), "-i", str(path), "-frames:v", "1", "-vf", "scale=480:-2",
                 "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                capture_output=True, timeout=60, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if out.returncode == 0 and out.stdout:
            return out.stdout
    return None


def _looks_svg(data: bytes, ctype: str) -> bool:
    return "svg" in (ctype or "") or data[:400].lstrip().startswith((b"<svg", b"<?xml"))


class Enricher:
    def __init__(self, ctx: Context, http: Http):
        self.ctx = ctx
        self.db = ctx.db
        self.http = http
        self.sources = build_sources(ctx.settings, http)

    async def thumbs_batch(self, limit: int = 24) -> int:
        rows = self.db.pending_thumbs(limit)
        if not rows:
            return 0
        sem = asyncio.Semaphore(8)

        async def one(a: dict[str, Any]) -> None:
            async with sem:
                await self.thumb_one(a)

        await asyncio.gather(*(one(a) for a in rows))
        return len(rows)

    async def thumb_one(self, a: dict[str, Any]) -> Path | None:
        url = a.get("thumb_url") or ""
        if url.startswith(("http://", "https://")):
            try:
                if a["source"] not in self.ctx.source_classes:
                    # URLs that came from saved web pages get the same SSRF guard as user input
                    await check_public_url(url, self.ctx.settings.allow_private_fetch)
                src = self.sources.get(a["source"])
                data, ctype = await self.http.fetch_bytes(url, max_bytes=15 * 1024 * 1024,
                                                          headers=src.fetch_headers() if src else None)
            except Exception as exc:  # network, 404, too large…
                log.debug("thumb fetch failed for %s: %s", a["id"], exc)
                self.db.update_asset(a["id"], thumb_state=THUMB_FAILED)
                return None
        elif a.get("blob_key"):
            data, ctype = await asyncio.to_thread(self._local_preview, a)
            if data is None:
                self.db.update_asset(a["id"], thumb_state=THUMB_NONE)
                return None
        else:
            self.db.update_asset(a["id"], thumb_state=THUMB_NONE)
            return None
        return await asyncio.to_thread(self._store_thumb, a, data, ctype)

    def _local_preview(self, a: dict[str, Any]) -> tuple[bytes | None, str]:
        """Preview bytes for files that live in the bank (uploads, folder imports, generations)."""
        mime = (a.get("blob_mime") or "").lower()
        key = a["blob_key"]
        path = self.ctx.storage.local_path(key)
        try:
            if mime.startswith("image/"):
                if path is not None:
                    return (path.read_bytes() if path.stat().st_size < 60 * 1024 * 1024 else None), mime
                with self.ctx.storage.open(key) as fh:
                    return fh.read(60 * 1024 * 1024), mime
            if path is None:
                return None, ""
            if mime.startswith("video/"):
                return video_frame(path), "image/jpeg"
            if a["kind"] == Kind.FONT:
                return render_font_specimen(str(path), (a.get("title") or "Aa Bb Cc")[:18]), "image/webp"
        except OSError as exc:
            log.debug("local preview failed for %s: %s", a["id"], exc)
        return None, ""

    def _store_thumb(self, a: dict[str, Any], data: bytes, ctype: str) -> Path | None:
        if a["kind"] == Kind.ICON or _looks_svg(data, ctype):
            if not _looks_svg(data, ctype) or len(data) > 512 * 1024:
                self.db.update_asset(a["id"], thumb_state=THUMB_FAILED)
                return None
            path = self.ctx.thumb_file(a["id"], ".svg")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self.db.update_asset(a["id"], thumb_state=THUMB_OK, thumb_path=str(path.relative_to(self.ctx.settings.thumbs_dir)))
            return path
        try:
            res = process_image(data, self.ctx.settings.thumb_size)
        except Exception as exc:
            log.debug("not an image for %s (%s): %s", a["id"], ctype, exc)
            self.db.update_asset(a["id"], thumb_state=THUMB_FAILED)
            return None
        path = self.ctx.thumb_file(a["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(res.data)
        fields: dict[str, Any] = {
            "thumb_state": THUMB_OK,
            "thumb_path": str(path.relative_to(self.ctx.settings.thumbs_dir)),
            "dhash": res.dhash,
        }
        # keep source-provided palettes only if they are richer than one average color
        existing = a.get("colors") or []
        if len(existing) < 3:
            fields["colors"] = res.colors
        w, h = a.get("width") or 0, a.get("height") or 0
        aspect_only = w < 16 or h < 16  # missing or just an aspect hint → use the real thumbnail shape
        if aspect_only:
            fields["width"], fields["height"] = res.src_width, res.src_height
        self.db.update_asset(a["id"], **fields)
        if aspect_only:
            self.db.merge_extra(a["id"], {"dims_from_thumb": True})  # not the file's real resolution
        return path

    def embed_batch(self, limit: int = 48) -> int:
        """Synchronous (CPU-bound); run it in a thread."""
        emb = self.ctx.embedder
        if not emb.ready or self.ctx.index.model != emb.name:
            return 0
        rows = self.db.pending_embeddings(limit)
        if not rows:
            return 0
        items = []
        for a in rows:
            path = self.ctx.settings.thumbs_dir / a["thumb_path"] if a.get("thumb_path") else None
            hist = None
            if isinstance(emb, HashEmbedder) and path and path.suffix != ".svg" and path.exists():
                try:
                    with Image.open(path) as im:
                        hist = color_hist(im.convert("RGBA"))
                except Exception:
                    hist = None
            items.append(EmbedInput(text=asset_text(a), thumb_path=path, hist=hist))
        try:
            vecs = emb.embed_assets(items)
        except Exception as exc:
            log.warning("embedding batch failed: %s", exc)
            return 0
        rows_out = []
        for a, (vec, modality) in zip(rows, vecs):
            vec = np.asarray(vec, dtype=np.float32)
            rows_out.append((a["id"], emb.name, modality, to_blob(vec)))
            self.ctx.index.add(a["id"], vec, modality)
        self.db.put_embeddings(rows_out)
        return len(rows_out)
