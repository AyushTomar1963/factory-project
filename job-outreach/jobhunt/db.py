"""Storage for SQLite (local dev) or Postgres (hosted; set DATABASE_URL).

SQL is written once in a portable subset: `?` placeholders (rewritten to `%s`
for Postgres), `ON CONFLICT DO NOTHING` and `RETURNING id`, which both engines
support.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id {pk},
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    company TEXT,
    domain TEXT,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT,
    description TEXT,
    season TEXT,
    poster_name TEXT,
    poster_url TEXT,
    posted_at TEXT,
    discovered_at TEXT NOT NULL,
    match_score REAL,
    keywords TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    note TEXT,
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS contacts (
    id {pk},
    company TEXT,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    first_name TEXT,
    title TEXT,
    email TEXT,
    email_confidence INTEGER,
    email_status TEXT,
    linkedin_url TEXT,
    source TEXT NOT NULL,
    lead_id INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE (domain, name)
);

CREATE TABLE IF NOT EXISTS documents (
    id {pk},
    lead_id INTEGER NOT NULL UNIQUE,
    tailored_json TEXT NOT NULL,
    resume_pdf BYTEA_OR_BLOB,
    cover_pdf BYTEA_OR_BLOB,
    cover_letter TEXT,
    pitch TEXT,
    violations TEXT,
    engine TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outreach (
    id {pk},
    lead_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'initial',
    parent_id INTEGER,
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    error TEXT,
    message_id TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    sent_at TEXT,
    replied_at TEXT,
    UNIQUE (lead_id, contact_id, channel, kind)
);

CREATE TABLE IF NOT EXISTS suppression (
    email TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS send_log (
    id {pk},
    sender_domain TEXT NOT NULL,
    recipient TEXT NOT NULL,
    outreach_id INTEGER,
    outcome TEXT NOT NULL,
    detail TEXT,
    at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DB:
    def __init__(self, target: str | Path):
        target = str(target)
        self.lock = threading.RLock()
        self.pg = target.startswith(("postgres://", "postgresql://"))
        self.target = target
        self._connect()
        schema = SCHEMA.replace("{pk}", "BIGSERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY")
        schema = schema.replace("BYTEA_OR_BLOB", "BYTEA" if self.pg else "BLOB")
        with self.lock:
            if self.pg:
                for stmt in filter(str.strip, schema.split(";")):
                    self.conn.execute(stmt)
            else:
                self.conn.executescript(schema)
                self.conn.commit()

    def _connect(self) -> None:
        if self.pg:
            import psycopg
            from psycopg.rows import dict_row

            self.conn = psycopg.connect(self.target, autocommit=True, row_factory=dict_row)
        else:
            if self.target != ":memory:":
                Path(self.target).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.target, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.pg else sql

    def _run(self, sql: str, params: Iterable[Any]) -> list[dict]:
        params = tuple(params)
        with self.lock:
            try:
                cur = self.conn.execute(self._sql(sql), params)
            except Exception as exc:
                if not self.pg or "closed" not in str(exc).lower() and "terminat" not in str(exc).lower():
                    raise
                self._connect()  # hosted Postgres drops idle connections
                cur = self.conn.execute(self._sql(sql), params)
            # SQLite can't commit while a RETURNING cursor is unread, so drain first.
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
            if not self.pg:
                self.conn.commit()
            return rows

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        self._run(sql, params)

    def insert(self, sql: str, params: Iterable[Any] = ()) -> int | None:
        """Run an INSERT ... RETURNING id; returns None if a conflict skipped it."""
        rows = self._run(sql, params)
        return rows[0]["id"] if rows else None

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return self._run(sql, params)

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        rows = self._run(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.one(sql, params)
        return next(iter(row.values())) if row else None

    # ---- key/value (settings, master resume, autopilot state) ----
    def kv_get(self, key: str, default: Any = None) -> Any:
        v = self.scalar("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(v) if v is not None else default

    def kv_set(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO kv (key, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT (key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, json.dumps(value), now_iso()),
        )

    # ---- leads ----
    def upsert_lead(self, lead: dict) -> tuple[int, bool]:
        existing = self.one("SELECT id FROM leads WHERE source=? AND external_id=?", (lead["source"], lead["external_id"]))
        if existing:
            return existing["id"], False
        new_id = self.insert(
            "INSERT INTO leads (source, external_id, company, domain, title, location, url, description, season, "
            "poster_name, poster_url, posted_at, discovered_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT DO NOTHING RETURNING id",
            (lead["source"], lead["external_id"], lead.get("company"), (lead.get("domain") or None),
             lead["title"], lead.get("location"), lead.get("url"), lead.get("description"), lead.get("season"),
             lead.get("poster_name"), lead.get("poster_url"), lead.get("posted_at"), now_iso()),
        )
        if new_id is None:  # lost a race with a concurrent insert
            return self.one("SELECT id FROM leads WHERE source=? AND external_id=?",
                            (lead["source"], lead["external_id"]))["id"], False
        return new_id, True

    # ---- contacts ----
    def upsert_contact(self, c: dict) -> int:
        existing = self.one("SELECT id, email FROM contacts WHERE domain=? AND name=?", (c["domain"], c["name"]))
        email = (c.get("email") or "").lower() or None
        if existing:
            if email and not existing["email"]:
                self.execute(
                    "UPDATE contacts SET email=?, email_confidence=?, email_status=? WHERE id=?",
                    (email, c.get("email_confidence"), c.get("email_status"), existing["id"]),
                )
            return existing["id"]
        return self.insert(
            "INSERT INTO contacts (company, domain, name, first_name, title, email, email_confidence, email_status, "
            "linkedin_url, source, lead_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
            (c.get("company"), c["domain"], c["name"], c.get("first_name"), c.get("title"), email,
             c.get("email_confidence"), c.get("email_status"), c.get("linkedin_url"), c["source"],
             c.get("lead_id"), now_iso()),
        )

    # ---- suppression ----
    def suppress(self, email: str, reason: str) -> None:
        self.execute(
            "INSERT INTO suppression (email, reason, created_at) VALUES (?,?,?) ON CONFLICT DO NOTHING",
            (email.lower(), reason, now_iso()),
        )

    def is_suppressed(self, email: str) -> bool:
        return self.scalar("SELECT 1 FROM suppression WHERE email=?", (email.lower(),)) is not None
