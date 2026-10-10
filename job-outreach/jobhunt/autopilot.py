"""Auto emailer.

Free hosts sleep and kill long-running loops, so instead of a daemon the app
is driven by a "tick": something external (cron-job.org, Vercel cron, GitHub
Actions, plain crontab) calls /cron/tick every ~15 minutes. Each tick:

  1. reads the inbox (if IMAP is set) so replies and bounces stop follow-ups;
  2. every `cycle_every_hours`, runs a full cycle: find new internship leads,
     find people, craft a tailored resume per lead, draft emails;
  3. queues due follow-ups and, when auto-send is on, approves drafts to
     verified addresses;
  4. sends at most `per_tick` approved emails, inside the warm-up/daily cap.

Spreading sends over many ticks keeps volume human-looking.
"""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Callable

from . import mailer, pipeline
from .config import Settings, effective_targeting
from .db import DB, now_iso

_lock = threading.Lock()
status: dict = {"running": False, "started": None, "step": None}
HISTORY = 20


def cycle_due(state: dict, every_hours: int, now: datetime) -> bool:
    last = state.get("last_cycle")
    return not last or now - datetime.fromisoformat(last) >= timedelta(hours=every_hours)


def cycle(settings: Settings, db: DB, log: Callable[[str], None]) -> None:
    t = effective_targeting(settings, db)
    master = pipeline.load_master(settings, db)
    llm = pipeline.make_llm(settings)
    steps = [
        ("discover", lambda: pipeline.run_discover(settings, db, master)),
        ("enrich", lambda: pipeline.run_enrich(settings, db, limit=t.tailor_per_cycle * 2)),
        ("tailor", lambda: pipeline.run_tailor(settings, db, master, llm, limit=t.tailor_per_cycle)),
        ("queue", lambda: pipeline.run_queue(settings, db, master)),
    ]
    for name, fn in steps:
        _step(name, fn, log)


def _step(name: str, fn, log: Callable[[str], None]) -> None:
    status["step"] = name
    try:
        log(fn().summary(name))
    except Exception as exc:  # one failing stage must not stop sending or the next tick
        log(f"{name} failed: {exc}")
        traceback.print_exc()


def tick(settings: Settings, db: DB, force_cycle: bool = False, now: datetime | None = None,
         transport_factory: Callable[[Settings], mailer.Transport] = mailer.SMTPTransport,
         sleep: Callable[[float], None] = time.sleep) -> dict:
    if not _lock.acquire(blocking=False):
        return {"skipped": "a tick is already running"}
    now = now or datetime.now(timezone.utc)
    lines: list[str] = []
    status.update(running=True, started=now_iso(), step=None)
    state = db.kv_get("autopilot") or {}
    try:
        t = effective_targeting(settings, db)
        s = settings.secrets

        if s.imap_host:
            status["step"] = "inbox"
            try:
                got = mailer.check_replies(db, settings)
                lines.append(f"inbox: {got['replies']} new repl(ies), {got['bounces']} bounce(s)")
            except Exception as exc:
                lines.append(f"inbox check failed: {exc}")

        if force_cycle or cycle_due(state, t.cycle_every_hours, now):
            state["last_cycle"] = now.isoformat()
            db.kv_set("autopilot", state)
            cycle(settings, db, lines.append)

        master = None
        try:
            master = pipeline.load_master(settings, db)
        except Exception as exc:
            lines.append(f"no master resume: {exc}")
        if master:
            _step("followups", lambda: pipeline.run_followups(settings, db, master, t, now), lines.append)
        _step("auto-approve", lambda: pipeline.auto_approve(settings, db, t), lines.append)

        if not t.auto_send:
            lines.append("send: auto-send is off; approve drafts on the Outreach page")
        else:
            status["step"] = "send"
            blockers = mailer.live_blockers(settings)
            if blockers:
                lines.append("send blocked: " + "; ".join(blockers))
            else:
                transport = None
                try:
                    transport = transport_factory(settings)
                    summary = mailer.send_approved(db, settings, transport, limit=t.per_tick, sleep=sleep,
                                                   log=lambda m: None)
                    lines.append(f"send: {summary.sent} sent, {summary.bounced} bounced, {summary.failed} failed, "
                                 f"{summary.skipped} skipped" +
                                 (f" ({summary.blocked_reason})" if summary.blocked_reason else ""))
                except Exception as exc:
                    lines.append(f"send failed: {exc}")
                finally:
                    if transport:
                        transport.close()
    finally:
        report = {"at": now.isoformat(), "lines": lines}
        state = {**(db.kv_get("autopilot") or {}), "last_tick": now.isoformat()}
        state["history"] = ([report] + (state.get("history") or []))[:HISTORY]
        db.kv_set("autopilot", state)
        status.update(running=False, step=None)
        _lock.release()
    return report


def start_background(settings: Settings, db: DB, force_cycle: bool = False) -> bool:
    if _lock.locked():
        return False
    threading.Thread(target=tick, args=(settings, db), kwargs={"force_cycle": force_cycle}, daemon=True).start()
    return True
