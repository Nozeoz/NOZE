"""Process-wide state shared by the API server, the background worker and the CLI."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import numpy as np

from .config import Settings
from .db import Database
from .embeddings import Embedder, HashEmbedder, VectorIndex, make_embedder
from .sources import SOURCE_CLASSES, source_labels
from .storage import Storage, get_storage

log = logging.getLogger("noze")


class Context:
    def __init__(self, settings: Settings):
        settings.ensure_dirs()
        self.settings = settings
        self.db = Database(settings.db_path)
        self.storage: Storage = get_storage(settings)
        self.embedder: Embedder = make_embedder(settings.embedder, settings.models_dir)
        self.embedder_error = ""
        self.index = VectorIndex()
        self.labels = source_labels()
        self.source_classes = {cls.name: cls for cls in SOURCE_CLASSES}
        if self.embedder.ready:  # the hash embedder needs no download
            self._activate_embedder()

    # -- embeddings -----------------------------------------------------------
    def _activate_embedder(self) -> None:
        name = self.embedder.name
        if self.db.get_meta("embedder") != name:
            # new model → every asset gets re-embedded by the worker (thumbnails are cached)
            self.db.reset_embeddings()
            self.db.set_meta("embedder", name)
        self.index.reset(name, self.embedder.dim)
        n = self.index.load(self.db.iter_embeddings(name))
        log.info("vector index: %d vectors (%s)", n, name)

    def ensure_embedder(self) -> None:
        """Load the configured embedder (may download a model); fall back to hashing on failure."""
        if self.embedder.ready and self.index.model == self.embedder.name:
            return
        try:
            self.embedder.load()
        except Exception as exc:  # no internet for the model download, broken install, …
            self.embedder_error = f"{type(exc).__name__}: {exc}"
            log.warning("could not load %s (%s); using the lightweight hash embedder", self.embedder.name, exc)
            self.embedder = HashEmbedder()
        self._activate_embedder()

    def query_vector(self, text: str, colors: list[str] | None = None) -> np.ndarray | None:
        if not self.embedder.ready or self.index.model != self.embedder.name or not (text or colors):
            return None
        try:
            return self.embedder.embed_query(text, colors or [])
        except Exception as exc:
            log.warning("query embedding failed: %s", exc)
            return None

    @property
    def semantic(self) -> bool:
        """True when a real image/text model (CLIP/SigLIP) is active."""
        return self.embedder.ready and not isinstance(self.embedder, HashEmbedder)

    # -- paths ----------------------------------------------------------------
    def thumb_file(self, asset_id: str, ext: str = ".webp") -> Path:
        h = hashlib.sha1(asset_id.encode("utf-8")).hexdigest()
        return self.settings.thumbs_dir / h[:2] / f"{h}{ext}"

    def source_label(self, name: str) -> str:
        return self.labels.get(name, name)

    def is_hotlink(self, source: str) -> bool:
        cls = self.source_classes.get(source)
        return bool(cls and cls.hotlink)

    # -- serialization ----------------------------------------------------------
    def asset_json(self, a: dict[str, Any], full: bool = False) -> dict[str, Any]:
        cached = bool(a.get("thumb_path")) and not self.is_hotlink(a["source"])
        if cached:
            thumb = f"/api/thumb/{a['id']}"
        elif a.get("thumb_url"):
            thumb = a["thumb_url"]
        else:
            thumb = ""
        extra = a.get("extra") or {}
        out = {
            "id": a["id"], "source": a["source"], "source_label": self.source_label(a["source"]), "kind": a["kind"],
            "title": a.get("title") or "", "author": a.get("author") or "", "thumb": thumb,
            "thumb_remote": a.get("thumb_url") or "", "preview_url": a.get("preview_url") or "",
            "page_url": a.get("page_url") or "", "width": a.get("width"), "height": a.get("height"),
            "duration": a.get("duration"), "usage": a.get("usage"), "license": a.get("license"),
            "license_label": a.get("license_label") or "", "colors": a.get("colors") or [],
            "saved": bool(a.get("saved")), "stored": bool(a.get("blob_key")),
            "video": extra.get("video") or extra.get("mp4") or "",
        }
        if full:
            out.update({
                "description": a.get("description") or "", "tags": a.get("tags") or [],
                "author_url": a.get("author_url") or "", "download_url": a.get("download_url") or "",
                "license_url": a.get("license_url") or "", "attribution": a.get("attribution") or "",
                "popularity": a.get("popularity") or 0, "created_at": a.get("created_at") or "", "extra": extra,
                "blob_size": a.get("blob_size"), "blob_mime": a.get("blob_mime"),
                "file_url": f"/api/assets/{a['id']}/file" if a.get("blob_key") else "",
            })
        return out
