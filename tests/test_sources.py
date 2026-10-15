"""Every connector against a recorded-shape response (no network)."""

import asyncio
import json

import httpx
import respx

from noze.http import Http
from noze.models import Kind, Usage
from noze.sources import build_sources
from tests.conftest import make_settings
from tests.fixtures import responses as R


def run(coro):
    return asyncio.run(coro)


async def _with_source(tmp_path, name, fn, **env):
    settings = make_settings(tmp_path, **env)
    http = Http(settings)
    try:
        src = build_sources(settings, http)[name]
        return await fn(src)
    finally:
        await http.aclose()


def search(tmp_path, name, query="neon", kinds=(), page=1, cursor=None, **env):
    res = run(_with_source(tmp_path, name, lambda s: s.search(query, set(kinds), page, 30, cursor), **env))
    for a in res.assets:
        a.clean()  # what the harvester does before storing
    return res


def by_id(result):
    return {a.source_id: a.clean() for a in result.assets}


@respx.mock
def test_openverse(tmp_path):
    img = respx.get(url__startswith="https://api.openverse.org/v1/images/").respond(json=R.OPENVERSE_IMAGES)
    respx.get(url__startswith="https://api.openverse.org/v1/audio/").respond(json=R.OPENVERSE_AUDIO)
    res = search(tmp_path, "openverse")
    assets = by_id(res)
    assert set(assets) == {"4bc43a04-ef46-4544-a0c1-63c63f56e276", "aud-1"}  # mature result dropped
    a = assets["4bc43a04-ef46-4544-a0c1-63c63f56e276"]
    assert a.kind == Kind.IMAGE and a.usage == Usage.CREDIT and a.license == "cc-by-sa-2.0"
    assert a.tags[:2] == ["neon", "rain"] and a.width == 800 and a.height == 1200
    assert a.attribution.startswith('"Neon rain street" by Ana')
    audio = assets["aud-1"]
    assert audio.kind == Kind.AUDIO and audio.duration == 1.25 and audio.usage == Usage.FREE
    assert not res.exhausted
    assert img.calls[0].request.url.params["mature"] == "false"


@respx.mock
def test_openverse_related(tmp_path):
    respx.get(url__regex=r".*/images/abc/related/").respond(json=R.OPENVERSE_IMAGES)
    out = run(_with_source(tmp_path, "openverse", lambda s: s.related({"kind": "image", "source_id": "abc"})))
    assert [a.source_id for a in out] == ["4bc43a04-ef46-4544-a0c1-63c63f56e276"]


@respx.mock
def test_wikimedia(tmp_path):
    route = respx.get(url__startswith="https://commons.wikimedia.org/w/api.php").respond(json=R.WIKIMEDIA)
    res = search(tmp_path, "wikimedia")
    ids = [a.source_id for a in res.assets]
    assert ids == ["111", "222"]  # sorted by search index, PDF skipped
    video, photo = res.assets
    assert video.kind == Kind.VIDEO and video.usage == Usage.FREE
    assert photo.author == "Kei" and photo.description == "Neon signs in Shinjuku"
    assert photo.usage == Usage.CREDIT and "neon signs" in photo.tags
    assert "/1280px-" in photo.preview_url  # big originals get a standard-size preview
    assert not res.exhausted
    assert route.calls[0].request.headers["user-agent"].startswith("NOZE/")


@respx.mock
def test_polyhaven_search_and_download(tmp_path):
    respx.get("https://api.polyhaven.com/assets").respond(json=R.POLYHAVEN_ASSETS)
    respx.get("https://api.polyhaven.com/files/studio_small_08").respond(json=R.POLYHAVEN_FILES_HDRI)
    respx.get("https://api.polyhaven.com/files/rusty_metal").respond(json=R.POLYHAVEN_FILES_TEXTURE)

    async def go(src):
        res = await src.search("studio", {Kind.HDRI}, 1, 30)
        rust = await src.search("rust", set(), 1, 30)
        hdri_parts = await src.resolve_download({"kind": Kind.HDRI, "source_id": "studio_small_08"})
        tex_parts = await src.resolve_download({"kind": Kind.TEXTURE, "source_id": "rusty_metal"})
        return res, rust, hdri_parts, tex_parts

    res, rust, hdri_parts, tex_parts = run(_with_source(tmp_path, "polyhaven", go))
    assert [a.source_id for a in res.assets] == ["studio_small_08"]
    a = res.assets[0]
    assert a.kind == Kind.HDRI and a.usage == Usage.FREE and a.author == "Sergej Majboroda"
    assert [x.source_id for x in rust.assets] == ["rusty_metal"]
    assert hdri_parts[0].url.endswith("studio_small_08_2k.hdr")
    assert {p.name for p in tex_parts} == {"rusty_metal_diff_2k.jpg", "rusty_metal_nor_gl_2k.jpg"}


@respx.mock
def test_ambientcg(tmp_path):
    respx.get(url__startswith="https://ambientcg.com/api/v2/full_json").respond(json=R.AMBIENTCG)
    res = search(tmp_path, "ambientcg", "metal")
    a = res.assets[0]
    assert a.kind == Kind.TEXTURE and a.usage == Usage.FREE
    assert a.download_url.endswith("Metal012_2K-JPG.zip")
    assert "256-PNG" in a.thumb_url and "1024-PNG" in a.preview_url


@respx.mock
def test_nasa_search_and_manifest(tmp_path):
    respx.get(url__startswith="https://images-api.nasa.gov/search").respond(json=R.NASA)
    respx.get(url__regex=r"https://images-assets\.nasa\.gov/video/Launch.*collection\.json").respond(json=R.NASA_MANIFEST)

    async def go(src):
        res = await src.search("nebula", set(), 1, 30)
        video = next(a for a in res.assets if a.kind == Kind.VIDEO)
        parts = await src.resolve_download({"kind": Kind.VIDEO, "extra": video.extra, "download_url": ""})
        return res, video, parts

    res, video, parts = run(_with_source(tmp_path, "nasa", go))
    image = next(a for a in res.assets if a.kind == Kind.IMAGE)
    assert image.preview_url.endswith("PIA12235~medium.jpg") and image.download_url.endswith("~orig.jpg")
    assert image.usage == Usage.FREE and image.description == "A supernova remnant."
    assert "Launch%20Clip~mobile.mp4" in video.preview_url
    assert parts[0].url == "https://images-assets.nasa.gov/video/Launch Clip/Launch Clip~medium.mp4"
    assert not res.exhausted


@respx.mock
def test_met(tmp_path):
    met_search = respx.get(url__startswith="https://collectionapi.metmuseum.org/public/collection/v1.1/search").respond(json=R.MET_SEARCH)
    respx.get("https://collectionapi.metmuseum.org/public/collection/v1/objects/436535").respond(json=R.MET_OBJECT)
    respx.get("https://collectionapi.metmuseum.org/public/collection/v1/objects/999").respond(json=R.MET_OBJECT_PRIVATE)
    respx.get("https://collectionapi.metmuseum.org/public/collection/v1/objects/1000").respond(status_code=404)
    res = search(tmp_path, "met", "cypress")
    assert [a.source_id for a in res.assets] == ["436535"]
    assert met_search.calls[0].request.url.params["offset"] == "0" and res.exhausted
    assert res.assets[0].author == "Vincent van Gogh" and res.assets[0].usage == Usage.FREE


@respx.mock
def test_artic(tmp_path):
    route = respx.get(url__startswith="https://api.artic.edu/api/v1/artworks/search").respond(json=R.ARTIC)
    res = search(tmp_path, "artic", "park")
    assert len(res.assets) == 1
    a = res.assets[0]
    assert a.thumb_url == "https://www.artic.edu/iiif/2/1adf2696-8489-499b-cad2-821d7fde4b33/full/400,/0/default.jpg"
    assert a.colors and a.colors[0][0].startswith("#") and a.width == 3000
    assert "AIC-User-Agent" in route.calls[0].request.headers or "aic-user-agent" in route.calls[0].request.headers


@respx.mock
def test_cleveland_smithsonian_europeana(tmp_path):
    respx.get(url__startswith="https://openaccess-api.clevelandart.org/api/artworks/").respond(json=R.CLEVELAND)
    si = respx.get(url__startswith="https://api.si.edu/openaccess/api/v1.0/search").respond(json=R.SMITHSONIAN)
    eu = respx.get(url__startswith="https://api.europeana.eu/record/v2/search.json").respond(json=R.EUROPEANA)
    cl = search(tmp_path, "cleveland", "sunset").assets[0]
    assert cl.usage == Usage.FREE and cl.download_url.endswith("_print.jpg") and cl.author.startswith("Frederic Edwin Church")
    sm = search(tmp_path, "smithsonian", "neon").assets[0]
    assert sm.title == "Neon sign poster" and sm.usage == Usage.FREE and "max=1200" in sm.preview_url
    assert si.calls[0].request.url.params["api_key"] == "DEMO_KEY"
    ev = search(tmp_path, "europeana", "vermeer").assets[0]
    assert ev.usage == Usage.FREE and ev.page_url == "https://www.europeana.eu/item/2021672/resource_document_mauritshuis_670"
    assert eu.calls[0].request.url.params["reusability"] == "open"


@respx.mock
def test_internet_archive(tmp_path):
    respx.get(url__startswith="https://archive.org/advancedsearch.php").respond(json=R.ARCHIVE)
    respx.get("https://archive.org/metadata/Neon_Signs_1955").respond(json=R.ARCHIVE_METADATA)

    async def go(src):
        res = await src.search("neon", set(), 1, 30)
        film = next(a for a in res.assets if a.source_id == "Neon_Signs_1955")
        fields = await src.hydrate({"source_id": film.source_id, "kind": film.kind})
        return res, film, fields

    res, film, fields = run(_with_source(tmp_path, "archive", go))
    assert film.kind == Kind.VIDEO and film.usage == Usage.FREE and "neon" in film.tags
    tape = next(a for a in res.assets if a.source_id == "mystery_tape")
    assert tape.usage == Usage.CHECK and tape.kind == Kind.AUDIO
    assert fields["preview_url"].endswith("Neon_Signs_1955.mp4")  # h.264 preferred


@respx.mock
def test_iconify(tmp_path):
    respx.get(url__startswith="https://api.iconify.design/search").respond(json=R.ICONIFY)
    res = search(tmp_path, "iconify", "rain")
    a, b = res.assets
    assert a.source_id == "mdi:weather-rainy" and a.kind == Kind.ICON
    assert a.thumb_url == "https://api.iconify.design/mdi/weather-rainy.svg"
    assert a.license == "apache-2.0" and b.license == "mit" and a.usage == Usage.FREE


@respx.mock
def test_fontsource_vibe_search(tmp_path):
    respx.get("https://api.fontsource.org/v1/fonts").respond(json=R.FONTSOURCE)

    async def go(src):
        return (await src.search("cyberpunk code", {Kind.FONT}, 1, 30), await src.search("abril", set(), 1, 30),
                await src.resolve_download({"source_id": "space-mono", "extra": {"weights": [400, 700], "styles": ["normal"], "subset": "latin"}}),
                await src.search("neon city night", set(), 1, 30))

    vibe, name, parts, mixed = run(_with_source(tmp_path, "fontsource", go))
    assert mixed.assets == []  # an "All" search doesn't get flooded with loosely matching fonts
    assert vibe.assets[0].source_id == "space-mono"  # "code" → monospace
    assert name.assets[0].source_id == "abril-fatface"
    assert vibe.assets[0].preview_url == "https://cdn.jsdelivr.net/fontsource/fonts/space-mono@latest/latin-400-normal.woff2"
    assert [p.name for p in parts] == ["space-mono-400-normal.ttf", "space-mono-700-normal.ttf"]
    assert vibe.assets[0].usage == Usage.FREE


@respx.mock
def test_github(tmp_path):
    route = respx.get(url__startswith="https://api.github.com/search/repositories").respond(json=R.GITHUB)
    res = search(tmp_path, "github", "lottie", GITHUB_TOKEN="ghp_x")
    lottie, shaders = res.assets
    assert lottie.usage == Usage.FREE and lottie.popularity == 30000 and lottie.thumb_url.endswith("/airbnb/lottie-web")
    assert shaders.usage == Usage.REFERENCE  # no license = all rights reserved
    assert route.calls[0].request.headers["authorization"] == "Bearer ghp_x"


@respx.mock
def test_arena_search_and_related_graph(tmp_path):
    respx.get(url__startswith="https://api.are.na/v2/search").respond(json=R.ARENA_SEARCH)
    respx.get(url__startswith="https://api.are.na/v2/channels/nu-brutalism/contents").respond(json=R.ARENA_CHANNEL)
    respx.get(url__startswith="https://api.are.na/v2/blocks/1001/channels").respond(json=R.ARENA_CHANNELS)
    small = respx.get(url__startswith="https://api.are.na/v2/channels/concrete-dreams/contents").respond(json=R.ARENA_CONTENTS)
    respx.get(url__startswith="https://api.are.na/v2/channels/big-catch-all/contents").respond(json={"contents": []})

    async def go(src):
        return await src.search("brutalism", set(), 1, 30), await src.related({"source_id": "1001", "kind": "image"})

    res, related = run(_with_source(tmp_path, "arena", go))
    assert [a.source_id for a in res.assets] == ["1001", "1003"]  # text block skipped
    assert res.assets[0].usage == Usage.REFERENCE and res.assets[1].kind == Kind.GIF
    assert res.assets[0].extra["group"] == "arena:nu-brutalism" and "Nu-Brutalism" in res.assets[0].tags
    assert res.assets[0].extra["source_url"] == "https://example.com/poster"
    assert [a.source_id for a in related] == ["2001"]  # itself excluded
    assert small.called and related[0].extra["edge_weight"] > 0


@respx.mock
def test_lottiefiles_with_schema_fallback(tmp_path):
    route = respx.post("https://graphql.lottiefiles.com/2022-08").mock(side_effect=[
        httpx.Response(200, json=R.LOTTIE_ERROR), httpx.Response(200, json=R.LOTTIE)])
    res = search(tmp_path, "lottiefiles", "loading")
    a = res.assets[0]
    assert a.kind == Kind.MOTION and a.usage == Usage.FREE and a.preview_url.endswith(".json")
    assert a.extra["video"].endswith(".mp4") and res.cursor == "c1" and not res.exhausted
    assert "likesCount" not in json.loads(route.calls[1].request.content)["query"]


@respx.mock
def test_civitai_filters_nsfw_and_matches_prompt(tmp_path):
    route = respx.get(url__startswith="https://civitai.com/api/v1/images").respond(json=R.CIVITAI)
    res = search(tmp_path, "civitai", "neon rain")
    assert [a.source_id for a in res.assets] == ["101"]
    a = res.assets[0]
    assert a.usage == Usage.CHECK and "original=true" not in a.thumb_url and a.extra["prompt"].startswith("cinematic neon")
    assert route.calls[0].request.url.params["nsfw"] == "None"


@respx.mock
def test_pexels_photos_and_videos(tmp_path):
    photos = respx.get(url__startswith="https://api.pexels.com/v1/search").respond(json=R.PEXELS_PHOTOS)
    respx.get(url__startswith="https://api.pexels.com/videos/search").respond(json=R.PEXELS_VIDEOS)
    res = search(tmp_path, "pexels", PEXELS_API_KEY="k", NOZE_VIDEO_MAX_WIDTH="1920")
    photo = next(a for a in res.assets if a.kind == Kind.IMAGE)
    video = next(a for a in res.assets if a.kind == Kind.VIDEO)
    assert photo.usage == Usage.FREE and photo.colors == [["#978E82", 0.5]] and photo.title == "Neon lights in the rain"
    assert video.preview_url.endswith("sd.mp4") and video.download_url.endswith("hd.mp4")  # capped at 1920px
    assert video.title == "rain on window at night" and video.duration == 12
    assert photos.calls[0].request.headers["authorization"] == "k"


def test_keyed_sources_are_disabled_without_keys(tmp_path):
    async def go(_):
        return None

    settings = make_settings(tmp_path)
    srcs = build_sources(settings, Http(settings))
    assert not srcs["pexels"].enabled and srcs["pexels"].missing_keys() == ["PEXELS_API_KEY"]
    assert srcs["openverse"].enabled


@respx.mock
def test_pixabay(tmp_path):
    imgs = respx.get(url__regex=r"https://pixabay\.com/api/\?.*").respond(json=R.PIXABAY_IMAGES)
    respx.get(url__startswith="https://pixabay.com/api/videos/").respond(json=R.PIXABAY_VIDEOS)
    res = search(tmp_path, "pixabay", PIXABAY_API_KEY="k")
    image = next(a for a in res.assets if a.kind == Kind.IMAGE)
    video = next(a for a in res.assets if a.kind == Kind.VIDEO)
    assert image.tags[:3] == ["neon", "light", "sign"] and image.usage == Usage.FREE
    assert video.preview_url.endswith("125_tiny.mp4") and video.download_url.endswith("125_large.mp4")
    assert video.thumb_url.endswith("125_medium.jpg") and "animation" in video.tags
    assert imgs.calls[0].request.url.params["safesearch"] == "true"


@respx.mock
def test_unsplash_and_download_ping(tmp_path):
    respx.get(url__startswith="https://api.unsplash.com/search/photos").respond(json=R.UNSPLASH)
    ping = respx.get(url__startswith="https://api.unsplash.com/photos/eOLpJytrbsQ/download").respond(json={"url": "x"})

    async def go(src):
        res = await src.search("coffee", set(), 1, 30)
        a = res.assets[0]
        await src.on_download({"extra": a.extra})
        return res

    res = run(_with_source(tmp_path, "unsplash", go, UNSPLASH_ACCESS_KEY="k"))
    a = res.assets[0]
    assert a.usage == Usage.FREE and "utm_source=noze" in a.page_url and a.tags == ["coffee"]
    assert a.attribution.startswith("Photo by James on Unsplash")
    assert ping.called and ping.calls[0].request.headers["authorization"] == "Client-ID k"


@respx.mock
def test_freesound_and_giphy(tmp_path):
    respx.get(url__startswith="https://freesound.org/apiv2/search/text/").respond(json=R.FREESOUND)
    respx.get(url__startswith="https://api.giphy.com/v1/gifs/search").respond(json=R.GIPHY)
    respx.get(url__startswith="https://api.giphy.com/v1/stickers/search").respond(json={"data": [], "pagination": {"total_count": 0}})
    sound = search(tmp_path, "freesound", "whoosh", FREESOUND_API_KEY="k").assets[0]
    assert sound.kind == Kind.AUDIO and sound.usage == Usage.FREE and sound.preview_url.endswith("_hq.mp3")
    gif = search(tmp_path, "giphy", "neon", GIPHY_API_KEY="k").assets[0]
    assert gif.kind == Kind.GIF and gif.usage == Usage.REFERENCE and gif.width == 480
    assert gif.preview_url.endswith("200w.mp4")


@respx.mock
def test_reddit(tmp_path):
    respx.post("https://www.reddit.com/api/v1/access_token").respond(json=R.REDDIT_TOKEN)
    route = respx.get(url__startswith="https://oauth.reddit.com/r/").respond(json=R.REDDIT_SEARCH)
    res = search(tmp_path, "reddit", "liquid chrome", REDDIT_CLIENT_ID="id", REDDIT_CLIENT_SECRET="secret")
    ids = [a.source_id for a in res.assets]
    assert ids == ["abc123", "img1"]  # NSFW dropped
    video, image = res.assets
    assert video.kind == Kind.VIDEO and video.preview_url.endswith("DASH_720.mp4") and video.usage == Usage.REFERENCE
    assert image.kind == Kind.IMAGE and image.thumb_url.endswith("poster-320.png")
    assert res.cursor == "t3_next"
    assert route.calls[0].request.headers["authorization"] == "Bearer tok"


@respx.mock
def test_wallhaven(tmp_path):
    route = respx.get(url__startswith="https://wallhaven.cc/api/v1/search").respond(json=R.WALLHAVEN)
    res = search(tmp_path, "wallhaven", "neon city")
    assert [a.source_id for a in res.assets] == ["rdj2q7"]  # non-SFW dropped
    a = res.assets[0]
    assert a.usage == Usage.REFERENCE and a.width == 1920 and a.colors[0][0] == "#663399"
    assert {"neon", "city", "wallpaper"} <= set(a.tags) and not res.exhausted
    assert route.calls[0].request.url.params["purity"] == "100"


@respx.mock
def test_tumblr_npf_images_and_reblogged_video(tmp_path):
    route = respx.get(url__startswith="https://api.tumblr.com/v2/tagged").respond(json=R.TUMBLR)
    res = search(tmp_path, "tumblr", "vaporwave", TUMBLR_API_KEY="k")
    img = next(a for a in res.assets if a.kind == Kind.IMAGE)
    vid = next(a for a in res.assets if a.kind == Kind.VIDEO)
    assert img.title == "pink sunset grid" and img.preview_url.endswith("s1280x1920/x.jpg") and img.thumb_url.endswith("s500x750/x.jpg")
    assert img.usage == Usage.REFERENCE and img.author == "vaporwavedreams" and "aesthetic" in img.tags
    assert vid.preview_url.endswith(".mp4") and vid.thumb_url.endswith("p.jpg")
    assert res.cursor == "1759990000"
    assert route.calls[0].request.url.params["npf"] == "true"


@respx.mock
def test_flickr_licenses_per_photo(tmp_path):
    respx.get(url__startswith="https://api.flickr.com/services/rest/").respond(json=R.FLICKR)
    res = search(tmp_path, "flickr", "neon", FLICKR_API_KEY="k")
    cc, arr = res.assets
    assert cc.usage == Usage.CREDIT and cc.license == "cc-by-2.0" and cc.download_url.endswith("o.jpg")
    assert cc.description == "rain night" and cc.page_url == "https://www.flickr.com/photos/12@N01/531"
    assert arr.usage == Usage.REFERENCE and not arr.download_url.endswith("o2.jpg")


@respx.mock
def test_deviantart(tmp_path):
    respx.post("https://www.deviantart.com/oauth2/token").respond(json=R.DEVIANTART_TOKEN)
    route = respx.get(url__startswith="https://www.deviantart.com/api/v1/oauth2/browse/home").respond(json=R.DEVIANTART_HOME)
    res = search(tmp_path, "deviantart", "neon city", DEVIANTART_CLIENT_ID="i", DEVIANTART_CLIENT_SECRET="s")
    assert [a.source_id for a in res.assets] == ["ABC-1"]  # mature dropped
    a = res.assets[0]
    assert a.thumb_url.endswith("300.jpg") and a.download_url.endswith("full.jpg") and a.usage == Usage.REFERENCE
    assert route.calls[0].request.headers["authorization"] == "Bearer da-tok"
    assert route.calls[0].request.url.params["q"] == "neon city"


@respx.mock
def test_vimeo_and_youtube_are_embed_only(tmp_path):
    respx.get(url__startswith="https://api.vimeo.com/videos").respond(json=R.VIMEO)
    respx.get(url__startswith="https://www.googleapis.com/youtube/v3/search").respond(json=R.YOUTUBE)
    reel, cc = search(tmp_path, "vimeo", "liquid chrome", VIMEO_ACCESS_TOKEN="t").assets
    assert reel.extra["embed"] == "https://player.vimeo.com/video/1084537" and reel.download_url == ""
    assert reel.thumb_url.endswith("1_640.jpg") and reel.usage == Usage.REFERENCE and cc.usage == Usage.CREDIT
    yt = search(tmp_path, "youtube", "kinetic typography", YOUTUBE_API_KEY="k")
    v = yt.assets[0]
    assert v.title == "Kinetic typography breakdown & tips" and v.extra["embed"].endswith("/embed/dQw4w9WgXcQ")
    assert yt.cursor == "CBkQAA" and v.download_url == ""
