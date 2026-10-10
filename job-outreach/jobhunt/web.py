"""Dashboard, cron endpoint and public unsubscribe endpoint.

Everything except /u/*, /cron/* and /healthz is behind HTTP Basic auth when
DASHBOARD_PASSWORD is set (it must be, if you expose this publicly). /cron/*
is protected by CRON_SECRET instead.
"""
from __future__ import annotations

import base64
import json
import os
import secrets as pysecrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import autopilot, crafter, deliverability, mailer, pipeline, render
from .config import Targeting, load_settings

settings = load_settings()
db = pipeline.open_db(settings)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates" / "web"))
templates.env.filters["fromjson"] = lambda s: json.loads(s) if s else None
templates.env.filters["when"] = lambda s: (s or "")[:16].replace("T", " ")

app = FastAPI(title="jobhunt", docs_url=None, redoc_url=None)

PUBLIC_PREFIXES = ("/u/", "/healthz", "/cron/")
SOURCES = {
    "hiring_posts": "LinkedIn posts by people hiring interns (Apify Google search)",
    "linkedin_jobs": "LinkedIn internship listings, used to find who to email (Apify)",
    "companies": "Your own list of companies to cold-email",
}

_send_lock = threading.Lock()
send_state: dict = {"running": False, "started": None, "log": [], "summary": None}


def _password_ok(header: str, password: str) -> bool:
    if header.lower().startswith("bearer "):
        return pysecrets.compare_digest(header[7:], password)
    if header.lower().startswith("basic "):
        try:
            _, _, given = base64.b64decode(header[6:]).decode().partition(":")
            return pysecrets.compare_digest(given, password)
        except (ValueError, UnicodeDecodeError):
            return False
    return False


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    password = os.environ.get("DASHBOARD_PASSWORD")
    path = request.url.path
    if (password and request.method != "OPTIONS" and not path.startswith(PUBLIC_PREFIXES)
            and not _password_ok(request.headers.get("authorization", ""), password)):
        if path.startswith("/api/"):
            # No WWW-Authenticate here, so browsers don't pop their own login box over the SPA's.
            return JSONResponse({"error": "authentication required"}, 401)
        return Response("authentication required", 401, {"WWW-Authenticate": 'Basic realm="jobhunt"'})
    return await call_next(request)


# The Vercel frontend normally calls /api through a same-origin rewrite, so CORS
# never comes into play; this covers calling the Render URL directly instead.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX", r"https://[\w.-]+\.vercel\.app|http://localhost(:\d+)?"),
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


def _render(request: Request, name: str, **ctx) -> HTMLResponse:
    ctx.setdefault("flash", request.query_params.get("msg"))
    return templates.TemplateResponse(request, name, ctx)


def _back(path: str, msg: str) -> RedirectResponse:
    from urllib.parse import quote
    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{sep}msg={quote(msg)}", status_code=303)


def _master() -> dict | None:
    try:
        return pipeline.load_master(settings, db)
    except Exception:
        return None


def setup_status() -> list[dict]:
    s = settings.secrets
    return [
        {"name": "Your resume", "ok": bool(db.kv_get("master_resume")), "how": "Resume crafter: upload your PDF",
         "href": "/resume"},
        {"name": "Apify (find internship leads)", "ok": bool(s.apify_token), "how": "set APIFY_TOKEN"},
        {"name": "Apollo / Hunter (find emails)", "ok": bool(s.apollo_api_key or s.hunter_api_key),
         "how": "set APOLLO_API_KEY and/or HUNTER_API_KEY"},
        {"name": "LLM (resume + email writing)", "ok": bool(s.llm_api_key), "how": "set LLM_API_KEY (+ LLM_BASE_URL, LLM_MODEL)"},
        {"name": "SMTP (sending)", "ok": bool(s.smtp_host and s.sender_email), "how": "set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SENDER_EMAIL, SENDER_NAME"},
        {"name": "IMAP (reply detection)", "ok": bool(s.imap_host), "how": "set IMAP_HOST (login defaults to the SMTP one)"},
        {"name": "Persistent database", "ok": bool(s.database_url), "how": "set DATABASE_URL (Postgres); otherwise data resets on redeploy"},
        {"name": "Cron secret (auto emailer)", "ok": bool(s.cron_secret), "how": "set CRON_SECRET and point a cron at /cron/tick"},
    ]


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    allow = mailer.allowance(db, settings) if settings.secrets.sender_email else None
    top = db.all(
        "SELECT * FROM leads WHERE status NOT IN ('skipped','no_contact') ORDER BY discovered_at DESC, id DESC LIMIT 8")
    return _render(request, "home.html", stats=pipeline.stats(db), allow=allow, top=top, stage=stage_state,
                   t=pipeline.targeting(settings, db), setup=setup_status(), auto=db.kv_get("autopilot") or {},
                   auto_status=autopilot.status)


# ---------------------------------------------------------------- manual stages

STAGES = {
    "discover": lambda m: pipeline.run_discover(settings, db, m),
    "enrich": lambda m: pipeline.run_enrich(settings, db),
    "tailor": lambda m: pipeline.run_tailor(settings, db, m, pipeline.make_llm(settings), limit=10),
    "queue": lambda m: pipeline.run_queue(settings, db, m),
    "followups": lambda m: pipeline.run_followups(settings, db, m),
}
# Stages run in a background thread: discovery can take minutes, longer than
# a proxy in front of the app (e.g. Vercel rewrites) will hold a request open.
_stage_lock = threading.Lock()
stage_state: dict = {"running": None, "result": None}


def _stage_worker(stage: str) -> None:
    try:
        stage_state["result"] = STAGES[stage](pipeline.load_master(settings, db)).summary(stage)
    except Exception as exc:  # shown on the overview page
        stage_state["result"] = f"{stage} failed: {exc}"
    finally:
        stage_state["running"] = None


def start_stage(stage: str) -> tuple[bool, str]:
    if stage in ("cycle", "tick"):
        started = autopilot.start_background(settings, db, force_cycle=stage == "cycle")
        return started, "Autopilot " + ("started" if started else "is already running")
    if stage not in STAGES:
        raise HTTPException(404)
    with _stage_lock:
        if stage_state["running"]:
            return False, f"{stage_state['running']} is still running"
        stage_state.update(running=stage, result=None)
        threading.Thread(target=_stage_worker, args=(stage,), daemon=True).start()
    return True, f"{stage} started"


@app.post("/actions/{stage}")
def run_stage(stage: str):
    if stage == "send":
        return send_now()
    return _back("/", start_stage(stage)[1])


# ---------------------------------------------------------------- cron

def _cron_ok(request: Request, key: str | None) -> bool:
    secret = settings.secrets.cron_secret
    if not secret:
        return False
    given = key or ""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        given = header[7:]
    return pysecrets.compare_digest(given, secret)


@app.api_route("/cron/tick", methods=["GET", "POST"])
def cron_tick(request: Request, key: str | None = None, cycle: int = 0):
    if not settings.secrets.cron_secret:
        return JSONResponse({"error": "CRON_SECRET is not set on the server"}, 503)
    if not _cron_ok(request, key):
        return JSONResponse({"error": "bad cron secret"}, 401)
    started = autopilot.start_background(settings, db, force_cycle=bool(cycle))
    return JSONResponse({"started": started, "running": autopilot.status}, 202 if started else 200)


# ---------------------------------------------------------------- leads

LEAD_TABS = ["new", "enriched", "tailored", "queued", "contacted", "replied", "no_contact", "skipped", "all"]


@app.get("/leads", response_class=HTMLResponse)
def leads(request: Request, status: str = "all", source: str = "all", q: str = ""):
    sql = "SELECT l.*, d.id AS doc_id FROM leads l LEFT JOIN documents d ON d.lead_id=l.id WHERE 1=1"
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
    rows = db.all(sql + " ORDER BY l.discovered_at DESC, l.id DESC LIMIT 300", params)
    counts = {r["status"]: r["n"] for r in db.all("SELECT status, COUNT(*) AS n FROM leads GROUP BY status")}
    return _render(request, "leads.html", leads=rows, status=status, source=source, q=q, counts=counts,
                   tabs=LEAD_TABS, sources=SOURCES)


@app.get("/leads/{lead_id}", response_class=HTMLResponse)
def lead_detail(request: Request, lead_id: int):
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise HTTPException(404)
    doc = db.one("SELECT id, tailored_json, cover_letter, pitch, violations, engine, created_at, "
                 "resume_pdf IS NOT NULL AS has_pdf, cover_pdf IS NOT NULL AS has_cover "
                 "FROM documents WHERE lead_id=?", (lead_id,))
    payload = json.loads(doc["tailored_json"]) if doc else None
    outreach = db.all("SELECT o.*, c.name, c.email FROM outreach o JOIN contacts c ON c.id=o.contact_id "
                      "WHERE o.lead_id=? ORDER BY o.id", (lead_id,))
    return _render(request, "lead.html", lead=lead, doc=doc, payload=payload, contacts=pipeline.lead_contacts(db, lead),
                   outreach=outreach, keywords=json.loads(lead["keywords"] or "[]"),
                   violations=json.loads(doc["violations"] or "[]") if doc else [], sources=SOURCES)


@app.post("/leads/{lead_id}/tailor")
def lead_tailor(lead_id: int):
    try:
        msg = tailor_one(lead_id)
    except Exception as exc:
        return _back(f"/leads/{lead_id}", f"tailoring failed: {exc}")
    return _back(f"/leads/{lead_id}", msg)


def enrich_one(lead_id: int) -> str:
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise HTTPException(404)
    from .enrich import enrich_lead
    apollo, hunter = pipeline._providers(settings, None, None)
    out = enrich_lead(lead, settings.targets, apollo, hunter)
    for c in out["contacts"]:
        db.upsert_contact({**c, "lead_id": lead_id})
    status = "enriched" if out["contacts"] else "no_contact"
    db.execute("UPDATE leads SET company=COALESCE(company, ?), domain=COALESCE(domain, ?), "
               "status=CASE WHEN status IN ('new','no_contact','enriched') THEN ? ELSE status END WHERE id=?",
               (out["company"], out["domain"], status, lead_id))
    return f"{len(out['contacts'])} contact(s)" + (f"; {out['errors'][0]}" if out["errors"] else "")


def tailor_one(lead_id: int) -> str:
    out = pipeline.tailor_lead(settings, db, pipeline.load_master(settings, db), lead_id, pipeline.make_llm(settings))
    n = len(out["result"].violations)
    return f"resume crafted with {out['result'].engine}" + (f", fact guard intervened {n}x" if n else "")


@app.post("/leads/{lead_id}/enrich")
def lead_enrich(lead_id: int):
    return _back(f"/leads/{lead_id}", enrich_one(lead_id))


@app.post("/leads/{lead_id}/status")
def lead_status(lead_id: int, status: str = Form(...)):
    if status not in ("new", "skipped", "enriched"):
        raise HTTPException(400)
    db.execute("UPDATE leads SET status=? WHERE id=?", (status, lead_id))
    return _back(f"/leads/{lead_id}", f"status set to {status}")


@app.get("/files/{lead_id}/{kind}")
def files(lead_id: int, kind: str):
    doc = db.one("SELECT * FROM documents WHERE lead_id=?", (lead_id,))
    if not doc:
        raise HTTPException(404)
    resume = json.loads(doc["tailored_json"])["resume"]
    if kind == "resume.html":
        return HTMLResponse(render.resume_html(resume))
    blob = {"resume.pdf": doc["resume_pdf"], "cover.pdf": doc["cover_pdf"]}.get(kind)
    if not blob:
        raise HTTPException(404)
    name = render.pdf_filename(resume, "resume" if kind == "resume.pdf" else "cover-letter")
    return Response(bytes(blob), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


# ---------------------------------------------------------------- resume crafter

@app.get("/resume", response_class=HTMLResponse)
def resume_page(request: Request):
    saved = db.kv_get("master_resume")
    master = _master()
    return _render(request, "resume.html", saved=bool(saved), master=master,
                   master_json=json.dumps(master, indent=2, ensure_ascii=False) if master else "",
                   warnings=db.kv_get("master_resume_warnings") or [], llm=bool(settings.secrets.llm_api_key))


@app.post("/resume/import")
async def resume_import(file: UploadFile | None = File(None), text: str = Form("")):
    try:
        if file is not None and file.filename:
            data = await file.read()
            text = crafter.pdf_text(data) if file.filename.lower().endswith(".pdf") else data.decode("utf-8", "replace")
        resume, warnings = crafter.import_text(text, pipeline.make_llm(settings))
    except crafter.CraftError as exc:
        return _back("/resume", f"Import failed: {exc}")
    db.kv_set("master_resume", resume)
    db.kv_set("master_resume_warnings", warnings)
    msg = "Resume imported. Check every section below, then save."
    if warnings:
        msg += f" {len(warnings)} item(s) were not found in your original text; review them."
    return _back("/resume", msg)


@app.post("/resume/save")
def resume_save(resume_json: str = Form(...)):
    try:
        data = crafter.parse_json(resume_json)
    except crafter.CraftError as exc:
        return _back("/resume", f"Not saved: {exc}")
    db.kv_set("master_resume", data)
    db.kv_set("master_resume_warnings", [])
    return _back("/resume", "Saved. New tailored resumes will use this version.")


@app.post("/resume/reset")
def resume_reset():
    db.execute("DELETE FROM kv WHERE key IN ('master_resume','master_resume_warnings')")
    return _back("/resume", "Reverted to the example resume bundled with the app")


@app.get("/resume/preview")
def resume_preview(fmt: str = "html"):
    master = _master()
    if not master:
        raise HTTPException(404)
    html = render.resume_html(master)
    if fmt == "pdf":
        pdf = render.to_pdf(html)
        if not pdf:
            raise HTTPException(503, "PDF engine unavailable")
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{render.pdf_filename(master)}"'})
    return HTMLResponse(html)


# ---------------------------------------------------------------- targeting / autopilot settings

def _lines(v: str) -> list[str]:
    return [x.strip() for x in v.replace("\r", "").split("\n") if x.strip()]


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    base = str(request.base_url).rstrip("/")
    public = settings.secrets.public_base_url if not settings.secrets.public_base_url.startswith("http://localhost") else base
    return _render(request, "settings.html", t=pipeline.targeting(settings, db), sources=SOURCES,
                   setup=setup_status(), auto=db.kv_get("autopilot") or {}, auto_status=autopilot.status,
                   cron_url=f"{public}/cron/tick?key=" + ("YOUR_CRON_SECRET" if settings.secrets.cron_secret else "(set CRON_SECRET first)"),
                   min_conf=settings.targets.min_email_confidence)


@app.post("/settings")
def settings_save(
    seasons: str = Form(""), roles: str = Form(""), locations: str = Form(""), companies: str = Form(""),
    sources: list[str] = Form([]), max_results_per_query: int = Form(25), require_season: bool = Form(False),
    auto_send: bool = Form(False), cycle_every_hours: int = Form(24), per_tick: int = Form(3),
    tailor_per_cycle: int = Form(15), followups_enabled: bool = Form(False), followup_after_days: int = Form(5),
):
    t = Targeting(
        seasons=[s.strip() for s in seasons.replace("\n", ",").split(",") if s.strip()],
        roles=_lines(roles), locations=_lines(locations), companies=_lines(companies),
        sources=[s for s in sources if s in SOURCES], max_results_per_query=max(5, min(max_results_per_query, 100)),
        require_season=require_season, auto_send=auto_send, cycle_every_hours=max(1, cycle_every_hours),
        per_tick=max(1, min(per_tick, 10)), tailor_per_cycle=max(1, min(tailor_per_cycle, 50)),
        followups_enabled=followups_enabled, followup_after_days=max(2, followup_after_days),
    )
    if not t.roles:
        return _back("/settings", "Add at least one role")
    db.kv_set("targeting", t.model_dump())
    return _back("/settings", "Saved" + (". Auto-send is ON: approved emails go out on each tick." if auto_send else ""))


# ---------------------------------------------------------------- outreach review

@app.get("/outreach", response_class=HTMLResponse)
def outreach(request: Request, status: str = "draft", channel: str = "all"):
    sql = ("SELECT o.*, c.name, c.title AS contact_title, c.email, c.linkedin_url, c.email_confidence, c.source, "
           "l.title AS lead_title, l.company, l.season, l.source AS lead_source FROM outreach o "
           "JOIN contacts c ON c.id=o.contact_id JOIN leads l ON l.id=o.lead_id WHERE 1=1")
    params: list = []
    if status != "all":
        sql += " AND o.status=?"
        params.append(status)
    if channel != "all":
        sql += " AND o.channel=?"
        params.append(channel)
    rows = db.all(sql + " ORDER BY o.id DESC LIMIT 300", params)
    counts = {r["status"]: r["n"] for r in db.all("SELECT status, COUNT(*) AS n FROM outreach GROUP BY status")}
    return _render(request, "outreach.html", rows=rows, status=status, channel=channel, counts=counts)


@app.post("/outreach/approve-all")
def outreach_approve_all():
    rows = db.all("SELECT o.id FROM outreach o JOIN contacts c ON c.id=o.contact_id "
                  "WHERE o.channel='email' AND o.status='draft' AND c.email IS NOT NULL")
    for r in rows:
        pipeline.set_outreach_status(db, r["id"], "approved")
    return _back("/outreach?status=approved", f"approved {len(rows)} email(s)")


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


# ---------------------------------------------------------------- sending

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


def start_send() -> tuple[bool, str]:
    blockers = mailer.live_blockers(settings)
    if blockers:
        return False, "Not sending: " + "; ".join(blockers)
    with _send_lock:
        if send_state["running"]:
            return False, "A send batch is already running"
        send_state.update(running=True, log=[], summary=None,
                          started=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    threading.Thread(target=_send_worker, daemon=True).start()
    return True, "Send batch started; messages go out with randomised spacing"


def send_now():
    return _back("/sending", start_send()[1])


@app.post("/sending/check-inbox")
def check_inbox():
    if not settings.secrets.imap_host:
        return _back("/sending", "Set IMAP_HOST first")
    try:
        got = mailer.check_replies(db, settings)
    except Exception as exc:
        return _back("/sending", f"Inbox check failed: {exc}")
    return _back("/sending", f"{got['replies']} new repl(ies), {got['bounces']} bounce(s)")


@app.get("/sending", response_class=HTMLResponse)
def sending(request: Request, check: int = 0):
    s = settings.secrets
    report = deliverability.check_domain(s.sender_domain, s.dkim_selector, s.smtp_host) if check and s.sender_domain else None
    allow = mailer.allowance(db, settings) if s.sender_email else None
    log = db.all("SELECT * FROM send_log ORDER BY id DESC LIMIT 50")
    suppressed = db.all("SELECT * FROM suppression ORDER BY created_at DESC LIMIT 50")
    approved = db.scalar("SELECT COUNT(*) FROM outreach WHERE channel='email' AND status='approved'")
    replies = db.all("SELECT o.*, c.name, c.email, l.company FROM outreach o JOIN contacts c ON c.id=o.contact_id "
                     "JOIN leads l ON l.id=o.lead_id WHERE o.replied_at IS NOT NULL ORDER BY o.replied_at DESC LIMIT 50")
    return _render(request, "sending.html", report=report, allow=allow, log=log, suppressed=suppressed,
                   approved=approved, sender=s.sender_email, outreach_cfg=settings.outreach, send_state=send_state,
                   replies=replies, imap=bool(s.imap_host))


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


from . import api  # noqa: E402  (api reads this module's globals at call time)

app.include_router(api.router)
