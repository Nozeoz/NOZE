"""The bank itself: storage, ranking, related, feed, boards, export, imports."""

import asyncio
import json
import zipfile

import respx

from noze.enrich import Enricher
from noze.exporter import export_board
from noze.harvest import Harvester, group_edges
from noze.http import Http
from noze.importers.folder import import_folder
from noze.lexicon import parse_query
from noze.models import Asset, Kind, Usage
from noze.search import Ranker, SearchRequest
from tests.conftest import png_bytes


def asset(i, title, tags, kind=Kind.IMAGE, usage=Usage.FREE, source="testsrc", **kw):
    return Asset(source=source, source_id=str(i), kind=kind, title=title, tags=tags, usage=usage,
                 license="cc0" if usage == Usage.FREE else "reference", page_url=f"https://example.com/{i}", **kw)


def seed(ctx):
    items = [
        asset(1, "Neon rain street", ["neon", "rain", "night", "city"]),
        asset(2, "Pink neon sign", ["neon", "sign", "pink"]),
        asset(3, "Sunny beach", ["beach", "summer", "sun"]),
        asset(4, "Rainy window loop", ["rain", "window"], kind=Kind.VIDEO),
        asset(5, "Neon reference poster", ["neon", "poster"], usage=Usage.REFERENCE),
        asset(6, "Whoosh transition", ["whoosh", "transition"], kind=Kind.AUDIO),
    ]
    ids = ctx.db.upsert_assets(items)
    Enricher_embed(ctx)
    return ids


def Enricher_embed(ctx):
    ctx.db.execute("UPDATE assets SET thumb_state = 2")  # no thumbnails in these tests
    e = Enricher(ctx, http=None)
    while e.embed_batch(64):
        pass


def test_upsert_is_idempotent_and_keeps_local_state(ctx):
    seed(ctx)
    ctx.db.update_asset("testsrc:1", blob_key="ab/cd/x.jpg", colors=[["#ff0000", 1.0]])
    ctx.db.upsert_assets([asset(1, "Neon rain street (updated)", ["neon"])])
    a = ctx.db.get_asset("testsrc:1")
    assert a["title"] == "Neon rain street (updated)"
    assert a["blob_key"] == "ab/cd/x.jpg" and a["colors"] == [["#ff0000", 1.0]]
    assert ctx.db.stats()["assets"] == 6


def test_keyword_and_vector_ranking_with_filters(ctx):
    seed(ctx)
    r = Ranker(ctx)
    pq = parse_query("hujan neon")  # → "rain neon"
    f, applied = r.resolve_filters(SearchRequest(q="hujan neon"), pq)
    ids = r.rank_query(pq, f)
    assert ids[0] == "testsrc:1"  # matches both words
    assert "testsrc:3" not in ids[:3]
    f_usable, _ = r.resolve_filters(SearchRequest(q="neon", usages=["usable"]), parse_query("neon"))
    assert "testsrc:5" not in r.rank_query(parse_query("neon"), f_usable)
    pq_video = parse_query("rain video")
    f_video, applied = r.resolve_filters(SearchRequest(q="rain video"), pq_video)
    assert applied["kinds"] == [Kind.VIDEO]
    assert r.rank_query(pq_video, f_video) == ["testsrc:4"]


def test_related_uses_board_cooccurrence_and_graph(ctx):
    seed(ctx)
    board = ctx.db.create_board("Moodboard")
    for aid in ("testsrc:1", "testsrc:3"):
        ctx.db.add_to_board(board, aid)
    ctx.db.add_edges([("testsrc:1", "testsrc:2", "source", 1.0)])
    related = Ranker(ctx).related("testsrc:1")
    assert "testsrc:1" not in related
    assert {"testsrc:2", "testsrc:3"} <= set(related[:4])
    assert "testsrc:6" not in related  # audio isn't "more like" a photo


def test_feed_prefers_what_you_saved(ctx):
    seed(ctx)
    for _ in range(3):
        ctx.db.log_interaction("testsrc:2", "save", 3.0)
    feed = Ranker(ctx).feed(Ranker(ctx).resolve_filters(SearchRequest(), parse_query(""))[0], seed=1)
    assert feed.index("testsrc:1") < feed.index("testsrc:3")  # neon stuff beats the beach


def test_group_edges_link_co_curated_items():
    a = [Asset("arena", str(i), Kind.IMAGE, extra={"group": "arena:x", "group_size": 30}) for i in range(4)]
    edges = group_edges(a, [x.id for x in a], fanout=2)
    assert ("arena:0", "arena:1", "group", edges[0][3]) in edges and len(edges) == 5


def test_harvest_caches_and_records_hits(ctx):
    ov = {"page_count": 1, "results": [{"id": "x1", "title": "Neon", "url": "https://i/1.jpg", "license": "cc0",
                                        "license_version": "1.0", "tags": [], "mature": False, "thumbnail": "https://t/1"}]}

    async def go():
        http = Http(ctx.settings)
        h = Harvester(ctx, http)
        try:
            first = await h.search(parse_query("neon"), only={"openverse"}, kinds={Kind.IMAGE})
            second = await h.search(parse_query("neon"), only={"openverse"}, kinds={Kind.IMAGE})
            return first, second
        finally:
            await http.aclose()

    with respx.mock() as m:
        route = m.get(url__startswith="https://api.openverse.org/v1/images/").respond(json=ov)
        first, second = asyncio.run(go())
    assert first.sources["openverse"].startswith("ok") and second.sources["openverse"] == "cached"
    assert route.call_count == 1
    assert ctx.db.query_hits("neon")[0][0] == "openverse:x1"


def test_thumbnail_enrichment_and_color_search(ctx):
    ctx.db.upsert_assets([asset(10, "Red thing", ["thing"], thumb_url="https://img.test/red.png"),
                          asset(11, "Blue thing", ["thing"], thumb_url="https://img.test/blue.png")])

    async def go():
        http = Http(ctx.settings)
        try:
            return await Enricher(ctx, http).thumbs_batch()
        finally:
            await http.aclose()

    with respx.mock() as m:
        m.get("https://img.test/red.png").respond(content=png_bytes((220, 30, 30)), headers={"content-type": "image/png"})
        m.get("https://img.test/blue.png").respond(content=png_bytes((30, 60, 220)), headers={"content-type": "image/png"})
        assert asyncio.run(go()) == 2
    red = ctx.db.get_asset("testsrc:10")
    assert red["thumb_path"] and red["colors"] and red["dhash"]
    assert (ctx.settings.thumbs_dir / red["thumb_path"]).exists()
    r = Ranker(ctx)
    f, _ = r.resolve_filters(SearchRequest(q="thing"), parse_query("thing"))
    assert r.rank_query(parse_query("thing"), f, color="#1e63d6")[0] == "testsrc:11"
    assert r.rank_query(parse_query("thing"), f, color="#e53935")[0] == "testsrc:10"


def test_folder_import_and_board_export(ctx, tmp_path):
    root = tmp_path / "Assets"
    (root / "Overlays" / "Light Leaks").mkdir(parents=True)
    (root / "Overlays" / "Light Leaks" / "leak_warm_01.png").write_bytes(png_bytes((250, 160, 60)))
    (root / "fonts").mkdir()
    (root / "fonts" / "readme.txt").write_text("not an asset")
    (root / "anim.json").write_text(json.dumps({"v": "5.7.4", "fr": 30, "layers": []}))
    res = import_folder(ctx, root, board="Old packs")
    assert res["imported"] == 2 and res["skipped"] == 1
    board = ctx.db.board_by_name("Old packs")
    ids = ctx.db.board_item_ids(board["id"])
    rows = ctx.db.get_assets(ids)
    leak = next(a for a in rows.values() if a["kind"] == Kind.IMAGE)
    assert {"overlays", "light leaks", "leak", "warm"} <= set(leak["tags"]) and leak["usage"] == Usage.OWN
    assert any(a["kind"] == Kind.MOTION for a in rows.values())
    out = tmp_path / "pack.zip"
    info = export_board(ctx, board["id"], out)
    assert info["items"] == 2 and info["without_file"] == 0
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "CREDITS.txt" in names and "assets.json" in names
        assert sum(n.startswith("files/") for n in names) == 2
        assert "Your own assets" in z.read("CREDITS.txt").decode()


def test_deleted_thumbnails_are_rebuilt(ctx):
    ctx.db.upsert_assets([asset(20, "Thing", ["thing"], thumb_url="https://img.test/t.png")])
    ctx.thumb_file("testsrc:20").parent.mkdir(parents=True, exist_ok=True)
    ctx.thumb_file("testsrc:20").write_bytes(b"x")
    rel = str(ctx.thumb_file("testsrc:20").relative_to(ctx.settings.thumbs_dir))
    ctx.db.update_asset("testsrc:20", thumb_path=rel, thumb_state=1)
    assert ctx.db.reset_missing_thumbs(ctx.settings.thumbs_dir) == 0
    ctx.thumb_file("testsrc:20").unlink()
    assert ctx.db.reset_missing_thumbs(ctx.settings.thumbs_dir) == 1
    a = ctx.db.get_asset("testsrc:20")
    assert a["thumb_state"] == 0 and a["thumb_path"] is None
