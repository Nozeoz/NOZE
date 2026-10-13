"""Save anything from any website into the bank — the bookmarklet, the
"paste a link" box and file uploads all land here.

This is the legit way to keep references from Pinterest, Behance, Dribbble,
X, Dreamina/Higgsfield/Kling community feeds, etc.: YOU pick what to keep
while browsing (like pressing "Save"), NOZE stores it with the page link for
credit and marks it reference-only (rights stay with the creator).
"""

from __future__ import annotations

import hashlib
import mimetypes
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from ..context import Context
from ..http import Http, SourceError
from ..licenses import known
from ..models import Asset, Kind
from ..storage import guess_ext


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and len(self.title) < 300:
            self.title += data


def kind_for_mime(mime: str, name: str = "") -> str | None:
    mime = (mime or "").split(";")[0].strip().lower()
    if not mime or mime == "application/octet-stream":
        mime = mimetypes.guess_type(name)[0] or ""
    if mime == "image/gif":
        return Kind.GIF
    if mime.startswith("image/"):
        return Kind.IMAGE
    if mime.startswith("video/"):
        return Kind.VIDEO
    if mime.startswith("audio/"):
        return Kind.AUDIO
    if mime.startswith("font/") or name.lower().endswith((".ttf", ".otf", ".woff", ".woff2")):
        return Kind.FONT
    if name.lower().endswith(".json") or mime == "application/json":
        return Kind.MOTION
    return None


def _finish(ctx: Context, asset: Asset, board: str | None, note: str) -> dict[str, Any]:
    ctx.db.upsert_assets([asset])
    if board:
        ctx.db.add_to_board(ctx.db.create_board(board), asset.id, note)
    return ctx.db.get_asset(asset.id)


async def ingest_url(ctx: Context, http: Http, url: str, page_url: str = "", title: str = "", note: str = "",
                     tags: list[str] | None = None, board: str | None = None) -> dict[str, Any]:
    url = (url or "").strip()
    if not url:
        raise SourceError("no URL")
    body, ctype, final = await http.fetch_user_url(url, max_bytes=2 * 1024 * 1024)
    mime = ctype.split(";")[0].strip().lower()
    lic = known("reference")
    site = urlparse(page_url or final).hostname or ""
    tags = [t for t in (tags or []) if t] + ([site.removeprefix("www.")] if site else [])
    kind = kind_for_mime(mime, urlparse(final).path)
    if kind is not None:
        # a direct media link: keep the file itself in the bank
        d = await http.download(final, ctx.settings.tmp_dir, ctx.settings.max_download_mb * 1024 * 1024,
                                check_public=True)
        try:
            key = ctx.storage.put_file(d.path, d.sha256, guess_ext(d.mime, final), d.mime.split(";")[0])
        finally:
            d.path.unlink(missing_ok=True)
        asset = Asset(
            source="web", source_id=d.sha256[:24], kind=kind,
            title=title or Path(urlparse(final).path).stem.replace("-", " ").replace("_", " ") or site,
            description=note, tags=tags, author=site, page_url=page_url or final, thumb_url="",
            preview_url=final, download_url=final, license=lic.code, license_label=lic.label, usage=lic.usage,
            attribution=f"Saved from {page_url or final} — rights belong to the original creator",
            extra={"saved_from": page_url or final, "media_url": final},
        )
        _finish(ctx, asset, board, note)
        ctx.db.update_asset(asset.id, blob_key=key, blob_size=d.size, blob_mime=d.mime.split(";")[0], thumb_state=0,
                            preview_url=f"/api/assets/{asset.id}/file")
        return ctx.db.get_asset(asset.id)
    if "html" not in mime and not body.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        raise SourceError(f"don't know how to save {mime or 'this link'}")
    parser = _MetaParser()
    parser.feed(body.decode("utf-8", errors="ignore"))
    m = parser.meta
    image = m.get("og:image") or m.get("og:image:url") or m.get("twitter:image") or m.get("twitter:image:src") or ""
    video = m.get("og:video:secure_url") or m.get("og:video:url") or m.get("og:video") or ""
    image = urljoin(final, image) if image else ""
    video = urljoin(final, video) if video else ""
    kind = Kind.VIDEO if video and video.lower().split("?")[0].endswith((".mp4", ".webm", ".mov")) else (
        Kind.IMAGE if image else Kind.LINK)
    name = title or m.get("og:title") or m.get("twitter:title") or parser.title.strip() or site
    asset = Asset(
        source="web", source_id=hashlib.sha1(final.encode()).hexdigest()[:24], kind=kind, title=name,
        description=note or m.get("og:description") or m.get("description") or "", tags=tags,
        author=m.get("author") or m.get("article:author") or m.get("og:site_name") or site,
        page_url=page_url or final, thumb_url=image, preview_url=video or image, download_url=video or image,
        license=lic.code, license_label=lic.label, usage=lic.usage,
        attribution=f"Saved from {page_url or final} — rights belong to the original creator",
        extra={"saved_from": page_url or final, "site": m.get("og:site_name") or site},
    )
    return _finish(ctx, asset, board, note)


def ingest_file(ctx: Context, path: Path, filename: str, mime: str, tags: list[str] | None = None,
                board: str | None = None, note: str = "") -> dict[str, Any]:
    kind = kind_for_mime(mime, filename)
    if kind is None:
        ext = Path(filename).suffix.lower()
        from .folder import EXT_KIND

        kind = EXT_KIND.get(ext, Kind.TEMPLATE)
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    sha = h.hexdigest()
    ext = Path(filename).suffix.lower() or guess_ext(mime, filename)
    mime = mime or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    key = ctx.storage.put_file(path, sha, ext, mime)
    lic = known("own")
    asset = Asset(
        source="upload", source_id=sha[:24], kind=kind,
        title=Path(filename).stem.replace("_", " ").replace("-", " ") or filename, description=note,
        tags=(tags or []) + [ext.lstrip(".")], author="you", license=lic.code, license_label=lic.label,
        usage=lic.usage, extra={"filename": filename},
    )
    _finish(ctx, asset, board, note)
    ctx.db.update_asset(asset.id, blob_key=key, blob_size=path.stat().st_size, blob_mime=mime, thumb_state=0,
                        preview_url=f"/api/assets/{asset.id}/file")
    return ctx.db.get_asset(asset.id)
