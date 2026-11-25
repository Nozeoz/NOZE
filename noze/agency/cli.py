"""``noze agency …`` — run and steer the clipping studio from the terminal."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path


def _ax(args):
    from .context import AgencyContext

    return AgencyContext.load(data_dir=args.data_dir)


def _agency(args):
    from .pipeline import Agency

    return Agency(_ax(args))


def _read_terms(args) -> str:
    if getattr(args, "terms_file", None):
        return Path(args.terms_file).read_text(encoding="utf-8")
    if getattr(args, "terms", None) == "-":
        return sys.stdin.read()
    return getattr(args, "terms", None) or ""


def _hms(text: str) -> float:
    from .media.fetch import parse_hms

    try:
        return parse_hms(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _ago(ts: float | None) -> str:
    if not ts:
        return "—"
    d = time.time() - ts
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if d >= n:
            return f"{int(d // n)}{unit} ago"
    return "just now"


# -- setup -----------------------------------------------------------------------------------------
FONT_URLS = {  # OFL fonts from Fontsource's CDN (same source NOZE indexes)
    "Montserrat-ExtraBold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-800-normal.ttf",
    "Montserrat-Black.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-900-normal.ttf",
    "Anton-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/anton@latest/latin-400-normal.ttf",
}


def cmd_init(args) -> None:
    import httpx

    ax = _ax(args)
    cfg = ax.cfg
    print(f"agency folders ready under {cfg.root}")
    for name, url in FONT_URLS.items():
        dest = cfg.fonts_dir / name
        if dest.exists():
            continue
        try:
            r = httpx.get(url, timeout=30.0, follow_redirects=True)
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"  font: {name} (SIL Open Font License)")
        except httpx.HTTPError as exc:
            print(f"  font: {name} not downloaded ({exc}); captions fall back to system fonts")
    from .media.sfx import RECIPES, sfx_file

    for kind in RECIPES:
        sfx_file(kind, cfg.assets_dir, cfg.root / "cache" / "sfx")
    print(f"  {len(RECIPES)} built-in SFX ready (drop your own in {cfg.assets_dir / 'sfx'}: whoosh_*.wav, pop_*.wav …)")
    cmd_doctor(args)


def cmd_doctor(args) -> None:
    import importlib.util

    from .media import faces
    from .media.captions import pick_font
    from .media.ffmpeg import available, run

    ax = _ax(args)
    cfg = ax.cfg

    def mark(ok: bool) -> str:
        return "✓" if ok else "✗"

    ff = available()
    libass = bool(ff and re.search(r"^\s*\S+\s+ass\s", run(["-filters"], check=False).stdout.decode(), re.M))
    print(f"{mark(ff)} ffmpeg/ffprobe" + ("" if ff else "  → install ffmpeg"))
    print(f"{mark(libass)} libass (burned-in captions)")
    fw = importlib.util.find_spec("faster_whisper") is not None
    print(f"{mark(fw)} faster-whisper transcription" + ("" if fw else "  → pip install faster-whisper "
                                                         "(or put .srt/.vtt next to each video)"))
    ytd = bool(shutil.which("yt-dlp") or importlib.util.find_spec("yt_dlp"))
    print(f"{mark(ytd)} yt-dlp (platform links; AGENCY_ALLOW_DOWNLOAD={int(cfg.allow_download)})")
    print(f"{mark(faces.available())} OpenCV speaker locator (optional: pip install opencv-python-headless)")
    via = {"api": "Anthropic API", "cli": f"Claude Code CLI / subscription ({ax.llm.cli})"}.get(ax.llm.backend, "")
    print(f"{mark(ax.llm.available)} Claude ({cfg.models_label()}) " + (
        ax.llm.reason if not ax.llm.available else f"via {via} — fallbacks {'on' if cfg.fallbacks else 'off'}"))
    print(f"  captions font: {pick_font(cfg.fonts_dir)}")
    print(f"  platform: {cfg.platform} · {cfg.width}x{cfg.height}@{cfg.fps} · {cfg.target_lufs} LUFS · "
          f"max {cfg.max_rounds} review rounds · auto-approve {'on' if cfg.auto_approve else 'off'}")
    print(f"  publish targets: {', '.join(cfg.publish_targets)} (auto-publish {'on' if cfg.auto_publish else 'off'})")
    leads = [n for n, ok in (("whop", cfg.key("WHOP_API_KEY")), ("reddit", cfg.base.key("REDDIT_CLIENT_ID")),
                             ("youtube", cfg.base.key("YOUTUBE_API_KEY")), ("feeds", cfg.lead_feeds)) if ok]
    print(f"  lead sources: {', '.join(leads) or 'manual only (noze agency lead add <url> --terms-file …)'}")
    print(f"  LLM budget: ${cfg.job_budget_usd:.2f}/source, ${cfg.daily_budget_usd:.2f}/day")


# -- campaigns & leads ------------------------------------------------------------------------------------
def cmd_campaign(args) -> None:
    ax = _ax(args)
    if args.action == "add":
        from .pipeline import Agency

        if not args.name:
            sys.exit("usage: noze agency campaign add <name> --terms-file terms.txt [--url …]")

        terms = _read_terms(args)
        if not terms and not args.own:
            sys.exit("paste the campaign terms (--terms '…' / --terms-file terms.txt / --terms - for stdin) — they "
                     "are the studio's proof that the creator invited clipping")
        if args.own:
            terms = terms or "Our own content: we hold the rights and may clip and repost it freely."
        cid = Agency(ax).create_campaign(args.name, terms=terms, url=args.url or "", creator=args.creator or "")
        c = ax.store.get_campaign(cid)
        b = c["brief"]
        print(f"✓ campaign #{cid} '{c['name']}'")
        print(f"  permission: {'granted — ' + b['permission']['evidence'][:120] if b['permission']['granted'] else 'NOT found in the terms'}")
        print(f"  payout: {b['payout']['model']} {b['payout']['rate_usd'] or ''} per {b['payout']['per'] or '?'} · "
              f"length {b['clip_length']['min_s'] or '?'}-{b['clip_length']['max_s'] or '?'}s · platforms "
              f"{', '.join(b['platforms']) or '?'}")
        req = b["requirements"]
        print(f"  must include: {' '.join(req['hashtags'] + req['mentions']) or '—'}"
              + (f" · disclosure {req['disclosure']}" if req.get("disclosure") else "")
              + (f" · CTA '{req['cta']}'" if req.get("cta") else ""))
        if b.get("risks"):
            print(f"  ⚠ risks: {', '.join(b['risks'])}")
        print(f"  drop source videos into {ax.cfg.inbox_dir / c['name']} or run: noze agency submit <video> "
              f"--campaign '{c['name']}'")
    elif args.action == "list":
        for c in ax.store.list_campaigns():
            n = len(ax.store.list_jobs(kind="clip", campaign_id=c["id"], states=["delivered"], limit=10000))
            print(f"#{c['id']:<3} {c['name'][:40]:40} {c['status']:8} permission:"
                  f"{'yes' if (c['permission'] or {}).get('granted') else 'NO ':3}  delivered clips: {n}")
    elif args.action == "show":
        c = ax.store.get_campaign(args.name)
        if not c:
            sys.exit(f"no campaign {args.name!r}")
        print(json.dumps({k: c[k] for k in ("id", "name", "creator", "status", "brief", "permission")}, indent=2,
                         ensure_ascii=False, default=str))


def cmd_lead(args) -> None:
    from .leads import LeadFinder

    ax = _ax(args)
    lf = LeadFinder(ax)
    if args.action == "scout":
        rep = lf.scout()
        print("sources: " + ", ".join(f"{k}: {v}" for k, v in rep["sources"].items()))
        for q in rep["qualified"]:
            print(f"  #{q['id']} [{q['decision']:6}] {q['score']:5.0f}  {q['title'][:80]}")
        if not rep["new"]:
            print("no new leads (configure WHOP_API_KEY / REDDIT_* / YOUTUBE_API_KEY / AGENCY_LEAD_FEEDS, or add "
                  "campaigns you found by hand with `noze agency lead add <url> --terms-file terms.txt`)")
    elif args.action == "add":
        url = args.url or args.id
        if not url:
            sys.exit("usage: noze agency lead add <url> [--terms-file terms.txt]")
        try:
            q = lf.add_manual(url, _read_terms(args), title=args.title or "", creator=args.creator or "")
        except PermissionError as exc:
            sys.exit(str(exc))
        print(f"lead #{q['id']}: {q['decision']} (score {q['score']:.0f}) — {q['title'][:80]}")
        print(f"  accept it with: noze agency lead accept {q['id']}")
    elif args.action == "list":
        for l in ax.store.list_leads(args.status or None, limit=args.limit):
            print(f"#{l['id']:<4} {l['status']:9} {l['decision'] or '-':6} {l['score'] if l['score'] is not None else '-':>5}"
                  f"  {l['source'][:18]:18} {l['title'][:70]}")
    elif args.action == "show":
        l = ax.store.get_lead(int(args.id))
        if not l:
            sys.exit("no such lead")
        print(f"#{l['id']} {l['title']}\n{l['url']}\nstatus {l['status']} · decision {l['decision']} · score {l['score']}")
        print("reasons:\n  " + "\n  ".join(l["reasons"] or ["—"]))
        print(f"outreach draft (not sent):\n{l['outreach']}")
    elif args.action == "accept":
        cid = lf.accept(int(args.id), args.name or "")
        c = ax.store.get_campaign(cid)
        print(f"✓ campaign #{cid} '{c['name']}' created from lead #{args.id}"
              f" (permission {'granted' if (c['permission'] or {}).get('granted') else 'NOT recorded'})")


# -- production ------------------------------------------------------------------------------------------
def _load_vod_map(ref: str | None) -> list[dict] | None:
    """``--vod-map`` = a ``*.vodmap.json`` written by ``fetch_pack`` (a list, or ``{"vod_map": [...]}``) or inline JSON."""
    if not ref:
        return None
    text = Path(ref).read_text(encoding="utf-8") if Path(ref).exists() else ref
    try:
        data = json.loads(text)
        data = data.get("vod_map") if isinstance(data, dict) else data
        return [{"file_start": float(x["file_start"]), "file_end": float(x["file_end"]),
                 "vod_start": float(x["vod_start"])} for x in data] or None
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit(f"bad --vod-map ({exc}): expected the *.vodmap.json from `noze agency scan`/fetch_pack")


def _load_moments(path: str | None) -> list[dict] | None:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    picks = data.get("picks", data.get("chosen")) if isinstance(data, dict) else data
    if not isinstance(picks, list) or not all(isinstance(m, dict) and "start_s" in m for m in picks):
        raise SystemExit(f"--moments {path}: expected the scan's *.moments.json (a list of moments under 'picks')")
    return picks


def cmd_submit(args) -> None:
    ag = _agency(args)
    jid = ag.submit(args.source, args.campaign, references=args.ref or [], clips=args.clips,
                    own_content=args.own, notes=args.notes or "", signals_url=args.vod_url or "",
                    offset_s=args.vod_offset or 0.0, internal_test=args.internal_test,
                    vod_map=_load_vod_map(args.vod_map), moments=_load_moments(args.moments))
    print(f"✓ source job #{jid} queued — run `noze agency run` (or keep `noze agency run --forever` going)")


def cmd_fetch(args) -> None:
    from .media.ffmpeg import MediaError
    from .media.fetch import fetch_range, fmt_hms

    a, b = args.from_, args.to
    out = Path(args.output) if args.output else Path.cwd() / f"vod_{fmt_hms(a).replace(':', '')}-{fmt_hms(b).replace(':', '')}.mp4"
    t0 = time.time()
    try:
        fetch_range(args.url, a, b, out, workers=args.workers)
    except (MediaError, ValueError) as exc:
        raise SystemExit(f"fetch failed: {exc}")
    print(f"✓ {out}  ({fmt_hms(b - a)}, {out.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f}s, decoded clean)")
    print("  only clip content the campaign lets you clip. Next:")
    print(f'  noze agency submit "{out}" --campaign <name> --vod-url "{args.url}" --vod-offset {a:g}')


AUDIO_BYTES_PER_S = 20_000   # Twitch audio_only ~160 kbps
VIDEO_BYTES_PER_S = 1_000_000  # re-encoded 1080p60 at crf 18 lands around 6-10 Mbps; this is a ceiling-ish estimate


def _mb(n: float) -> str:
    return f"{n / 1e6:,.0f} MB"


def cmd_scan(args) -> None:
    """Audio-only scan of a stream window -> transcript + chat/clip signals -> ``Analyst.scan_arcs`` -> (unless
    --dry-run) download only the picked pieces, glued into one pack with a vod_map for ``submit``."""
    from .media.fetch import fetch_audio_range, fetch_pack, fmt_hms
    from .media.ffmpeg import MediaError
    from .media.signals import collect_signals, parse_vod_url
    from .media.transcribe import all_words, transcribe
    from .roles.analyst import fetch_plan

    a, b = args.from_, args.to
    kind = parse_vod_url(args.url)
    if not kind:
        raise SystemExit("scan needs a Twitch VOD or YouTube link")
    if b <= a:
        raise SystemExit("--to must be after --from")
    if (b - a) > args.max_hours * 3600:
        raise SystemExit(f"window is {(b - a) / 3600:.1f} h, over --max-hours {args.max_hours:g} "
                         "(audio + transcript + signals of that much is slow; scan it in pieces or raise the cap)")
    ag = _agency(args)
    camp = ag.store.get_campaign(args.campaign)
    if not camp:
        raise SystemExit(f"no campaign {args.campaign!r} (noze agency campaign add …)")
    brief = ag._brief({"campaign_id": camp["id"]})
    cache = ag.cfg.root / "cache" / "scan" / f"{kind[1]}_{int(a)}_{int(b)}"
    cache.mkdir(parents=True, exist_ok=True)
    print(f"scan {args.url}  {fmt_hms(a)}-{fmt_hms(b)} ({fmt_hms(b - a)})  campaign '{camp['name']}'")

    audio = cache / "audio.m4a"
    t0 = time.time()
    from .media.fetch import verify_audio
    if audio.exists():  # a cache hit must still be a whole, decodable window (not a truncated leftover)
        try:
            verify_audio(audio, b - a)
        except MediaError as exc:
            print(f"  cached audio unusable ({exc}); downloading again")
            audio.unlink(missing_ok=True)
            for stale in ("transcript.json", "signals.json"):  # built from the bad audio: never reuse them
                (audio.parent / stale).unlink(missing_ok=True)
    if not audio.exists():
        print(f"  audio-only download, ~{_mb((b - a) * AUDIO_BYTES_PER_S)} …")
        try:
            fetch_audio_range(args.url, a, b, audio, workers=args.workers)
        except (MediaError, ValueError) as exc:
            raise SystemExit(f"audio fetch failed: {exc}")
        print(f"  audio ready ({audio.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f}s)")
    else:
        print(f"  audio cached ({audio.stat().st_size / 1e6:.0f} MB)")

    names = [brief.get("creator") or ""] + [h.rsplit("/", 1)[-1] for h in brief.get("creator_handles") or []]
    hint = ", ".join(dict.fromkeys(n.lstrip("@") for n in names if n))
    tr = transcribe(audio, ag.cfg.transcriber, ag.cfg.whisper_model, language=brief.get("language") or None,
                    cache=cache / "transcript.json", hint=f"{hint}." if hint else "")
    print(f"  transcript: {tr.get('source')} ({len(all_words(tr))} words)")
    sig = collect_signals(audio, cache, url=args.url, offset_s=a, allow_network=True,
                          models_dir=ag.cfg.root / "cache" / "models")
    print(f"  signals: {', '.join(sig.get('sources') or []) or 'none'}; {len(sig.get('peaks') or [])} peaks, "
          f"{len(sig.get('clips') or [])} viewer clips")

    length = brief.get("clip_length") or {}
    min_s = float(length.get("min_s") or ag.cfg.min_clip_s)
    max_s = float(length.get("max_s") or ag.cfg.max_clip_s)
    job = ag.store.get_job(ag.store.create_job("scan", "scanned", campaign_id=camp["id"], title=f"scan {kind[1]}",
                                               input={"url": args.url, "from": a, "to": b}))
    picks = list(ag.analyst.scan_arcs(job, tr, sig, brief, args.clips, min_s, max_s, gap_min_s=args.min_gap))
    # the audio file's seconds start at ``--from``: move every picked part onto VOD time
    for m in picks:
        m["start_s"], m["end_s"] = m["start_s"] + a, m["end_s"] + a
        for part in m.get("parts") or []:
            part["start_s"], part["end_s"] = part["start_s"] + a, part["end_s"] + a
    if not picks:
        raise SystemExit("no clip candidates in that window (try a wider window or another campaign brief)")
    print(f"\n{len(picks)} candidate(s):")
    for i, m in enumerate(picks, 1):
        print(f"#{i} [{m.get('structure', 'linear')}] emotion={m.get('emotion') or '-'} "
              f"overall={m.get('overall', '?')}  {m.get('title', '')[:70]}")
        if m.get("story"):
            print(f"    story: {str(m['story'])[:200]}")
        for j, part in enumerate(m.get("parts") or [], 1):
            print(f"    part {j}: {fmt_hms(part['start_s'])}-{fmt_hms(part['end_s'])}  {part.get('role', '')}")
        if m.get("rationale"):
            print(f"    why: {str(m['rationale'])[:200]}")
    ranges = [(max(a, x), min(b, y)) for x, y in fetch_plan(picks)]
    ranges = [(x, y) for x, y in ranges if y > x]
    total = sum(y - x for x, y in ranges)
    print(f"\nvideo to download: {len(ranges)} piece(s), {fmt_hms(total)} total, ~{_mb(total * VIDEO_BYTES_PER_S)} "
          f"(instead of ~{_mb((b - a) * VIDEO_BYTES_PER_S)} for the whole window)")
    for x, y in ranges:
        print(f"    {fmt_hms(x)}-{fmt_hms(y)}")
    if args.dry_run:
        print("--dry-run: no video fetched.")
        return
    out = Path(args.output) if args.output else cache / "pack.mp4"
    t0 = time.time()
    try:
        out, vod_map = fetch_pack(args.url, ranges, out, workers=args.workers)
    except (MediaError, ValueError) as exc:
        raise SystemExit(f"pack fetch failed: {exc}")
    sidecar = out.with_name(out.name + ".vodmap.json")
    picks_file = out.with_name(out.name + ".moments.json")
    picks_file.write_text(json.dumps({"picks": picks}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {out}  ({out.stat().st_size / 1e6:.0f} MB, {time.time() - t0:.0f}s)  vod map: {sidecar}")
    granted = (brief.get("permission") or {}).get("granted")
    flags = (f'--campaign "{camp["name"]}" --vod-url "{args.url}" --vod-map "{sidecar}" --moments "{picks_file}" '
             f'--clips {args.clips}')
    if not granted:
        flags += " --internal-test"
        print("  this campaign has no clipping permission on record: --internal-test renders for your review only "
              "(never delivered/published).")
    print("  only clip content the campaign lets you clip. Next:")
    print(f'  noze agency submit "{out}" {flags}')


GTA_WORDS = re.compile(r"gta|grand theft|\bvi\b|\b6\b", re.I)


def cmd_vods(args) -> None:
    from datetime import datetime, timedelta, timezone

    from .media.fetch import fmt_hms
    from .media.signals import twitch_clips, twitch_vods

    try:
        vods = twitch_vods(args.login, limit=40)
        clips = twitch_clips(args.login, "LAST_MONTH" if args.days > 7 else "LAST_WEEK")
    except Exception as exc:  # network down / the unofficial endpoint changed
        raise SystemExit(f"twitch lookup failed: {exc}")
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    shown = 0
    for v in vods:
        try:
            when = datetime.fromisoformat(v["created_at"].replace("Z", "+00:00"))
        except ValueError:
            when = None
        if when and when < cutoff:
            continue
        shown += 1
        mine = sorted((c for c in clips if c["vod_id"] == v["id"]), key=lambda c: -c["views"])
        flag = "  <== GTA" if GTA_WORDS.search(v["title"]) else ""
        stamp = f"{when:%Y-%m-%d %H:%M}Z  " if when else ""
        print(f"{v['id']}  {stamp}{fmt_hms(v['length_s'])}  {v['views']:,} views  {v['title'][:70]}{flag}")
        print(f"    viewer clips: {len(mine)}")
        for c in mine[:3]:
            print(f"      {fmt_hms(c['start_s'])}  {c['views']:,} views  {c['title'][:60]}")
        print(f"    https://www.twitch.tv/videos/{v['id']}")
    if not shown:
        print(f"no past broadcasts of {args.login} in the last {args.days} days")


def cmd_run(args) -> None:
    import logging

    ag = _agency(args)
    if not args.verbose:
        logging.getLogger("noze").setLevel(logging.INFO)
    print("studio running — Ctrl+C to stop" if args.forever else "processing the queue until it's idle…")
    try:
        ag.run(idle_sleep=args.interval, once=not args.forever)
    except KeyboardInterrupt:
        print("stopped")
    _print_status(ag.ax, limit=12)


def _print_status(ax, limit: int = 30) -> None:
    from .roles import Manager

    st = ax.store
    counts = st.state_counts("clip")
    print("clips: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none yet"))
    for j in st.list_jobs(limit=limit):
        extra = f" r{j['round']}" if j["kind"] == "clip" and j["round"] else ""
        err = f"  ⚠ {j['error'][:70]}" if j.get("error") else ""
        print(f"  #{j['id']:<4} {j['kind']:6} {j['state'] + extra:16} {j['title'][:55]:55} {_ago(j['updated_at'])}{err}")
    for a in Manager(ax).monitor()[:10]:
        print(f"  [{a['level']}] {a['message']}")
    print(f"LLM spend last 24h: ${st.spend(since=time.time() - 86400):.2f}")


def cmd_status(args) -> None:
    _print_status(_ax(args), limit=args.limit)


def cmd_show(args) -> None:
    ax = _ax(args)
    st = ax.store
    j = st.get_job(int(args.job))
    if not j:
        sys.exit("no such job")
    print(f"#{j['id']} {j['kind']} '{j['title']}' — {j['state']} (round {j['round']}, canary {bool(j['canary'])})")
    if j.get("error"):
        print(f"error: {j['error']}")
    for r in st.reviews(j["id"]):
        print(f"  review r{r['round']} by {r['reviewer']}: {r['verdict']} {r['score'] if r['score'] is not None else ''}"
              f" — {r['summary'][:150]}")
        for i in r["issues"][:8]:
            tc = f"@{i['timecode_s']}s " if i.get("timecode_s") is not None else ""
            print(f"     [{i['severity']}] {tc}{i['description'][:120]}  → {i['fix'][:100]}")
    print("timeline:")
    for e in st.events(j["id"], limit=args.limit):
        print(f"  {time.strftime('%H:%M:%S', time.localtime(e['ts']))} {e['role']:9} {e['message'][:140]}")
    for a in st.artifacts(j["id"]):
        if a["path"]:
            print(f"  {a['kind']} v{a['version']}: {a['path']}")


def cmd_decide(args) -> None:
    ag = _agency(args)
    state = ag.decide(int(args.clip), args.decision, args.note or [])
    print(f"clip #{args.clip} → {state}" + ("" if state != "revising" else " (run `noze agency run` to revise)"))


def cmd_clip_add(args) -> None:
    a, _, b = args.range.partition("-")
    cid = _agency(args).add_clip(int(args.source), float(a), float(b), args.title or "")
    print(f"✓ clip job #{cid} assigned — run `noze agency run`")


def cmd_retry(args) -> None:
    print(f"job #{args.job} → {_agency(args).retry(int(args.job))}")


def cmd_publish(args) -> None:
    from .publish import Publisher

    info = Publisher(_ax(args)).publish(int(args.clip), args.target)
    print(json.dumps(info, indent=2))


def cmd_metrics(args) -> None:
    ax = _ax(args)
    if not ax.store.get_job(int(args.clip)):
        sys.exit("no such clip")
    for key in ("views", "likes", "comments", "shares", "retention", "earnings"):
        val = getattr(args, key)
        if val is not None:
            ax.store.add_metric(int(args.clip), key, float(val), {"url": args.url or ""})
    if args.url:
        ax.store.add_publication(int(args.clip), args.platform or "post", "posted", url=args.url)
    print(f"✓ recorded performance for clip #{args.clip} — the scout now prefers your best performers as references")


def cmd_report(args) -> None:
    from .reports import team_report

    ax = _ax(args)
    path, _ = team_report(ax, days=args.days)
    text = path.read_text(encoding="utf-8")
    print(text)
    print(f"(saved to {path})")
    if args.notify:
        from .publish import Publisher

        Publisher(ax).notify(text[:3800])
        print("sent to your webhook/Telegram")


def cmd_playbook(args) -> None:
    ax = _ax(args)
    st = ax.store
    if args.action == "show":
        statuses = None if args.all else ["active", "candidate"]
        rows = st.lessons(args.role or None, statuses)
        for l in rows:
            print(f"[{l['id']}] {l['status']:11} {l['role']:8} h={l['helpful']} x={l['harmful']} u={l['uses']} "
                  f"{l['scope'] if l['scope'] != 'global' else ''}\n      {l['text']}")
        print(f"playbook v{st.current_version()} — {len(rows)} lesson(s)")
    elif args.action == "add":
        if not (args.role and args.text):
            sys.exit("playbook add needs --role and --text")
        lid = st.add_lesson(args.role, args.text if args.text.endswith(".") else args.text + ".",
                            section=args.section, scope=args.scope, status="active", origin="human", protected=True,
                            version=st.current_version() + 1)
        st.update_lesson(lid, activated_at=time.time())
        st.new_version(f"human lesson {lid}", {"added": [lid]})
        print(f"✓ {lid} added to the {args.role} playbook (active, protected from automatic pruning)")
    elif args.action in ("retire", "restore"):
        if not args.id or not st.get_lesson(args.id):
            sys.exit("give an existing lesson id, e.g. noze agency playbook retire edi-00003")
        st.update_lesson(args.id, status="archived" if args.action == "retire" else "active",
                         activated_at=time.time() if args.action == "restore" else None)
        st.new_version(f"{args.action} {args.id}", {args.action: [args.id]})
        print(f"✓ {args.id} {args.action}d")
    elif args.action == "versions":
        for v in st.versions(limit=30):
            print(f"v{v['version']:<4} {time.strftime('%Y-%m-%d %H:%M', time.localtime(v['created_at']))} "
                  f"{v['status']:11} {v['note']}")


def cmd_analyze(args) -> None:
    """Measured facts + frame sheets for any video (what the analyst/reviewer see)."""
    from .media.analyze import measure
    from .media.transcribe import for_prompt, speech_rate, transcribe

    ax = _ax(args)
    video = Path(args.video).resolve()
    out = ax.cfg.root / "cache" / "analyze" / video.stem
    facts = measure(video, with_frames_dir=out / "frames")
    tr = transcribe(video, ax.cfg.transcriber, ax.cfg.whisper_model, cache=out / "transcript.json")
    facts["speech_wpm"] = speech_rate(tr)
    facts.pop("onsets", None)
    print(json.dumps(facts, indent=2, default=str))
    if args.transcript:
        print(for_prompt(tr, max_chars=20000) or "(no transcript)")


def cmd_frames(args) -> None:
    """Labelled frame sheets of a clip's latest render (or any video file)."""
    from .media.analyze import contact_sheets, extract_frames, sample_times
    from .media.ffmpeg import probe

    ax = _ax(args)
    is_id = str(args.target).isdigit()
    if getattr(args, "debug", False) and not is_id:
        sys.exit("--debug needs a clip id (it draws what the reviewer measured from that clip's plan)")
    path = Path(args.target)
    if not path.is_file():
        if not is_id:
            sys.exit(f"no such video file or clip id: {args.target}")
        job = ax.store.get_job(int(args.target))
        if not job:
            sys.exit(f"no such clip: #{args.target}")
        data = job.get("data") or {}
        path = Path(data.get("final_path") or data.get("render_path") or "")
        if not path.is_file():  # Path("") is "." — a folder, so this also covers "never rendered"
            sys.exit("no render for that clip yet")
    dur = probe(path)["duration"]
    times = sample_times(dur, [], n=args.n)
    st = path.stat()  # re-renders reuse file names: key the cache by content too, or old frames come back
    out = ax.cfg.root / "cache" / "frames" / f"{path.stem}_{int(st.st_mtime)}_{st.st_size}"
    if getattr(args, "debug", False):
        for p in _debug_frames(ax, int(args.target), path, times, out / "debug"):
            print(p)
        return
    frames = extract_frames(path, times, out, width=360)
    for p in contact_sheets(frames, times, out / "sheet"):
        print(p)


def _debug_frames(ax, clip_id: int, path: Path, times: list[float], out: Path) -> list[Path]:
    """Full-size frames with what the reviewer measured drawn on top: safe zone (yellow), each text
    layer's box (cyan caption, magenta title/label/cta, orange watermark), cam band seam and face area."""
    from PIL import Image, ImageDraw

    from .media.analyze import extract_frames
    from .media.qc import layout_lint, measure_cam_faces, stack_seams
    from .media.timeline import Timeline
    from .pipeline import Agency
    from .standards import safe_zone

    job = ax.store.get_job(clip_id)
    plan = ((ax.store.artifact(clip_id, "plan") or {}).get("data")) if job else None
    if not plan:
        sys.exit("--debug needs a clip id with a plan")
    c = Agency(ax).clip_ctx(job)
    cfg = ax.cfg
    p = c["source_info"]
    dbg: dict = {}
    src = (int(p["width"]), int(p["height"])) if p.get("width") else None
    # the same measured faces the reviewer uses (output frames), so the green box is where the face really is
    measured = measure_cam_faces(str(path), stack_seams(plan, src, cfg.width, cfg.height), out / "cam")
    issues = layout_lint(plan, c["brief"], words=Timeline(plan["segments"]).map_words(c["words"]), width=cfg.width,
                         height=cfg.height, platform=cfg.platform, fonts_dir=cfg.fonts_dir, src_size=src, debug=dbg,
                         measured_faces=measured, video_path=str(path))
    for i in issues:
        print(f"  [{i['severity']}] {i['id']}: {i['description'][:140]}")
    frames = extract_frames(path, times, out, width=cfg.width)
    z = safe_zone(cfg.platform, cfg.width, cfg.height)
    colors = {"caption": (0, 220, 255), "watermark": (255, 150, 0)}
    shots = []
    for t, f in zip(times, frames):
        im = Image.open(f).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle((z["left"], z["top"], cfg.width - z["right"], cfg.height - z["bottom"]), outline=(255, 230, 0), width=3)
        for a, b, band in dbg.get("seams", []):
            if a - 0.01 <= t < b:
                d.line((0, band, cfg.width, band), fill=(0, 255, 0), width=3)
        for a, b, area, measured in dbg.get("faces", []):
            if a - 0.01 <= t < b:
                d.rectangle(area, outline=(0, 255, 0) if measured else (120, 255, 120), width=3)
        for ly in dbg.get("layers", []):
            if ly["a"] <= t < ly["b"]:
                d.rectangle(ly["box"], outline=colors.get(ly["kind"], (255, 0, 200)), width=4)
        d.text((12, cfg.height - 40), f"t={t:.2f}s", fill=(255, 255, 255))
        dst = out / f"debug_{t:07.2f}.jpg"
        im.save(dst, quality=88)
        shots.append(dst)
    return shots


def cmd_plan(args) -> None:
    """Print a clip's current edit plan, or replace it (--set plan.json) and queue a re-render."""
    ax = _ax(args)
    job = ax.store.get_job(int(args.clip))
    if not job or job["kind"] != "clip":
        sys.exit("no such clip")
    if not args.set:
        art = ax.store.artifact(job["id"], "plan")
        print(json.dumps((art or {}).get("data") or {}, indent=2, ensure_ascii=False))
        return
    from .pipeline import Agency
    from .schemas import EDIT_PLAN, conform

    ag = Agency(ax)
    c = ag.clip_ctx(job)
    plan = conform(json.loads(Path(args.set).read_text(encoding="utf-8")), EDIT_PLAN)
    if args.moment:  # a human editor may re-cut the moment itself; plans are clamped to it
        a, _, b = args.moment.partition("-")
        moment = dict(c["moment"], start_s=float(a), end_s=float(b), structure="linear",
                      parts=[{"start_s": float(a), "end_s": float(b), "role": "build", "label": ""}])
        ax.store.update_job(job["id"], input=dict(job["input"], moment=moment))
        c["moment"] = moment
    prep = ag.editor.prepare(job, c["source"], c["moment"], c["transcript"], c["blueprint"], c["source_info"])
    plan = ag.editor.finalize(plan, c["moment"], c["brief"], c["blueprint"], prep)
    v = ax.store.put_artifact(job["id"], "plan", plan, role="human")
    ax.store.update_job(job["id"], state="rendering", next_run=0, error="", finished_at=None)
    ax.store.log(job["id"], "human", "plan", f"plan v{v} set by hand — re-rendering")
    print(f"✓ plan v{v} saved; run `noze agency run` to render and review it")


def cmd_learn(args) -> None:
    ax = _ax(args)
    lr = ax.learner
    print(json.dumps({"promote_prune": lr.promote_and_prune(), "mined": lr.mine_recurring(),
                      "guard": lr.regression_guard()}, indent=2))


# -- wiring --------------------------------------------------------------------------------------------------
def register(sub: argparse._SubParsersAction) -> None:
    ag = sub.add_parser("agency", help="the automated clipping studio (manager, scout, analyst, editor, reviewer)")
    s = ag.add_subparsers(dest="agency_cmd", required=True)

    p = s.add_parser("init", help="create folders, fetch caption fonts, prepare SFX, check tools")
    p.set_defaults(func=cmd_init)
    p = s.add_parser("doctor", help="check tools, credentials and settings")
    p.set_defaults(func=cmd_doctor)

    p = s.add_parser("campaign", help="campaigns = briefs + permission records")
    p.add_argument("action", choices=("add", "list", "show"))
    p.add_argument("name", nargs="?")
    p.add_argument("--terms", help="campaign terms text, or - to read stdin")
    p.add_argument("--terms-file")
    p.add_argument("--url")
    p.add_argument("--creator")
    p.add_argument("--own", action="store_true", help="your own content (you hold the rights)")
    p.set_defaults(func=cmd_campaign)

    p = s.add_parser("lead", help="find and qualify creators who hire clippers")
    p.add_argument("action", choices=("scout", "add", "list", "show", "accept"))
    p.add_argument("id", nargs="?", help="lead id (show/accept) or the URL (add)")
    p.add_argument("--url")
    p.add_argument("--terms")
    p.add_argument("--terms-file")
    p.add_argument("--title")
    p.add_argument("--creator")
    p.add_argument("--name", help="campaign name when accepting")
    p.add_argument("--status")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_lead)

    p = s.add_parser("submit", help="queue a long video for clipping")
    p.add_argument("source", help="file path, direct video URL, noze:<asset id>, or a platform link (opt-in)")
    p.add_argument("--campaign")
    p.add_argument("--clips", type=int)
    p.add_argument("--ref", action="append", help="reference clip (repeatable)")
    p.add_argument("--own", action="store_true", help="your own content (no campaign needed)")
    p.add_argument("--internal-test", action="store_true",
                   help="render for your review only while the campaign's permission is missing: clips can "
                        "never be delivered or published until real terms grant permission")
    p.add_argument("--notes")
    p.add_argument("--vod-url", help="the Twitch VOD / YouTube page this file came from (chat, viewer clips, "
                                      "most-replayed are read from it)")
    p.add_argument("--vod-offset", type=_hms, default=0.0,
                   help="where this file starts inside that VOD (HH:MM:SS or seconds)")
    p.add_argument("--vod-map", help="story pack: the *.vodmap.json (file second -> VOD second per piece) that "
                                     "`noze agency scan` wrote next to the pack; replaces --vod-offset")
    p.add_argument("--moments", help="story pack: the *.moments.json the scan wrote (its picked moments, VOD "
                                     "seconds) — used first, so a found cross-period arc is not re-mined away")
    p.set_defaults(func=cmd_submit)

    p = s.add_parser("scan", help="scan a whole stream window from its AUDIO only, then download just the pieces "
                                  "the best story clips need (story pack)")
    p.add_argument("url", help="Twitch VOD / YouTube link")
    p.add_argument("--from", dest="from_", type=_hms, default=0.0, help="window start, HH:MM:SS (default 0)")
    p.add_argument("--to", type=_hms, required=True, help="window end, HH:MM:SS")
    p.add_argument("--campaign", required=True)
    p.add_argument("--clips", type=int, default=3)
    p.add_argument("--min-gap", type=float, default=600.0,
                   help="seconds between setup and payoff for a cross-period arc (default 600)")
    p.add_argument("--max-hours", type=float, default=8.0, help="refuse a window longer than this (disk guard)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("-o", "--output", help="where to write the pack mp4 (default: next to the scan cache)")
    p.add_argument("--dry-run", action="store_true", help="show the candidates + download size, fetch no video")
    p.set_defaults(func=cmd_scan)

    p = s.add_parser("fetch", help="download just a section of a long VOD, fast (Twitch segments in parallel)")
    p.add_argument("url")
    p.add_argument("--from", dest="from_", type=_hms, default=0.0, help="start, HH:MM:SS (default 0)")
    p.add_argument("--to", type=_hms, required=True, help="end, HH:MM:SS")
    p.add_argument("-o", "--output")
    p.add_argument("--workers", type=int, default=8)
    p.set_defaults(func=cmd_fetch)

    p = s.add_parser("vods", help="latest Twitch VODs of a channel + their top viewer clips (find the GTA stream)")
    p.add_argument("login")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_vods)

    p = s.add_parser("run", help="process the queue (until idle, or --forever)")
    p.add_argument("--forever", action="store_true")
    p.add_argument("--interval", type=float, default=5.0)
    p.set_defaults(func=cmd_run)

    p = s.add_parser("status", help="the studio board")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_status)

    p = s.add_parser("show", help="one job: reviews, timeline, files")
    p.add_argument("job")
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(func=cmd_show)

    for name, decision in (("approve", "approve"), ("reject", "reject"), ("changes", "changes")):
        p = s.add_parser(name, help=f"{decision} a clip yourself")
        p.add_argument("clip")
        p.add_argument("--note", action="append", help="what to change (repeatable)")
        p.set_defaults(func=cmd_decide, decision=decision)

    p = s.add_parser("clip", help="manager: assign an extra clip at a hand-picked moment")
    cs = p.add_subparsers(dest="clip_cmd", required=True)
    q = cs.add_parser("add", help="clip add <source id> START-END [--title …]")
    q.add_argument("source")
    q.add_argument("range", help="source seconds, e.g. 952.3-1015")
    q.add_argument("--title")
    q.set_defaults(func=cmd_clip_add)

    p = s.add_parser("retry", help="resume a failed/blocked job from its last good step")
    p.add_argument("job")
    p.set_defaults(func=cmd_retry)

    p = s.add_parser("publish", help="upload an approved clip to a platform / notify")
    p.add_argument("clip")
    p.add_argument("--target", required=True, choices=("youtube", "tiktok", "webhook", "rclone"))
    p.set_defaults(func=cmd_publish)

    p = s.add_parser("metrics", help="record how a posted clip performed (feeds the learning loop)")
    p.add_argument("clip")
    for key in ("views", "likes", "comments", "shares", "retention", "earnings"):
        p.add_argument(f"--{key}", type=float)
    p.add_argument("--url")
    p.add_argument("--platform")
    p.set_defaults(func=cmd_metrics)

    p = s.add_parser("report", help="team report (KPIs per role, problems, spend, learning)")
    p.add_argument("--days", type=float, default=7.0)
    p.add_argument("--notify", action="store_true", help="also send it to the webhook/Telegram")
    p.set_defaults(func=cmd_report)

    p = s.add_parser("playbook", help="what the team has learned")
    p.add_argument("action", nargs="?", default="show", choices=("show", "add", "retire", "restore", "versions"))
    p.add_argument("id", nargs="?", help="lesson id (retire/restore)")
    p.add_argument("--role", choices=("manager", "scout", "analyst", "editor", "reviewer"))
    p.add_argument("--text")
    p.add_argument("--section", default="general")
    p.add_argument("--scope", default="global", help="global | campaign:<id> | creator:<name>")
    p.add_argument("--all", action="store_true", help="include archived/quarantined")
    p.set_defaults(func=cmd_playbook)

    p = s.add_parser("analyze", help="measure any video (shots, loudness, silence, frames, transcript)")
    p.add_argument("video")
    p.add_argument("--transcript", action="store_true")
    p.set_defaults(func=cmd_analyze)

    p = s.add_parser("frames", help="labelled frame sheets of a clip render (or a video file)")
    p.add_argument("target", help="clip id or video path")
    p.add_argument("-n", type=int, default=16)
    p.add_argument("--debug", action="store_true",
                   help="full-size frames with the measured text boxes, safe zone, cam seam and face area drawn on")
    p.set_defaults(func=cmd_frames)

    p = s.add_parser("plan", help="show a clip's edit plan, or --set a hand-edited one and re-render")
    p.add_argument("clip")
    p.add_argument("--set", help="path to an edited plan JSON")
    p.add_argument("--moment", help="with --set: new source range START-END in seconds (e.g. 952.3-1015)")
    p.set_defaults(func=cmd_plan)

    p = s.add_parser("learn", help="run promotion/pruning, the issue miner and the regression guard now")
    p.set_defaults(func=cmd_learn)

