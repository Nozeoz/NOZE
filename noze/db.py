"""SQLite storage for the whole bank: assets (+FTS5), embeddings, boards,
interactions, query cache, interests, jobs, source health, relation graph.

One file, WAL mode, a connection per thread. Plenty for a personal bank of
millions of rows.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .models import Asset

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    author TEXT NOT NULL DEFAULT '',
    author_url TEXT NOT NULL DEFAULT '',
    page_url TEXT NOT NULL DEFAULT '',
    thumb_url TEXT NOT NULL DEFAULT '',
    preview_url TEXT NOT NULL DEFAULT '',
    download_url TEXT NOT NULL DEFAULT '',
    width INTEGER,
    height INTEGER,
    duration REAL,
    license TEXT NOT NULL DEFAULT 'unknown',
    license_label TEXT NOT NULL DEFAULT '',
    license_url TEXT NOT NULL DEFAULT '',
    usage TEXT NOT NULL DEFAULT 'check',
    attribution TEXT NOT NULL DEFAULT '',
    popularity REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '{}',
    colors TEXT,
    dhash TEXT,
    thumb_path TEXT,
    thumb_state INTEGER NOT NULL DEFAULT 0,
    embed_state INTEGER NOT NULL DEFAULT 0,
    blob_key TEXT,
    blob_size INTEGER,
    blob_mime TEXT,
    saved INTEGER NOT NULL DEFAULT 0,
    hidden INTEGER NOT NULL DEFAULT 0,
    fetched_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);
CREATE INDEX IF NOT EXISTS idx_assets_source ON assets(source);
CREATE INDEX IF NOT EXISTS idx_assets_usage ON assets(usage);
CREATE INDEX IF NOT EXISTS idx_assets_fetched ON assets(fetched_at);
CREATE INDEX IF NOT EXISTS idx_assets_thumb_state ON assets(thumb_state, embed_state);
CREATE INDEX IF NOT EXISTS idx_assets_dhash ON assets(dhash);
CREATE INDEX IF NOT EXISTS idx_assets_author ON assets(source, author);

CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
    title, description, tags, author, source,
    content='assets', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS assets_ai AFTER INSERT ON assets BEGIN
    INSERT INTO assets_fts(rowid, title, description, tags, author, source)
    VALUES (new.rowid, new.title, new.description, new.tags, new.author, new.source);
END;
CREATE TRIGGER IF NOT EXISTS assets_ad AFTER DELETE ON assets BEGIN
    INSERT INTO assets_fts(assets_fts, rowid, title, description, tags, author, source)
    VALUES ('delete', old.rowid, old.title, old.description, old.tags, old.author, old.source);
END;
CREATE TRIGGER IF NOT EXISTS assets_au AFTER UPDATE OF title, description, tags, author, source ON assets BEGIN
    INSERT INTO assets_fts(assets_fts, rowid, title, description, tags, author, source)
    VALUES ('delete', old.rowid, old.title, old.description, old.tags, old.author, old.source);
    INSERT INTO assets_fts(rowid, title, description, tags, author, source)
    VALUES (new.rowid, new.title, new.description, new.tags, new.author, new.source);
END;

CREATE TABLE IF NOT EXISTS embeddings (
    asset_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    modality TEXT NOT NULL,
    vec BLOB NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON embeddings(model);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS board_items (
    board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    added_at REAL NOT NULL,
    PRIMARY KEY (board_id, asset_id)
);
CREATE INDEX IF NOT EXISTS idx_board_items_asset ON board_items(asset_id);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY,
    asset_id TEXT NOT NULL,
    action TEXT NOT NULL,
    weight REAL NOT NULL,
    query TEXT NOT NULL DEFAULT '',
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(ts);
CREATE INDEX IF NOT EXISTS idx_interactions_asset ON interactions(asset_id);

CREATE TABLE IF NOT EXISTS query_cache (
    qkey TEXT NOT NULL,
    source TEXT NOT NULL,
    kinds TEXT NOT NULL,
    page INTEGER NOT NULL,
    fetched_at REAL NOT NULL,
    n INTEGER NOT NULL,
    next_cursor TEXT,
    exhausted INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    PRIMARY KEY (qkey, source, kinds, page)
);
CREATE TABLE IF NOT EXISTS query_hits (
    qkey TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    source TEXT NOT NULL,
    rank INTEGER NOT NULL,
    PRIMARY KEY (qkey, asset_id)
);
CREATE INDEX IF NOT EXISTS idx_query_hits_asset ON query_hits(asset_id);

CREATE TABLE IF NOT EXISTS interests (
    id INTEGER PRIMARY KEY,
    query TEXT NOT NULL UNIQUE,
    kinds TEXT NOT NULL DEFAULT '',
    every_hours REAL NOT NULL DEFAULT 24,
    next_page INTEGER NOT NULL DEFAULT 1,
    max_pages INTEGER NOT NULL DEFAULT 5,
    last_run REAL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    result TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id);

CREATE TABLE IF NOT EXISTS source_state (
    source TEXT PRIMARY KEY,
    calls INTEGER NOT NULL DEFAULT 0,
    items INTEGER NOT NULL DEFAULT 0,
    last_ok REAL,
    last_error TEXT,
    last_error_at REAL,
    cooldown_until REAL,
    window_start REAL,
    window_calls INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS edges (
    a TEXT NOT NULL,
    b TEXT NOT NULL,
    kind TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    PRIMARY KEY (a, b, kind)
);
CREATE INDEX IF NOT EXISTS idx_edges_b ON edges(b);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# columns an upsert from a source may overwrite (local state is never touched)
_SOURCE_COLUMNS = (
    "kind", "title", "description", "tags", "author", "author_url", "page_url", "thumb_url", "preview_url",
    "download_url", "width", "height", "duration", "license", "license_label", "license_url", "usage",
    "attribution", "popularity", "created_at", "extra",
)

JSON_COLUMNS = ("tags", "extra", "colors")


def now() -> float:
    return time.time()


def iso(ts: float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds")


@dataclass
class Filters:
    kinds: set[str] | None = None
    usages: set[str] | None = None
    sources: set[str] | None = None
    include_hidden: bool = False
    saved_only: bool = False

    def sql(self, alias: str = "a") -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if self.kinds:
            clauses.append(f"{alias}.kind IN ({','.join('?' * len(self.kinds))})")
            params.extend(sorted(self.kinds))
        if self.usages:
            clauses.append(f"{alias}.usage IN ({','.join('?' * len(self.usages))})")
            params.extend(sorted(self.usages))
        if self.sources:
            clauses.append(f"{alias}.source IN ({','.join('?' * len(self.sources))})")
            params.extend(sorted(self.sources))
        if not self.include_hidden:
            clauses.append(f"{alias}.hidden = 0")
        if self.saved_only:
            clauses.append(f"{alias}.saved = 1")
        return (" AND ".join(clauses) if clauses else "1=1"), params


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for col in JSON_COLUMNS:
        if col in d:
            raw = d[col]
            if raw is None:
                d[col] = None if col == "colors" else ([] if col == "tags" else {})
            else:
                try:
                    d[col] = json.loads(raw)
                except (TypeError, ValueError):
                    d[col] = [] if col == "tags" else {}
    return d


def fts_query(terms: Iterable[str]) -> str:
    """Build a safe FTS5 MATCH expression (OR of quoted terms, prefix on long ones)."""
    parts: list[str] = []
    seen: set[str] = set()
    for t in terms:
        t = "".join(ch for ch in t.lower() if ch.isalnum() or ch in "-_")
        t = t.replace("-", " ").replace("_", " ").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        if " " in t:
            parts.append('"' + t + '"')
        elif len(t) >= 4:
            parts.append('"' + t + '"*')
        else:
            parts.append('"' + t + '"')
    return " OR ".join(parts)


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self.migrate()

    # -- connections ---------------------------------------------------
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            # not every SQLite build ships math functions
            c.create_function("ln", 1, lambda x: math.log(x) if x and x > 0 else 0.0, deterministic=True)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA busy_timeout=30000")
            self._local.conn = c
        return c

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    def migrate(self) -> None:
        with self._write_lock:
            self.conn().executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn().execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn().execute(sql, tuple(params)).fetchall()

    def write(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._write_lock:
            return self.conn().execute(sql, tuple(params))

    # -- assets ----------------------------------------------------------
    def upsert_assets(self, assets: Iterable[Asset]) -> list[str]:
        ids: list[str] = []
        t = now()
        cols = ("id", "source", "source_id") + _SOURCE_COLUMNS + ("colors", "fetched_at", "updated_at")
        placeholders = ",".join("?" * len(cols))
        updates = ",".join(f"{c}=excluded.{c}" for c in _SOURCE_COLUMNS)
        # keep palette we computed ourselves unless we had none
        updates += ", colors=COALESCE(assets.colors, excluded.colors), fetched_at=excluded.fetched_at, updated_at=excluded.updated_at"
        # a new thumbnail URL means the cached thumbnail may be stale
        updates += ", thumb_state=CASE WHEN assets.thumb_url != excluded.thumb_url THEN 0 ELSE assets.thumb_state END"
        sql = f"INSERT INTO assets ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}"
        rows = []
        for a in assets:
            a.clean()
            ids.append(a.id)
            rows.append((
                a.id, a.source, a.source_id, a.kind, a.title, a.description, json.dumps(a.tags, ensure_ascii=False),
                a.author, a.author_url, a.page_url, a.thumb_url, a.preview_url, a.download_url, a.width, a.height,
                a.duration, a.license, a.license_label, a.license_url, a.usage, a.attribution, a.popularity,
                a.created_at, json.dumps(a.extra, ensure_ascii=False, default=str),
                json.dumps(a.colors) if a.colors else None, t, t,
            ))
        if rows:
            with self._write_lock:
                c = self.conn()
                c.execute("BEGIN")
                try:
                    c.executemany(sql, rows)
                    c.execute("COMMIT")
                except Exception:
                    c.execute("ROLLBACK")
                    raise
        return ids

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        return row_to_dict(self.conn().execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone())

    def get_assets(self, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
        ids = list(dict.fromkeys(ids))
        out: dict[str, dict[str, Any]] = {}
        for chunk in _chunks(ids, 500):
            rows = self.conn().execute(
                f"SELECT * FROM assets WHERE id IN ({','.join('?' * len(chunk))})", chunk
            ).fetchall()
            for r in rows:
                d = row_to_dict(r)
                out[d["id"]] = d
        return out

    def update_asset(self, asset_id: str, **fields: Any) -> None:
        if not fields:
            return
        sets = []
        params: list[Any] = []
        for k, v in fields.items():
            if k in JSON_COLUMNS and v is not None and not isinstance(v, str):
                v = json.dumps(v, ensure_ascii=False, default=str)
            sets.append(f"{k} = ?")
            params.append(v)
        sets.append("updated_at = ?")
        params.append(now())
        params.append(asset_id)
        self.write(f"UPDATE assets SET {', '.join(sets)} WHERE id = ?", params)

    def merge_extra(self, asset_id: str, values: dict[str, Any]) -> None:
        with self._write_lock:
            row = self.conn().execute("SELECT extra FROM assets WHERE id = ?", (asset_id,)).fetchone()
            if row is None:
                return
            try:
                extra = json.loads(row["extra"] or "{}")
            except ValueError:
                extra = {}
            extra.update(values)
            self.update_asset(asset_id, extra=extra)

    def filter_ids(self, ids: Iterable[str], filters: Filters) -> list[str]:
        """Keep only ids matching filters, preserving input order."""
        ids = list(ids)
        if not ids:
            return []
        where, params = filters.sql("a")
        keep: set[str] = set()
        for chunk in _chunks(ids, 500):
            rows = self.conn().execute(
                f"SELECT a.id FROM assets a WHERE a.id IN ({','.join('?' * len(chunk))}) AND {where}",
                list(chunk) + params,
            ).fetchall()
            keep.update(r[0] for r in rows)
        return [i for i in ids if i in keep]

    def fts_search(self, terms: Iterable[str], filters: Filters, limit: int = 500) -> list[tuple[str, float]]:
        match = fts_query(terms)
        if not match:
            return []
        where, params = filters.sql("a")
        sql = (
            "SELECT a.id, bm25(assets_fts, 4.0, 1.0, 3.0, 0.5, 0.2) AS score FROM assets_fts "
            "JOIN assets a ON a.rowid = assets_fts.rowid "
            f"WHERE assets_fts MATCH ? AND {where} ORDER BY score LIMIT ?"
        )
        try:
            rows = self.conn().execute(sql, [match] + params + [limit]).fetchall()
        except sqlite3.OperationalError:
            return []
        # bm25: lower is better; flip sign so higher is better
        return [(r[0], -float(r[1])) for r in rows]

    def recent_ids(self, filters: Filters, limit: int = 200, offset: int = 0) -> list[str]:
        where, params = filters.sql("a")
        rows = self.conn().execute(
            f"SELECT a.id FROM assets a WHERE {where} ORDER BY a.fetched_at DESC, a.popularity DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [r[0] for r in rows]

    def random_ids(self, filters: Filters, limit: int, seed: int) -> list[str]:
        where, params = filters.sql("a")
        # deterministic pseudo-random order per seed (stable across pages)
        rows = self.conn().execute(
            f"SELECT a.id FROM assets a WHERE {where} "
            "ORDER BY ((a.rowid * 2654435761 + ?) % 4294967296) LIMIT ?",
            params + [seed, limit],
        ).fetchall()
        return [r[0] for r in rows]

    def ids_by_author(self, source: str, author: str, filters: Filters, limit: int = 60) -> list[str]:
        if not author:
            return []
        where, params = filters.sql("a")
        rows = self.conn().execute(
            f"SELECT a.id FROM assets a WHERE a.source = ? AND a.author = ? AND {where} "
            "ORDER BY a.popularity DESC LIMIT ?",
            [source, author] + params + [limit],
        ).fetchall()
        return [r[0] for r in rows]

    def dhash_duplicates(self, dhash: str) -> list[str]:
        if not dhash:
            return []
        return [r[0] for r in self.conn().execute("SELECT id FROM assets WHERE dhash = ?", (dhash,)).fetchall()]

    def pending_thumbs(self, limit: int = 32) -> list[dict[str, Any]]:
        rows = self.conn().execute(
            "SELECT * FROM assets WHERE thumb_state = 0 AND hidden = 0 "
            "ORDER BY saved DESC, fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row_to_dict(r) for r in rows]

    def pending_embeddings(self, limit: int = 32) -> list[dict[str, Any]]:
        rows = self.conn().execute(
            "SELECT * FROM assets WHERE embed_state = 0 AND thumb_state != 0 AND hidden = 0 "
            "ORDER BY saved DESC, fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [row_to_dict(r) for r in rows]

    def reset_embeddings(self) -> None:
        self.write("UPDATE assets SET embed_state = 0")

    def reset_missing_thumbs(self, thumbs_dir: Path) -> int:
        """Thumbnails are a cache: if files were deleted, queue them to be rebuilt."""
        missing = [r[0] for r in self.conn().execute("SELECT id, thumb_path FROM assets WHERE thumb_path IS NOT NULL")
                   if not (thumbs_dir / r[1]).exists()]
        for chunk in _chunks(missing, 500):
            self.write(f"UPDATE assets SET thumb_state = 0, thumb_path = NULL WHERE id IN ({','.join('?' * len(chunk))})",
                       chunk)
        return len(missing)

    # -- embeddings -------------------------------------------------------
    def put_embeddings(self, rows: list[tuple[str, str, str, bytes]]) -> None:
        if not rows:
            return
        t = now()
        with self._write_lock:
            c = self.conn()
            c.execute("BEGIN")
            try:
                c.executemany(
                    "INSERT INTO embeddings (asset_id, model, modality, vec, created_at) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(asset_id) DO UPDATE SET model=excluded.model, modality=excluded.modality, "
                    "vec=excluded.vec, created_at=excluded.created_at",
                    [(a, m, mod, v, t) for a, m, mod, v in rows],
                )
                c.executemany("UPDATE assets SET embed_state = 1 WHERE id = ?", [(r[0],) for r in rows])
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

    def iter_embeddings(self, model: str) -> Iterator[tuple[str, str, bytes]]:
        cur = self.conn().execute("SELECT asset_id, modality, vec FROM embeddings WHERE model = ?", (model,))
        while True:
            rows = cur.fetchmany(2000)
            if not rows:
                break
            for r in rows:
                yield r[0], r[1], r[2]

    def get_embedding(self, asset_id: str) -> tuple[str, str, bytes] | None:
        r = self.conn().execute("SELECT model, modality, vec FROM embeddings WHERE asset_id = ?", (asset_id,)).fetchone()
        return (r[0], r[1], r[2]) if r else None

    # -- query cache ------------------------------------------------------
    def cache_get(self, qkey: str, source: str, kinds: str, page: int) -> sqlite3.Row | None:
        return self.conn().execute(
            "SELECT * FROM query_cache WHERE qkey=? AND source=? AND kinds=? AND page=?", (qkey, source, kinds, page)
        ).fetchone()

    def cache_put(self, qkey: str, source: str, kinds: str, page: int, ids: list[str], next_cursor: str | None,
                  exhausted: bool, error: str | None = None) -> None:
        t = now()
        with self._write_lock:
            c = self.conn()
            c.execute("BEGIN")
            try:
                c.execute(
                    "INSERT INTO query_cache (qkey, source, kinds, page, fetched_at, n, next_cursor, exhausted, error) "
                    "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(qkey, source, kinds, page) DO UPDATE SET "
                    "fetched_at=excluded.fetched_at, n=excluded.n, next_cursor=excluded.next_cursor, "
                    "exhausted=excluded.exhausted, error=excluded.error",
                    (qkey, source, kinds, page, t, len(ids), next_cursor, int(exhausted), error),
                )
                base = (page - 1) * 1000
                c.executemany(
                    "INSERT INTO query_hits (qkey, asset_id, source, rank) VALUES (?,?,?,?) "
                    "ON CONFLICT(qkey, asset_id) DO UPDATE SET rank=MIN(rank, excluded.rank)",
                    [(qkey, aid, source, base + i) for i, aid in enumerate(ids)],
                )
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

    def query_hits(self, qkey: str) -> list[tuple[str, str, int]]:
        rows = self.conn().execute(
            "SELECT asset_id, source, rank FROM query_hits WHERE qkey = ? ORDER BY rank", (qkey,)
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def cached_pages(self, qkey: str, kinds: str) -> dict[str, dict[str, Any]]:
        """Per source: highest fetched page, cursor for the next one, exhausted flag."""
        rows = self.conn().execute(
            "SELECT source, page, next_cursor, exhausted, fetched_at, error FROM query_cache "
            "WHERE qkey = ? AND kinds = ? ORDER BY page",
            (qkey, kinds),
        ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            out[r["source"]] = {
                "page": r["page"], "cursor": r["next_cursor"], "exhausted": bool(r["exhausted"]),
                "fetched_at": r["fetched_at"], "error": r["error"],
            }
        return out

    # -- boards -------------------------------------------------------------
    def create_board(self, name: str, description: str = "") -> int:
        t = now()
        name = name.strip()[:120] or "Untitled"
        with self._write_lock:
            row = self.conn().execute("SELECT id FROM boards WHERE name = ?", (name,)).fetchone()
            if row:
                return int(row[0])
            cur = self.conn().execute(
                "INSERT INTO boards (name, description, created_at, updated_at) VALUES (?,?,?,?)",
                (name, description, t, t),
            )
            return int(cur.lastrowid)

    def list_boards(self) -> list[dict[str, Any]]:
        rows = self.conn().execute(
            "SELECT b.*, COUNT(bi.asset_id) AS count, MAX(bi.added_at) AS last_added FROM boards b "
            "LEFT JOIN board_items bi ON bi.board_id = b.id GROUP BY b.id "
            "ORDER BY COALESCE(MAX(bi.added_at), b.updated_at) DESC"
        ).fetchall()
        boards = [dict(r) for r in rows]
        for b in boards:
            covers = self.conn().execute(
                "SELECT asset_id FROM board_items WHERE board_id = ? ORDER BY added_at DESC LIMIT 4", (b["id"],)
            ).fetchall()
            b["cover_ids"] = [c[0] for c in covers]
        return boards

    def get_board(self, board_id: int) -> dict[str, Any] | None:
        r = self.conn().execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
        return dict(r) if r else None

    def board_by_name(self, name: str) -> dict[str, Any] | None:
        r = self.conn().execute("SELECT * FROM boards WHERE name = ?", (name,)).fetchone()
        return dict(r) if r else None

    def update_board(self, board_id: int, name: str | None = None, description: str | None = None) -> None:
        if name is not None:
            self.write("UPDATE boards SET name = ?, updated_at = ? WHERE id = ?", (name.strip()[:120], now(), board_id))
        if description is not None:
            self.write("UPDATE boards SET description = ?, updated_at = ? WHERE id = ?", (description, now(), board_id))

    def delete_board(self, board_id: int) -> None:
        with self._write_lock:
            ids = [r[0] for r in self.conn().execute(
                "SELECT asset_id FROM board_items WHERE board_id = ?", (board_id,)).fetchall()]
            self.conn().execute("DELETE FROM board_items WHERE board_id = ?", (board_id,))
            self.conn().execute("DELETE FROM boards WHERE id = ?", (board_id,))
            self._refresh_saved(ids)

    def add_to_board(self, board_id: int, asset_id: str, note: str = "") -> None:
        with self._write_lock:
            self.conn().execute(
                "INSERT INTO board_items (board_id, asset_id, note, added_at) VALUES (?,?,?,?) "
                "ON CONFLICT(board_id, asset_id) DO UPDATE SET note = CASE WHEN excluded.note != '' "
                "THEN excluded.note ELSE board_items.note END",
                (board_id, asset_id, note, now()),
            )
            self.conn().execute("UPDATE assets SET saved = 1 WHERE id = ?", (asset_id,))
            self.conn().execute("UPDATE boards SET updated_at = ? WHERE id = ?", (now(), board_id))

    def remove_from_board(self, board_id: int, asset_id: str) -> None:
        with self._write_lock:
            self.conn().execute("DELETE FROM board_items WHERE board_id = ? AND asset_id = ?", (board_id, asset_id))
            self._refresh_saved([asset_id])

    def _refresh_saved(self, ids: list[str]) -> None:
        for aid in ids:
            n = self.conn().execute("SELECT COUNT(*) FROM board_items WHERE asset_id = ?", (aid,)).fetchone()[0]
            self.conn().execute("UPDATE assets SET saved = ? WHERE id = ?", (1 if n else 0, aid))

    def board_item_ids(self, board_id: int, limit: int = 10000, offset: int = 0) -> list[str]:
        rows = self.conn().execute(
            "SELECT asset_id FROM board_items WHERE board_id = ? ORDER BY added_at DESC LIMIT ? OFFSET ?",
            (board_id, limit, offset),
        ).fetchall()
        return [r[0] for r in rows]

    def boards_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        rows = self.conn().execute(
            "SELECT b.id, b.name FROM board_items bi JOIN boards b ON b.id = bi.board_id WHERE bi.asset_id = ?",
            (asset_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def co_saved(self, asset_id: str, limit: int = 200) -> list[tuple[str, float]]:
        """Items sharing boards with asset_id, weighted like Pinterest's pin–board graph
        (small, focused boards say more than giant catch-all boards)."""
        rows = self.conn().execute(
            "SELECT bi2.asset_id, SUM(1.0 / (1.0 + ln(1.0 + cnt.n))) AS w "
            "FROM board_items bi1 "
            "JOIN board_items bi2 ON bi2.board_id = bi1.board_id AND bi2.asset_id != bi1.asset_id "
            "JOIN (SELECT board_id, COUNT(*) AS n FROM board_items GROUP BY board_id) cnt ON cnt.board_id = bi1.board_id "
            "WHERE bi1.asset_id = ? GROUP BY bi2.asset_id ORDER BY w DESC LIMIT ?",
            (asset_id, limit),
        ).fetchall()
        return [(r[0], float(r[1])) for r in rows]

    # -- interactions -----------------------------------------------------
    def log_interaction(self, asset_id: str, action: str, weight: float, query: str = "") -> None:
        self.write(
            "INSERT INTO interactions (asset_id, action, weight, query, ts) VALUES (?,?,?,?,?)",
            (asset_id, action, weight, query[:200], now()),
        )

    def interactions_since(self, since_ts: float, limit: int = 2000) -> list[dict[str, Any]]:
        rows = self.conn().execute(
            "SELECT asset_id, action, weight, ts FROM interactions WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
            (since_ts, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- graph edges -------------------------------------------------------
    def add_edges(self, edges: list[tuple[str, str, str, float]]) -> None:
        if not edges:
            return
        t = now()
        with self._write_lock:
            self.conn().executemany(
                "INSERT INTO edges (a, b, kind, weight, created_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(a, b, kind) DO UPDATE SET weight = MAX(edges.weight, excluded.weight)",
                [(a, b, k, w, t) for a, b, k, w in edges if a != b],
            )

    def neighbors(self, asset_id: str, limit: int = 200) -> list[tuple[str, float]]:
        rows = self.conn().execute(
            "SELECT other, SUM(weight) AS w FROM ("
            " SELECT b AS other, weight FROM edges WHERE a = ? "
            " UNION ALL SELECT a AS other, weight FROM edges WHERE b = ?"
            ") GROUP BY other ORDER BY w DESC LIMIT ?",
            (asset_id, asset_id, limit),
        ).fetchall()
        return [(r[0], float(r[1])) for r in rows]

    # -- source health -----------------------------------------------------
    def source_states(self) -> dict[str, dict[str, Any]]:
        return {r["source"]: dict(r) for r in self.conn().execute("SELECT * FROM source_state").fetchall()}

    def source_ok(self, source: str, items: int) -> None:
        self.write(
            "INSERT INTO source_state (source, calls, items, last_ok) VALUES (?, 1, ?, ?) "
            "ON CONFLICT(source) DO UPDATE SET calls = calls + 1, items = items + excluded.items, last_ok = excluded.last_ok",
            (source, items, now()),
        )

    def source_error(self, source: str, message: str, cooldown_s: float = 0) -> None:
        t = now()
        until = t + cooldown_s if cooldown_s else None
        self.write(
            "INSERT INTO source_state (source, calls, last_error, last_error_at, cooldown_until) VALUES (?, 1, ?, ?, ?) "
            "ON CONFLICT(source) DO UPDATE SET calls = calls + 1, last_error = excluded.last_error, "
            "last_error_at = excluded.last_error_at, cooldown_until = COALESCE(excluded.cooldown_until, cooldown_until)",
            (source, message[:500], t, until),
        )

    def take_budget(self, source: str, per_hour: int | None) -> bool:
        """Consume one call from an hourly budget; False when exhausted or cooling down."""
        t = now()
        with self._write_lock:
            c = self.conn()
            row = c.execute("SELECT * FROM source_state WHERE source = ?", (source,)).fetchone()
            if row is None:
                c.execute("INSERT INTO source_state (source, window_start, window_calls) VALUES (?, ?, 0)", (source, t))
                row = c.execute("SELECT * FROM source_state WHERE source = ?", (source,)).fetchone()
            if row["cooldown_until"] and row["cooldown_until"] > t:
                return False
            if not per_hour:
                return True
            start = row["window_start"] or t
            calls = row["window_calls"] or 0
            if t - start >= 3600:
                start, calls = t, 0
            if calls >= per_hour:
                return False
            c.execute("UPDATE source_state SET window_start = ?, window_calls = ? WHERE source = ?", (start, calls + 1, source))
            return True

    # -- interests & jobs --------------------------------------------------
    def add_interest(self, query: str, kinds: str = "", every_hours: float = 24, max_pages: int = 5) -> int:
        with self._write_lock:
            row = self.conn().execute("SELECT id FROM interests WHERE query = ?", (query,)).fetchone()
            if row:
                self.conn().execute(
                    "UPDATE interests SET kinds = ?, every_hours = ?, max_pages = ?, enabled = 1 WHERE id = ?",
                    (kinds, every_hours, max_pages, row[0]),
                )
                return int(row[0])
            cur = self.conn().execute(
                "INSERT INTO interests (query, kinds, every_hours, max_pages, created_at) VALUES (?,?,?,?,?)",
                (query, kinds, every_hours, max_pages, now()),
            )
            return int(cur.lastrowid)

    def list_interests(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn().execute("SELECT * FROM interests ORDER BY id").fetchall()]

    def delete_interest(self, interest_id: int) -> None:
        self.write("DELETE FROM interests WHERE id = ?", (interest_id,))

    def due_interests(self) -> list[dict[str, Any]]:
        t = now()
        rows = self.conn().execute(
            "SELECT * FROM interests WHERE enabled = 1 AND (last_run IS NULL OR last_run + every_hours * 3600 <= ?)",
            (t,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_interest_run(self, interest_id: int, next_page: int) -> None:
        self.write("UPDATE interests SET last_run = ?, next_page = ? WHERE id = ?", (now(), next_page, interest_id))

    def enqueue_job(self, type_: str, payload: dict[str, Any] | None = None, dedupe: bool = True) -> int:
        body = json.dumps(payload or {}, sort_keys=True)
        with self._write_lock:
            if dedupe:
                row = self.conn().execute(
                    "SELECT id FROM jobs WHERE type = ? AND payload = ? AND status IN ('queued', 'running')",
                    (type_, body),
                ).fetchone()
                if row:
                    return int(row[0])
            cur = self.conn().execute(
                "INSERT INTO jobs (type, payload, status, created_at) VALUES (?, ?, 'queued', ?)", (type_, body, now())
            )
            return int(cur.lastrowid)

    def claim_job(self) -> dict[str, Any] | None:
        with self._write_lock:
            row = self.conn().execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
            if not row:
                return None
            self.conn().execute("UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?", (now(), row["id"]))
            job = dict(row)
            job["payload"] = json.loads(job["payload"] or "{}")
            return job

    def finish_job(self, job_id: int, result: Any = None, error: str | None = None) -> None:
        self.write(
            "UPDATE jobs SET status = ?, result = ?, error = ?, finished_at = ? WHERE id = ?",
            ("failed" if error else "done", json.dumps(result, default=str) if result is not None else None,
             error, now(), job_id),
        )

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        r = self.conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        for k in ("payload", "result"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    pass
        return d

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.conn().execute("SELECT id FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self.get_job(r[0]) for r in rows]

    def requeue_stale_jobs(self) -> None:
        """Jobs left 'running' by a crash/restart go back to the queue."""
        self.write("UPDATE jobs SET status = 'queued' WHERE status = 'running'")

    # -- meta & stats --------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        r = self.conn().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return r[0] if r else default

    def set_meta(self, key: str, value: str) -> None:
        self.write("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                   (key, value))

    def stats(self) -> dict[str, Any]:
        c = self.conn()
        total = c.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        by_kind = {r[0]: r[1] for r in c.execute("SELECT kind, COUNT(*) FROM assets GROUP BY kind ORDER BY 2 DESC")}
        by_source = {r[0]: r[1] for r in c.execute("SELECT source, COUNT(*) FROM assets GROUP BY source ORDER BY 2 DESC")}
        by_usage = {r[0]: r[1] for r in c.execute("SELECT usage, COUNT(*) FROM assets GROUP BY usage ORDER BY 2 DESC")}
        saved = c.execute("SELECT COUNT(*) FROM assets WHERE saved = 1").fetchone()[0]
        stored = c.execute("SELECT COUNT(*), COALESCE(SUM(blob_size), 0) FROM assets WHERE blob_key IS NOT NULL").fetchone()
        thumbs = c.execute("SELECT COUNT(*) FROM assets WHERE thumb_path IS NOT NULL").fetchone()[0]
        embedded = c.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        boards = c.execute("SELECT COUNT(*) FROM boards").fetchone()[0]
        return {
            "assets": total, "by_kind": by_kind, "by_source": by_source, "by_usage": by_usage, "saved": saved,
            "stored_files": stored[0], "stored_bytes": stored[1], "thumbs": thumbs, "embedded": embedded,
            "boards": boards,
        }


def _chunks(items: list[Any], n: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]
