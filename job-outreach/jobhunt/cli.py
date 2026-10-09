from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import deliverability, mailer, pipeline
from .config import load_settings

ROOT = Path(__file__).resolve().parent.parent


def _print_stage(name: str, res: pipeline.StageResult) -> None:
    counts = ", ".join(f"{k}={v}" for k, v in res.counts.items()) or "nothing to do"
    print(f"[{name}] {counts}")
    for e in res.errors:
        print(f"  ! {e}", file=sys.stderr)


def cmd_init(args, settings) -> int:
    for src, dst in (("config.example.yaml", "config.yaml"), (".env.example", ".env")):
        target = Path.cwd() / dst
        if target.exists():
            print(f"{dst} already exists, leaving it alone")
        else:
            shutil.copy(ROOT / src, target)
            print(f"created {dst}")
    print("Next: edit config.yaml (companies, resume path) and .env (API keys, SMTP).")
    return 0


def cmd_discover(args, settings) -> int:
    db, master = pipeline.open_db(settings), pipeline.load_master(settings)
    _print_stage("discover", pipeline.run_discover(settings, db, master))
    return 0


def cmd_enrich(args, settings) -> int:
    res = pipeline.run_enrich(settings, pipeline.open_db(settings), refresh=args.refresh)
    _print_stage("enrich", res)
    return 1 if res.errors and not res.counts else 0


def cmd_tailor(args, settings) -> int:
    db, master = pipeline.open_db(settings), pipeline.load_master(settings)
    llm = None if args.offline else pipeline.make_llm(settings)
    if llm is None:
        print("[tailor] using offline deterministic engine (set LLM_API_KEY for LLM rewriting)")
    _print_stage("tailor", pipeline.run_tailor(settings, db, master, llm, job_ids=args.job, limit=args.limit))
    return 0


def cmd_queue(args, settings) -> int:
    db, master = pipeline.open_db(settings), pipeline.load_master(settings)
    _print_stage("queue", pipeline.run_queue(settings, db, master))
    return 0


def cmd_run(args, settings) -> int:
    db, master = pipeline.open_db(settings), pipeline.load_master(settings)
    _print_stage("discover", pipeline.run_discover(settings, db, master))
    if settings.secrets.apollo_api_key or settings.secrets.hunter_api_key:
        _print_stage("enrich", pipeline.run_enrich(settings, db))
    else:
        print("[enrich] skipped: no APOLLO_API_KEY / HUNTER_API_KEY")
    _print_stage("tailor", pipeline.run_tailor(settings, db, master, pipeline.make_llm(settings), limit=args.limit))
    _print_stage("queue", pipeline.run_queue(settings, db, master))
    print("Review drafts with `jobhunt review` or the web dashboard, then `jobhunt send`.")
    return 0


def cmd_review(args, settings) -> int:
    db = pipeline.open_db(settings)
    rows = db.all(
        "SELECT o.id, o.channel, o.subject, o.body, c.name, c.title, c.email, c.linkedin_url, j.title AS job, "
        "j.company FROM outreach o JOIN contacts c ON c.id=o.contact_id JOIN jobs j ON j.id=o.job_id "
        "WHERE o.status='draft' ORDER BY o.id"
    )
    if not rows:
        print("no drafts awaiting review")
    for r in rows:
        to = r["email"] or r["linkedin_url"]
        print(f"\n#{r['id']} [{r['channel']}] {r['company']} / {r['job']}\n  to: {r['name']} ({r['title']}) <{to}>")
        if r["subject"]:
            print(f"  subject: {r['subject']}")
        print("  " + r["body"].replace("\n", "\n  "))
    if rows:
        print("\nApprove with `jobhunt approve ID [ID...]`, reject with `jobhunt reject ID`.")
    return 0


def _set_status(args, settings, status: str) -> int:
    db = pipeline.open_db(settings)
    for i in args.ids:
        try:
            pipeline.set_outreach_status(db, i, status)
            print(f"#{i} -> {status}")
        except (KeyError, ValueError) as exc:
            print(f"#{i}: {exc}", file=sys.stderr)
    return 0


def cmd_check_domain(args, settings) -> int:
    s = settings.secrets
    domain = args.domain or s.sender_domain
    if not domain:
        print("set SENDER_EMAIL or pass a domain", file=sys.stderr)
        return 2
    rep = deliverability.check_domain(domain, args.selector or s.dkim_selector, s.smtp_host)
    for c in rep.checks:
        mark = "PASS" if c.ok else ("FAIL" if c.required else "WARN")
        print(f"  {mark:4}  {c.name:16} {c.detail}")
    print("ready to send" if rep.ok else "NOT ready: fix the FAIL items before sending")
    return 0 if rep.ok else 1


def cmd_send(args, settings) -> int:
    db = pipeline.open_db(settings)
    s = settings.secrets
    if args.live:
        blockers = mailer.live_blockers(settings)
        if blockers:
            print("refusing to send:", file=sys.stderr)
            for b in blockers:
                print(f"  - {b}", file=sys.stderr)
            return 1
        transport = mailer.SMTPTransport(settings)
    else:
        outbox = settings.path(s.output_dir) / "outbox"
        transport = mailer.DryRunTransport(outbox)
        print(f"[send] dry run: writing .eml files to {outbox} (use --live to really send)")
    allow = mailer.allowance(db, settings)
    print(f"[send] warm-up day {allow.warmup_day}, cap {allow.cap}/day, sent today {allow.sent_today}")
    try:
        summary = mailer.send_approved(db, settings, transport, limit=args.limit, dry_run=not args.live)
    finally:
        transport.close()
    if summary.blocked_reason:
        print(f"[send] blocked: {summary.blocked_reason}")
    print(f"[send] sent={summary.sent} bounced={summary.bounced} failed={summary.failed} skipped={summary.skipped}")
    return 0


def cmd_suppress(args, settings) -> int:
    db = pipeline.open_db(settings)
    for e in args.emails:
        db.suppress(e, args.reason)
        print(f"suppressed {e}")
    return 0


def cmd_status(args, settings) -> int:
    db = pipeline.open_db(settings)
    print(json.dumps(pipeline.stats(db), indent=2))
    if settings.secrets.sender_email:
        a = mailer.allowance(db, settings)
        print(f"sending: warm-up day {a.warmup_day}, {a.remaining} of {a.cap} left today"
              + (f", PAUSED: {a.paused_reason}" if a.paused_reason else ""))
    return 0


def cmd_serve(args, settings) -> int:
    import uvicorn
    port = int(args.port or os.environ.get("PORT", 8000))
    uvicorn.run("jobhunt.web:app", host=args.host, port=port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobhunt", description="Direct-to-ATS job discovery, tailoring and outreach")
    p.add_argument("-c", "--config", help="path to config.yaml (default: ./config.yaml or $JOBHUNT_CONFIG)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create config.yaml and .env from the examples").set_defaults(fn=cmd_init)
    sub.add_parser("discover", help="pull jobs from Greenhouse/Lever/Ashby/Workday").set_defaults(fn=cmd_discover)
    e = sub.add_parser("enrich", help="find hiring managers via Apollo/Hunter")
    e.add_argument("--refresh", action="store_true", help="re-query companies that already have contacts")
    e.set_defaults(fn=cmd_enrich)
    t = sub.add_parser("tailor", help="build tailored resume, cover letter and pitch")
    t.add_argument("--job", type=int, action="append", help="job id (repeatable); default: all shortlisted")
    t.add_argument("--limit", type=int)
    t.add_argument("--offline", action="store_true", help="skip the LLM even if configured")
    t.set_defaults(fn=cmd_tailor)
    sub.add_parser("queue", help="create outreach drafts for tailored jobs").set_defaults(fn=cmd_queue)
    r = sub.add_parser("run", help="discover + enrich + tailor + queue")
    r.add_argument("--limit", type=int, help="max jobs to tailor this run")
    r.set_defaults(fn=cmd_run)
    sub.add_parser("review", help="print drafts awaiting approval").set_defaults(fn=cmd_review)
    a = sub.add_parser("approve", help="approve drafts for sending")
    a.add_argument("ids", type=int, nargs="+")
    a.set_defaults(fn=lambda args, s: _set_status(args, s, "approved"))
    rj = sub.add_parser("reject", help="reject drafts")
    rj.add_argument("ids", type=int, nargs="+")
    rj.set_defaults(fn=lambda args, s: _set_status(args, s, "rejected"))
    d = sub.add_parser("done", help="mark manual LinkedIn tasks as done")
    d.add_argument("ids", type=int, nargs="+")
    d.set_defaults(fn=lambda args, s: _set_status(args, s, "done"))
    cd = sub.add_parser("check-domain", help="verify SPF/DKIM/DMARC/MX/FCrDNS for the sender domain")
    cd.add_argument("domain", nargs="?")
    cd.add_argument("--selector", help="DKIM selector (default: $DKIM_SELECTOR)")
    cd.set_defaults(fn=cmd_check_domain)
    sd = sub.add_parser("send", help="send approved emails (dry run unless --live)")
    sd.add_argument("--live", action="store_true")
    sd.add_argument("--limit", type=int)
    sd.set_defaults(fn=cmd_send)
    su = sub.add_parser("suppress", help="never email these addresses")
    su.add_argument("emails", nargs="+")
    su.add_argument("--reason", default="manual")
    su.set_defaults(fn=cmd_suppress)
    sub.add_parser("status", help="pipeline counts and sending allowance").set_defaults(fn=cmd_status)
    sv = sub.add_parser("serve", help="run the web dashboard + unsubscribe endpoint")
    sv.add_argument("--host", default="0.0.0.0")
    sv.add_argument("--port", type=int)
    sv.set_defaults(fn=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config:
        os.environ["JOBHUNT_CONFIG"] = args.config
    settings = load_settings(args.config)
    return args.fn(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
