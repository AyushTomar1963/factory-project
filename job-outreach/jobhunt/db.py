from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    domain TEXT NOT NULL,
    ats TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    department TEXT,
    url TEXT,
    description TEXT,
    posted_at TEXT,
    discovered_at TEXT NOT NULL,
    match_score REAL,
    keywords TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    UNIQUE (ats, company, external_id)
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    domain TEXT NOT NULL,
    name TEXT NOT NULL,
    first_name TEXT,
    title TEXT,
    email TEXT,
    email_confidence INTEGER,
    email_status TEXT,
    linkedin_url TEXT,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (domain, name)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
    tailored_json TEXT NOT NULL,
    resume_html TEXT,
    resume_pdf TEXT,
    cover_letter TEXT,
    pitch TEXT,
    violations TEXT,
    engine TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    channel TEXT NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    error TEXT,
    message_id TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    sent_at TEXT,
    UNIQUE (job_id, contact_id, channel)
);

CREATE TABLE IF NOT EXISTS suppression (
    email TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS send_log (
    id INTEGER PRIMARY KEY,
    sender_domain TEXT NOT NULL,
    recipient TEXT NOT NULL,
    outreach_id INTEGER,
    outcome TEXT NOT NULL,
    detail TEXT,
    at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DB:
    def __init__(self, path: str | Path):
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, tuple(params))
        self.conn.commit()
        return cur

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        return row[0] if row else None

    # ---- jobs ----
    def upsert_job(self, job: dict) -> tuple[int, bool]:
        existing = self.one(
            "SELECT id FROM jobs WHERE ats=? AND company=? AND external_id=?",
            (job["ats"], job["company"], job["external_id"]),
        )
        if existing:
            self.execute(
                "UPDATE jobs SET title=?, location=?, department=?, url=?, description=?, posted_at=? "
                "WHERE id=?",
                (job["title"], job.get("location"), job.get("department"), job.get("url"),
                 job.get("description"), job.get("posted_at"), existing["id"]),
            )
            return existing["id"], False
        cur = self.execute(
            "INSERT INTO jobs (company, domain, ats, external_id, title, location, department, url, "
            "description, posted_at, discovered_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (job["company"], job["domain"], job["ats"], job["external_id"], job["title"],
             job.get("location"), job.get("department"), job.get("url"), job.get("description"),
             job.get("posted_at"), now_iso()),
        )
        return cur.lastrowid, True

    def set_job_score(self, job_id: int, score: float, keywords: list[str], status: str) -> None:
        self.execute(
            "UPDATE jobs SET match_score=?, keywords=?, status=? WHERE id=?",
            (score, json.dumps(keywords), status, job_id),
        )

    # ---- contacts ----
    def upsert_contact(self, c: dict) -> int:
        existing = self.one("SELECT id, email FROM contacts WHERE domain=? AND name=?", (c["domain"], c["name"]))
        if existing:
            if c.get("email") and not existing["email"]:
                self.execute(
                    "UPDATE contacts SET email=?, email_confidence=?, email_status=? WHERE id=?",
                    (c["email"], c.get("email_confidence"), c.get("email_status"), existing["id"]),
                )
            return existing["id"]
        cur = self.execute(
            "INSERT INTO contacts (company, domain, name, first_name, title, email, email_confidence, "
            "email_status, linkedin_url, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (c["company"], c["domain"], c["name"], c.get("first_name"), c.get("title"),
             (c.get("email") or None) and c["email"].lower(), c.get("email_confidence"),
             c.get("email_status"), c.get("linkedin_url"), c["source"], now_iso()),
        )
        return cur.lastrowid

    # ---- suppression ----
    def suppress(self, email: str, reason: str) -> None:
        self.execute(
            "INSERT OR IGNORE INTO suppression (email, reason, created_at) VALUES (?,?,?)",
            (email.lower(), reason, now_iso()),
        )

    def is_suppressed(self, email: str) -> bool:
        return self.scalar("SELECT 1 FROM suppression WHERE email=?", (email.lower(),)) is not None
