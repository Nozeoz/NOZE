"""Signals (where was it funny / hyped) + fast VOD section fetch. Offline: fake chat, fake YAMNet, synthetic audio."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import wave
from pathlib import Path

import httpx
import numpy as np
import pytest

from noze.agency.media import fetch as F
from noze.agency.media import signals as S
from noze.agency.media.ffmpeg import MediaError, available

FIX = Path(__file__).parent / "fixtures" / "signals"
needs_ffmpeg = pytest.mark.skipif(not available(), reason="ffmpeg not installed")
VOD = "https://www.twitch.tv/videos/999"
_REAL_CHAT = S.twitch_chat  # the autouse fixture swaps S.twitch_chat for a fake


def _wav(path: Path, seconds: int = 60, loud_at: tuple[float, float] | None = None) -> Path:
    """Quiet noise, optionally with a loud burst."""
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.01, 16000 * seconds)
    if loud_at:
        a, b = int(loud_at[0] * 16000), int(loud_at[1] * 16000)
        x[a:b] = rng.normal(0, 0.4, b - a)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


@pytest.fixture
def audio(tmp_path):
    if not available():
        pytest.skip("ffmpeg not installed")
    return _wav(tmp_path / "a.wav")


class _Net:
    """What the fake Twitch backend answers; ``chat`` may be replaced by a callable (to raise, to count)."""
    msgs: list = []
    clips: list = []
    chat = None


@pytest.fixture(autouse=True)
def net(monkeypatch):
    """Nothing here may touch the network or the real model unless a test says so."""
    n = _Net()
    n.msgs, n.clips = [], []
    monkeypatch.setattr(S, "_load_yamnet", lambda d, nw: (None, "no model in tests"))
    monkeypatch.setattr(S, "twitch_chat", lambda *a, **k: n.chat(*a, **k) if n.chat else n.msgs)
    monkeypatch.setattr(S, "twitch_video_meta", lambda *a, **k: {"login": "kai", "title": "", "length_s": 9999})
    monkeypatch.setattr(S, "twitch_clips", lambda *a, **k: n.clips)

    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(S, "yt_info", boom)
    monkeypatch.setattr(S, "yt_live_chat", boom)
    return n


def _chat(baseline_every: float = 4.0, spike_at: float | None = None, off: float = 100.0, dur: int = 60):
    msgs = [(off + t, "hi") for t in np.arange(0, dur, baseline_every)]
    if spike_at is not None:
        msgs += [(off + spike_at + i * 0.1, "KEKW") for i in range(40)]
    return msgs


def _collect(net, audio, tmp_path, name, msgs=None, clips=None, off=100.0, **kw):
    """collect_signals with fake Twitch backends."""
    net.msgs, net.clips = msgs or [], clips or []
    return S.collect_signals(audio, tmp_path / name, url=VOD, offset_s=off, models_dir=tmp_path / "m", **kw)


# -- parsers -------------------------------------------------------------------------------------------------
def test_classify_message():
    assert S.classify_message("KEKW")[0] == {"funny": 1}
    assert "funny" in S.classify_message("lol that was so funny haha")[0]
    assert S.classify_message("LETS GO")[0] == {"hype": 1}
    assert S.classify_message("???")[0] == {"shock": 1}
    assert S.classify_message("F")[0] == {"sad": 1}
    assert S.classify_message("nice weather today")[0] == {}  # no false positives on plain words
    assert S.classify_message("wrong answer")[0] == {}  # "w" inside a word is not a W


def test_parse_yt_chat_drops_non_text_and_bad_rows():
    got = S.parse_yt_chat(FIX / "yt_live_chat.jsonl")
    assert got == [(12.5, "lmao 😂"), (14.25, "W")]  # superchat, junk line, row without offset all dropped


def test_parse_heatmap_and_missing():
    info = json.loads((FIX / "yt_info.json").read_text())
    assert S.parse_heatmap(info) == [(0.0, 10.0, 0.1), (10.0, 20.0, 1.0), (20.0, 30.0, 0.3)]
    assert S.parse_heatmap({"heatmap": None}) == [] and S.parse_heatmap({}) == []


def test_parse_vod_url():
    assert S.parse_vod_url("https://www.twitch.tv/videos/2936683310?t=1h") == ("twitch", "2936683310")
    assert S.parse_vod_url("https://youtu.be/dQw4w9WgXcQ") == ("youtube", "dQw4w9WgXcQ")
    assert S.parse_vod_url("https://www.youtube.com/watch?v=abc123&t=5") == ("youtube", "abc123")
    assert S.parse_vod_url("https://www.twitch.tv/kaicenat") is None and S.parse_vod_url("") is None


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_twitch_chat_pages_by_cursor_and_clips_range():
    p1 = json.loads((FIX / "tw_chat_p1.json").read_text())
    p2 = json.loads((FIX / "tw_chat_p2.json").read_text())
    seen = []

    def handler(req):
        var = json.loads(req.content)[0]["variables"]
        seen.append(var)
        return httpx.Response(200, json=p2 if var.get("cursor") == "c3" else p1)

    got = _REAL_CHAT("999", 100, 105, client=_mock_client(handler), pause=0)
    assert [t for t, _ in got] == [100, 101, 103]  # blank fragment dropped, 112 is beyond the range
    assert got[1][1] == "KEKW that was OMEGALUL"  # fragments joined
    assert seen[0] == {"videoID": "999", "contentOffsetSeconds": 100} and seen[1]["cursor"] == "c3"


def test_twitch_chat_falls_back_to_offset_when_cursor_breaks():
    p1 = json.loads((FIX / "tw_chat_p1.json").read_text())
    p2 = json.loads((FIX / "tw_chat_p2.json").read_text())
    calls = []

    def handler(req):
        var = json.loads(req.content)[0]["variables"]
        calls.append(var)
        if var.get("cursor"):
            return httpx.Response(500)
        return httpx.Response(200, json=p2 if var["contentOffsetSeconds"] >= 102 else p1)

    got = _REAL_CHAT("999", 100, 104, client=_mock_client(handler), pause=0)
    assert [t for t, _ in got] == [100, 101, 103]
    assert any("cursor" in c for c in calls) and "contentOffsetSeconds" in calls[-1]


def test_twitch_chat_refused_query_raises_clear_error():
    def handler(req):
        return httpx.Response(200, json=[{"errors": [{"message": "PersistedQueryNotFound"}]}])

    with pytest.raises(MediaError, match="refused"):
        _REAL_CHAT("999", 0, 10, client=_mock_client(handler), pause=0)


# -- collect_signals: positive controls -----------------------------------------------------------------------
@needs_ffmpeg
def test_chat_spike_raises_heat_where_injected_and_drops_when_removed(net, audio, tmp_path):
    spike = _collect(net, audio, tmp_path, "s", msgs=_chat(spike_at=30))
    flat = _collect(net, audio, tmp_path, "f", msgs=_chat())
    b = int(30 / 2)
    assert spike["bins"][b]["chat_n"] >= 20 and spike["bins"][b]["chat_tags"]["funny"] >= 20
    assert spike["bins"][b]["heat"] > 6.0
    assert spike["bins"][b]["heat"] > flat["bins"][b]["heat"] + 3.0  # remove the spike -> heat falls
    assert max(x["heat"] for i, x in enumerate(spike["bins"]) if abs(i - b) > 3) < spike["bins"][b]["heat"] - 3
    pk = max(spike["peaks"], key=lambda p: p["heat"])
    assert pk["start_s"] <= 30 <= pk["end_s"] and "funny" in pk["tags"]
    assert "chat×" in pk["evidence"] and "KEKW" in pk["evidence"]
    assert "twitch_chat" in spike["sources"]


@needs_ffmpeg
def test_viewer_clip_raises_heat_and_is_listed(net, audio, tmp_path):
    clip = [{"vod_id": "999", "start_s": 130.0, "end_s": 140.0, "title": "KAI SCREAMS", "views": 9000, "slug": "x"}]
    base = _collect(net, audio, tmp_path, "b", msgs=_chat())
    with_clip = _collect(net, audio, tmp_path, "c", msgs=_chat(), clips=clip)
    assert with_clip["clips"] == [{"start_s": 30.0, "end_s": 40.0, "title": "KAI SCREAMS", "views": 9000}]
    b = int(34 / 2)
    assert with_clip["bins"][b]["heat"] > base["bins"][b]["heat"] + 3.0
    pk = max(with_clip["peaks"], key=lambda p: p["heat"])
    assert "clip" in pk["tags"] and "KAI SCREAMS" in pk["evidence"]
    assert "twitch_clips" in with_clip["sources"]
    # a clip that points at ANOTHER vod is not used
    other = [{**clip[0], "vod_id": "123"}]
    assert _collect(net, audio, tmp_path, "o", msgs=_chat(), clips=other)["clips"] == []


@needs_ffmpeg
def test_agreeing_sources_beat_a_single_source(net, audio, tmp_path):
    clip = [{"vod_id": "999", "start_s": 130.0, "end_s": 136.0, "title": "x", "views": 100, "slug": "x"}]
    only_chat = _collect(net, audio, tmp_path, "1", msgs=_chat(spike_at=30))
    both = _collect(net, audio, tmp_path, "2", msgs=_chat(spike_at=30), clips=clip)
    assert both["bins"][15]["heat"] >= only_chat["bins"][15]["heat"]
    assert both["bins"][15]["heat"] == 10.0


@needs_ffmpeg
def test_times_are_file_seconds_and_out_of_range_chat_is_dropped(net, audio, tmp_path):
    msgs = [(50.0, "KEKW")] * 30 + [(100 + 10.0, "KEKW")] * 30 + [(100 + 99.0, "KEKW")] * 30  # before / inside / after
    sig = _collect(net, audio, tmp_path, "r", msgs=msgs)
    assert sum(x["chat_n"] for x in sig["bins"]) == 30
    assert sig["bins"][5]["chat_n"] == 30  # vod 110 - offset 100 = file 10 s = bin 5
    assert sig["duration"] == pytest.approx(60, abs=0.5)


@needs_ffmpeg
def test_loudness_alone_marks_the_burst(tmp_path):
    video = _wav(tmp_path / "l.wav", loud_at=(20, 24))
    sig = S.collect_signals(video, tmp_path / "w", allow_network=False, models_dir=tmp_path / "m")
    assert sig["sources"] == ["loudness"]
    assert sig["bins"][11]["loud"] > 0.9 and sig["bins"][2]["loud"] < 0.3
    assert sig["bins"][11]["chat"] is None and sig["bins"][11]["replay"] is None and sig["bins"][11]["music"] is None
    assert len(sig["bins"]) == 30 and sig["bin_s"] == 2.0
    assert any("YAMNet" in n or "model" in n for n in sig["notes"])


class _FakeYam:
    """Laughter at 19-23 s (rows of 0.48 s), nothing else."""
    def scores(self, pcm):
        n = int(pcm.size / (0.48 * 16000))
        z = np.zeros(n, dtype=np.float32)
        laugh = z.copy()
        laugh[38:46] = 0.9
        return {"laugh": laugh, "cheer": z, "scream": z, "music": z + 0.7}


@needs_ffmpeg
def test_audio_events_lift_heat_and_set_music(audio, tmp_path, monkeypatch):
    base = S.collect_signals(audio, tmp_path / "a", allow_network=False, models_dir=tmp_path / "m")
    monkeypatch.setattr(S, "_load_yamnet", lambda d, n: (_FakeYam(), ""))
    sig = S.collect_signals(audio, tmp_path / "b", allow_network=False, models_dir=tmp_path / "m")
    assert "yamnet" in sig["sources"]
    assert sig["bins"][10]["laugh"] >= 0.89 and sig["bins"][2]["laugh"] == 0
    assert sig["bins"][10]["heat"] > base["bins"][10]["heat"] + 3
    assert sig["bins"][10]["music"] == pytest.approx(0.7, abs=0.01)
    pk = max(sig["peaks"], key=lambda p: p["heat"])
    assert "funny" in pk["tags"] and "music" in pk["tags"] and "laughter" in pk["evidence"]


@needs_ffmpeg
def test_youtube_heatmap_becomes_replay_bins(audio, tmp_path, monkeypatch):
    info = json.loads((FIX / "yt_info.json").read_text())
    monkeypatch.setattr(S, "yt_info", lambda url: info)
    monkeypatch.setattr(S, "yt_live_chat", lambda url, w: S.parse_yt_chat(FIX / "yt_live_chat.jsonl"))
    sig = S.collect_signals(audio, tmp_path / "y", url="https://youtu.be/abc", offset_s=0, models_dir=tmp_path / "m")
    assert sig["bins"][7]["replay"] == 1.0 and sig["bins"][1]["replay"] == 0.1  # 14 s in the 1.0 bin, 2 s in the 0.1 bin
    assert "yt_heatmap" in sig["sources"] and "yt_chat" in sig["sources"]
    assert sig["bins"][6]["chat_n"] == 1 and sig["bins"][7]["chat_n"] == 1  # 12.5 s / 14.25 s


@needs_ffmpeg
def test_youtube_without_heatmap_is_a_note_not_an_error(audio, tmp_path, monkeypatch):
    monkeypatch.setattr(S, "yt_info", lambda url: {"heatmap": None})
    monkeypatch.setattr(S, "yt_live_chat", lambda url, w: (_ for _ in ()).throw(MediaError("no live chat replay")))
    sig = S.collect_signals(audio, tmp_path / "n", url="https://youtu.be/abc", models_dir=tmp_path / "m")
    assert sig["bins"][3]["replay"] is None and sig["bins"][3]["chat"] is None
    assert any("heatmap" in n for n in sig["notes"]) and any("live chat" in n for n in sig["notes"])


# -- degradation + cache ---------------------------------------------------------------------------------------
@needs_ffmpeg
def test_network_failure_and_network_off_never_raise(net, audio, tmp_path, monkeypatch):
    def fail(*a, **k):
        raise httpx.ConnectError("no route")

    net.chat = fail
    monkeypatch.setattr(S, "twitch_video_meta", fail)
    sig = S.collect_signals(audio, tmp_path / "x", url=VOD, offset_s=100, models_dir=tmp_path / "m")
    assert any("twitch" in n for n in sig["notes"]) and "loudness" in sig["sources"]
    saved = json.loads((tmp_path / "x" / "signals.json").read_text(encoding="utf-8"))
    assert saved["partial"] and "loudness" in saved["sources"]  # written for the analyst (loudness survives) ...
    calls = []
    net.chat = lambda *a, **k: calls.append(1) or fail()
    S.collect_signals(audio, tmp_path / "x", url=VOD, offset_s=100, models_dir=tmp_path / "m")
    assert calls  # ... but never a cache hit: the next call retries the failed source
    off = S.collect_signals(audio, tmp_path / "y", url=VOD, offset_s=100, allow_network=False, models_dir=tmp_path / "m")
    assert any("network off" in n for n in off["notes"])
    junk = S.collect_signals(tmp_path / "missing.mp4", tmp_path / "z")
    assert junk["bins"] == [] and junk["notes"]  # unreadable video -> empty result, still no raise


@needs_ffmpeg
def test_cache_is_reused_and_invalidated_by_offset(net, audio, tmp_path):
    first = _collect(net, audio, tmp_path, "c", msgs=_chat(spike_at=30))
    net.chat = lambda *a, **k: (_ for _ in ()).throw(AssertionError("should come from cache"))
    again = S.collect_signals(audio, tmp_path / "c", url=VOD, offset_s=100, models_dir=tmp_path / "m")
    assert again["bins"] == first["bins"]
    net.chat = lambda *a, **k: []  # different offset => recomputed (no chat now)
    moved = S.collect_signals(audio, tmp_path / "c", url=VOD, offset_s=500, models_dir=tmp_path / "m")
    assert moved["bins"][15]["chat_n"] == 0


@needs_ffmpeg
def test_heat_between_and_prompt_timeline(net, audio, tmp_path):
    sig = _collect(net, audio, tmp_path, "h", msgs=_chat(spike_at=30))
    hot, cold = S.heat_between(sig, 28, 36), S.heat_between(sig, 0, 10)
    assert hot["heat"] > cold["heat"] + 3 and hot["chat"] == 1.0 and "funny" in hot["tags"]
    assert "KEKW" in hot["evidence"] and cold["music"] is None
    assert S.heat_between(sig, 500, 600)["heat"] == 0.0  # outside the file
    text = S.prompt_timeline(sig, max_items=5)
    assert "twitch_chat" in text and re.search(r"\[\d+s–\d+s\] heat", text) and "KEKW" in text  # plain seconds
    assert S.prompt_timeline({"peaks": [], "sources": []}).endswith("(no peak stood out)")


# -- fetch: time parsing, playlist parsing, verification, segment fetch ----------------------------------------------
def test_parse_hms_and_fmt():
    assert F.parse_hms("90") == 90 and F.parse_hms("1:30") == 90 and F.parse_hms("01:02:03") == 3723
    assert F.parse_hms("1h2m3s") == 3723 and F.parse_hms("45s") == 45
    with pytest.raises(ValueError):
        F.parse_hms("1:2:3:4")
    assert F.fmt_hms(3723) == "01:02:03"


def test_parse_m3u8_byterange_and_init():
    text = ('#EXTM3U\n#EXT-X-MAP:URI="init.mp4",BYTERANGE="100@0"\n#EXTINF:2.0,\n#EXT-X-BYTERANGE:500@100\nf.mp4\n'
            '#EXTINF:2.0,\n#EXT-X-BYTERANGE:400\nf.mp4\n#EXTINF:1.5,\nseg3.ts\n')
    segs, init = F.parse_m3u8(text, "https://cdn.x/v/index.m3u8")
    assert init == ("https://cdn.x/v/init.mp4", "bytes=0-99")
    assert segs == [("https://cdn.x/v/f.mp4", 2.0, "bytes=100-599"), ("https://cdn.x/v/f.mp4", 2.0, "bytes=600-999"),
                    ("https://cdn.x/v/seg3.ts", 1.5, None)]


def test_verify_clip_rejects_the_262_byte_exit0_file(tmp_path):
    tiny = tmp_path / "t.mp4"
    tiny.write_bytes(b"x" * 262)
    with pytest.raises(MediaError, match="tiny"):
        F.verify_clip(tiny, 10)
    with pytest.raises(MediaError, match="tiny"):
        F.verify_clip(tmp_path / "nope.mp4", 10)


def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@needs_ffmpeg
def test_verify_clip_checks_duration(tmp_path):
    clip = tmp_path / "c.mp4"
    _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=15", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:v", "400k", str(clip))
    assert F.verify_clip(clip, 5) == pytest.approx(5, abs=0.5)
    with pytest.raises(MediaError, match="asked for"):
        F.verify_clip(clip, 30)


@needs_ffmpeg
def test_fetch_range_downloads_only_overlapping_segments(tmp_path, monkeypatch):
    segs = {}
    for i in range(4):  # 4 x 2 s MPEG-TS segments
        p = tmp_path / f"s{i}.ts"
        _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=15",
            "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-b:v", "300k", "-f", "mpegts", str(p))
        segs[f"/v/s{i}.ts"] = p.read_bytes()
    playlist = "#EXTM3U\n" + "".join(f"#EXTINF:2.0,\ns{i}.ts\n" for i in range(4)) + "#EXT-X-ENDLIST\n"
    asked: list[str] = []

    def handler(req):
        asked.append(req.url.path)
        if req.url.path.endswith("index.m3u8"):
            return httpx.Response(200, text=playlist)
        return httpx.Response(200, content=segs[req.url.path])

    real = httpx.Client
    monkeypatch.setattr(F.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(F, "_ytdlp_urls", lambda url, fmt: ["https://cdn.example/v/index.m3u8"])
    out = F.fetch_range("https://www.twitch.tv/videos/5", 2.5, 5.5, tmp_path / "o" / "cut.mp4", workers=3)
    assert out.exists() and F.verify_clip(out, 3.0) == pytest.approx(3.0, abs=0.6)
    assert sorted(p for p in asked if p.endswith(".ts")) == ["/v/s1.ts", "/v/s2.ts"]  # 2-4 s and 4-6 s only
    with pytest.raises(MediaError, match="outside the VOD"):
        F.fetch_range("https://www.twitch.tv/videos/5", 50, 60, tmp_path / "o" / "late.mp4")
    assert not (tmp_path / "o" / "late.mp4").exists()  # failure leaves no half file behind
    with pytest.raises(MediaError, match="--to"):
        F.fetch_range("https://www.twitch.tv/videos/5", 10, 5, tmp_path / "bad.mp4")


# -- CLI --------------------------------------------------------------------------------------------------------------
def _parser():
    from noze.agency import cli

    root = argparse.ArgumentParser()
    cli.register(root.add_subparsers(dest="cmd"))
    return root


def test_cli_parses_fetch_vods_and_submit_flags():
    p = _parser()
    a = p.parse_args(["agency", "fetch", VOD, "--from", "1:02:03", "--to", "1:05:00", "-o", "x.mp4"])
    assert (a.from_, a.to, a.output, a.workers) == (3723.0, 3900.0, "x.mp4", 8)
    v = p.parse_args(["agency", "vods", "kaicenat", "--days", "3"])
    assert (v.login, v.days) == ("kaicenat", 3)
    s = p.parse_args(["agency", "submit", "a.mp4", "--vod-url", VOD, "--vod-offset", "1h2m3s"])
    assert (s.vod_url, s.vod_offset) == (VOD, 3723.0)
    assert p.parse_args(["agency", "submit", "a.mp4"]).vod_offset == 0.0
    with pytest.raises(SystemExit):
        p.parse_args(["agency", "fetch", VOD, "--to", "banana"])


def test_cli_submit_passes_vod_url_and_offset(monkeypatch, capsys):
    from noze.agency import cli

    got = {}

    class FakeAgency:
        def submit(self, source, campaign, **kw):
            got.update(source=source, campaign=campaign, **kw)
            return 7

    monkeypatch.setattr(cli, "_agency", lambda args: FakeAgency())
    args = _parser().parse_args(["agency", "submit", "a.mp4", "--campaign", "gta6", "--vod-url", VOD, "--vod-offset", "90"])
    cli.cmd_submit(args)
    assert got["signals_url"] == VOD and got["offset_s"] == 90.0 and got["campaign"] == "gta6"
    got.clear()
    cli.cmd_submit(_parser().parse_args(["agency", "submit", "a.mp4", "--own"]))
    assert got["signals_url"] == "" and got["offset_s"] == 0.0


def test_cli_fetch_prints_ready_submit_command(monkeypatch, tmp_path, capsys):
    from noze.agency import cli

    def fake_fetch(url, a, b, out, workers=8):
        Path(out).write_bytes(b"0" * 1000)

    monkeypatch.setattr(F, "fetch_range", fake_fetch)
    out = tmp_path / "c.mp4"
    cli.cmd_fetch(_parser().parse_args(["agency", "fetch", VOD, "--from", "1:00", "--to", "2:00", "-o", str(out)]))
    text = capsys.readouterr().out
    assert f'--vod-url "{VOD}" --vod-offset 60' in text and str(out) in text
    monkeypatch.setattr(F, "fetch_range", lambda *a, **k: (_ for _ in ()).throw(MediaError("boom")))
    with pytest.raises(SystemExit, match="boom"):
        cli.cmd_fetch(_parser().parse_args(["agency", "fetch", VOD, "--to", "2:00", "-o", str(out)]))


def test_cli_vods_flags_gta_and_lists_top_clips(monkeypatch, capsys):
    from datetime import datetime, timezone

    from noze.agency import cli

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    monkeypatch.setattr(S, "twitch_vods", lambda login, limit=30, client=None: [
        {"id": "1", "title": "PLAYING GTA 6 FIRST TIME", "length_s": 3600, "created_at": now, "views": 10},
        {"id": "2", "title": "just chatting", "length_s": 60, "created_at": now, "views": 5},
        {"id": "3", "title": "old", "length_s": 60, "created_at": "2020-01-01T00:00:00Z", "views": 1}])
    clips = [{"vod_id": "1", "start_s": 7528.0 + i, "end_s": 7550.0, "title": f"clip{i}", "views": 100 - i, "slug": ""}
             for i in range(5)]
    monkeypatch.setattr(S, "twitch_clips", lambda login, period="LAST_WEEK", client=None: clips)
    cli.cmd_vods(_parser().parse_args(["agency", "vods", "kai"]))
    text = capsys.readouterr().out
    assert "<== GTA" in text and text.count("<== GTA") == 1
    assert "viewer clips: 5" in text and "clip0" in text and "clip2" in text and "clip3" not in text  # top 3 only
    assert "02:05:28" in text and "old" not in text  # 7 day window drops the 2020 VOD


# -- review fixes: truncation, no caching of failures, yamnet in the cache key, "--" before urls ------------------------
def _endless_chat_handler(req):
    """Every page is one message one second later, always has a next page (a chat that never ends)."""
    var = json.loads(req.content)[0]["variables"]
    t = int(var["cursor"][1:]) if var.get("cursor") else int(var["contentOffsetSeconds"])
    node = {"id": f"m{t}", "contentOffsetSeconds": t, "message": {"fragments": [{"text": "hi"}]}}
    page = {"edges": [{"cursor": f"c{t + 1}", "node": node}], "pageInfo": {"hasNextPage": True}}
    return httpx.Response(200, json=[{"data": {"video": {"comments": page}}}])


def test_twitch_chat_reports_truncation_and_budget_scales_with_range():
    info: dict = {}
    got = _REAL_CHAT("1", 0, 10_000, client=_mock_client(_endless_chat_handler), pause=0, max_pages=50, info=info)
    assert len(got) == 50 and info["truncated_at"] == pytest.approx(49, abs=1)  # stopped early, and says where
    done: dict = {}
    _REAL_CHAT("1", 0, 20, client=_mock_client(_endless_chat_handler), pause=0, info=done)
    assert "truncated_at" not in done  # reached the end of the range: not truncated
    slow: dict = {}
    _REAL_CHAT("1", 0, 10_000, client=_mock_client(_endless_chat_handler), pause=0, max_seconds=-1, info=slow)
    assert "truncated_at" in slow  # time limit also reports instead of silently stopping
    # default budget grows with the range instead of the old fixed 800 pages
    big: dict = {}
    got = _REAL_CHAT("1", 0, 1500, client=_mock_client(_endless_chat_handler), pause=0, info=big)
    assert "truncated_at" not in big and len(got) >= 1500  # old fixed 800-page cap would have cut this at ~800 s


@needs_ffmpeg
def test_truncated_chat_leaves_unread_bins_none_not_zero_and_is_not_cached(net, audio, tmp_path):
    calls = []

    def chat(vid, a, b, client=None, info=None):
        calls.append(1)
        info["truncated_at"] = 120.0  # read up to file second 20
        return [(100 + t, "hi") for t in range(0, 20, 2)] + [(110 + i * 0.1, "KEKW") for i in range(30)]

    net.chat = chat
    sig = S.collect_signals(audio, tmp_path / "t", url=VOD, offset_s=100, models_dir=tmp_path / "m")
    assert any("chat truncated at 00:00:20" in n for n in sig["notes"])
    assert sig["bins"][5]["chat"] is not None and sig["bins"][9]["chat"] is not None
    assert all(b["chat"] is None for b in sig["bins"][10:])  # unread, not "quiet"
    assert sig["bins"][5]["heat"] > 5
    S.collect_signals(audio, tmp_path / "t", url=VOD, offset_s=100, models_dir=tmp_path / "m")
    assert len(calls) == 2  # truncated result was not cached


@needs_ffmpeg
def test_unread_chat_bins_do_not_pull_heat_down(net, audio, tmp_path):
    net.chat = lambda vid, a, b, client=None, info=None: (info.update(truncated_at=100.0), [(105.0, "KEKW")] * 10)[1]
    cut = S.collect_signals(audio, tmp_path / "c", url=VOD, offset_s=100, models_dir=tmp_path / "m")
    plain = S.collect_signals(audio, tmp_path / "p", models_dir=tmp_path / "m")  # no chat source at all
    assert [b["heat"] for b in cut["bins"]] == [b["heat"] for b in plain["bins"]]


@needs_ffmpeg
def test_yamnet_availability_is_part_of_the_cache_key(net, audio, tmp_path):
    models = tmp_path / "m"
    n = []
    net.chat = lambda *a, **k: (n.append(1), [])[1]
    S.collect_signals(audio, tmp_path / "k", url=VOD, offset_s=100, models_dir=models)
    S.collect_signals(audio, tmp_path / "k", url=VOD, offset_s=100, models_dir=models)
    assert len(n) == 1  # stable -> cached
    models.mkdir()
    (models / "yamnet.onnx").write_bytes(b"x")
    (models / "yamnet_class_map.csv").write_text("index,mid,display_name\n")
    S.collect_signals(audio, tmp_path / "k", url=VOD, offset_s=100, models_dir=models)
    assert len(n) == 2  # model appeared -> recomputed


def test_urls_are_passed_after_double_dash(monkeypatch):
    seen = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="http://x/v\n", stderr="")

    monkeypatch.setattr(S, "_ytdlp", lambda: ["yt-dlp"])
    monkeypatch.setattr(S.subprocess, "run", fake_run)
    monkeypatch.setattr(F.subprocess, "run", fake_run)
    monkeypatch.setattr(F, "_ytdlp_cmd", lambda: ["yt-dlp"])
    evil = "--exec=calc"
    F._ytdlp_urls(evil, "best")
    try:
        S.yt_info(evil)
    except Exception:
        pass
    for cmd in seen:
        assert cmd[-2:] == ["--", evil]


# -- story pack: vod_map, audio-only scan, pack fetch ------------------------------------------------------------
PACK_MAP = [{"file_start": 0, "file_end": 30, "vod_start": 1000}, {"file_start": 30, "file_end": 60, "vod_start": 5000}]


@needs_ffmpeg
def test_vod_map_places_chat_per_piece_and_control_without_it_lands_wrong(net, audio, tmp_path):
    asked = []

    def chat(vid, a, b, client=None, info=None):
        asked.append((a, b))
        # quiet chat in both pieces + a KEKW spike at VOD 5010 (= file 40, bin 20) + 20 messages in the gap
        allm = ([(1000 + t, "hi") for t in range(0, 30, 3)] + [(5000 + t, "hi") for t in range(0, 30, 3)]
                + [(5010 + i * 0.04, "KEKW") for i in range(40)] + [(3000.0, "KEKW")] * 20)
        return [m for m in allm if a <= m[0] <= b]  # a real fetch only returns what was asked

    net.chat = chat
    sig = S.collect_signals(audio, tmp_path / "m", url=VOD, vod_map=PACK_MAP, models_dir=tmp_path / "m0")
    assert asked == [(1000.0, 1030.0), (5000.0, 5030.0)]  # chat only for the pieces' VOD ranges
    assert sig["bins"][20]["chat_n"] >= 40 and sig["bins"][20]["chat_tags"]["funny"] >= 40
    assert sum(b["chat_n"] for b in sig["bins"]) == 60  # 10 + 10 + 40; the gap's 20 messages were never asked for
    assert sig["bins"][20]["heat"] > 6 and sig["bins"][20]["heat"] > sig["bins"][5]["heat"] + 3
    # control: one offset (1000) cannot place VOD 5010 -> the spike is lost and bin 20 is quiet
    ctl = S.collect_signals(audio, tmp_path / "c", url=VOD, offset_s=1000, models_dir=tmp_path / "m0")
    assert ctl["bins"][20]["chat_n"] < 5 and ctl["bins"][20]["heat"] < sig["bins"][20]["heat"] - 3


@needs_ffmpeg
def test_vod_map_is_part_of_the_cache_key_and_maps_clips(net, audio, tmp_path):
    net.clips = [{"vod_id": "999", "start_s": 5005.0, "end_s": 5015.0, "title": "wow", "views": 10},
                 {"vod_id": "999", "start_s": 3000.0, "end_s": 3010.0, "title": "gap", "views": 10}]
    sig = S.collect_signals(audio, tmp_path / "k", url=VOD, vod_map=PACK_MAP, models_dir=tmp_path / "m0")
    assert [(c["start_s"], c["end_s"], c["title"]) for c in sig["clips"]] == [(35.0, 45.0, "wow")]  # gap clip dropped
    other = S.collect_signals(audio, tmp_path / "k", url=VOD, vod_map=PACK_MAP[:1], models_dir=tmp_path / "m0")
    assert other["key"]["vod_map"] != sig["key"]["vod_map"] and other["clips"] == []


@needs_ffmpeg
def test_vod_map_truncation_leaves_only_the_unread_part_none(net, audio, tmp_path):
    def chat(vid, a, b, client=None, info=None):
        if a == 5000:
            info["truncated_at"] = 5010.0  # piece 2 read to file second 40 only
        return [(a + t, "hi") for t in range(0, 30, 2)]

    net.chat = chat
    sig = S.collect_signals(audio, tmp_path / "t", url=VOD, vod_map=PACK_MAP, models_dir=tmp_path / "m0")
    assert sig["bins"][5]["chat"] is not None and sig["bins"][17]["chat"] is not None  # piece 1 + start of piece 2
    assert all(b["chat"] is None for b in sig["bins"][20:])  # unread tail of piece 2
    assert sig["partial"] is True  # retried next time


def test_vod_map_maps_the_youtube_heatmap_and_helpers_per_piece():
    pcs = S._pieces(PACK_MAP)
    x = S._replay_bins([(5000.0, 5030.0, 0.9)], 0.0, 30, pcs)
    assert x[:15].sum() == 0 and (x[15:] == 0.9).all()  # only the second piece is in the hot VOD range
    assert S._vod_to_file(3000.0, pcs) is None and S._vod_to_file(5010.0, pcs) == 40.0 and S._file_to_vod(40.0, pcs) == 5010.0


def _synth(path: Path, secs: float, freq: int):
    _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=15", "-f", "lavfi", "-i", f"sine=frequency={freq}", "-t", str(secs),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:v", "300k", str(path))


@needs_ffmpeg
def test_fetch_pack_glues_pieces_and_writes_a_consistent_vodmap(tmp_path, monkeypatch):
    got = []

    def fake_range(url, a, b, out, workers=8):
        got.append((url, a, b))
        _synth(Path(out), b - a, 440 if a < 200 else 880)
        return Path(out)

    monkeypatch.setattr(F, "fetch_range", fake_range)
    out, vm = F.fetch_pack(VOD, [(100, 103), (500, 504)], tmp_path / "o" / "pack.mp4")
    assert got == [(VOD, 100, 103), (VOD, 500, 504)]
    assert F.verify_clip(out, 7.0, tol=0.8) == pytest.approx(7.0, abs=0.8)
    side = json.loads((tmp_path / "o" / "pack.mp4.vodmap.json").read_text())
    assert side == vm and [p["vod_start"] for p in vm] == [100, 500]
    assert vm[0]["file_start"] == 0 and vm[0]["file_end"] == vm[1]["file_start"]
    assert vm[1]["file_end"] == pytest.approx(7.0, abs=0.6)
    assert not [p for p in (tmp_path / "o").iterdir() if p.name.startswith(".pack_")]  # temp pieces cleaned
    # the seam is faded: the audio samples around it are ~silent (no click)
    pcm = np.frombuffer(S.run(["-v", "error", "-i", str(out), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]).stdout,
                        dtype=np.int16).astype(float)
    seam = int(vm[0]["file_end"] * 16000)
    assert abs(pcm[seam - 3:seam + 3]).max() < 0.05 * 32767
    with pytest.raises(MediaError, match="no ranges"):
        F.fetch_pack(VOD, [], tmp_path / "x.mp4")


def _has_video(p: Path) -> bool:
    from noze.agency.media.ffmpeg import probe

    return probe(p)["has_video"]


@needs_ffmpeg
def test_fetch_audio_range_uses_the_audio_only_rendition_and_verifies(tmp_path, monkeypatch):
    segs = {}
    for i in range(4):  # 4 x 2 s audio-only MPEG-TS segments
        p = tmp_path / f"a{i}.ts"
        _ff("-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:a", "aac", "-f", "mpegts", str(p))
        segs[f"/v/a{i}.ts"] = p.read_bytes()
    playlist = "#EXTM3U\n" + "".join(f"#EXTINF:2.0,\na{i}.ts\n" for i in range(4)) + "#EXT-X-ENDLIST\n"
    asked: list[str] = []

    def handler(req):
        if req.url.path.endswith("m3u8"):
            return httpx.Response(200, text=playlist)
        asked.append(req.url.path)
        return httpx.Response(200, content=segs[req.url.path])

    real = httpx.Client
    monkeypatch.setattr(F.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    fmts: list[str] = []
    monkeypatch.setattr(F, "_ytdlp_urls", lambda url, fmt: (fmts.append(fmt), ["https://cdn.example/v/index.m3u8"])[1])
    out = F.fetch_audio_range("https://www.twitch.tv/videos/5", 2.5, 5.5, tmp_path / "o" / "a.m4a")
    assert fmts == ["audio_only"] and sorted(asked) == ["/v/a1.ts", "/v/a2.ts"]
    assert F.verify_audio(out, 3.0) == pytest.approx(3.0, abs=0.6) and not _has_video(out)
    with pytest.raises(MediaError, match="outside the VOD"):
        F.fetch_audio_range("https://www.twitch.tv/videos/5", 50, 60, tmp_path / "o" / "late.m4a")
    assert not (tmp_path / "o" / "late.m4a").exists()
    tiny = tmp_path / "t.m4a"
    tiny.write_bytes(b"0" * 100)
    with pytest.raises(MediaError, match="tiny"):
        F.verify_audio(tiny, 3.0)


def _hls_mock(tmp_path, monkeypatch, n=4):
    segs = {}
    for i in range(n):
        p = tmp_path / f"a{i}.ts"
        _ff("-f", "lavfi", "-i", "sine=frequency=440", "-t", "2", "-c:a", "aac", "-f", "mpegts", str(p))
        segs[f"/v/a{i}.ts"] = p.read_bytes()
    playlist = "#EXTM3U\n" + "".join(f"#EXTINF:2.0,\na{i}.ts\n" for i in range(n)) + "#EXT-X-ENDLIST\n"

    def handler(req):
        return httpx.Response(200, text=playlist) if req.url.path.endswith("m3u8") else httpx.Response(200, content=segs[req.url.path])

    real = httpx.Client
    monkeypatch.setattr(F.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(F, "_ytdlp_urls", lambda url, fmt: ["https://cdn.example/v/index.m3u8"])


@needs_ffmpeg
def test_hls_segments_go_to_disk_beside_out_and_the_parts_folder_is_removed(tmp_path, monkeypatch):
    _hls_mock(tmp_path, monkeypatch)
    seen = []
    real_cut = F._cut_audio

    def spy(inputs, rel, length, out):
        joined = Path(inputs[-1])
        seen.append((joined.parent, joined.parent.parent == out.parent, joined.exists()))
        return real_cut(inputs, rel, length, out)

    monkeypatch.setattr(F, "_cut_audio", spy)
    monkeypatch.setattr(F.tempfile, "TemporaryDirectory", lambda *a, **k: pytest.fail("must not use %TEMP%"))
    out = F.fetch_audio_range("https://www.twitch.tv/videos/5", 0, 8, tmp_path / "o" / "a.m4a")
    assert seen and seen[0][0].name == "a.part.m4a.parts" and seen[0][1] and seen[0][2]  # joined file sat beside the output
    assert sorted(p.name for p in (tmp_path / "o").iterdir()) == ["a.m4a"]  # parts folder + .part file gone
    assert out.name == "a.m4a"
    # a failure mid-way also cleans up and leaves no final file
    monkeypatch.setattr(F, "_cut_audio", lambda *a, **k: (_ for _ in ()).throw(MediaError("boom")))
    with pytest.raises(MediaError, match="boom"):
        F.fetch_audio_range("https://www.twitch.tv/videos/5", 0, 8, tmp_path / "o2" / "b.m4a")
    assert list((tmp_path / "o2").iterdir()) == []


def test_fetch_audio_range_interrupt_leaves_no_file_with_the_final_name(tmp_path, monkeypatch):
    def boom(url, start, end, out, workers, fmt="best", audio=False):
        Path(out).write_bytes(b"half" * 1000)  # what ffmpeg leaves behind
        raise KeyboardInterrupt

    monkeypatch.setattr(F, "_fetch_hls", boom)
    final = tmp_path / "o" / "audio.m4a"
    with pytest.raises(KeyboardInterrupt):
        F.fetch_audio_range("https://www.twitch.tv/videos/5", 0, 8, final)
    assert not final.exists() and list(final.parent.iterdir()) == []


def test_cli_scan_redownloads_a_truncated_cached_audio_but_keeps_a_whole_one(monkeypatch, tmp_path, capsys):
    from noze.agency import cli

    picks = [{"start_s": 10.0, "end_s": 40.0, "structure": "linear", "title": "t", "parts": [{"start_s": 10.0, "end_s": 40.0}]}]
    ag = _scan_agency(tmp_path, True, picks)
    calls: list = []
    _scan_patches(monkeypatch, calls)
    cache = ag.cfg.root / "cache" / "scan" / "123456_0_600"
    cache.mkdir(parents=True)
    (cache / "audio.m4a").write_bytes(b"0" * 5000)  # big enough for the old ">=1000 bytes" check, but truncated
    verdict = {"ok": False}

    def fake_verify(path, want_s, tol=2.0):
        if not verdict["ok"]:
            raise MediaError("fetched 10.0s of audio but asked for 600.0s")
        return want_s

    monkeypatch.setattr(F, "verify_audio", fake_verify)
    monkeypatch.setattr(cli, "_agency", lambda args: ag)
    argv = ["agency", "scan", "https://www.twitch.tv/videos/123456", "--to", "10:00", "--campaign", "gta6", "--dry-run"]
    cli.cmd_scan(_parser().parse_args(argv))
    assert ("audio", 0.0, 600.0) in calls and "unusable" in capsys.readouterr().out  # control: truncated -> downloaded again
    calls.clear()
    verdict["ok"] = True
    cli.cmd_scan(_parser().parse_args(argv))
    assert not [c for c in calls if c[0] == "audio"] and "audio cached" in capsys.readouterr().out  # whole -> reused


class _ScanStore:
    def __init__(self):
        self.jobs = {}

    def get_campaign(self, ref):
        return {"id": 3, "name": "gta6"} if ref == "gta6" else None

    def create_job(self, *a, **k):
        self.jobs[1] = {"id": 1, "campaign_id": k.get("campaign_id")}
        return 1

    def get_job(self, i):
        return self.jobs[i]


def _scan_agency(tmp_path, granted, picks):
    from types import SimpleNamespace as NS

    class An:
        def scan_arcs(self, job, tr, sig, brief, n, min_s, max_s, gap_min_s=600.0, **kw):
            An.seen = (n, gap_min_s, min_s, max_s)
            return picks

    cfg = NS(root=tmp_path / "ag", transcriber="auto", whisper_model="small", min_clip_s=20, max_clip_s=60)
    return NS(cfg=cfg, store=_ScanStore(), analyst=An(), _brief=lambda job: {
        "clip_length": {}, "creator": "kai", "creator_handles": [], "permission": {"granted": granted}})


def _scan_patches(monkeypatch, calls):
    from noze.agency.media import transcribe as T

    def fake_audio(url, a, b, out, workers=8):
        calls.append(("audio", a, b))
        Path(out).write_bytes(b"0" * 5000)

    def fake_signals(*a, **k):
        calls.append(("signals", k.get("offset_s")))
        return {"sources": [], "peaks": [], "clips": []}

    monkeypatch.setattr(F, "fetch_audio_range", fake_audio)
    monkeypatch.setattr(T, "transcribe", lambda *a, **k: {"source": "stub", "segments": []})
    monkeypatch.setattr(S, "collect_signals", fake_signals)


def test_cli_scan_dry_run_prints_candidates_in_vod_time_and_fetches_no_video(monkeypatch, tmp_path, capsys):
    from noze.agency import cli

    picks = [{"start_s": 100.0, "end_s": 130.0, "structure": "arc", "emotion": "hype", "overall": 8.2, "title": "the bet",
              "story": "bet -> payoff", "rationale": "x",
              "parts": [{"start_s": 100.0, "end_s": 115.0, "role": "setup"},
                        {"start_s": 3000.0, "end_s": 3015.0, "role": "payoff"}]}]
    ag = _scan_agency(tmp_path, True, picks)
    calls: list = []
    _scan_patches(monkeypatch, calls)
    monkeypatch.setattr(F, "fetch_pack", lambda *a, **k: pytest.fail("dry-run must not fetch video"))
    monkeypatch.setattr(cli, "_agency", lambda args: ag)
    cli.cmd_scan(_parser().parse_args(["agency", "scan", VOD, "--from", "1:00:00", "--to", "2:00:00", "--campaign", "gta6",
                                       "--clips", "2", "--min-gap", "300", "--dry-run"]))
    text = capsys.readouterr().out
    assert ("audio", 3600.0, 7200.0) in calls and ("signals", 3600.0) in calls  # audio window; offset = --from
    assert ag.analyst.seen == (2, 300.0, 20.0, 60.0)
    assert "01:01:40-01:01:55" in text and "01:50:00-01:50:15" in text and "[arc]" in text  # file second + 3600
    assert "00:01:40" not in text  # not left in file time
    assert "2 piece(s)" in text and "--dry-run: no video fetched" in text


def test_cli_scan_fetches_pack_and_prints_submit_with_vod_map_and_internal_test(monkeypatch, tmp_path, capsys):
    from noze.agency import cli

    picks = [{"start_s": 10.0, "end_s": 40.0, "structure": "linear", "title": "t",
              "parts": [{"start_s": 10.0, "end_s": 40.0}]}]
    ag = _scan_agency(tmp_path, False, picks)
    calls: list = []
    _scan_patches(monkeypatch, calls)

    def fake_pack(url, ranges, out, workers=8):
        calls.append(("pack", ranges))
        Path(out).write_bytes(b"0" * 2000)
        vm = [{"file_start": 0.0, "file_end": 46.0, "vod_start": 1802.0}]
        Path(str(out) + ".vodmap.json").write_text(json.dumps(vm))
        return Path(out), vm

    monkeypatch.setattr(F, "fetch_pack", fake_pack)
    monkeypatch.setattr(cli, "_agency", lambda args: ag)
    cli.cmd_scan(_parser().parse_args(["agency", "scan", VOD, "--from", "30:00", "--to", "40:00", "--campaign", "gta6"]))
    text = capsys.readouterr().out
    assert ("pack", [(1802.0, 1848.0)]) in calls  # file 10-40 s + 1800 s offset, +-8 s pad
    assert "--vod-map" in text and "pack.mp4.vodmap.json" in text and "--internal-test" in text
    assert f'--vod-url "{VOD}"' in text
    # window too long / unknown campaign / bad link are clean refusals
    with pytest.raises(SystemExit, match="max-hours"):
        cli.cmd_scan(_parser().parse_args(["agency", "scan", VOD, "--to", "9:00:00", "--campaign", "gta6"]))
    with pytest.raises(SystemExit, match="no campaign"):
        cli.cmd_scan(_parser().parse_args(["agency", "scan", VOD, "--to", "10:00", "--campaign", "nope"]))
    with pytest.raises(SystemExit, match="Twitch VOD or YouTube"):
        cli.cmd_scan(_parser().parse_args(["agency", "scan", "https://example.com/x", "--to", "10:00", "--campaign", "gta6"]))


def test_cli_submit_loads_the_vod_map_file_or_json_and_rejects_garbage(monkeypatch, tmp_path):
    from noze.agency import cli

    got: dict = {}

    class FakeAgency:
        def submit(self, source, campaign, **kw):
            got.update(kw)
            return 1

    monkeypatch.setattr(cli, "_agency", lambda args: FakeAgency())
    f = tmp_path / "p.mp4.vodmap.json"
    f.write_text(json.dumps(PACK_MAP))
    cli.cmd_submit(_parser().parse_args(["agency", "submit", "a.mp4", "--own", "--vod-map", str(f)]))
    assert got["vod_map"] == [{"file_start": 0.0, "file_end": 30.0, "vod_start": 1000.0},
                              {"file_start": 30.0, "file_end": 60.0, "vod_start": 5000.0}]
    cli.cmd_submit(_parser().parse_args(["agency", "submit", "a.mp4", "--own"]))
    assert got["vod_map"] is None
    with pytest.raises(SystemExit, match="bad --vod-map"):
        cli.cmd_submit(_parser().parse_args(["agency", "submit", "a.mp4", "--own", "--vod-map", "{nope"]))
