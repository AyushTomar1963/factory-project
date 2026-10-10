"""Stage orchestration: discover -> enrich -> tailor -> queue -> approve -> send -> follow up."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from . import keywords, render, resume as resume_mod, sources, tailor as tailor_mod
from .config import Settings, Targeting, effective_targeting
from .db import DB, now_iso
from .enrich import Apollo, Hunter, enrich_lead
from .llm import LLMClient


@dataclass
class StageResult:
    counts: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def bump(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def summary(self, name: str) -> str:
        counts = ", ".join(f"{k}: {v}" for k, v in self.counts.items()) or "nothing to do"
        errors = f" | {len(self.errors)} error(s): {self.errors[0]}" if self.errors else ""
        return f"{name}: {counts}{errors}"


def open_db(settings: Settings) -> DB:
    return DB(settings.db_target)


def load_master(settings: Settings, db: DB | None = None) -> dict:
    """The resume saved from the dashboard wins over the file in the repo."""
    saved = db.kv_get("master_resume") if db is not None else None
    if saved:
        resume_mod.validate(saved)
        return saved
    return resume_mod.load(settings.path(settings.candidate.resume))


def make_llm(settings: Settings) -> LLMClient | None:
    s = settings.secrets
    return LLMClient(s.llm_base_url, s.llm_api_key, s.llm_model) if s.llm_api_key else None


def targeting(settings: Settings, db: DB) -> Targeting:
    return effective_targeting(settings, db)


# ---------------------------------------------------------------- discover

def run_discover(settings: Settings, db: DB, master: dict, client: httpx.Client | None = None) -> StageResult:
    res = StageResult()
    t = targeting(settings, db)
    leads, res.errors = sources.discover(settings.secrets, t, client)
    cand_kw = resume_mod.candidate_keywords(master)
    for lead in leads:
        lead_id, is_new = db.upsert_lead(lead)
        res.bump("found")
        if not is_new:
            continue
        res.bump(f"new_{lead['source']}")
        kw = keywords.extract(f"{lead['title']}\n{lead.get('description') or ''}")
        score = keywords.match_score(kw, cand_kw) if kw else None
        db.execute("UPDATE leads SET match_score=?, keywords=? WHERE id=?", (score, json.dumps(kw), lead_id))
    return res


# ---------------------------------------------------------------- enrich

def _providers(settings: Settings, apollo: Apollo | None, hunter: Hunter | None):
    s = settings.secrets
    apollo = apollo or (Apollo(s.apollo_api_key) if s.apollo_api_key else None)
    hunter = hunter or (Hunter(s.hunter_api_key) if s.hunter_api_key else None)
    return apollo, hunter


def run_enrich(settings: Settings, db: DB, apollo: Apollo | None = None, hunter: Hunter | None = None,
               limit: int | None = None) -> StageResult:
    """Find the people to email for each new lead. Leads at a company we've
    already enriched reuse those contacts instead of spending credits again."""
    res = StageResult()
    apollo, hunter = _providers(settings, apollo, hunter)
    if not apollo and not hunter:
        res.errors.append("no email finder configured: set APOLLO_API_KEY and/or HUNTER_API_KEY "
                          "(hiring-post authors are still kept as LinkedIn contacts)")
    leads = db.all("SELECT * FROM leads WHERE status='new' ORDER BY match_score DESC, id")
    for lead in leads[:limit] if limit else leads:
        if lead.get("domain") and not lead.get("poster_url") and db.scalar(
                "SELECT 1 FROM contacts WHERE domain=? AND email IS NOT NULL", (lead["domain"],)):
            db.execute("UPDATE leads SET status='enriched' WHERE id=?", (lead["id"],))
            res.bump("reused_company")
            continue
        out = enrich_lead(lead, settings.targets, apollo, hunter)
        res.errors += [f"lead {lead['id']}: {e}" for e in out["errors"]]
        for c in out["contacts"]:
            db.upsert_contact({**c, "lead_id": lead["id"]})
            res.bump("contacts")
            if c.get("email"):
                res.bump("with_email")
        has_any = bool(out["contacts"]) or bool(out["domain"] and db.scalar(
            "SELECT 1 FROM contacts WHERE domain=?", (out["domain"],)))
        db.execute(
            "UPDATE leads SET company=COALESCE(company, ?), domain=COALESCE(domain, ?), status=? WHERE id=?",
            (out["company"], out["domain"], "enriched" if has_any else "no_contact", lead["id"]),
        )
        res.bump("enriched" if has_any else "no_contact")
    return res


def lead_contacts(db: DB, lead: dict) -> list[dict]:
    return db.all(
        "SELECT * FROM contacts WHERE lead_id=? OR (domain=? AND domain IS NOT NULL) "
        "ORDER BY (email IS NULL), COALESCE(email_confidence, 0) DESC, id",
        (lead["id"], lead.get("domain") or ""),
    )


# ---------------------------------------------------------------- tailor

def tailor_lead(settings: Settings, db: DB, master: dict, lead_id: int, llm: LLMClient | None) -> dict:
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise KeyError(f"lead {lead_id} not found")
    result = tailor_mod.tailor(master, lead, llm)
    files = render.build(result.resume, lead, result.cover_letter)
    payload = {
        "resume": result.resume,
        "linkedin_note": result.linkedin_note,
        "matched": result.matched,
        "missing": result.missing,
        "job_keywords": result.job_keywords,
    }
    db.execute("DELETE FROM documents WHERE lead_id=?", (lead_id,))
    db.execute(
        "INSERT INTO documents (lead_id, tailored_json, resume_pdf, cover_pdf, cover_letter, pitch, violations, "
        "engine, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (lead_id, json.dumps(payload), files["resume_pdf"], files["cover_pdf"], result.cover_letter,
         result.pitch, json.dumps(result.violations), result.engine, now_iso()),
    )
    if lead["status"] in ("new", "enriched", "no_contact"):
        db.execute("UPDATE leads SET status='tailored' WHERE id=?", (lead_id,))
    return {"lead": lead, "files": files, "result": result}


def run_tailor(settings: Settings, db: DB, master: dict, llm: LLMClient | None = None,
               lead_ids: list[int] | None = None, limit: int | None = None) -> StageResult:
    res = StageResult()
    if lead_ids:
        ids = lead_ids
    else:
        rows = db.all(
            "SELECT l.id FROM leads l LEFT JOIN documents d ON d.lead_id=l.id "
            "WHERE l.status='enriched' AND d.id IS NULL ORDER BY l.match_score DESC, l.id"
        )
        ids = [r["id"] for r in rows]
    for lead_id in ids[:limit] if limit else ids:
        out = tailor_lead(settings, db, master, lead_id, llm)
        res.bump("tailored")
        if out["result"].violations:
            res.bump("guard_interventions", len(out["result"].violations))
        if not out["files"]["resume_pdf"]:
            res.errors.append(f"lead {lead_id}: PDF engine unavailable")
    return res


# ---------------------------------------------------------------- queue

def run_queue(settings: Settings, db: DB, master: dict) -> StageResult:
    """One initial message per person, ever: if the same recruiter shows up on
    several leads they are pitched only for the best-matching one."""
    res = StageResult()
    leads = db.all(
        "SELECT l.*, d.pitch, d.tailored_json FROM leads l JOIN documents d ON d.lead_id=l.id "
        "WHERE l.status='tailored' ORDER BY l.match_score DESC, l.id"
    )
    for lead in leads:
        payload = json.loads(lead["tailored_json"])
        contacts = lead_contacts(db, lead)
        if not contacts:
            res.bump("leads_without_contacts")
            continue
        queued = 0
        for c in contacts:
            if queued >= settings.targets.max_contacts_per_company:
                break
            if db.scalar("SELECT 1 FROM outreach WHERE contact_id=? AND kind='initial' AND status <> 'rejected'",
                         (c["id"],)):
                continue
            if c.get("email") and not db.is_suppressed(c["email"]):
                subject, body = tailor_mod.compose_email(master, lead, c, lead["pitch"])
                channel = "email"
            elif c.get("linkedin_url"):
                subject, body = None, tailor_mod.compose_linkedin_note(c, payload.get("linkedin_note", ""))
                channel = "linkedin"
            else:
                continue
            new_id = db.insert(
                "INSERT INTO outreach (lead_id, contact_id, channel, kind, subject, body, status, created_at) "
                "VALUES (?,?,?,'initial',?,?,'draft',?) ON CONFLICT DO NOTHING RETURNING id",
                (lead["id"], c["id"], channel, subject, body, now_iso()),
            )
            if new_id:
                queued += 1
                res.bump(f"{channel}_drafts")
        if queued:
            db.execute("UPDATE leads SET status='queued' WHERE id=?", (lead["id"],))
    return res


def run_followups(settings: Settings, db: DB, master: dict, t: Targeting | None = None,
                  now: datetime | None = None) -> StageResult:
    """One polite nudge per thread, only if they haven't replied or opted out."""
    res = StageResult()
    t = t or targeting(settings, db)
    if not t.followups_enabled:
        return res
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=t.followup_after_days)).isoformat()
    rows = db.all(
        "SELECT o.*, c.email, c.name, c.first_name FROM outreach o JOIN contacts c ON c.id=o.contact_id "
        "WHERE o.channel='email' AND o.kind='initial' AND o.status='sent' AND o.replied_at IS NULL "
        "AND o.sent_at <= ? AND NOT EXISTS (SELECT 1 FROM outreach f WHERE f.parent_id=o.id)",
        (cutoff,),
    )
    for o in rows:
        if not o["email"] or db.is_suppressed(o["email"]):
            continue
        lead = db.one("SELECT * FROM leads WHERE id=?", (o["lead_id"],)) or {"title": ""}
        subject, body = tailor_mod.compose_followup(master, lead, o, o["subject"] or "")
        status = "approved" if t.auto_send else "draft"
        new_id = db.insert(
            "INSERT INTO outreach (lead_id, contact_id, channel, kind, parent_id, subject, body, status, created_at, "
            "approved_at) VALUES (?,?,'email','followup',?,?,?,?,?,?) ON CONFLICT DO NOTHING RETURNING id",
            (o["lead_id"], o["contact_id"], o["id"], subject, body, status, now_iso(),
             now_iso() if status == "approved" else None),
        )
        if new_id:
            res.bump(f"followups_{status}")
    return res


def auto_approve(settings: Settings, db: DB, t: Targeting | None = None) -> StageResult:
    """With auto-send on, drafts to addresses we trust are approved without a click.
    Low-confidence guesses still wait for a human."""
    res = StageResult()
    t = t or targeting(settings, db)
    if not t.auto_send:
        return res
    rows = db.all(
        "SELECT o.id FROM outreach o JOIN contacts c ON c.id=o.contact_id "
        "WHERE o.channel='email' AND o.status='draft' AND c.email IS NOT NULL "
        "AND (c.email_status='verified' OR COALESCE(c.email_confidence, 0) >= ?)",
        (settings.targets.min_email_confidence,),
    )
    for r in rows:
        set_outreach_status(db, r["id"], "approved")
        res.bump("approved")
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


def stats(db: DB) -> dict:
    def group(sql: str) -> dict:
        return {r["k"]: r["n"] for r in db.all(sql)}
    return {
        "leads": group("SELECT status AS k, COUNT(*) AS n FROM leads GROUP BY status"),
        "sources": group("SELECT source AS k, COUNT(*) AS n FROM leads GROUP BY source"),
        "outreach": group("SELECT channel || ':' || status AS k, COUNT(*) AS n FROM outreach GROUP BY channel, status"),
        "contacts": db.scalar("SELECT COUNT(*) FROM contacts"),
        "contacts_with_email": db.scalar("SELECT COUNT(*) FROM contacts WHERE email IS NOT NULL"),
        "replies": db.scalar("SELECT COUNT(*) FROM outreach WHERE replied_at IS NOT NULL"),
        "suppressed": db.scalar("SELECT COUNT(*) FROM suppression"),
    }
