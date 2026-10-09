"""Stage orchestration: discover -> enrich -> tailor -> queue -> (human approval) -> send."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import discovery, keywords, render, resume as resume_mod, tailor as tailor_mod
from .config import Company, Settings
from .db import DB, now_iso
from .enrich import Apollo, Hunter, enrich_company
from .llm import LLMClient


@dataclass
class StageResult:
    counts: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n


def open_db(settings: Settings) -> DB:
    return DB(settings.path(settings.secrets.db_path))


def load_master(settings: Settings) -> dict:
    return resume_mod.load(settings.path(settings.candidate.resume))


def make_llm(settings: Settings) -> LLMClient | None:
    s = settings.secrets
    return LLMClient(s.llm_base_url, s.llm_api_key, s.llm_model) if s.llm_api_key else None


# ---------------------------------------------------------------- discover

def run_discover(settings: Settings, db: DB, master: dict, client: httpx.Client | None = None) -> StageResult:
    res = StageResult()
    jobs, res.errors = discovery.discover(settings.companies, client, settings.search)
    cand_kw = resume_mod.candidate_keywords(master)
    for job in jobs:
        job_id, is_new = db.upsert_job(job)
        res.bump("fetched")
        res.bump("new" if is_new else "updated")
        current = db.one("SELECT status FROM jobs WHERE id=?", (job_id,))["status"]
        kw = keywords.extract(f"{job['title']}\n{job.get('description') or ''}")
        score = keywords.match_score(kw, cand_kw)
        if current in ("new", "filtered", "shortlisted"):
            keep = discovery.passes_filters(job, settings.search) and score >= settings.search.min_match_score
            status = "shortlisted" if keep else "filtered"
            if status == "shortlisted" and current != "shortlisted":
                res.bump("shortlisted")
        else:
            status = current
        db.set_job_score(job_id, score, kw, status)
    return res


# ---------------------------------------------------------------- enrich

def _company(settings: Settings, name: str) -> Company | None:
    return next((c for c in settings.companies if c.name == name), None)


def run_enrich(settings: Settings, db: DB, apollo: Apollo | None = None, hunter: Hunter | None = None,
               refresh: bool = False) -> StageResult:
    res = StageResult()
    s = settings.secrets
    apollo = apollo or (Apollo(s.apollo_api_key) if s.apollo_api_key else None)
    hunter = hunter or (Hunter(s.hunter_api_key) if s.hunter_api_key else None)
    if not apollo and not hunter:
        res.errors.append("no enrichment provider configured: set APOLLO_API_KEY and/or HUNTER_API_KEY")
        return res
    names = [r["company"] for r in db.all(
        "SELECT DISTINCT company FROM jobs WHERE status IN ('shortlisted','tailored')"
    )]
    for name in names:
        company = _company(settings, name)
        if not company:
            continue
        have = db.scalar("SELECT COUNT(*) FROM contacts WHERE domain=?", (company.domain,))
        if have and not refresh:
            res.bump("cached_companies")
            continue
        contacts, errors = enrich_company(company, settings.targets, apollo, hunter)
        res.errors += errors
        for c in contacts:
            db.upsert_contact(c)
            res.bump("contacts")
            if c.get("email"):
                res.bump("with_email")
    return res


# ---------------------------------------------------------------- tailor

def tailor_job(settings: Settings, db: DB, master: dict, job_id: int, llm: LLMClient | None) -> dict:
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise KeyError(f"job {job_id} not found")
    result = tailor_mod.tailor(master, job, llm)
    files = render.build(result.resume, job, result.cover_letter, settings.path(settings.secrets.output_dir))
    payload = {
        "resume": result.resume,
        "linkedin_note": result.linkedin_note,
        "matched": result.matched,
        "missing": result.missing,
        "job_keywords": result.job_keywords,
        "cover_pdf": files["cover_pdf"],
        "folder": files["folder"],
    }
    db.execute("DELETE FROM documents WHERE job_id=?", (job_id,))
    db.execute(
        "INSERT INTO documents (job_id, tailored_json, resume_html, resume_pdf, cover_letter, pitch, violations, "
        "engine, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (job_id, json.dumps(payload), files["resume_html"], files["resume_pdf"], result.cover_letter,
         result.pitch, json.dumps(result.violations), result.engine, now_iso()),
    )
    if job["status"] in ("new", "shortlisted", "filtered"):
        db.execute("UPDATE jobs SET status='tailored' WHERE id=?", (job_id,))
    return {"job": job, "files": files, "result": result}


def run_tailor(settings: Settings, db: DB, master: dict, llm: LLMClient | None = None,
               job_ids: list[int] | None = None, limit: int | None = None) -> StageResult:
    res = StageResult()
    if job_ids:
        ids = job_ids
    else:
        rows = db.all(
            "SELECT j.id FROM jobs j LEFT JOIN documents d ON d.job_id=j.id "
            "WHERE j.status='shortlisted' AND d.id IS NULL ORDER BY j.match_score DESC"
        )
        ids = [r["id"] for r in rows]
    for job_id in ids[:limit] if limit else ids:
        out = tailor_job(settings, db, master, job_id, llm)
        res.bump("tailored")
        if out["result"].violations:
            res.bump("guard_interventions", len(out["result"].violations))
        if not out["files"]["resume_pdf"]:
            res.errors.append(f"job {job_id}: PDF engine unavailable, wrote HTML only")
    return res


# ---------------------------------------------------------------- queue

def run_queue(settings: Settings, db: DB, master: dict) -> StageResult:
    """Create draft outreach for every tailored job. Each contact is pitched for at
    most one role (the best-matching one) so nobody receives several emails."""
    res = StageResult()
    jobs = db.all(
        "SELECT j.*, d.pitch, d.tailored_json FROM jobs j JOIN documents d ON d.job_id=j.id "
        "WHERE j.status='tailored' ORDER BY j.match_score DESC"
    )
    for job in jobs:
        payload = json.loads(job["tailored_json"])
        contacts = db.all("SELECT * FROM contacts WHERE domain=? ORDER BY id", (job["domain"],))
        if not contacts:
            res.bump("jobs_without_contacts")
            continue
        for c in contacts[: settings.targets.max_contacts_per_company]:
            taken = db.scalar(
                "SELECT 1 FROM outreach WHERE contact_id=? AND status NOT IN ('rejected')", (c["id"],)
            )
            if taken:
                continue
            if c.get("email") and not db.is_suppressed(c["email"]):
                subject, body = tailor_mod.compose_email(master, job, c, job["pitch"])
                channel = "email"
            elif c.get("linkedin_url"):
                subject, body = None, tailor_mod.compose_linkedin_note(c, payload.get("linkedin_note", ""))
                channel = "linkedin"
            else:
                continue
            db.execute(
                "INSERT OR IGNORE INTO outreach (job_id, contact_id, channel, subject, body, status, created_at) "
                "VALUES (?,?,?,?,?,'draft',?)",
                (job["id"], c["id"], channel, subject, body, now_iso()),
            )
            res.bump(f"{channel}_drafts")
    return res


# ---------------------------------------------------------------- review

def set_outreach_status(db: DB, outreach_id: int, status: str, subject: str | None = None,
                        body: str | None = None) -> None:
    allowed = {"approved", "rejected", "draft", "done"}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    row = db.one("SELECT * FROM outreach WHERE id=?", (outreach_id,))
    if not row:
        raise KeyError(f"outreach {outreach_id} not found")
    if row["status"] in ("sent", "bounced"):
        raise ValueError("already sent; cannot change")
    if status == "done" and row["channel"] != "linkedin":
        raise ValueError("'done' is only for manual LinkedIn tasks")
    if body is not None:
        db.execute("UPDATE outreach SET body=? WHERE id=?", (body, outreach_id))
    if subject is not None:
        db.execute("UPDATE outreach SET subject=? WHERE id=?", (subject, outreach_id))
    db.execute(
        "UPDATE outreach SET status=?, approved_at=? WHERE id=?",
        (status, now_iso() if status == "approved" else row["approved_at"], outreach_id),
    )
    if status in ("approved", "done"):
        db.execute("UPDATE jobs SET status='contacted' WHERE id=? AND status='tailored'", (row["job_id"],))


def stats(db: DB) -> dict:
    def group(sql: str) -> dict:
        return {r["k"]: r["n"] for r in db.all(sql)}
    return {
        "jobs": group("SELECT status AS k, COUNT(*) AS n FROM jobs GROUP BY status"),
        "outreach": group("SELECT channel || ':' || status AS k, COUNT(*) AS n FROM outreach GROUP BY channel, status"),
        "contacts": db.scalar("SELECT COUNT(*) FROM contacts"),
        "contacts_with_email": db.scalar("SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL"),
        "suppressed": db.scalar("SELECT COUNT(*) FROM suppression"),
    }


def resume_pdf_path(db: DB, job_id: int) -> Path | None:
    p = db.scalar("SELECT resume_pdf FROM documents WHERE job_id=?", (job_id,))
    return Path(p) if p else None
