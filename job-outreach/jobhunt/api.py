"""JSON API for the standalone frontend (deployed on Vercel).

Shares state and helpers with `web` (looked up at call time, so reloading
`web` in tests keeps working). Auth is the same DASHBOARD_PASSWORD, sent as
`Authorization: Bearer <password>` or Basic.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError

from . import autopilot, crafter, deliverability, mailer, pipeline, render
from . import web as core
from .config import Targeting

router = APIRouter(prefix="/api")


def _allowance() -> dict | None:
    if not core.settings.secrets.sender_email:
        return None
    a = mailer.allowance(core.db, core.settings)
    return {"cap": a.cap, "sent_today": a.sent_today, "remaining": a.remaining, "warmup_day": a.warmup_day,
            "bounce_rate": a.bounce_rate, "paused_reason": a.paused_reason}


def _status() -> dict:
    return {"stage": {"running": core.stage_state["running"], "result": core.stage_state["result"]},
            "autopilot": dict(autopilot.status), "send": dict(core.send_state)}


@router.get("/me")
def me():
    s = core.settings.secrets
    return {"ok": True, "sender": s.sender_email, "sender_name": s.sender_name}


@router.get("/overview")
def overview():
    db = core.db
    return {
        "stats": pipeline.stats(db),
        "setup": core.setup_status(),
        "targeting": pipeline.targeting(core.settings, db).model_dump(),
        "autopilot": db.kv_get("autopilot") or {},
        "allowance": _allowance(),
        "latest": db.all("SELECT id, source, company, title, season, poster_name, status, discovered_at FROM leads "
                         "WHERE status NOT IN ('skipped','no_contact') ORDER BY discovered_at DESC, id DESC LIMIT 8"),
        **_status(),
    }


@router.get("/status")
def status():
    return _status()


@router.post("/actions/{stage}")
def action(stage: str):
    ok, msg = core.start_send() if stage == "send" else core.start_stage(stage)
    return {"ok": ok, "message": msg, **_status()}


# ---------------------------------------------------------------- leads

@router.get("/leads")
def leads(status: str = "all", source: str = "all", q: str = ""):
    sql = ("SELECT l.id, l.source, l.company, l.domain, l.title, l.location, l.url, l.season, l.poster_name, "
           "l.match_score, l.status, l.discovered_at, d.id AS doc_id FROM leads l "
           "LEFT JOIN documents d ON d.lead_id=l.id WHERE 1=1")
    params: list = []
    if status != "all":
        sql += " AND l.status=?"
        params.append(status)
    if source != "all":
        sql += " AND l.source=?"
        params.append(source)
    if q:
        sql += " AND (LOWER(l.title) LIKE ? OR LOWER(COALESCE(l.company,'')) LIKE ? OR LOWER(COALESCE(l.poster_name,'')) LIKE ?)"
        params += [f"%{q.lower()}%"] * 3
    rows = core.db.all(sql + " ORDER BY l.discovered_at DESC, l.id DESC LIMIT 500", params)
    counts = {r["status"]: r["n"] for r in core.db.all("SELECT status, COUNT(*) AS n FROM leads GROUP BY status")}
    return {"leads": rows, "counts": counts, "sources": core.SOURCES}


@router.get("/leads/{lead_id}")
def lead(lead_id: int):
    db = core.db
    row = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not row:
        raise HTTPException(404, "lead not found")
    doc = db.one("SELECT tailored_json, cover_letter, pitch, violations, engine, created_at, "
                 "resume_pdf IS NOT NULL AS has_pdf, cover_pdf IS NOT NULL AS has_cover "
                 "FROM documents WHERE lead_id=?", (lead_id,))
    document = None
    if doc:
        payload = json.loads(doc.pop("tailored_json"))
        document = {**doc, "has_pdf": bool(doc["has_pdf"]), "has_cover": bool(doc["has_cover"]),
                    "violations": json.loads(doc["violations"] or "[]"),
                    "matched": payload.get("matched", []), "missing": payload.get("missing", [])}
    outreach = db.all("SELECT o.id, o.channel, o.kind, o.status, o.subject, o.replied_at, o.sent_at, c.name, c.email "
                      "FROM outreach o JOIN contacts c ON c.id=o.contact_id WHERE o.lead_id=? ORDER BY o.id", (lead_id,))
    return {"lead": {**row, "keywords": json.loads(row["keywords"] or "[]")}, "document": document,
            "contacts": pipeline.lead_contacts(db, row), "outreach": outreach}


@router.post("/leads/{lead_id}/tailor")
def lead_tailor(lead_id: int):
    try:
        return {"ok": True, "message": core.tailor_one(lead_id)}
    except KeyError:
        raise HTTPException(404, "lead not found")
    except Exception as exc:
        return {"ok": False, "message": f"tailoring failed: {exc}"}


@router.post("/leads/{lead_id}/enrich")
def lead_enrich(lead_id: int):
    return {"ok": True, "message": core.enrich_one(lead_id)}


class LeadStatus(BaseModel):
    status: str


@router.post("/leads/{lead_id}/status")
def lead_status(lead_id: int, body: LeadStatus):
    if body.status not in ("new", "skipped", "enriched"):
        raise HTTPException(400, "bad status")
    core.db.execute("UPDATE leads SET status=? WHERE id=?", (body.status, lead_id))
    return {"ok": True, "message": f"status set to {body.status}"}


@router.get("/files/{lead_id}/{kind}")
def files(lead_id: int, kind: str):
    return core.files(lead_id, kind)


# ---------------------------------------------------------------- outreach

@router.get("/outreach")
def outreach(status: str = "draft", channel: str = "all"):
    sql = ("SELECT o.*, c.name, c.title AS contact_title, c.email, c.linkedin_url, c.email_confidence, "
           "c.source AS contact_source, l.title AS lead_title, l.company, l.season, l.source AS lead_source "
           "FROM outreach o JOIN contacts c ON c.id=o.contact_id JOIN leads l ON l.id=o.lead_id WHERE 1=1")
    params: list = []
    if status != "all":
        sql += " AND o.status=?"
        params.append(status)
    if channel != "all":
        sql += " AND o.channel=?"
        params.append(channel)
    rows = core.db.all(sql + " ORDER BY o.id DESC LIMIT 300", params)
    counts = {r["status"]: r["n"] for r in core.db.all("SELECT status, COUNT(*) AS n FROM outreach GROUP BY status")}
    return {"rows": rows, "counts": counts}


class OutreachAction(BaseModel):
    action: str
    subject: str | None = None
    body: str | None = None


@router.post("/outreach/approve-all")
def approve_all():
    rows = core.db.all("SELECT o.id FROM outreach o JOIN contacts c ON c.id=o.contact_id "
                       "WHERE o.channel='email' AND o.status='draft' AND c.email IS NOT NULL")
    for r in rows:
        pipeline.set_outreach_status(core.db, r["id"], "approved")
    return {"ok": True, "message": f"approved {len(rows)} email(s)"}


@router.post("/outreach/{outreach_id}")
def outreach_action(outreach_id: int, body: OutreachAction):
    status = {"approve": "approved", "reject": "rejected", "done": "done", "save": "draft",
              "unapprove": "draft"}.get(body.action)
    if not status:
        raise HTTPException(400, "bad action")
    try:
        pipeline.set_outreach_status(core.db, outreach_id, status, subject=body.subject, body=body.body)
    except (KeyError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}
    return {"ok": True, "message": f"#{outreach_id} {status}"}


# ---------------------------------------------------------------- resume

@router.get("/resume")
def resume():
    db = core.db
    return {"saved": bool(db.kv_get("master_resume")), "resume": core._master(),
            "warnings": db.kv_get("master_resume_warnings") or [], "llm": bool(core.settings.secrets.llm_api_key)}


@router.post("/resume/import")
async def resume_import(file: UploadFile | None = File(None), text: str = Form("")):
    try:
        if file is not None and file.filename:
            data = await file.read()
            text = crafter.pdf_text(data) if file.filename.lower().endswith(".pdf") else data.decode("utf-8", "replace")
        parsed, warnings = crafter.import_text(text, pipeline.make_llm(core.settings))
    except crafter.CraftError as exc:
        return {"ok": False, "message": str(exc)}
    core.db.kv_set("master_resume", parsed)
    core.db.kv_set("master_resume_warnings", warnings)
    return {"ok": True, "message": "Resume imported. Review it, then save.", "resume": parsed, "warnings": warnings}


@router.put("/resume")
async def resume_save(request: Request):
    try:
        data = crafter.parse_json(json.dumps(await request.json()))
    except (crafter.CraftError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}
    core.db.kv_set("master_resume", data)
    core.db.kv_set("master_resume_warnings", [])
    return {"ok": True, "message": "Saved. New tailored resumes will use this version.", "resume": data}


@router.delete("/resume")
def resume_reset():
    core.db.execute("DELETE FROM kv WHERE key IN ('master_resume','master_resume_warnings')")
    return {"ok": True, "message": "Reverted to the bundled example resume", "resume": core._master()}


@router.get("/resume/preview")
def resume_preview(fmt: str = "pdf"):
    master = core._master()
    if not master:
        raise HTTPException(404, "no resume")
    html = render.resume_html(master)
    if fmt == "html":
        return Response(html, media_type="text/html")
    pdf = render.to_pdf(html)
    if not pdf:
        raise HTTPException(503, "PDF engine unavailable")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{render.pdf_filename(master)}"'})


# ---------------------------------------------------------------- settings

@router.get("/settings")
def get_settings():
    s = core.settings.secrets
    return {"targeting": pipeline.targeting(core.settings, core.db).model_dump(), "sources": core.SOURCES,
            "setup": core.setup_status(), "autopilot": core.db.kv_get("autopilot") or {},
            "min_email_confidence": core.settings.targets.min_email_confidence,
            "cron_configured": bool(s.cron_secret), "outreach": core.settings.outreach.model_dump()}


@router.put("/settings")
def put_settings(body: dict):
    try:
        t = Targeting.model_validate({k: v for k, v in body.items() if k in Targeting.model_fields})
    except ValidationError as exc:
        return {"ok": False, "message": str(exc.errors()[0].get("msg"))}
    t.seasons = [x.strip() for x in t.seasons if x.strip()]
    t.roles = [x.strip() for x in t.roles if x.strip()]
    t.locations = [x.strip() for x in t.locations if x.strip()]
    t.companies = [x.strip() for x in t.companies if x.strip()]
    t.sources = [x for x in t.sources if x in core.SOURCES]
    t.max_results_per_query = max(5, min(t.max_results_per_query, 100))
    t.cycle_every_hours = max(1, t.cycle_every_hours)
    t.per_tick = max(1, min(t.per_tick, 10))
    t.tailor_per_cycle = max(1, min(t.tailor_per_cycle, 50))
    t.followup_after_days = max(2, t.followup_after_days)
    if not t.roles:
        return {"ok": False, "message": "Add at least one role"}
    core.db.kv_set("targeting", t.model_dump())
    return {"ok": True, "message": "Saved", "targeting": t.model_dump()}


# ---------------------------------------------------------------- sending

@router.get("/sending")
def sending(check: int = 0):
    db, s = core.db, core.settings.secrets
    report = None
    if check and s.sender_domain:
        rep = deliverability.check_domain(s.sender_domain, s.dkim_selector, s.smtp_host)
        report = {"ok": rep.ok, "checks": [{"name": c.name, "ok": c.ok, "required": c.required, "detail": c.detail}
                                           for c in rep.checks]}
    return {
        "sender": s.sender_email, "imap": bool(s.imap_host), "allowance": _allowance(), "report": report,
        "approved": db.scalar("SELECT COUNT(*) FROM outreach WHERE channel='email' AND status='approved'"),
        "log": db.all("SELECT * FROM send_log ORDER BY id DESC LIMIT 50"),
        "suppressed": db.all("SELECT * FROM suppression ORDER BY created_at DESC LIMIT 50"),
        "replies": db.all("SELECT o.id, o.subject, o.replied_at, c.name, c.email, l.company FROM outreach o "
                          "JOIN contacts c ON c.id=o.contact_id JOIN leads l ON l.id=o.lead_id "
                          "WHERE o.replied_at IS NOT NULL ORDER BY o.replied_at DESC LIMIT 50"),
        "outreach": core.settings.outreach.model_dump(),
        **_status(),
    }


@router.post("/sending/check-inbox")
def check_inbox():
    if not core.settings.secrets.imap_host:
        return {"ok": False, "message": "Set IMAP_HOST first"}
    try:
        got = mailer.check_replies(core.db, core.settings)
    except Exception as exc:
        return {"ok": False, "message": f"Inbox check failed: {exc}"}
    return {"ok": True, "message": f"{got['replies']} new repl(ies), {got['bounces']} bounce(s)"}


class Suppress(BaseModel):
    email: str


@router.post("/sending/suppress")
def suppress(body: Suppress):
    if "@" not in body.email:
        return {"ok": False, "message": "not an email address"}
    core.db.suppress(body.email.strip(), "manual")
    return {"ok": True, "message": f"{body.email} will never be emailed"}
