"""Low-volume, authenticated cold-email dispatch over plain SMTP.

Works with a Gmail App Password (smtp.gmail.com, no OAuth tokens to refresh)
or any other SMTP server: port 587 uses STARTTLS, port 465 implicit TLS.

Safety rails, all enforced here rather than left to the caller:
  * only approved outreach rows are sent (approved by you, or by autopilot
    for verified addresses when auto-send is switched on);
  * SPF + DKIM + DMARC must be published for the sender domain;
  * warm-up ramp and per-domain daily cap;
  * randomised spacing between messages;
  * suppression list (unsubscribes, hard bounces) and a re-contact window
    (a single threaded follow-up is the only exception);
  * RFC 8058 one-click List-Unsubscribe headers plus a visible opt-out link;
  * automatic pause when the recent hard-bounce rate is too high.
"""
from __future__ import annotations

import base64
import email as email_lib
import hashlib
import hmac
import html
import imaplib
import json
import mimetypes
import random
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr
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
                  attachments: list[tuple[str, bytes]] | None = None,
                  in_reply_to: str | None = None) -> EmailMessage:
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
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body + footer)
    msg.add_alternative(_html_body(body, unsub_url, s.sender_postal_address), subtype="html")
    for filename, data in attachments or []:
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(bytes(data), maintype=maintype, subtype=subtype, filename=filename)
    return msg


_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _linkify(text: str) -> str:
    out, last = [], 0
    for m in _URL_RE.finditer(text):
        out.append(html.escape(text[last:m.start()]))
        url = m.group(0).rstrip(".,);")
        out.append(f'<a href="{html.escape(url)}" style="color:#4f46e5">{html.escape(url)}</a>')
        out.append(html.escape(m.group(0)[len(url):]))
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def _html_body(body: str, unsub_url: str, postal: str) -> str:
    """A plain-looking HTML part: personal email, not a newsletter template."""
    paras = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    content = "".join(
        f'<p style="margin:0 0 14px">{_linkify(p).replace(chr(10), "<br>")}</p>' for p in paras)
    foot = (f'If you\'d rather not hear from me again, reply "no thanks" or '
            f'<a href="{html.escape(unsub_url)}" style="color:#6b7280">unsubscribe</a>.')
    if postal:
        foot += f"<br>{html.escape(postal)}"
    return (
        '<!doctype html><html><body style="margin:0;padding:0">'
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'font-size:15px;line-height:1.55;color:#111827;max-width:600px">'
        f'{content}<p style="margin:24px 0 0;font-size:12px;color:#6b7280">{foot}</p>'
        "</div></body></html>"
    )


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


class SMTPAuthError(RuntimeError):
    pass


class SMTPTransport:
    """One connection per batch, reopened if the server drops it mid-batch
    (Gmail closes idle connections during the randomised gaps)."""

    def __init__(self, settings: Settings, smtp_cls=smtplib.SMTP, smtp_ssl_cls=smtplib.SMTP_SSL):
        self.s = settings.secrets
        if not self.s.smtp_ready:
            raise RuntimeError("SMTP_USER, SMTP_PASSWORD and SENDER_EMAIL must be set for live sending")
        self.smtp_cls, self.smtp_ssl_cls = smtp_cls, smtp_ssl_cls
        self.smtp: smtplib.SMTP | None = None
        self._connect()

    def _connect(self) -> None:
        s = self.s
        ctx = ssl.create_default_context()
        if s.smtp_use_ssl:
            conn = self.smtp_ssl_cls(s.smtp_host, s.smtp_port, context=ctx, timeout=60)
        else:
            conn = self.smtp_cls(s.smtp_host, s.smtp_port, timeout=60)
            conn.ehlo()
            conn.starttls(context=ctx)
            conn.ehlo()
        try:
            conn.login(s.smtp_username, s.smtp_password)
        except smtplib.SMTPAuthenticationError as exc:
            _quit(conn)
            hint = (" Gmail needs a 16-character App Password (myaccount.google.com/apppasswords, "
                    "2-Step Verification must be on), not your normal password.") if s.uses_gmail else ""
            raise SMTPAuthError(f"SMTP login failed for {s.smtp_username}: {exc.smtp_code}.{hint}") from exc
        self.smtp = conn

    def send(self, msg: EmailMessage) -> None:
        try:
            self.smtp.send_message(msg)
        except smtplib.SMTPServerDisconnected:
            self._connect()
            self.smtp.send_message(msg)

    def close(self) -> None:
        if self.smtp is not None:
            _quit(self.smtp)
            self.smtp = None


def _quit(conn: smtplib.SMTP) -> None:
    try:
        conn.quit()
    except (smtplib.SMTPException, OSError):
        pass


_QUOTA_RE = re.compile(r"5\.4\.5|4\.7\.0|quota|rate limit|too many|sending limit", re.IGNORECASE)


def _is_quota_error(exc: smtplib.SMTPException) -> bool:
    """Provider-side sending limits (e.g. Gmail's daily cap): stop the batch, don't fail the rows."""
    code = getattr(exc, "smtp_code", 0) or 0
    text = str(getattr(exc, "smtp_error", b"") or exc)
    return code in (421, 450, 451, 452, 454) or bool(_QUOTA_RE.search(text))


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
    if not s.smtp_ready:
        problems.append("set SMTP_USER and SMTP_PASSWORD (a Gmail App Password, or your SMTP server's login)"
                        + ("" if s.sender_email else " and SENDER_EMAIL"))
    if s.unsubscribe_secret == "dev-only-secret":
        problems.append("set UNSUBSCRIBE_SECRET (shared by whatever sends and whatever serves /u/)")
    if s.public_base_url.startswith(("http://localhost", "http://127.")):
        problems.append("PUBLIC_BASE_URL must be publicly reachable so unsubscribe links work")
    if settings.outreach.require_authentication and s.sender_domain and s.smtp_ready:
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
        "SELECT o.*, c.email, c.name AS contact_name, d.resume_pdf, d.tailored_json, "
        "p.message_id AS parent_message_id, p.status AS parent_status, p.replied_at AS parent_replied_at "
        "FROM outreach o JOIN contacts c ON c.id = o.contact_id "
        "LEFT JOIN documents d ON d.lead_id = o.lead_id LEFT JOIN outreach p ON p.id = o.parent_id "
        "WHERE o.channel='email' AND o.status='approved' "
        "ORDER BY CASE WHEN o.kind='followup' THEN 0 ELSE 1 END, o.approved_at, o.id"
    )
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.outreach.recontact_after_days)).isoformat()
    domain = settings.secrets.sender_domain
    first = True
    for row in rows:
        if summary.sent + summary.bounced >= budget:
            break
        email = (row["email"] or "").lower()
        followup = row["kind"] == "followup"
        if not email:
            mark(db, row["id"], "skipped", "contact has no email")
            summary.skipped += 1
            continue
        if db.is_suppressed(email):
            mark(db, row["id"], "skipped", "recipient is on the suppression list")
            summary.skipped += 1
            continue
        if followup and (row["parent_status"] != "sent" or row["parent_replied_at"]):
            mark(db, row["id"], "skipped", "original was not delivered or already got a reply")
            summary.skipped += 1
            continue
        recent = db.scalar(
            "SELECT 1 FROM send_log WHERE recipient=? AND outcome='sent' AND at >= ?", (email, cutoff)
        )
        if (recent and not followup) or email in seen:
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
        if settings.outreach.attach_resume and row["resume_pdf"]:
            attachments.append((_resume_filename(row["tailored_json"]), row["resume_pdf"]))
        msg = build_message(settings, email, row["contact_name"], row["subject"], row["body"], attachments,
                            in_reply_to=row["parent_message_id"] if followup else None)
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
        except (smtplib.SMTPDataError, smtplib.SMTPSenderRefused, smtplib.SMTPResponseException) as exc:
            if _is_quota_error(exc):
                summary.blocked_reason = f"the SMTP server is limiting sends ({exc}); the rest stay approved for next time"
                log(f"  stopped: {summary.blocked_reason}")
                break
            _log(db, domain, email, row["id"], "failed", str(exc))
            _mark(db, row["id"], "failed", str(exc))
            summary.failed += 1
            log(f"  failed: {email}: {exc}")
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
        db.execute("UPDATE leads SET status='contacted' WHERE id=? AND status IN ('tailored','queued')",
                   (row["lead_id"],))
        summary.sent += 1
        log(f"  sent: {email} - {row['subject']}")
    return summary


def _resume_filename(tailored_json: str | None) -> str:
    from .render import pdf_filename

    try:
        return pdf_filename(json.loads(tailored_json)["resume"])
    except (TypeError, KeyError, ValueError):
        return "resume.pdf"


# ---------------------------------------------------------------- replies & bounces (IMAP)

_ADDR_RE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")


def process_inbox(db: DB, messages: list[dict]) -> dict:
    """`messages` are {"from", "in_reply_to", "references", "body"} dicts.
    Replies stop follow-ups; delivery-failure notices count as hard bounces."""
    counts = {"replies": 0, "bounces": 0}
    sent = {r["email"].lower(): r for r in db.all(
        "SELECT DISTINCT c.email FROM outreach o JOIN contacts c ON c.id=o.contact_id "
        "WHERE o.status='sent' AND c.email IS NOT NULL"
    )}
    by_msgid = {r["message_id"]: r["id"] for r in db.all(
        "SELECT id, message_id FROM outreach WHERE message_id IS NOT NULL")}
    for m in messages:
        sender = (parseaddr(m.get("from") or "")[1] or "").lower()
        if re.match(r"(mailer-daemon|postmaster)@", sender):
            hits = {a.lower() for a in _ADDR_RE.findall(m.get("body") or "")} & set(sent)
            for addr in hits:
                if db.is_suppressed(addr):
                    continue
                db.suppress(addr, "hard_bounce")
                db.execute(
                    "UPDATE outreach SET status='bounced', error='bounce notice received' WHERE status='sent' "
                    "AND kind='initial' AND contact_id IN (SELECT id FROM contacts WHERE email=?)", (addr,))
                _cancel_pending(db, addr, "address bounced")
                counts["bounces"] += 1
            continue
        refs = " ".join([m.get("in_reply_to") or "", m.get("references") or ""])
        matched_ids = [oid for mid, oid in by_msgid.items() if mid and mid in refs]
        if sender not in sent and not matched_ids:
            continue
        when = now_iso()
        updated = db.all(
            "SELECT o.id FROM outreach o JOIN contacts c ON c.id=o.contact_id "
            "WHERE o.status='sent' AND o.replied_at IS NULL AND c.email=?", (sender,))
        ids = {r["id"] for r in updated} | set(matched_ids)
        for oid in ids:
            db.execute("UPDATE outreach SET replied_at=? WHERE id=? AND replied_at IS NULL", (when, oid))
        if ids:
            counts["replies"] += 1
            if sender in sent:
                _cancel_pending(db, sender, "they replied")
            db.execute("UPDATE leads SET status='replied' WHERE id IN "
                       f"(SELECT lead_id FROM outreach WHERE id IN ({','.join('?' * len(ids))}))", tuple(ids))
    return counts


def _cancel_pending(db: DB, email: str, why: str) -> None:
    db.execute(
        "UPDATE outreach SET status='rejected', error=? WHERE status IN ('draft','approved') "
        "AND contact_id IN (SELECT id FROM contacts WHERE email=?)", (why, email))


def fetch_inbox(settings: Settings, days: int = 14) -> list[dict]:
    s = settings.secrets
    if not (s.imap_host and s.imap_username):
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    out = []
    with imaplib.IMAP4_SSL(s.imap_host, timeout=60) as box:
        box.login(s.imap_username, s.imap_password)
        box.select("INBOX", readonly=True)
        _, data = box.search(None, f"(SINCE {since})")
        for num in (data[0] or b"").split()[-300:]:
            _, parts = box.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM IN-REPLY-TO REFERENCES)] BODY.PEEK[TEXT]<0.20000>)")
            raw = [p[1] for p in parts if isinstance(p, tuple)]
            if not raw:
                continue
            headers = email_lib.message_from_bytes(raw[0])
            out.append({
                "from": headers.get("From", ""),
                "in_reply_to": headers.get("In-Reply-To", ""),
                "references": headers.get("References", ""),
                "body": raw[1].decode("utf-8", "replace") if len(raw) > 1 else "",
            })
    return out


def check_replies(db: DB, settings: Settings) -> dict:
    return process_inbox(db, fetch_inbox(settings))


def _mark(db: DB, outreach_id: int, status: str, error: str | None) -> None:
    db.execute("UPDATE outreach SET status=?, error=? WHERE id=?", (status, error, outreach_id))


def _log(db: DB, domain: str, recipient: str, outreach_id: int, outcome: str, detail: str | None) -> None:
    db.execute(
        "INSERT INTO send_log (sender_domain, recipient, outreach_id, outcome, detail, at) VALUES (?,?,?,?,?,?)",
        (domain, recipient, outreach_id, outcome, detail, now_iso()),
    )
