"""Low-volume, authenticated cold-email dispatch.

Safety rails, all enforced here rather than left to the caller:
  * only outreach rows a human has approved are sent;
  * SPF + DKIM + DMARC must be published for the sender domain;
  * warm-up ramp and per-domain daily cap;
  * randomised spacing between messages;
  * suppression list (unsubscribes, hard bounces) and a re-contact window;
  * RFC 8058 one-click List-Unsubscribe headers plus a visible opt-out link;
  * automatic pause when the recent hard-bounce rate is too high.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import mimetypes
import random
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Callable, Protocol

from .config import Settings
from .db import DB, now_iso


# ---------------------------------------------------------------- unsubscribe tokens

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def unsubscribe_token(email: str, secret: str) -> str:
    email = email.lower().encode()
    sig = hmac.new(secret.encode(), email, hashlib.sha256).digest()[:16]
    return f"{_b64(email)}.{_b64(sig)}"


def verify_token(token: str, secret: str) -> str | None:
    try:
        raw, sig = token.split(".", 1)
        email = _unb64(raw)
        expected = hmac.new(secret.encode(), email, hashlib.sha256).digest()[:16]
        if hmac.compare_digest(expected, _unb64(sig)):
            return email.decode()
    except (ValueError, UnicodeDecodeError):
        pass
    return None


# ---------------------------------------------------------------- message

def build_message(settings: Settings, to_email: str, to_name: str, subject: str, body: str,
                  attachments: list[Path] | None = None) -> EmailMessage:
    s = settings.secrets
    token = unsubscribe_token(to_email, s.unsubscribe_secret)
    unsub_url = f"{s.public_base_url}/u/{token}"
    footer = f"\n\n--\nIf you'd rather not hear from me again, reply \"no thanks\" or unsubscribe here: {unsub_url}"
    if s.sender_postal_address:
        footer += f"\n{s.sender_postal_address}"

    msg = EmailMessage()
    msg["From"] = formataddr((s.sender_name, s.sender_email))
    msg["To"] = formataddr((to_name, to_email))
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=s.sender_domain or None)
    msg["Reply-To"] = s.sender_email
    msg["List-Unsubscribe"] = f"<{unsub_url}>, <mailto:{s.sender_email}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(body + footer)
    for path in attachments or []:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg


# ---------------------------------------------------------------- transports

class Transport(Protocol):
    def send(self, msg: EmailMessage) -> None: ...
    def close(self) -> None: ...


class DryRunTransport:
    """Writes .eml files instead of sending. Default mode."""

    def __init__(self, outbox: Path):
        self.outbox = outbox
        outbox.mkdir(parents=True, exist_ok=True)

    def send(self, msg: EmailMessage) -> None:
        name = msg["Message-ID"].strip("<>").replace("@", "_at_")
        (self.outbox / f"{name}.eml").write_bytes(bytes(msg))

    def close(self) -> None:
        pass


class SMTPTransport:
    def __init__(self, settings: Settings):
        s = settings.secrets
        if not (s.smtp_host and s.sender_email):
            raise RuntimeError("SMTP_HOST and SENDER_EMAIL must be set for live sending")
        ctx = ssl.create_default_context()
        if s.smtp_use_ssl:
            self.smtp = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ctx, timeout=60)
        else:
            self.smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=60)
            self.smtp.starttls(context=ctx)
        if s.smtp_username:
            self.smtp.login(s.smtp_username, s.smtp_password)

    def send(self, msg: EmailMessage) -> None:
        self.smtp.send_message(msg)

    def close(self) -> None:
        try:
            self.smtp.quit()
        except smtplib.SMTPException:
            pass


# ---------------------------------------------------------------- throttle

@dataclass
class Allowance:
    cap: int
    sent_today: int
    warmup_day: int
    bounce_rate: float
    paused_reason: str | None

    @property
    def remaining(self) -> int:
        return 0 if self.paused_reason else max(0, self.cap - self.sent_today)


def allowance(db: DB, settings: Settings, now: datetime | None = None) -> Allowance:
    now = now or datetime.now(timezone.utc)
    domain = settings.secrets.sender_domain
    o = settings.outreach
    first = db.scalar(
        "SELECT MIN(at) FROM send_log WHERE sender_domain=? AND outcome IN ('sent','bounced')", (domain,)
    )
    day = (now - datetime.fromisoformat(first)).days if first else 0

    steps = sorted(o.warmup, key=lambda s: s.from_day)
    cap = o.daily_cap
    for step in steps:
        if day >= step.from_day:
            cap = step.cap
    if steps and day >= steps[-1].from_day + 7:
        cap = o.daily_cap
    cap = min(cap, o.daily_cap)

    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    sent_today = db.scalar(
        "SELECT COUNT(*) FROM send_log WHERE sender_domain=? AND outcome IN ('sent','bounced') AND at >= ?",
        (domain, start),
    )
    recent = db.all(
        "SELECT outcome FROM send_log WHERE sender_domain=? AND outcome IN ('sent','bounced') ORDER BY at DESC LIMIT 100",
        (domain,),
    )
    bounces = sum(1 for r in recent if r["outcome"] == "bounced")
    rate = bounces / len(recent) if recent else 0.0
    paused = None
    if len(recent) >= 20 and rate > o.max_bounce_rate:
        paused = f"hard-bounce rate {rate:.1%} over the last {len(recent)} sends exceeds {o.max_bounce_rate:.0%}; clean your list"
    return Allowance(cap=cap, sent_today=sent_today, warmup_day=day, bounce_rate=rate, paused_reason=paused)


def live_blockers(settings: Settings) -> list[str]:
    """Reasons live sending must not start. Empty list means go."""
    from . import deliverability

    s = settings.secrets
    problems = []
    if not (s.smtp_host and s.sender_email):
        problems.append("SMTP_HOST and SENDER_EMAIL must be set")
    if s.unsubscribe_secret == "dev-only-secret":
        problems.append("set UNSUBSCRIBE_SECRET (shared by whatever sends and whatever serves /u/)")
    if s.public_base_url.startswith(("http://localhost", "http://127.")):
        problems.append("PUBLIC_BASE_URL must be publicly reachable so unsubscribe links work")
    if settings.outreach.require_authentication and s.sender_domain:
        rep = deliverability.check_domain(s.sender_domain, s.dkim_selector, s.smtp_host)
        problems += [f"sender domain not authenticated: {f}" for f in rep.failures()]
    return problems


# ---------------------------------------------------------------- batch send

@dataclass
class SendSummary:
    sent: int = 0
    bounced: int = 0
    failed: int = 0
    skipped: int = 0
    blocked_reason: str | None = None


def send_approved(db: DB, settings: Settings, transport: Transport, limit: int | None = None,
                  sleep: Callable[[float], None] = time.sleep, log: Callable[[str], None] = print,
                  dry_run: bool = False) -> SendSummary:
    """With dry_run=True messages go to `transport` but the database is left untouched,
    so previews never consume warm-up budget or trigger the re-contact window."""
    summary = SendSummary()
    mark = (lambda *a: None) if dry_run else _mark
    seen: set[str] = set()
    allow = allowance(db, settings)
    if allow.paused_reason:
        summary.blocked_reason = allow.paused_reason
        return summary
    budget = allow.remaining if limit is None else min(limit, allow.remaining)
    if budget <= 0:
        summary.blocked_reason = f"daily cap reached ({allow.sent_today}/{allow.cap}, warm-up day {allow.warmup_day})"
        return summary

    rows = db.all(
        "SELECT o.*, c.email, c.name AS contact_name, d.resume_pdf FROM outreach o "
        "JOIN contacts c ON c.id = o.contact_id LEFT JOIN documents d ON d.job_id = o.job_id "
        "WHERE o.channel='email' AND o.status='approved' ORDER BY o.approved_at, o.id"
    )
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.outreach.recontact_after_days)).isoformat()
    domain = settings.secrets.sender_domain
    first = True
    for row in rows:
        if summary.sent + summary.bounced >= budget:
            break
        email = (row["email"] or "").lower()
        if not email:
            mark(db, row["id"], "skipped", "contact has no email")
            summary.skipped += 1
            continue
        if db.is_suppressed(email):
            mark(db, row["id"], "skipped", "recipient is on the suppression list")
            summary.skipped += 1
            continue
        recent = db.scalar(
            "SELECT 1 FROM send_log WHERE recipient=? AND outcome='sent' AND at >= ?", (email, cutoff)
        )
        if recent or email in seen:
            mark(db, row["id"], "skipped", f"already contacted within {settings.outreach.recontact_after_days} days")
            summary.skipped += 1
            continue

        seen.add(email)
        if not first and not dry_run:
            delay = random.uniform(settings.outreach.min_delay_seconds, settings.outreach.max_delay_seconds)
            log(f"  waiting {delay:.0f}s before next send")
            sleep(delay)
        first = False

        attachments = []
        if settings.outreach.attach_resume and row["resume_pdf"] and Path(row["resume_pdf"]).exists():
            attachments.append(Path(row["resume_pdf"]))
        msg = build_message(settings, email, row["contact_name"], row["subject"], row["body"], attachments)
        try:
            transport.send(msg)
            if dry_run:
                summary.sent += 1
                log(f"  [dry-run] would send: {email} - {row['subject']}")
                continue
        except smtplib.SMTPRecipientsRefused as exc:
            code = next(iter(exc.recipients.values()))[0] if exc.recipients else 550
            _log(db, domain, email, row["id"], "bounced", str(exc))
            _mark(db, row["id"], "bounced", str(exc))
            if 500 <= code < 600:
                db.suppress(email, "hard_bounce")
            summary.bounced += 1
            log(f"  bounced: {email} ({code})")
            continue
        except (smtplib.SMTPException, OSError) as exc:
            _log(db, domain, email, row["id"], "failed", str(exc))
            _mark(db, row["id"], "failed", str(exc))
            summary.failed += 1
            log(f"  failed: {email}: {exc}")
            continue
        _log(db, domain, email, row["id"], "sent", None)
        db.execute(
            "UPDATE outreach SET status='sent', sent_at=?, message_id=?, error=NULL WHERE id=?",
            (now_iso(), msg["Message-ID"], row["id"]),
        )
        summary.sent += 1
        log(f"  sent: {email} - {row['subject']}")
    return summary


def _mark(db: DB, outreach_id: int, status: str, error: str | None) -> None:
    db.execute("UPDATE outreach SET status=?, error=? WHERE id=?", (status, error, outreach_id))


def _log(db: DB, domain: str, recipient: str, outreach_id: int, outcome: str, detail: str | None) -> None:
    db.execute(
        "INSERT INTO send_log (sender_domain, recipient, outreach_id, outcome, detail, at) VALUES (?,?,?,?,?,?)",
        (domain, recipient, outreach_id, outcome, detail, now_iso()),
    )
