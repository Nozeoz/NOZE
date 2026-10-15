"""Autopilot: self-seeding, learning interests, keys from the UI, Pinterest OAuth + sync."""

import asyncio
import os
import time
from urllib.parse import parse_qs, urlparse

import httpx
import respx
from fastapi.testclient import TestClient

from noze import autopilot
from noze.api import create_app
from noze.http import Http
from noze.importers import pinterest
from noze.lexicon import STARTER_TOPICS
from tests.conftest import make_settings
from tests.test_api import mock_sources

PIN_API = "https://api.pinterest.com/v5"


def pin(i, title="Neon alley"):
    return {"id": str(i), "title": f"{title} {i}", "description": "", "link": "https://example.com/x",
            "board_id": "b1", "media": {"media_type": "image", "images": {
                "600x": {"url": f"https://i.pinimg.com/600x/{i}.jpg", "width": 600, "height": 900},
                "1200x": {"url": f"https://i.pinimg.com/1200x/{i}.jpg", "width": 1200, "height": 1800}}}}


def mock_pinterest(m, pages):
    m.get(f"{PIN_API}/user_account").respond(json={"username": "dalvin"})
    m.get(f"{PIN_API}/boards").respond(json={"items": [
        {"id": "b1", "name": "Cyberpunk moodboard"}, {"id": "b2", "name": "Saved"}], "bookmark": None})

    def board_pins(request):
        bookmark = request.url.params.get("bookmark")
        idx = int(bookmark) if bookmark else 0
        nxt = str(idx + 1) if idx + 1 < len(pages) else None
        return httpx.Response(200, json={"items": pages[idx], "bookmark": nxt})

    route = m.get(url__regex=rf"{PIN_API}/boards/b1/pins").mock(side_effect=board_pins)
    m.get(url__regex=rf"{PIN_API}/boards/b2/pins").respond(json={"items": [pin(900, "Saved thing")], "bookmark": None})
    return route


def test_bank_seeds_itself_once(ctx):
    assert autopilot.seed_if_new(ctx.db)
    assert len(ctx.db.list_interests()) == len(STARTER_TOPICS)
    ctx.db.delete_interest(ctx.db.list_interests()[0]["id"])
    assert not autopilot.seed_if_new(ctx.db)  # never re-seeded, even if you prune the list


def test_repeated_searches_and_saves_become_interests(tmp_path):
    settings = make_settings(tmp_path, NOZE_SOURCES="openverse,iconify")
    with TestClient(create_app(settings, start_worker=False)) as c, respx.mock(assert_all_called=False) as m:
        mock_sources(m)
        c.get("/api/search", params={"q": "Neon  Rain"})
        assert c.get("/api/interests").json() == []
        c.get("/api/search", params={"q": "neon rain", "live": 0})
        learned = c.get("/api/interests").json()
        assert [i["query"] for i in learned] == ["neon rain"]
        # deleting it means "not interested": searching again does not bring it back
        c.delete(f"/api/interests/{learned[0]['id']}")
        c.get("/api/search", params={"q": "neon rain", "live": 0})
        assert c.get("/api/interests").json() == []
        # one save from a search is enough
        aid = "openverse:4bc43a04-ef46-4544-a0c1-63c63f56e276"
        c.post("/api/save", json={"asset_id": aid, "board": "Refs", "query": "rainy window"})
        assert [i["query"] for i in c.get("/api/interests").json()] == ["rainy window"]


def test_autopilot_can_be_switched_off(tmp_path):
    settings = make_settings(tmp_path, NOZE_SOURCES="openverse,iconify", NOZE_AUTOPILOT="0")
    with TestClient(create_app(settings, start_worker=False)) as c, respx.mock(assert_all_called=False) as m:
        mock_sources(m)
        for _ in range(3):
            c.get("/api/search", params={"q": "neon rain"})
        assert c.get("/api/interests").json() == []


def test_keys_pasted_in_the_ui_turn_sources_on(tmp_path):
    settings = make_settings(tmp_path, NOZE_SOURCES="openverse,pexels")
    with TestClient(create_app(settings, start_worker=False)) as c:
        pexels = lambda: next(s for s in c.get("/api/sources").json() if s["name"] == "pexels")  # noqa: E731
        assert not pexels()["enabled"]
        assert c.post("/api/settings/keys", json={"PEXELS_API_KEY": "abc123"}).json()["configured"]
        assert pexels()["enabled"]
        keys = c.get("/api/settings/keys").json()
        assert keys["keys"]["PEXELS_API_KEY"] is True and "abc123" not in str(keys)
        env = settings.data_dir / ".env"
        assert "PEXELS_API_KEY=abc123" in env.read_text()
        if os.name == "posix":
            assert env.stat().st_mode & 0o777 == 0o600
        assert c.post("/api/settings/keys", json={"NOZE_PASSWORD": "x"}).status_code == 400
        assert c.post("/api/settings/keys", json={"PEXELS_API_KEY": "a\nNOZE_PASSWORD=x"}).status_code == 400
        # clearing a key removes the line and switches the source off again
        c.post("/api/settings/keys", json={"PEXELS_API_KEY": ""})
        assert "PEXELS_API_KEY" not in env.read_text() and not pexels()["enabled"]
        # survives a restart
        c.post("/api/settings/keys", json={"PEXELS_API_KEY": "zzz"})
    from noze.config import Settings
    reloaded = Settings.load(data_dir=settings.data_dir, env={"NOZE_EMBEDDER": "hash"}, dotenv=True)
    assert reloaded.key("PEXELS_API_KEY") == "zzz"


def test_pinterest_connect_flow(tmp_path):
    settings = make_settings(tmp_path, NOZE_SOURCES="openverse", PINTEREST_APP_ID="1234", PINTEREST_APP_SECRET="s3cret")
    with TestClient(create_app(settings, start_worker=False)) as c, respx.mock(assert_all_called=False) as m:
        st = c.get("/api/pinterest").json()
        assert not st["connected"] and st["can_oauth"]
        assert st["redirect_uri"] == "http://testserver/api/pinterest/callback"
        r = c.get("/api/pinterest/connect", follow_redirects=False)
        loc = urlparse(r.headers["location"])
        qs = parse_qs(loc.query)
        assert loc.netloc == "www.pinterest.com" and qs["client_id"] == ["1234"] and "pins:read" in qs["scope"][0]
        token = m.post(f"{PIN_API}/oauth/token").respond(json={
            "access_token": "pina_A", "refresh_token": "pinr_R", "expires_in": 2592000,
            "refresh_token_expires_at": int(time.time()) + 60 * 86400})
        # a forged callback (wrong state) is refused
        c.get("/api/pinterest/callback", params={"code": "x", "state": "nope"}, follow_redirects=False)
        assert not token.called and "expired" in c.get("/api/pinterest").json()["last_error"]
        r = c.get("/api/pinterest/callback", params={"code": "the-code", "state": qs["state"][0]}, follow_redirects=False)
        assert r.status_code in (302, 307) and r.headers["location"] == "/#/bank"
        sent = token.calls.last.request
        assert sent.headers["authorization"] == "Basic MTIzNDpzM2NyZXQ="
        assert b"grant_type=authorization_code" in sent.content and b"code=the-code" in sent.content
        st = c.get("/api/pinterest").json()
        assert st["connected"] and st["via"] == "oauth" and not st["last_error"]
        assert any(j["type"] == "pinterest_sync" for j in c.get("/api/jobs").json())
        # the state can't be replayed
        c.get("/api/pinterest/callback", params={"code": "again", "state": qs["state"][0]}, follow_redirects=False)
        assert token.call_count == 1


def test_pinterest_sync_is_incremental_and_learns_boards(ctx):
    ctx.db.set_meta("pinterest.access_token", "pina_A")
    ctx.db.set_meta("pinterest.expires_at", str(time.time() + 25 * 86400))

    async def run(pages):
        with respx.mock(assert_all_called=False) as m:
            route = mock_pinterest(m, pages)
            http = Http(ctx.settings)
            try:
                res = await pinterest.sync_pinterest(ctx, http)
            finally:
                await http.aclose()
            return res, route.call_count

    first, calls = asyncio.run(run([[pin(i) for i in range(1, 4)], [pin(i) for i in range(4, 6)]]))
    assert first == {"boards": 2, "pins": 6, "new": 6} and calls == 2
    assert ctx.db.get_meta("pinterest.user") == "dalvin"
    a = ctx.db.get_asset("pinterest:1")
    assert a["usage"] == "reference" and a["preview_url"].endswith("/1200x/1.jpg")
    names = {b["name"] for b in ctx.db.list_boards()}
    assert {"Pinterest · Cyberpunk moodboard", "Pinterest · Saved"} <= names
    # board names become crawl interests — but not generic ones like "Saved"
    assert [i["query"] for i in ctx.db.list_interests()] == ["cyberpunk moodboard"]
    assert not pinterest.sync_due(ctx)

    # next sync: two new pins on top; stops after the first page that is all known
    second, calls = asyncio.run(run([[pin(10), pin(11), pin(1)], [pin(2), pin(3)], [pin(4), pin(5)]]))
    assert second["new"] == 2 and calls == 2


def test_pinterest_token_refreshes_itself(ctx):
    ctx.settings.keys.update({"PINTEREST_APP_ID": "1234", "PINTEREST_APP_SECRET": "s3cret"})
    ctx.db.set_meta("pinterest.access_token", "pina_OLD")
    ctx.db.set_meta("pinterest.refresh_token", "pinr_R")
    ctx.db.set_meta("pinterest.expires_at", str(time.time() + 2 * 86400))

    async def run():
        with respx.mock() as m:
            tok = m.post(f"{PIN_API}/oauth/token").respond(json={
                "access_token": "pina_NEW", "refresh_token": "pinr_R2", "expires_in": 2592000,
                "refresh_token_expires_at": int(time.time()) + 60 * 86400})
            http = Http(ctx.settings)
            try:
                return await pinterest.current_token(ctx, http), tok.calls.last.request.content
            finally:
                await http.aclose()

    token, body = asyncio.run(run())
    assert token == "pina_NEW" and b"grant_type=refresh_token" in body and b"refresh_token=pinr_R" in body
    assert ctx.db.get_meta("pinterest.refresh_token") == "pinr_R2"
    assert float(ctx.db.get_meta("pinterest.expires_at")) > time.time() + 29 * 86400
