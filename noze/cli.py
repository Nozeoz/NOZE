"""Command line: `noze serve`, `noze harvest "neon rain"`, `noze import-folder ~/Assets`, …"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import Settings


def _ctx(args):
    from .context import Context

    return Context(Settings.load(data_dir=args.data_dir))


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def cmd_serve(args) -> None:
    import uvicorn

    from .api import create_app

    settings = Settings.load(data_dir=args.data_dir)
    host = args.host or settings.host
    port = args.port or settings.port
    if host not in ("127.0.0.1", "localhost") and not settings.password:
        print("⚠  Listening on a public interface without NOZE_PASSWORD — anyone on the network can use your bank.")
    app = create_app(settings, start_worker=not args.no_worker)
    print(f"NOZE → http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}  (data: {settings.data_dir})")
    uvicorn.run(app, host=host, port=port, log_level="info" if args.verbose else "warning")


async def _harvest(args, queries: list[str]) -> None:
    from .harvest import Harvester
    from .http import Http
    from .lexicon import parse_query
    from .models import expand_kinds

    ctx = _ctx(args)
    http = Http(ctx.settings)
    h = Harvester(ctx, http)
    kinds = expand_kinds(args.kinds.split(",")) if args.kinds else None
    only = set(args.sources.split(",")) if args.sources else None
    try:
        for q in queries:
            total = 0
            for page in range(1, args.pages + 1):
                rep = await h.search(parse_query(q), kinds=kinds, only=only, page=page, force=args.force)
                total += rep.new_items
                bad = {k: v for k, v in rep.sources.items() if not v.startswith(("ok", "cached"))}
                print(f"  {q!r} p{page}: +{rep.new_items}" + (f"  ({'; '.join(f'{k}: {v}' for k, v in bad.items())})" if bad else ""))
                if rep.exhausted:
                    break
            print(f"✓ {q!r}: {total} items banked")
    finally:
        await http.aclose()
    await _enrich(ctx, args.enrich_limit)


async def _enrich(ctx, limit: int) -> None:
    from .enrich import Enricher
    from .http import Http

    if limit <= 0:
        return
    ctx.ensure_embedder()
    http = Http(ctx.settings)
    e = Enricher(ctx, http)
    done_t = done_e = 0
    try:
        while done_t < limit:
            n = await e.thumbs_batch(32)
            done_t += n
            done_e += await asyncio.to_thread(e.embed_batch, 64)
            if n == 0:
                break
        while True:
            n = await asyncio.to_thread(e.embed_batch, 128)
            done_e += n
            if n == 0:
                break
    finally:
        await http.aclose()
    print(f"✓ thumbnails processed: {done_t}, vectors computed: {done_e} ({ctx.embedder.name})")


def cmd_harvest(args) -> None:
    asyncio.run(_harvest(args, [" ".join(args.query)]))


def cmd_starter(args) -> None:
    from .lexicon import STARTER_TOPICS

    print(f"Harvesting {len(STARTER_TOPICS)} starter topics for motion/design editors…")
    asyncio.run(_harvest(args, STARTER_TOPICS))


def cmd_search(args) -> None:
    from .harvest import Harvester
    from .http import Http
    from .lexicon import parse_query
    from .search import Ranker, SearchRequest

    ctx = _ctx(args)
    ctx.ensure_embedder()
    ranker = Ranker(ctx)
    q = " ".join(args.query)
    req = SearchRequest(q=q, kinds=args.kinds.split(",") if args.kinds else None,
                        usages=args.usage.split(",") if args.usage else None)
    pq = parse_query(q)
    filters, applied = ranker.resolve_filters(req, pq)
    if pq.translated:
        print(f"(searching as: {pq.text})")
    if applied:
        print(f"(auto filters: {applied})")
    if args.live:
        async def live():
            http = Http(ctx.settings)
            try:
                rep = await Harvester(ctx, http).search(pq, kinds=filters.kinds, page=1, timeout=ctx.settings.live_timeout)
                print(f"(live: +{rep.new_items} new from {sum(1 for v in rep.sources.values() if v.startswith('ok'))} sources)")
            finally:
                await http.aclose()
        asyncio.run(live())
    ids = ranker.rank_query(pq, filters)[: args.limit]
    rows = ctx.db.get_assets(ids)
    for i, aid in enumerate(ids, 1):
        a = rows[aid]
        print(f"{i:3}. [{a['kind']:7}] [{a['usage']:13}] {a['title'][:60]:60}  {ctx.source_label(a['source'])}")
        print(f"      {a['page_url'] or a['preview_url']}")
    if pq.vibes:
        print("\nrelated vibes: " + " · ".join(pq.vibes))


def cmd_sources(args) -> None:
    from .harvest import Harvester
    from .http import Http

    ctx = _ctx(args)

    async def run():
        http = Http(ctx.settings)
        try:
            h = Harvester(ctx, http)
            states = ctx.db.source_states()
            for name, s in h.sources.items():
                mark = "✓" if s.enabled else "·"
                note = f"needs {', '.join(s.missing_keys())} → {s.signup_url}" if s.missing_keys() else s.description
                err = (states.get(name) or {}).get("last_error")
                print(f" {mark} {s.label:26} {','.join(s.kinds):28} {note}")
                if err:
                    print(f"     last error: {err[:100]}")
        finally:
            await http.aclose()

    asyncio.run(run())


def cmd_enrich(args) -> None:
    ctx = _ctx(args)
    missing = ctx.db.reset_missing_thumbs(ctx.settings.thumbs_dir)
    if missing:
        print(f"rebuilding {missing} missing thumbnails")
    asyncio.run(_enrich(ctx, args.limit))


def cmd_reindex(args) -> None:
    ctx = _ctx(args)
    ctx.db.reset_embeddings()
    asyncio.run(_enrich(ctx, 10**9))


def cmd_import_folder(args) -> None:
    from .importers.folder import import_folder

    ctx = _ctx(args)

    def progress(n: int, path: Path) -> None:
        if n % 50 == 0:
            print(f"  {n} files… ({path.name})")

    res = import_folder(ctx, Path(args.path), board=args.board, link=args.link,
                        extra_tags=args.tags.split(",") if args.tags else None, progress=progress)
    print(f"✓ imported {res['imported']} files ({res['skipped']} skipped)")
    asyncio.run(_enrich(ctx, 10**9))


def cmd_import_pinterest(args) -> None:
    from .http import Http
    from .importers.pinterest import import_pinterest

    ctx = _ctx(args)

    async def run():
        http = Http(ctx.settings)
        try:
            res = await import_pinterest(ctx, http, token=args.token)
            print(f"✓ imported {res['pins']} pins from {res['boards']} boards (reference-only)")
        finally:
            await http.aclose()

    asyncio.run(run())
    asyncio.run(_enrich(ctx, 10**9))


def cmd_save(args) -> None:
    from .http import Http
    from .importers.web import ingest_url

    ctx = _ctx(args)

    async def run():
        http = Http(ctx.settings)
        try:
            a = await ingest_url(ctx, http, args.url, board=args.board, note=args.note or "")
            print(f"✓ saved: {a['title']} [{a['kind']}]")
        finally:
            await http.aclose()

    asyncio.run(run())


def cmd_export(args) -> None:
    from .exporter import export_board

    ctx = _ctx(args)
    b = ctx.db.board_by_name(args.board)
    if not b:
        sys.exit(f"no board named {args.board!r}")
    res = export_board(ctx, b["id"], Path(args.out))
    print(f"✓ {res['items']} items → {res['path']} ({res['without_file']} without a stored file — press Download in the UI first)")


def cmd_stats(args) -> None:
    ctx = _ctx(args)
    s = ctx.db.stats()
    print(f"assets: {s['assets']}  saved: {s['saved']}  boards: {s['boards']}  vectors: {s['embedded']}")
    print(f"stored originals: {s['stored_files']} files, {_fmt_bytes(s['stored_bytes'])} ({ctx.storage.name})")
    thumbs = sum(p.stat().st_size for p in ctx.settings.thumbs_dir.rglob('*') if p.is_file())
    print(f"thumbnail cache: {s['thumbs']} files, {_fmt_bytes(thumbs)}")
    print("by kind:   " + ", ".join(f"{k} {v}" for k, v in s["by_kind"].items()))
    print("by usage:  " + ", ".join(f"{k} {v}" for k, v in s["by_usage"].items()))
    print("by source: " + ", ".join(f"{ctx.source_label(k)} {v}" for k, v in s["by_source"].items()))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="noze", description="NOZE — your creative asset bank")
    p.add_argument("--data-dir", default=None, help="where the bank lives (default ./noze-data or NOZE_DATA_DIR)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the web app")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.add_argument("--no-worker", action="store_true", help="don't run background crawling/enrichment")
    s.set_defaults(func=cmd_serve)

    for name, fn, helptext in (("harvest", cmd_harvest, "crawl sources for a query into the bank"),
                               ("starter", cmd_starter, "pre-fill the bank with ~50 motion/design topics")):
        h = sub.add_parser(name, help=helptext)
        if name == "harvest":
            h.add_argument("query", nargs="+")
        h.add_argument("--kinds", default="", help="e.g. video,motion,image,audio,icon,font,texture,hdri,3d,code")
        h.add_argument("--sources", default="", help="limit to these sources (comma separated)")
        h.add_argument("--pages", type=int, default=2 if name == "harvest" else 1)
        h.add_argument("--force", action="store_true", help="ignore the query cache")
        h.add_argument("--enrich-limit", type=int, default=400, help="thumbnails to cache right away")
        h.set_defaults(func=fn)

    s = sub.add_parser("search", help="search the bank from the terminal")
    s.add_argument("query", nargs="+")
    s.add_argument("--kinds", default="")
    s.add_argument("--usage", default="", help="usable | free | any")
    s.add_argument("--live", action="store_true", help="also ask the sources")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("sources", help="list sources and whether they're enabled")
    s.set_defaults(func=cmd_sources)

    s = sub.add_parser("enrich", help="cache thumbnails + compute vectors now")
    s.add_argument("--limit", type=int, default=2000)
    s.set_defaults(func=cmd_enrich)

    s = sub.add_parser("reindex", help="recompute all vectors (after installing CLIP)")
    s.set_defaults(func=cmd_reindex)

    s = sub.add_parser("import-folder", help="index an existing asset folder")
    s.add_argument("path")
    s.add_argument("--board", default=None)
    s.add_argument("--link", action="store_true", help="index files in place instead of copying them")
    s.add_argument("--tags", default="")
    s.set_defaults(func=cmd_import_folder)

    s = sub.add_parser("import-pinterest", help="import YOUR boards via Pinterest's official API")
    s.add_argument("--token", default=None)
    s.set_defaults(func=cmd_import_pinterest)

    s = sub.add_parser("save", help="save a URL (image/video/page) into the bank")
    s.add_argument("url")
    s.add_argument("--board", default=None)
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_save)

    s = sub.add_parser("export-board", help="zip a board with CREDITS.txt")
    s.add_argument("board")
    s.add_argument("out")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("stats", help="what's in the bank and how much space it uses")
    s.set_defaults(func=cmd_stats)

    from .agency.cli import register as register_agency

    register_agency(sub)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
