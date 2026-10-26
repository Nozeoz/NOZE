"""SQLite state for the agency: leads, campaigns, jobs, artifacts, the event log
(the team's shared "message pool"), reviews, playbook lessons + versions,
metrics, publications and LLM spend.

Separate file from the asset bank (``agency/agency.db``), same conventions as
``noze.db``: WAL, a connection per thread, a write lock, JSON columns.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    creator TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    posted_at TEXT NOT NULL DEFAULT '',
    score REAL,
    decision TEXT NOT NULL DEFAULT '',
    reasons TEXT NOT NULL DEFAULT '[]',
    terms TEXT NOT NULL DEFAULT '{}',
    outreach TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    found_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    creator TEXT NOT NULL DEFAULT '',
    lead_id INTEGER,
    brief TEXT NOT NULL DEFAULT '{}',
    permission TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    parent_id INTEGER,
    campaign_id INTEGER,
    state TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    input TEXT NOT NULL DEFAULT '{}',
    data TEXT NOT NULL DEFAULT '{}',
    round INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    canary INTEGER NOT NULL DEFAULT 0,
    playbook_version INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    next_run REAL NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state, next_run);
CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_id);
CREATE INDEX IF NOT EXISTS idx_jobs_campaign ON jobs(campaign_id);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    version INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    UNIQUE(job_id, kind, version)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    job_id INTEGER,
    ts REAL NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id, id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    round INTEGER NOT NULL,
    reviewer TEXT NOT NULL,
    verdict TEXT NOT NULL,
    score REAL,
    summary TEXT NOT NULL DEFAULT '',
    issues TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_job ON reviews(job_id, round);

CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    section TEXT NOT NULL DEFAULT 'general',
    scope TEXT NOT NULL DEFAULT 'global',
    text TEXT NOT NULL,
    helpful INTEGER NOT NULL DEFAULT 0,
    harmful INTEGER NOT NULL DEFAULT 0,
    uses INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'candidate',
    origin TEXT NOT NULL DEFAULT 'reflector',
    protected INTEGER NOT NULL DEFAULT 0,
    evidence TEXT NOT NULL DEFAULT '[]',
    jobs TEXT NOT NULL DEFAULT '[]',
    version_added INTEGER NOT NULL DEFAULT 0,
    activated_at REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lessons_role ON lessons(role, status);

CREATE TABLE IF NOT EXISTS playbook_versions (
    version INTEGER PRIMARY KEY,
    created_at REAL NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    changes TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'live'
);

CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY,
    job_id INTEGER,
    key TEXT NOT NULL,
    value REAL NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_key ON metrics(key, ts);
CREATE INDEX IF NOT EXISTS idx_metrics_job ON metrics(job_id);

CREATE TABLE IF NOT EXISTS publications (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    remote_id TEXT NOT NULL DEFAULT '',
    info TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_publications_job ON publications(job_id);

CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    job_id INTEGER,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read INTEGER NOT NULL DEFAULT 0,
    cache_write INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON llm_usage(ts);
CREATE INDEX IF NOT EXISTS idx_usage_job ON llm_usage(job_id);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

JSON_COLS = {
    "leads": ("reasons", "terms"),
    "campaigns": ("brief", "permission"),
    "jobs": ("input", "data"),
    "artifacts": ("data",),
    "events": ("data",),
    "reviews": ("issues",),
    "lessons": ("evidence", "jobs"),
    "playbook_versions": ("changes",),
    "metrics": ("data",),
    "publications": ("info",),
}


def now() -> float:
    return time.time()


def dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def _row(table: str, row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for col in JSON_COLS.get(table, ()):
        if col in d:
            try:
                d[col] = json.loads(d[col]) if d[col] else ({} if col not in ("reasons", "issues", "evidence", "jobs") else [])
            except ValueError:
                d[col] = {}
    return d


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.RLock()
        with self._lock:
            self.conn().executescript(SCHEMA)

    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA busy_timeout=30000")
            self._local.conn = c
        return c

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    def q(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn().execute(sql, tuple(params)).fetchall()

    def w(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.conn().execute(sql, tuple(params))

    def _update(self, table: str, key: str, key_value: Any, fields: dict[str, Any]) -> None:
        if not fields:
            return
        cols, params = [], []
        for k, v in fields.items():
            cols.append(f"{k} = ?")
            params.append(dumps(v) if k in JSON_COLS.get(table, ()) else v)
        if table in ("leads", "campaigns", "jobs", "lessons"):
            cols.append("updated_at = ?")
            params.append(now())
        params.append(key_value)
        self.w(f"UPDATE {table} SET {', '.join(cols)} WHERE {key} = ?", params)

    # -- leads -------------------------------------------------------------------
    def upsert_lead(self, lead: dict[str, Any]) -> tuple[int, bool]:
        """Insert a lead (keyed by URL). Returns (id, is_new); existing leads keep their status."""
        with self._lock:
            row = self.conn().execute("SELECT id FROM leads WHERE url = ?", (lead["url"],)).fetchone()
            if row:
                self._update("leads", "id", row[0], {k: lead[k] for k in ("title", "body", "creator", "posted_at")
                                                     if lead.get(k)})
                return int(row[0]), False
            t = now()
            cur = self.conn().execute(
                "INSERT INTO leads (source, url, title, creator, body, posted_at, found_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (lead.get("source", "manual"), lead["url"], lead.get("title", "")[:300], lead.get("creator", "")[:200],
                 lead.get("body", "")[:20000], lead.get("posted_at", ""), t, t),
            )
            return int(cur.lastrowid), True

    def get_lead(self, lead_id: int) -> dict[str, Any] | None:
        return _row("leads", self.conn().execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone())

    def update_lead(self, lead_id: int, **fields: Any) -> None:
        self._update("leads", "id", lead_id, fields)

    def list_leads(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if status:
            rows = self.q("SELECT * FROM leads WHERE status = ? ORDER BY COALESCE(score, -1) DESC, id DESC LIMIT ?",
                          (status, limit))
        else:
            rows = self.q("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,))
        return [_row("leads", r) for r in rows]

    # -- campaigns -----------------------------------------------------------------
    def create_campaign(self, name: str, brief: dict[str, Any], permission: dict[str, Any] | None = None,
                        creator: str = "", lead_id: int | None = None) -> int:
        t = now()
        cur = self.w(
            "INSERT INTO campaigns (name, creator, lead_id, brief, permission, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, creator, lead_id, dumps(brief), dumps(permission or {}), t, t),
        )
        return int(cur.lastrowid)

    def get_campaign(self, ref: int | str) -> dict[str, Any] | None:
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            row = self.conn().execute("SELECT * FROM campaigns WHERE id = ?", (int(ref),)).fetchone()
            if row:
                return _row("campaigns", row)
        return _row("campaigns", self.conn().execute("SELECT * FROM campaigns WHERE name = ?", (str(ref),)).fetchone())

    def update_campaign(self, campaign_id: int, **fields: Any) -> None:
        self._update("campaigns", "id", campaign_id, fields)

    def list_campaigns(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.q("SELECT * FROM campaigns WHERE status = ? ORDER BY id DESC", (status,))
        else:
            rows = self.q("SELECT * FROM campaigns ORDER BY id DESC")
        return [_row("campaigns", r) for r in rows]

    # -- jobs ------------------------------------------------------------------------
    def create_job(self, kind: str, state: str, *, campaign_id: int | None = None, parent_id: int | None = None,
                   title: str = "", input: dict[str, Any] | None = None, data: dict[str, Any] | None = None,
                   priority: int = 0, canary: bool = False, playbook_version: int = 0) -> int:
        t = now()
        cur = self.w(
            "INSERT INTO jobs (kind, parent_id, campaign_id, state, title, input, data, priority, canary, "
            "playbook_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, parent_id, campaign_id, state, title[:300], dumps(input or {}), dumps(data or {}), priority,
             int(canary), playbook_version, t, t),
        )
        return int(cur.lastrowid)

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        return _row("jobs", self.conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())

    def update_job(self, job_id: int, **fields: Any) -> None:
        self._update("jobs", "id", job_id, fields)

    def merge_job_data(self, job_id: int, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job = self.get_job(job_id) or {}
            data = dict(job.get("data") or {})
            data.update(values)
            self._update("jobs", "id", job_id, {"data": data})
            return data

    def claim_jobs(self, states: Iterable[str], limit: int = 1, lease_s: float = 7200.0) -> list[dict[str, Any]]:
        """Lease due jobs in the given states so two runners (threads *or* processes) never
        work on the same job: select + lease happen in one IMMEDIATE transaction.
        A crashed runner's lease simply expires and the job is picked up again."""
        states = list(states)
        t = now()
        with self._lock:
            c = self.conn()
            c.execute("BEGIN IMMEDIATE")
            try:
                rows = c.execute(
                    f"SELECT id FROM jobs WHERE state IN ({','.join('?' * len(states))}) AND next_run <= ? "
                    "AND locked_until <= ? ORDER BY priority DESC, id LIMIT ?",
                    (*states, t, t, limit),
                ).fetchall()
                ids = [r[0] for r in rows]
                for jid in ids:
                    c.execute("UPDATE jobs SET locked_until = ? WHERE id = ?", (t + lease_s, jid))
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise
        return [self.get_job(j) for j in ids]

    def transition(self, job_id: int, from_state: str, **fields: Any) -> bool:
        """Compare-and-set: apply ``fields`` only if the job is still in ``from_state``
        (so a human decision and the runner can't overwrite each other)."""
        cols, params = [], []
        for k, v in fields.items():
            cols.append(f"{k} = ?")
            params.append(dumps(v) if k in JSON_COLS["jobs"] else v)
        cols.append("updated_at = ?")
        params.append(now())
        cur = self.w(f"UPDATE jobs SET {', '.join(cols)} WHERE id = ? AND state = ?", (*params, job_id, from_state))
        return cur.rowcount == 1

    def release_job(self, job_id: int) -> None:
        self.w("UPDATE jobs SET locked_until = 0 WHERE id = ?", (job_id,))

    def list_jobs(self, kind: str | None = None, states: Iterable[str] | None = None, campaign_id: int | None = None,
                  parent_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        clauses, params = [], []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if states:
            states = list(states)
            clauses.append(f"state IN ({','.join('?' * len(states))})")
            params.extend(states)
        if campaign_id is not None:
            clauses.append("campaign_id = ?")
            params.append(campaign_id)
        if parent_id is not None:
            clauses.append("parent_id = ?")
            params.append(parent_id)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self.q(f"SELECT * FROM jobs WHERE {where} ORDER BY id DESC LIMIT ?", (*params, limit))
        return [_row("jobs", r) for r in rows]

    def state_counts(self, kind: str = "clip") -> dict[str, int]:
        return {r[0]: r[1] for r in self.q("SELECT state, COUNT(*) FROM jobs WHERE kind = ? GROUP BY state", (kind,))}

    # -- artifacts -------------------------------------------------------------------------
    def put_artifact(self, job_id: int, kind: str, data: Any = None, path: str | Path = "", role: str = "") -> int:
        with self._lock:
            row = self.conn().execute("SELECT COALESCE(MAX(version), 0) FROM artifacts WHERE job_id = ? AND kind = ?",
                                      (job_id, kind)).fetchone()
            version = int(row[0]) + 1
            self.conn().execute(
                "INSERT INTO artifacts (job_id, kind, version, role, path, data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, kind, version, role, str(path or ""), dumps(data), now()),
            )
            return version

    def artifact(self, job_id: int, kind: str, version: int | None = None) -> dict[str, Any] | None:
        if version is None:
            row = self.conn().execute(
                "SELECT * FROM artifacts WHERE job_id = ? AND kind = ? ORDER BY version DESC LIMIT 1", (job_id, kind)
            ).fetchone()
        else:
            row = self.conn().execute("SELECT * FROM artifacts WHERE job_id = ? AND kind = ? AND version = ?",
                                      (job_id, kind, version)).fetchone()
        return _row("artifacts", row)

    def artifacts(self, job_id: int, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            rows = self.q("SELECT * FROM artifacts WHERE job_id = ? AND kind = ? ORDER BY version", (job_id, kind))
        else:
            rows = self.q("SELECT * FROM artifacts WHERE job_id = ? ORDER BY id", (job_id,))
        return [_row("artifacts", r) for r in rows]

    # -- events ------------------------------------------------------------------------------
    def log(self, job_id: int | None, role: str, type_: str, message: str = "", data: Any = None) -> None:
        self.w("INSERT INTO events (job_id, ts, role, type, message, data) VALUES (?, ?, ?, ?, ?, ?)",
               (job_id, now(), role, type_, message[:2000], dumps(data)))

    def events(self, job_id: int | None = None, limit: int = 200, since: float = 0.0,
               types: Iterable[str] | None = None) -> list[dict[str, Any]]:
        clauses, params = ["ts >= ?"], [since]
        if job_id is not None:
            clauses.append("job_id = ?")
            params.append(job_id)
        if types:
            types = list(types)
            clauses.append(f"type IN ({','.join('?' * len(types))})")
            params.extend(types)
        rows = self.q(f"SELECT * FROM events WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?", (*params, limit))
        return [_row("events", r) for r in reversed(rows)]

    # -- reviews --------------------------------------------------------------------------------
    def add_review(self, job_id: int, round_: int, reviewer: str, verdict: str, score: float | None,
                   issues: list[dict[str, Any]], summary: str = "") -> int:
        cur = self.w(
            "INSERT INTO reviews (job_id, round, reviewer, verdict, score, summary, issues, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, round_, reviewer, verdict, score, summary[:4000], dumps(issues), now()),
        )
        return int(cur.lastrowid)

    def reviews(self, job_id: int) -> list[dict[str, Any]]:
        return [_row("reviews", r) for r in self.q("SELECT * FROM reviews WHERE job_id = ? ORDER BY id", (job_id,))]

    def recent_reviews(self, limit: int = 50, reviewer: str | None = None) -> list[dict[str, Any]]:
        if reviewer:
            rows = self.q("SELECT * FROM reviews WHERE reviewer = ? ORDER BY id DESC LIMIT ?", (reviewer, limit))
        else:
            rows = self.q("SELECT * FROM reviews ORDER BY id DESC LIMIT ?", (limit,))
        return [_row("reviews", r) for r in rows]

    # -- lessons & playbook versions ------------------------------------------------------------------
    def next_lesson_id(self, role: str) -> str:
        prefix = role[:3]
        with self._lock:
            n = self.conn().execute("SELECT COUNT(*) FROM lessons WHERE role = ?", (role,)).fetchone()[0]
            while True:
                n += 1
                lid = f"{prefix}-{n:05d}"
                if not self.conn().execute("SELECT 1 FROM lessons WHERE id = ?", (lid,)).fetchone():
                    return lid

    def add_lesson(self, role: str, text: str, *, section: str = "general", scope: str = "global",
                   status: str = "candidate", origin: str = "reflector", evidence: list[Any] | None = None,
                   job_id: int | None = None, version: int = 0, protected: bool = False) -> str:
        with self._lock:
            lid = self.next_lesson_id(role)
            t = now()
            self.conn().execute(
                "INSERT INTO lessons (id, role, section, scope, text, status, origin, protected, evidence, jobs, "
                "version_added, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lid, role, section, scope, text, status, origin, int(protected), dumps(evidence or []),
                 dumps([job_id] if job_id else []), version, t, t),
            )
            return lid

    def get_lesson(self, lesson_id: str) -> dict[str, Any] | None:
        return _row("lessons", self.conn().execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone())

    def update_lesson(self, lesson_id: str, **fields: Any) -> None:
        self._update("lessons", "id", lesson_id, fields)

    def lessons(self, role: str | None = None, statuses: Iterable[str] | None = None,
                scopes: Iterable[str] | None = None) -> list[dict[str, Any]]:
        clauses, params = [], []
        if role:
            clauses.append("role = ?")
            params.append(role)
        if statuses:
            statuses = list(statuses)
            clauses.append(f"status IN ({','.join('?' * len(statuses))})")
            params.extend(statuses)
        if scopes:
            scopes = list(scopes)
            clauses.append(f"scope IN ({','.join('?' * len(scopes))})")
            params.extend(scopes)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self.q(f"SELECT * FROM lessons WHERE {where} ORDER BY (helpful - harmful) DESC, id", params)
        return [_row("lessons", r) for r in rows]

    def current_version(self) -> int:
        row = self.conn().execute("SELECT MAX(version) FROM playbook_versions WHERE status = 'live'").fetchone()
        return int(row[0] or 0)

    def new_version(self, note: str, changes: dict[str, Any]) -> int:
        with self._lock:
            v = int(self.conn().execute("SELECT COALESCE(MAX(version), 0) FROM playbook_versions").fetchone()[0]) + 1
            self.conn().execute("INSERT INTO playbook_versions (version, created_at, note, changes) VALUES (?, ?, ?, ?)",
                                (v, now(), note[:500], dumps(changes)))
            return v

    def versions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.q("SELECT * FROM playbook_versions ORDER BY version DESC LIMIT ?", (limit,))
        return [_row("playbook_versions", r) for r in rows]

    def set_version_status(self, version: int, status: str) -> None:
        self.w("UPDATE playbook_versions SET status = ? WHERE version = ?", (status, version))

    # -- metrics -----------------------------------------------------------------------------------------
    def add_metric(self, job_id: int | None, key: str, value: float, data: Any = None) -> None:
        self.w("INSERT INTO metrics (job_id, key, value, data, ts) VALUES (?, ?, ?, ?, ?)",
               (job_id, key, float(value), dumps(data), now()))

    def metrics(self, key: str, since: float = 0.0, limit: int = 1000) -> list[dict[str, Any]]:
        rows = self.q("SELECT * FROM metrics WHERE key = ? AND ts >= ? ORDER BY id DESC LIMIT ?", (key, since, limit))
        return [_row("metrics", r) for r in rows]

    def job_metrics(self, job_id: int) -> dict[str, float]:
        return {r["key"]: r["value"] for r in self.q("SELECT key, value FROM metrics WHERE job_id = ? ORDER BY id",
                                                      (job_id,))}

    # -- publications -------------------------------------------------------------------------------------
    def add_publication(self, job_id: int, target: str, status: str, url: str = "", remote_id: str = "",
                        info: Any = None) -> int:
        cur = self.w(
            "INSERT INTO publications (job_id, target, status, url, remote_id, info, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, target, status, url, remote_id, dumps(info), now()),
        )
        return int(cur.lastrowid)

    def publications(self, job_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if job_id is None:
            rows = self.q("SELECT * FROM publications ORDER BY id DESC LIMIT ?", (limit,))
        else:
            rows = self.q("SELECT * FROM publications WHERE job_id = ? ORDER BY id", (job_id,))
        return [_row("publications", r) for r in rows]

    # -- LLM spend -----------------------------------------------------------------------------------------
    def add_usage(self, job_id: int | None, role: str, model: str, input_tokens: int, output_tokens: int,
                  cache_read: int, cache_write: int, cost_usd: float) -> None:
        self.w("INSERT INTO llm_usage (ts, job_id, role, model, input_tokens, output_tokens, cache_read, cache_write, "
               "cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (now(), job_id, role, model, input_tokens, output_tokens, cache_read, cache_write, cost_usd))

    def spend(self, job_ids: Iterable[int] | None = None, since: float | None = None) -> float:
        if job_ids is not None:
            ids = list(job_ids)
            if not ids:
                return 0.0
            row = self.conn().execute(
                f"SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE job_id IN ({','.join('?' * len(ids))})", ids
            ).fetchone()
        else:
            row = self.conn().execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_usage WHERE ts >= ?",
                                      (since or 0.0,)).fetchone()
        return float(row[0] or 0.0)

    def spend_by_role(self, since: float = 0.0) -> dict[str, float]:
        return {r[0]: float(r[1]) for r in self.q(
            "SELECT role, SUM(cost_usd) FROM llm_usage WHERE ts >= ? GROUP BY role", (since,))}

    # -- meta ------------------------------------------------------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        r = self.conn().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return r[0] if r else default

    def set_meta(self, key: str, value: str) -> None:
        self.w("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
               (key, value))
