from noze.lexicon import normalize_key, parse_query
from noze.licenses import normalize_license
from noze.models import Asset, Kind, Usage, expand_kinds, expand_usages


def test_indonesian_query_is_translated_and_intents_extracted():
    pq = parse_query("hujan malam kota neon video gratis")
    assert pq.text == "rain night city neon"
    assert pq.kinds == {Kind.VIDEO}
    assert pq.usage == "usable"
    assert pq.translated
    # original Indonesian words are still searchable locally
    assert "hujan" in pq.terms


def test_ambiguous_words_stay_english():
    assert parse_query("hot air balloon").text == "hot air balloon"
    assert parse_query("strawberry jam").text == "strawberry jam"
    assert parse_query("air terjun sinematik").text == "waterfall cinematic"


def test_content_words_do_not_force_a_kind_filter():
    assert parse_query("paper texture").kinds == set()
    assert parse_query("mesh gradient").kinds == set()
    assert parse_query("font retro").kinds == {Kind.FONT}


def test_colors_and_vibes():
    pq = parse_query("merah muda aesthetic")
    assert pq.text == "pink aesthetic"
    assert pq.colors == ["#f06ba8"]
    assert "chrome" in parse_query("y2k").vibes
    assert parse_query("cyberpunk").vibes[0] == "neon city"


def test_query_that_is_only_a_kind_word_still_searches():
    pq = parse_query("sfx")
    assert pq.kinds == {Kind.AUDIO}
    assert pq.text == "sfx"


def test_normalize_key_is_order_insensitive():
    assert normalize_key("Neon rain") == normalize_key("rain neon")


def test_license_normalization():
    cases = {
        ("by-sa 2.0", None): ("cc-by-sa-2.0", Usage.CREDIT),
        ("cc0 1.0", None): ("cc0", Usage.FREE),
        (None, "https://creativecommons.org/licenses/by-nc/4.0/"): ("cc-by-nc-4.0", Usage.NONCOMMERCIAL),
        (None, "http://creativecommons.org/publicdomain/mark/1.0/"): ("pdm", Usage.FREE),
        (None, "http://rightsstatements.org/vocab/InC/1.0/"): ("in-copyright", Usage.REFERENCE),
        ("MIT", None): ("mit", Usage.FREE),
        ("GPL-3.0", None): ("gpl", Usage.CREDIT),
        ("NOASSERTION", None): ("unknown", Usage.CHECK),
        ("", ""): ("unknown", Usage.CHECK),
        ("pexels", None): ("pexels", Usage.FREE),
    }
    for (raw, url), (code, usage) in cases.items():
        info = normalize_license(raw, url)
        assert (info.code, info.usage) == (code, usage), (raw, url, info)


def test_kind_and_usage_expansion():
    assert expand_kinds(["moving"]) == {Kind.VIDEO, Kind.GIF, Kind.MOTION}
    assert expand_kinds(["motion"]) == {Kind.MOTION}
    assert expand_kinds(["3d"]) == {Kind.MODEL3D}
    assert expand_usages(["usable"]) == {Usage.FREE, Usage.CREDIT, Usage.OWN}


def test_asset_clean_rejects_dangerous_urls():
    a = Asset("x", "1", Kind.IMAGE, page_url="javascript:alert(1)", thumb_url="//cdn.example/a.jpg",
              preview_url="data:text/html,hi", tags=["  Neon ", "neon", "#Rain"]).clean()
    assert a.page_url == ""
    assert a.thumb_url == "https://cdn.example/a.jpg"
    assert a.preview_url == ""
    assert a.tags == ["neon", "rain"]
