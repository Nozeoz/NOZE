"""Import an existing asset folder (your old downloads, packs, project
assets) so everything is searchable in one place.

Folder names become tags: "Overlays/Light Leaks/leak_04.mp4" → tags
["overlays", "light leaks"]. By default files are copied into the bank's
storage (deduplicated by content); --link indexes them in place instead.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Callable

from ..context import Context
from ..licenses import known
from ..models import Asset, Kind

EXT_KIND = {
    **dict.fromkeys((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".avif", ".heic", ".jfif"), Kind.IMAGE),
    ".gif": Kind.GIF,
    ".svg": Kind.IMAGE,
    **dict.fromkeys((".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi", ".mxf", ".prores"), Kind.VIDEO),
    **dict.fromkeys((".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".aif", ".aiff"), Kind.AUDIO),
    **dict.fromkeys((".ttf", ".otf", ".woff", ".woff2"), Kind.FONT),
    **dict.fromkeys((".obj", ".fbx", ".glb", ".gltf", ".blend", ".stl", ".usdz", ".usd", ".c4d", ".3ds", ".abc"), Kind.MODEL3D),
    **dict.fromkeys((".hdr", ".exr"), Kind.HDRI),
    ".lottie": Kind.MOTION,
    **dict.fromkeys((".aep", ".aet", ".mogrt", ".prproj", ".ffx", ".cube", ".3dl", ".look", ".psd", ".psb", ".ai",
                     ".eps", ".fig", ".sketch", ".xd", ".drp", ".dra", ".lrtemplate", ".xmp", ".atn", ".abr",
                     ".pat", ".grd", ".aepx", ".osp", ".veg", ".kdenlive"), Kind.TEMPLATE),
}
SKIP_DIRS = {".git", "__MACOSX", "node_modules", ".cache", ".Trash", "$RECYCLE.BIN"}


def _is_lottie(path: Path) -> bool:
    if path.suffix.lower() != ".json" or path.stat().st_size > 20 * 1024 * 1024:
        return False
    try:
        head = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (ValueError, OSError):
        return False
    return isinstance(head, dict) and "layers" in head and ("v" in head or "fr" in head)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tags_for(path: Path, root: Path) -> list[str]:
    rel = path.relative_to(root)
    tags = [p.replace("_", " ").replace("-", " ").strip().lower() for p in rel.parts[:-1]]
    stem_words = [w for w in re.split(r"[\s_\-.()\[\]]+", path.stem.lower()) if w and not w.isdigit() and len(w) > 1]
    return tags + stem_words[:8] + [path.suffix.lower().lstrip(".")]


def import_folder(ctx: Context, root: Path, board: str | None = None, link: bool = False,
                  extra_tags: list[str] | None = None, progress: Callable[[int, Path], None] | None = None) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"not a folder: {root}")
    board_id = ctx.db.create_board(board) if board else None
    imported = skipped = 0
    batch: list[tuple[Asset, str, int, str]] = []

    def flush() -> None:
        if not batch:
            return
        ctx.db.upsert_assets([b[0] for b in batch])
        for a, key, size, mime in batch:
            ctx.db.update_asset(a.id, blob_key=key, blob_size=size, blob_mime=mime, thumb_state=0,
                                preview_url=f"/api/assets/{a.id}/file")
            if board_id:
                ctx.db.add_to_board(board_id, a.id)
        batch.clear()

    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS or part.startswith(".") for part in path.relative_to(root).parts):
            continue
        ext = path.suffix.lower()
        kind = EXT_KIND.get(ext) or (Kind.MOTION if _is_lottie(path) else None)
        if kind is None:
            skipped += 1
            continue
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        sha = _sha256(path)
        key = f"file:{path}" if link else ctx.storage.put_file(path, sha, ext, mime)
        title = re.sub(r"[_\-]+", " ", path.stem).strip() or path.name
        lic = known("own")
        asset = Asset(
            source="folder", source_id=sha[:24], kind=kind, title=title, tags=_tags_for(path, root) + (extra_tags or []),
            author="you", license=lic.code, license_label=lic.label, usage=lic.usage,
            extra={"original_path": str(path), "linked": link},
        )
        batch.append((asset, key, path.stat().st_size, mime))
        imported += 1
        if progress:
            progress(imported, path)
        if len(batch) >= 200:
            flush()
    flush()
    return {"imported": imported, "skipped": skipped, "board_id": board_id}
