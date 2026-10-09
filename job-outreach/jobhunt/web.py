"""Review dashboard + public unsubscribe endpoint.

Everything except /u/* and /healthz is behind HTTP Basic auth when
DASHBOARD_PASSWORD is set (it must be, if you expose this publicly).
"""
from __future__ import annotations

import base64
import json
import os
import secrets as pysecrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import deliverability, mailer, pipeline
from .config import load_settings

settings = load_settings()
db = pipeline.open_db(settings)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates" / "web"))
templates.env.filters["fromjson"] = lambda s: json.loads(s) if s else None

app = FastAPI(title="jobhunt", docs_url=None, redoc_url=None)

PUBLIC_PREFIXES = ("/u/", "/healthz")

_send_lock = threading.Lock()
send_state: dict = {"running": False, "started": None, "log": [], "summary": None}


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    password = os.environ.get("DASHBOARD_PASSWORD")
    if password and not request.url.path.startswith(PUBLIC_PREFIXES):
        header = request.headers.get("authorization", "")
        ok = False
        if header.lower().startswith("basic "):
            try:
                _, _, given = base64.b64decode(header[6:]).decode().partition(":")
                ok = pysecrets.compare_digest(given, password)
            except (ValueError, UnicodeDecodeError):
                ok = False
        if not ok:
            return Response("authentication required", 401, {"WWW-Authenticate": 'Basic realm="jobhunt"'})
    return await call_next(request)


def _render(request: Request, name: str, **ctx) -> HTMLResponse:
    ctx.setdefault("flash", request.query_params.get("msg"))
    return templates.TemplateResponse(request, name, ctx)


def _back(path: str, msg: str) -> RedirectResponse:
    from urllib.parse import quote
    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{sep}msg={quote(msg)}", status_code=303)


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    allow = mailer.allowance(db, settings) if settings.secrets.sender_email else None
    top = db.all(
        "SELECT * FROM jobs WHERE status IN ('shortlisted','tailored') ORDER BY match_score DESC LIMIT 8"
    )
    return _render(request, "home.html", stats=pipeline.stats(db), allow=allow, top=top,
                   companies=settings.companies, llm=bool(settings.secrets.llm_api_key),
                   enrich=bool(settings.secrets.apollo_api_key or settings.secrets.hunter_api_key))


@app.post("/actions/{stage}")
def run_stage(stage: str):
    if stage == "send":
        return send_now()
    master = pipeline.load_master(settings)
    if stage == "discover":
        res = pipeline.run_discover(settings, db, master)
    elif stage == "enrich":
        res = pipeline.run_enrich(settings, db)
    elif stage == "tailor":
        res = pipeline.run_tailor(settings, db, master, pipeline.make_llm(settings), limit=10)
    elif stage == "queue":
        res = pipeline.run_queue(settings, db, master)
    else:
        raise HTTPException(404)
    counts = ", ".join(f"{k}: {v}" for k, v in res.counts.items()) or "nothing to do"
    errors = f" | {len(res.errors)} error(s): {res.errors[0]}" if res.errors else ""
    return _back("/", f"{stage}: {counts}{errors}")


@app.get("/jobs", response_class=HTMLResponse)
def jobs(request: Request, status: str = "shortlisted", q: str = ""):
    sql = "SELECT j.*, d.id AS doc_id FROM jobs j LEFT JOIN documents d ON d.job_id=j.id WHERE 1=1"
    params: list = []
    if status != "all":
        sql += " AND j.status=?"
        params.append(status)
    if q:
        sql += " AND (j.title LIKE ? OR j.company LIKE ? OR j.location LIKE ?)"
        params += [f"%{q}%"] * 3
    rows = db.all(sql + " ORDER BY j.match_score DESC, j.discovered_at DESC LIMIT 300", params)
    counts = {r["status"]: r["n"] for r in db.all("SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
    return _render(request, "jobs.html", jobs=rows, status=status, q=q, counts=counts)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise HTTPException(404)
    doc = db.one("SELECT * FROM documents WHERE job_id=?", (job_id,))
    payload = json.loads(doc["tailored_json"]) if doc else None
    contacts = db.all("SELECT * FROM contacts WHERE domain=? ORDER BY id", (job["domain"],))
    outreach = db.all(
        "SELECT o.*, c.name, c.email FROM outreach o JOIN contacts c ON c.id=o.contact_id WHERE o.job_id=?", (job_id,)
    )
    return _render(request, "job.html", job=job, doc=doc, payload=payload, contacts=contacts, outreach=outreach,
                   keywords=json.loads(job["keywords"] or "[]"),
                   violations=json.loads(doc["violations"] or "[]") if doc else [])


@app.post("/jobs/{job_id}/tailor")
def job_tailor(job_id: int):
    master = pipeline.load_master(settings)
    out = pipeline.tailor_job(settings, db, master, job_id, pipeline.make_llm(settings))
    n = len(out["result"].violations)
    return _back(f"/jobs/{job_id}", f"tailored with {out['result'].engine}" + (f", guard intervened {n}x" if n else ""))


@app.post("/jobs/{job_id}/status")
def job_status(job_id: int, status: str = Form(...)):
    if status not in ("shortlisted", "skipped", "filtered"):
        raise HTTPException(400)
    db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    return _back(f"/jobs/{job_id}", f"status set to {status}")


@app.get("/files/{job_id}/{kind}")
def files(job_id: int, kind: str):
    doc = db.one("SELECT * FROM documents WHERE job_id=?", (job_id,))
    if not doc:
        raise HTTPException(404)
    payload = json.loads(doc["tailored_json"])
    path = {"resume.pdf": doc["resume_pdf"], "resume.html": doc["resume_html"],
            "cover.pdf": payload.get("cover_pdf")}.get(kind)
    if not path or not Path(path).exists():
        raise HTTPException(404)
    out_dir = settings.path(settings.secrets.output_dir).resolve()
    if out_dir not in Path(path).resolve().parents:
        raise HTTPException(403)
    return FileResponse(path)


@app.get("/outreach", response_class=HTMLResponse)
def outreach(request: Request, status: str = "draft", channel: str = "all"):
    sql = ("SELECT o.*, c.name, c.title AS contact_title, c.email, c.linkedin_url, c.email_confidence, c.source, "
           "j.title AS job_title, j.company, j.match_score FROM outreach o "
           "JOIN contacts c ON c.id=o.contact_id JOIN jobs j ON j.id=o.job_id WHERE 1=1")
    params: list = []
    if status != "all":
        sql += " AND o.status=?"
        params.append(status)
    if channel != "all":
        sql += " AND o.channel=?"
        params.append(channel)
    rows = db.all(sql + " ORDER BY o.id DESC LIMIT 300", params)
    counts = {r["status"]: r["n"] for r in db.all("SELECT status, COUNT(*) n FROM outreach GROUP BY status")}
    return _render(request, "outreach.html", rows=rows, status=status, channel=channel, counts=counts)


@app.post("/outreach/{outreach_id}")
def outreach_action(outreach_id: int, action: str = Form(...), subject: str | None = Form(None),
                    body: str | None = Form(None), back: str = Form("/outreach")):
    status = {"approve": "approved", "reject": "rejected", "done": "done", "save": "draft", "unapprove": "draft"}.get(action)
    if not status:
        raise HTTPException(400)
    try:
        pipeline.set_outreach_status(db, outreach_id, status, subject=subject, body=body)
    except (KeyError, ValueError) as exc:
        return _back(back, f"#{outreach_id}: {exc}")
    return _back(back, f"#{outreach_id} {status}")


def _send_worker() -> None:
    transport = None
    try:
        transport = mailer.SMTPTransport(settings)
        summary = mailer.send_approved(db, settings, transport, log=send_state["log"].append)
        send_state["summary"] = (f"sent {summary.sent}, bounced {summary.bounced}, failed {summary.failed}, "
                                 f"skipped {summary.skipped}" + (f" ({summary.blocked_reason})" if summary.blocked_reason else ""))
    except Exception as exc:  # surfaced on the page instead of dying silently in a thread
        send_state["summary"] = f"error: {exc}"
    finally:
        if transport:
            transport.close()
        send_state["running"] = False


def send_now():
    blockers = mailer.live_blockers(settings)
    if blockers:
        return _back("/sending", "Not sending: " + "; ".join(blockers))
    with _send_lock:
        if send_state["running"]:
            return _back("/sending", "A send batch is already running")
        send_state.update(running=True, log=[], summary=None,
                          started=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    threading.Thread(target=_send_worker, daemon=True).start()
    return _back("/sending", "Send batch started; messages go out with randomised spacing")


@app.get("/sending", response_class=HTMLResponse)
def sending(request: Request, check: int = 0):
    s = settings.secrets
    report = deliverability.check_domain(s.sender_domain, s.dkim_selector, s.smtp_host) if check and s.sender_domain else None
    allow = mailer.allowance(db, settings) if s.sender_email else None
    log = db.all("SELECT * FROM send_log ORDER BY id DESC LIMIT 50")
    suppressed = db.all("SELECT * FROM suppression ORDER BY created_at DESC LIMIT 50")
    approved = db.scalar("SELECT COUNT(*) FROM outreach WHERE channel='email' AND status='approved'")
    return _render(request, "sending.html", report=report, allow=allow, log=log, suppressed=suppressed,
                   approved=approved, sender=s.sender_email, outreach_cfg=settings.outreach, send_state=send_state)


# ---------------------------------------------------------------- public unsubscribe

def _unsub_email(token: str) -> str:
    email = mailer.verify_token(token, settings.secrets.unsubscribe_secret)
    if not email:
        raise HTTPException(404, "invalid link")
    return email


@app.get("/u/{token}", response_class=HTMLResponse)
def unsubscribe_page(request: Request, token: str):
    email = _unsub_email(token)
    return templates.TemplateResponse(request, "unsubscribe.html", {
        "email": email, "token": token, "done": db.is_suppressed(email), "sender": settings.secrets.sender_name,
    })


@app.post("/u/{token}", response_class=HTMLResponse)
def unsubscribe(request: Request, token: str):
    """Handles both the confirmation form and RFC 8058 one-click POSTs from mail clients."""
    email = _unsub_email(token)
    db.suppress(email, "unsubscribe")
    db.execute(
        "UPDATE outreach SET status='rejected', error='recipient unsubscribed' WHERE status IN ('draft','approved') "
        "AND contact_id IN (SELECT id FROM contacts WHERE email=?)", (email,),
    )
    return templates.TemplateResponse(request, "unsubscribe.html", {
        "email": email, "token": token, "done": True, "sender": settings.secrets.sender_name,
    })
