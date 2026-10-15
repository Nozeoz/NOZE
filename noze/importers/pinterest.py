"""Bring YOUR OWN Pinterest boards into NOZE through Pinterest's official API v5.

Scraping Pinterest search is against its terms (and pins belong to their
original creators anyway), so this only reads boards/pins of the account that
connected, and marks everything reference-only.

Two ways in:
- "Connect Pinterest" in the web UI (OAuth with PINTEREST_APP_ID/SECRET): tokens
  are refreshed automatically, so the sync keeps running forever;
- or a plain PINTEREST_ACCESS_TOKEN (expires after 30 days).

Once connected the worker syncs every few hours: new pins land in the bank,
each board becomes a NOZE board, and board names become crawl interests.
"""

from __future__ import annotations

import base64
import secrets
import time
from typing import Any
from urllib.parse import urlencode

from .. import autopilot
from ..context import Context
from ..http import Http, SourceError
from ..licenses import known
from ..models import Asset, Kind

API = "https://api.pinterest.com/v5"
AUTHORIZE = "https://www.pinterest.com/oauth/"
SCOPES = "boards:read,pins:read,user_accounts:read"
REFRESH_WITHIN = 10 * 86400  # refresh when the 30-day access token has less than this left


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


async def _paged(http: Http, url: str, token: str, limit: int, stop_when_known=None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    bookmark = None
    while len(items) < limit:
        params: dict[str, Any] = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        data = await http.get_json(url, params=params, headers={"Authorization": f"Bearer {token}"},
                                   rate_key="pinterest", min_interval=0.3)
        page = data.get("items") or []
        items.extend(page)
        bookmark = data.get("bookmark")
        if not bookmark or (stop_when_known and page and stop_when_known(page)):
            break
    return items[:limit]


# -- OAuth -----------------------------------------------------------------------------------
def can_oauth(ctx: Context) -> bool:
    return bool(ctx.settings.key("PINTEREST_APP_ID") and ctx.settings.key("PINTEREST_APP_SECRET"))


def authorize_url(ctx: Context, redirect_uri: str) -> str:
    state = secrets.token_urlsafe(24)
    ctx.db.set_meta("pinterest.oauth_state", state)
    ctx.db.set_meta("pinterest.redirect_uri", redirect_uri)
    return AUTHORIZE + "?" + urlencode({
        "client_id": ctx.settings.key("PINTEREST_APP_ID"), "redirect_uri": redirect_uri,
        "response_type": "code", "scope": SCOPES, "state": state,
    })


def _basic(ctx: Context) -> str:
    raw = f"{ctx.settings.key('PINTEREST_APP_ID')}:{ctx.settings.key('PINTEREST_APP_SECRET')}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def _store_tokens(ctx: Context, data: dict[str, Any]) -> None:
    if not data.get("access_token"):
        raise SourceError("Pinterest did not return an access token")
    t = time.time()
    db = ctx.db
    db.set_meta("pinterest.access_token", data["access_token"])
    db.set_meta("pinterest.expires_at", str(t + float(data.get("expires_in") or 2592000)))
    if data.get("refresh_token"):
        db.set_meta("pinterest.refresh_token", data["refresh_token"])
        exp = data.get("refresh_token_expires_at") or (t + float(data.get("refresh_token_expires_in") or 60 * 86400))
        db.set_meta("pinterest.refresh_expires_at", str(exp))
    db.set_meta("pinterest.last_error", "")


async def _token_call(ctx: Context, http: Http, form: dict[str, str]) -> dict[str, Any]:
    resp = await http.request("POST", f"{API}/oauth/token", data=form, rate_key="pinterest", headers={
        "Authorization": _basic(ctx), "Content-Type": "application/x-www-form-urlencoded"})
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError("invalid token response from Pinterest") from exc


async def finish_oauth(ctx: Context, http: Http, code: str, state: str) -> None:
    expected = ctx.db.get_meta("pinterest.oauth_state") or ""
    if not expected or not secrets.compare_digest(expected, state or ""):
        raise SourceError("Pinterest login expired or was not started here — click Connect again")
    ctx.db.set_meta("pinterest.oauth_state", "")
    data = await _token_call(ctx, http, {
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": ctx.db.get_meta("pinterest.redirect_uri") or "", "continuous_refresh": "true"})
    _store_tokens(ctx, data)


async def current_token(ctx: Context, http: Http) -> str | None:
    """OAuth token (refreshed when it gets old), else a pasted PINTEREST_ACCESS_TOKEN."""
    db = ctx.db
    token = db.get_meta("pinterest.access_token") or ""
    if token:
        expires = float(db.get_meta("pinterest.expires_at", "0") or 0)
        refresh = db.get_meta("pinterest.refresh_token") or ""
        if refresh and can_oauth(ctx) and expires - time.time() < REFRESH_WITHIN:
            data = await _token_call(ctx, http, {"grant_type": "refresh_token", "refresh_token": refresh})
            _store_tokens(ctx, data)
            token = data["access_token"]
        return token
    return ctx.settings.key("PINTEREST_ACCESS_TOKEN") or None


def disconnect(ctx: Context) -> None:
    for k in ("access_token", "refresh_token", "expires_at", "refresh_expires_at", "user", "last_error"):
        ctx.db.set_meta(f"pinterest.{k}", "")


def status(ctx: Context) -> dict[str, Any]:
    db = ctx.db
    oauth = bool(db.get_meta("pinterest.access_token"))
    pasted = bool(ctx.settings.key("PINTEREST_ACCESS_TOKEN"))
    pins = db.conn().execute("SELECT COUNT(*) FROM assets WHERE source = 'pinterest'").fetchone()[0]
    last = float(db.get_meta("pinterest.last_sync", "0") or 0)
    return {
        "connected": oauth or pasted, "via": "oauth" if oauth else ("token" if pasted else None),
        "can_oauth": can_oauth(ctx), "user": db.get_meta("pinterest.user") or "",
        "last_sync": last or None, "last_error": db.get_meta("pinterest.last_error") or "",
        "every_hours": ctx.settings.pinterest_sync_hours, "pins": pins,
        "boards": int(db.get_meta("pinterest.boards", "0") or 0),
    }


def sync_due(ctx: Context) -> bool:
    st = status(ctx)
    if not st["connected"]:
        return False
    last = st["last_sync"] or 0
    # after an error wait an hour, not the full interval
    wait = 3600 if st["last_error"] else ctx.settings.pinterest_sync_hours * 3600
    return time.time() - last >= wait


# -- import / sync ---------------------------------------------------------------------------
async def import_pinterest(ctx: Context, http: Http, token: str | None = None, max_pins: int = 5000,
                           incremental: bool = False) -> dict[str, Any]:
    token = token or await current_token(ctx, http)
    if not token:
        raise SourceError("connect Pinterest on the Bank page, or set PINTEREST_ACCESS_TOKEN (see docs/SOURCES.md → Pinterest)")
    db = ctx.db
    headers = {"Authorization": f"Bearer {token}"}
    try:
        me = await http.get_json(f"{API}/user_account", headers=headers, rate_key="pinterest")
        if me.get("username"):
            db.set_meta("pinterest.user", me["username"])
    except SourceError:
        pass  # older tokens may lack user_accounts:read; boards still work

    def all_known(page: list[dict[str, Any]]) -> bool:
        ids = [f"pinterest:{p.get('id')}" for p in page]
        return len(db.get_assets(ids)) == len(ids)

    boards = await _paged(http, f"{API}/boards", token, 1000)
    total = new = 0
    for b in boards:
        pins = await _paged(http, f"{API}/boards/{b['id']}/pins", token, max_pins,
                            stop_when_known=all_known if incremental else None)
        assets = [a for a in (parse_pin(p) for p in pins) if a]
        existing = db.get_assets([a.id for a in assets])
        ids = db.upsert_assets(assets)
        name = b.get("name") or str(b["id"])
        board_id = db.create_board(f"Pinterest · {name}", b.get("description") or "")
        for aid in ids:
            db.add_to_board(board_id, aid)
        total += len(ids)
        new += len([i for i in ids if i not in existing])
        if ctx.settings.autopilot:
            autopilot.learn_from_board(db, name)
    db.set_meta("pinterest.boards", str(len(boards)))
    return {"boards": len(boards), "pins": total, "new": new}


async def sync_pinterest(ctx: Context, http: Http) -> dict[str, Any]:
    db = ctx.db
    first = not db.get_meta("pinterest.last_sync")
    try:
        res = await import_pinterest(ctx, http, incremental=not first)
    except SourceError as exc:
        db.set_meta("pinterest.last_error", str(exc)[:300])
        db.set_meta("pinterest.last_sync", str(time.time()))
        raise
    db.set_meta("pinterest.last_error", "")
    db.set_meta("pinterest.last_sync", str(time.time()))
    return res
