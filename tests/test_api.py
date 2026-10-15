"""HTTP API end to end (sources mocked, worker off)."""

import base64
import io
import zipfile

import respx
from fastapi.testclient import TestClient

from noze.api import create_app
from tests.conftest import make_settings, png_bytes
from tests.fixtures import responses as R


def client(tmp_path, **env):
    settings = make_settings(tmp_path, NOZE_SOURCES="openverse,iconify", **env)
    return TestClient(create_app(settings, start_worker=False))


def mock_sources(m):
    m.get(url__startswith="https://api.openverse.org/v1/images/").respond(json=R.OPENVERSE_IMAGES)
    m.get(url__startswith="https://api.openverse.org/v1/audio/").respond(json=R.OPENVERSE_AUDIO)
    m.get(url__startswith="https://api.iconify.design/search").respond(json=R.ICONIFY)


def test_search_live_then_local(tmp_path):
    with client(tmp_path) as c, respx.mock(assert_all_called=False) as m:
        mock_sources(m)
        r = c.get("/api/search", params={"q": "hujan neon"}).json()
        assert r["query"]["text"] == "rain neon" and r["query"]["translated"]
        assert r["live"]["sources"]["openverse"].startswith("ok")
        ids = [i["id"] for i in r["items"]]
        assert "openverse:4bc43a04-ef46-4544-a0c1-63c63f56e276" in ids and "iconify:mdi:weather-rainy" in ids
        # second time: answered from the bank, no source calls
        before = len(m.calls)
        r2 = c.get("/api/search", params={"q": "neon hujan"}).json()
        assert len(m.calls) == before and r2["live"]["sources"]["openverse"] == "cached"
        offline = c.get("/api/search", params={"q": "rain", "live": 0}).json()
        assert offline["live"] is None and offline["total"] >= 2
        icons_only = c.get("/api/search", params={"q": "rain", "kinds": "icon", "live": 0}).json()
        assert {i["kind"] for i in icons_only["items"]} == {"icon"}
        usable = c.get("/api/search", params={"q": "neon", "usage": "free", "live": 0}).json()
        assert all(i["usage"] in ("free", "own") for i in usable["items"])


def test_asset_detail_board_save_and_export(tmp_path):
    with client(tmp_path) as c, respx.mock(assert_all_called=False) as m:
        # specific routes first: respx uses the first matching route
        m.get(url__regex=r"https://api\.openverse\.org/v1/images/4bc43a04.*/thumb/").respond(
            content=png_bytes(), headers={"content-type": "image/png"})
        mock_sources(m)
        m.get("https://live.staticflickr.com/1/1_o.jpg").respond(content=png_bytes((10, 200, 90), (120, 90)),
                                                                 headers={"content-type": "image/jpeg"})
        c.get("/api/search", params={"q": "neon"})
        aid = "openverse:4bc43a04-ef46-4544-a0c1-63c63f56e276"
        detail = c.get(f"/api/assets/{aid}").json()
        assert detail["usage"] == "credit" and detail["attribution"] and detail["boards"] == []
        thumb = c.get(f"/api/thumb/{aid}")
        assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
        saved = c.post("/api/save", json={"asset_id": aid, "board": "Neon refs"}).json()
        board_id = saved["board_id"]
        jobs = c.get("/api/jobs").json()
        assert {j["type"] for j in jobs} == {"download", "expand"}
        dl = c.post(f"/api/assets/{aid}/download", params={"wait": 1}).json()
        assert dl["asset"]["stored"] and dl["asset"]["file_url"]
        f = c.get(f"/api/assets/{aid}/file")
        assert f.status_code == 200 and len(f.content) > 100
        board = c.get(f"/api/boards/{board_id}").json()
        assert board["name"] == "Neon refs" and [i["id"] for i in board["items"]] == [aid]
        z = c.get(f"/api/boards/{board_id}/export")
        assert z.status_code == 200
        names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
        assert "CREDITS.txt" in names and any(n.startswith("files/") for n in names)
        related = c.get(f"/api/assets/{aid}/related", params={"live": 0}).json()
        assert aid not in [i["id"] for i in related["items"]]
        assert c.post(f"/api/assets/{aid}/hide").json()["ok"]
        assert aid not in [i["id"] for i in c.get("/api/search", params={"q": "neon", "live": 0}).json()["items"]]


def test_ingest_page_and_upload(tmp_path):
    page = b"""<html><head><title>Cool poster</title>
      <meta property="og:image" content="/img/poster.png"><meta property="og:site_name" content="Behance">
      </head><body>hi</body></html>"""
    with client(tmp_path, NOZE_ALLOW_PRIVATE_FETCH="1") as c, respx.mock(assert_all_called=False) as m:
        m.get("https://design.example/project/1").respond(content=page, headers={"content-type": "text/html"})
        r = c.post("/api/ingest/url", json={"url": "https://design.example/project/1", "board": "Web"}).json()
        assert r["kind"] == "image" and r["usage"] == "reference" and r["title"] == "Cool poster"
        assert r["thumb_remote"] == "https://design.example/img/poster.png" and r["author"] == "Behance"
        up = c.post("/api/ingest/upload", files={"file": ("my_light_leak.png", png_bytes(), "image/png")},
                    data={"tags": "overlay,leak", "board": "Mine"}).json()
        assert up["source"] == "upload" and up["usage"] == "own" and up["stored"]
        assert "overlay" in up["tags"]
        assert c.get(f"/api/thumb/{up['id']}").headers["content-type"] == "image/webp"
        boards = {b["name"]: b["count"] for b in c.get("/api/boards").json()}
        assert boards == {"Web": 1, "Mine": 1}


def test_ssrf_and_csrf_guards(tmp_path):
    with client(tmp_path) as c:
        bad = c.post("/api/ingest/url", json={"url": "http://127.0.0.1:8787/api/stats"})
        assert bad.status_code == 400 and "private" in bad.json()["detail"]
        assert c.post("/api/ingest/url", json={"url": "file:///etc/passwd"}).status_code == 400
        cross = c.post("/api/boards", json={"name": "x"}, headers={"Origin": "https://evil.example"})
        assert cross.status_code == 403
        same = c.post("/api/boards", json={"name": "x"}, headers={"Origin": "http://testserver"})
        assert same.status_code == 200


def test_password_protection(tmp_path):
    with client(tmp_path, NOZE_PASSWORD="s3cret") as c:
        assert c.get("/api/stats").status_code == 401
        good = base64.b64encode(b"me:s3cret").decode()
        assert c.get("/api/stats", headers={"Authorization": f"Basic {good}"}).status_code == 200
        wrong = base64.b64encode(b"me:nope").decode()
        assert c.get("/", headers={"Authorization": f"Basic {wrong}"}).status_code == 401


def test_sources_interests_and_pages(tmp_path):
    with client(tmp_path) as c:
        sources = {s["name"]: s for s in c.get("/api/sources").json()}
        assert sources["openverse"]["enabled"] and not sources["pexels"]["enabled"]
        assert sources["pexels"]["missing_keys"] == ["PEXELS_API_KEY"]
        iid = c.post("/api/interests", json={"query": "liquid chrome", "kinds": ["video"]}).json()["id"]
        assert [i["query"] for i in c.get("/api/interests").json()] == ["liquid chrome"]
        assert c.post("/api/interests/starter").json()["added"] > 30
        c.delete(f"/api/interests/{iid}")
        assert "liquid chrome" not in [i["query"] for i in c.get("/api/interests").json()]
        assert c.get("/").status_code == 200 and "NOZE" in c.get("/").text
        assert c.get("/save").status_code == 200
        assert c.get("/static/app.js").status_code == 200
        assert c.get("/api/vibes", params={"q": "cyberpunk"}).json()["vibes"][0] == "neon city"
        assert c.post("/api/generate", json={"prompt": "neon rain"}).status_code == 400  # no Replicate token
        stats = c.get("/api/stats").json()
        assert stats["embedder"] == "hash-v1" and "thumbs_bytes" in stats


def test_pinterest_saves_are_tagged_and_linked(tmp_path):
    with client(tmp_path, NOZE_ALLOW_PRIVATE_FETCH="1") as c, respx.mock(assert_all_called=False) as m:
        for n in (1, 2):
            m.get(f"https://i.pinimg.com/736x/aa/bb/{n}.jpg").respond(content=png_bytes((40 * n, 20, 200)),
                                                                      headers={"content-type": "image/jpeg"})
        feed = "https://www.pinterest.com/pin/111/"
        ids = []
        for n in (1, 2):
            r = c.post("/api/ingest/url", json={"url": f"https://i.pinimg.com/736x/aa/bb/{n}.jpg",
                                                "page_url": f"https://www.pinterest.com/pin/{n}00/", "title": f"neon {n}",
                                                "board": "From Pinterest", "context": feed}).json()
            assert r["source"] == "pinterest" and r["usage"] == "reference" and r["stored"]
            ids.append(r["id"])
        related = c.get(f"/api/assets/{ids[1]}/related", params={"live": 0}).json()
        assert ids[0] in [i["id"] for i in related["items"]]  # saved from the same Pinterest feed → related
