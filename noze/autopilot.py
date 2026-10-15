"""Autopilot: the bank fills and grows itself.

- first start: the starter pack of motion & design topics is queued without asking
- every search you repeat (or save something from) becomes an interest that is crawled daily
- Pinterest boards you connect turn into interests named after the board
- API keys can be pasted in the web UI; they're written to NOZE_DATA_DIR/.env
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import KEY_NAMES, Settings
from .db import Database
from .lexicon import STARTER_TOPICS

LEARN_AFTER = 2  # searches of the same thing before it becomes an interest
MAX_AUTO_INTERESTS = 150
GENERIC_BOARDS = {"saved", "quick saves", "untitled", "my board", "board", "pins", "inspo", "inspiration",
                  "ideas", "stuff", "random", "misc", "other", "favorites", "favourites", "likes", "new board"}


def normalize_query(q: str) -> str:
    q = re.sub(r"\s+", " ", (q or "").strip().lower())
    q = re.sub(r"^pinterest\s*[·:-]\s*", "", q)
    return q[:80].strip(" -_·|")


def _auto_count(db: Database) -> int:
    return int(db.get_meta("autopilot.auto_interests", "0") or 0)


def _learn(db: Database, query: str, every_hours: float = 24, max_pages: int = 5) -> int | None:
    if len(query) < 3 or db.get_meta(f"autopilot.ignore:{query}"):
        return None
    if any(i["query"] == query for i in db.list_interests()):
        return None
    if _auto_count(db) >= MAX_AUTO_INTERESTS:
        return None
    iid = db.add_interest(query, "", every_hours, max_pages)
    db.set_meta("autopilot.auto_interests", str(_auto_count(db) + 1))
    db.enqueue_job("interest", {"interest_id": iid})
    return iid


def seed_if_new(db: Database) -> bool:
    """Queue the starter pack once, on a brand-new bank, so it is never empty."""
    if db.get_meta("autopilot.seeded"):
        return False
    db.set_meta("autopilot.seeded", "1")
    if db.list_interests():
        return False
    for topic in STARTER_TOPICS:
        iid = db.add_interest(topic, "", 72, 3)
        db.enqueue_job("interest", {"interest_id": iid})
    return True


def learn_from_search(db: Database, raw: str) -> int | None:
    q = normalize_query(raw)
    if len(q) < 3:
        return None
    key = f"autopilot.searches:{q}"
    n = int(db.get_meta(key, "0") or 0) + 1
    db.set_meta(key, str(n))
    return _learn(db, q) if n >= LEARN_AFTER else None


def learn_from_save(db: Database, raw: str) -> int | None:
    return _learn(db, normalize_query(raw))


def learn_from_board(db: Database, name: str) -> int | None:
    q = normalize_query(name)
    if q in GENERIC_BOARDS or not re.search(r"[a-z]{3}", q):
        return None
    return _learn(db, q, every_hours=48, max_pages=4)


def forget(db: Database, query: str) -> None:
    """Called when you delete an interest: don't learn it back."""
    db.set_meta(f"autopilot.ignore:{normalize_query(query)}", "1")


# -- API keys from the web UI -----------------------------------------------------------------
def save_keys(settings: Settings, values: dict[str, str]) -> list[str]:
    """Write keys to NOZE_DATA_DIR/.env (keeping other lines) and apply them right away."""
    clean: dict[str, str] = {}
    for name, value in values.items():
        if name not in KEY_NAMES:
            raise ValueError(f"unknown key {name}")
        value = (value or "").strip()
        if any(c in value for c in "\r\n\0") or len(value) > 500:
            raise ValueError(f"{name}: invalid value")
        clean[name] = value
    path = Path(settings.data_dir) / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if key in clean:
            seen.add(key)
            if clean[key]:
                out.append(f"{key}={clean[key]}")
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in clean.items() if k not in seen and v]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    for k, v in clean.items():
        if v:
            settings.keys[k] = v
        else:
            settings.keys.pop(k, None)
    return sorted(k for k in KEY_NAMES if settings.key(k))
