"""Bring YOUR OWN Pinterest boards into NOZE through Pinterest's official API v5.

Scraping Pinterest search is against its terms (and pins belong to their
original creators anyway), so this only reads boards/pins of the account the
token belongs to, and marks everything reference-only.

Get a token: https://developers.pinterest.com/apps/ → create app → generate an
access token with boards:read and pins:read → PINTEREST_ACCESS_TOKEN=...
"""

from __future__ import annotations

from typing import Any

from ..context import Context
from ..http import Http, SourceError
from ..licenses import known
from ..models import Asset, Kind

API = "https://api.pinterest.com/v5"


def _best_image(images: dict[str, Any]) -> tuple[str, str, int | None, int | None]:
    def get(key: str) -> dict[str, Any]:
        return images.get(key) or {}

    big = get("1200x") or get("originals") or get("600x") or get("400x300") or get("150x150")
    small = get("600x") or get("400x300") or big
    return small.get("url") or "", big.get("url") or "", big.get("width"), big.get("height")


def parse_pin(pin: dict[str, Any]) -> Asset | None:
    media = pin.get("media") or {}
    images = media.get("images") or {}
    thumb, big, w, h = _best_image(images)
    if not thumb:
        return None
    lic = known("reference")
    kind = Kind.VIDEO if (media.get("media_type") or "").startswith("video") else Kind.IMAGE
    return Asset(
        source="pinterest", source_id=str(pin.get("id")), kind=kind,
        title=pin.get("title") or pin.get("alt_text") or (pin.get("description") or "")[:80] or "Pin",
        description=pin.get("description") or "", tags=["pinterest"],
        page_url=f"https://www.pinterest.com/pin/{pin.get('id')}/", thumb_url=thumb, preview_url=big,
        download_url=big, width=w, height=h, license=lic.code, license_label=lic.label, usage=lic.usage,
        attribution=f"Pinned on Pinterest — original source: {pin.get('link') or 'unknown'}",
        colors=[[pin["dominant_color"], 0.5]] if pin.get("dominant_color") else None,
        extra={"link": pin.get("link"), "board_id": pin.get("board_id")},
    )


async def _paged(http: Http, url: str, token: str, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    bookmark = None
    while len(items) < limit:
        params: dict[str, Any] = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        data = await http.get_json(url, params=params, headers={"Authorization": f"Bearer {token}"})
        items.extend(data.get("items") or [])
        bookmark = data.get("bookmark")
        if not bookmark:
            break
    return items[:limit]


async def import_pinterest(ctx: Context, http: Http, token: str | None = None, max_pins: int = 5000) -> dict[str, Any]:
    token = token or ctx.settings.key("PINTEREST_ACCESS_TOKEN")
    if not token:
        raise SourceError("set PINTEREST_ACCESS_TOKEN (see docs/SOURCES.md → Pinterest)")
    boards = await _paged(http, f"{API}/boards", token, 1000)
    total = 0
    for b in boards:
        pins = await _paged(http, f"{API}/boards/{b['id']}/pins", token, max_pins)
        assets = [a for a in (parse_pin(p) for p in pins) if a]
        ids = ctx.db.upsert_assets(assets)
        board_id = ctx.db.create_board(f"Pinterest · {b.get('name') or b['id']}", b.get("description") or "")
        for aid in ids:
            ctx.db.add_to_board(board_id, aid)
        total += len(ids)
    return {"boards": len(boards), "pins": total}
