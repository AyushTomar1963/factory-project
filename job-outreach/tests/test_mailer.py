import pytest
import json
import smtplib
from datetime import datetime, timedelta, timezone

from jobhunt import mailer
from jobhunt.db import now_iso


class FakeTransport:
    def __init__(self, refuse=()):
        self.sent, self.refuse = [], set(refuse)

    def send(self, msg):
        to = msg["To"].split("<")[-1].rstrip(">")
        if to in self.refuse:
            raise smtplib.SMTPRecipientsRefused({to: (550, b"no such user")})
        self.sent.append(msg)

    def close(self):
        pass


def _seed(db, emails, status="approved"):
    db.execute("INSERT INTO leads (id, source, external_id, company, domain, title, discovered_at, status) "
               "VALUES (1,'companies','acme','Acme','acme.com','Internship',?,'queued')", (now_iso(),))
    db.execute("INSERT INTO documents (lead_id, tailored_json, resume_pdf, created_at) VALUES (1,?,?,?)",
               (json.dumps({"resume": {"basics": {"name": "Jane Doe"}}}), b"%PDF-1.4 test", now_iso()))
    ids = []
    for i, e in enumerate(emails):
        cid = db.upsert_contact({"company": "Acme", "domain": "acme.com", "name": f"P{i}", "email": e, "source": "test"})
        ids.append(db.insert(
            "INSERT INTO outreach (lead_id, contact_id, channel, subject, body, status, created_at, approved_at) "
            "VALUES (1,?,'email','Hi','Body',?,?,?) RETURNING id", (cid, status, now_iso(), now_iso())))
    return ids


def test_token_roundtrip_and_tamper():
    t = mailer.unsubscribe_token("Ann@Acme.com", "s")
    assert mailer.verify_token(t, "s") == "ann@acme.com"
    assert mailer.verify_token(t, "other") is None
    assert mailer.verify_token(t[:-2] + "xx", "s") is None
    assert mailer.verify_token("garbage", "s") is None


def test_message_has_one_click_unsubscribe(settings):
    msg = mailer.build_message(settings, "ann@acme.com", "Ann", "Subj", "Hello", [("r.pdf", b"%PDF-1.4")])
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "https://jobs.example.com/u/" in msg["List-Unsubscribe"] and "mailto:" in msg["List-Unsubscribe"]
    assert msg["Message-ID"].endswith("@janedoe-careers.com>")
    text = msg.get_body(("plain",)).get_content()
    assert "unsubscribe here: https://jobs.example.com/u/" in text
    assert [p.get_filename() for p in msg.iter_attachments()] == ["r.pdf"]


def test_warmup_ramp(settings, db):
    domain = settings.secrets.sender_domain
    assert mailer.allowance(db, settings).cap == 5
    first = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    db.execute("INSERT INTO send_log (sender_domain, recipient, outcome, at) VALUES (?,?,?,?)", (domain, "x@y.com", "sent", first))
    assert mailer.allowance(db, settings).cap == 15
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    db.execute("INSERT INTO send_log (sender_domain, recipient, outcome, at) VALUES (?,?,?,?)", (domain, "x@y.com", "sent", old))
    assert mailer.allowance(db, settings).cap == settings.outreach.daily_cap


def test_send_respects_suppression_bounce_and_cap(settings, db):
    ids = _seed(db, ["a@acme.com", "b@acme.com", "c@acme.com", "d@acme.com", "e@acme.com", "f@acme.com", "g@acme.com"])
    db.suppress("b@acme.com", "unsubscribe")
    t = FakeTransport(refuse={"c@acme.com"})
    s = mailer.send_approved(db, settings, t, log=lambda *_: None, sleep=lambda *_: None)
    # warm-up day 0 cap is 5: a, (b skipped), c bounced, d, e, f -> 5 attempts
    assert (s.sent, s.bounced, s.skipped) == (4, 1, 1)
    assert db.is_suppressed("c@acme.com")
    statuses = {r["id"]: r["status"] for r in db.all("SELECT id, status FROM outreach")}
    assert statuses[ids[1]] == "skipped" and statuses[ids[2]] == "bounced" and statuses[ids[6]] == "approved"
    s2 = mailer.send_approved(db, settings, t, log=lambda *_: None)
    assert s2.blocked_reason.startswith("daily cap reached")


def test_dry_run_does_not_touch_db(settings, db):
    _seed(db, ["a@acme.com"])
    t = FakeTransport()
    s = mailer.send_approved(db, settings, t, log=lambda *_: None, dry_run=True)
    assert s.sent == 1 and len(t.sent) == 1
    assert db.scalar("SELECT COUNT(*) FROM send_log") == 0
    assert db.scalar("SELECT status FROM outreach") == "approved"


def test_recontact_window(settings, db):
    _seed(db, ["a@acme.com"])
    db.execute("INSERT INTO send_log (sender_domain, recipient, outcome, at) VALUES (?,?,?,?)",
               (settings.secrets.sender_domain, "a@acme.com", "sent", now_iso()))
    s = mailer.send_approved(db, settings, FakeTransport(), log=lambda *_: None)
    assert s.skipped == 1 and s.sent == 0


def test_bounce_rate_pauses(settings, db):
    d = settings.secrets.sender_domain
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    for i in range(30):
        db.execute("INSERT INTO send_log (sender_domain, recipient, outcome, at) VALUES (?,?,?,?)",
                   (d, f"{i}@x.com", "bounced" if i < 5 else "sent", old))
    a = mailer.allowance(db, settings)
    assert a.paused_reason and a.remaining == 0


def test_send_attaches_lead_resume_and_marks_contacted(settings, db):
    _seed(db, ["a@acme.com"])
    t = FakeTransport()
    assert mailer.send_approved(db, settings, t, log=lambda *_: None).sent == 1
    [att] = list(t.sent[0].iter_attachments())
    assert att.get_filename() == "jane-doe-resume.pdf" and att.get_content() == b"%PDF-1.4 test"
    assert db.scalar("SELECT status FROM leads WHERE id=1") == "contacted"


def _followup(db, parent_id, status="approved"):
    parent = db.one("SELECT * FROM outreach WHERE id=?", (parent_id,))
    return db.insert(
        "INSERT INTO outreach (lead_id, contact_id, channel, kind, parent_id, subject, body, status, created_at, approved_at) "
        "VALUES (1,?,'email','followup',?,'Re: Hi','Nudge',?,?,?) RETURNING id",
        (parent["contact_id"], parent_id, status, now_iso(), now_iso()))


def test_followup_is_threaded_and_bypasses_recontact_window(settings, db):
    [oid] = _seed(db, ["a@acme.com"])
    mailer.send_approved(db, settings, FakeTransport(), log=lambda *_: None)
    msgid = db.scalar("SELECT message_id FROM outreach WHERE id=?", (oid,))
    fid = _followup(db, oid)
    t = FakeTransport()
    s = mailer.send_approved(db, settings, t, log=lambda *_: None)
    assert s.sent == 1
    assert t.sent[0]["In-Reply-To"] == msgid and t.sent[0]["References"] == msgid
    assert db.scalar("SELECT status FROM outreach WHERE id=?", (fid,)) == "sent"


def test_followup_skipped_after_reply(settings, db):
    [oid] = _seed(db, ["a@acme.com"])
    mailer.send_approved(db, settings, FakeTransport(), log=lambda *_: None)
    db.execute("UPDATE outreach SET replied_at=? WHERE id=?", (now_iso(), oid))
    fid = _followup(db, oid)
    s = mailer.send_approved(db, settings, FakeTransport(), log=lambda *_: None)
    assert s.sent == 0 and db.scalar("SELECT status FROM outreach WHERE id=?", (fid,)) == "skipped"


def test_inbox_replies_cancel_followups_and_bounces_suppress(settings, db):
    a, b = _seed(db, ["a@acme.com", "b@acme.com"])
    mailer.send_approved(db, settings, FakeTransport(), log=lambda *_: None, sleep=lambda *_: None)
    fa, fb = _followup(db, a, "draft"), _followup(db, b, "approved")
    msgid_a = db.scalar("SELECT message_id FROM outreach WHERE id=?", (a,))
    got = mailer.process_inbox(db, [
        {"from": "P0 <A@acme.com>", "in_reply_to": msgid_a, "references": "", "body": "Sure, let's talk"},
        {"from": "MAILER-DAEMON@mx.acme.com", "body": "Delivery to b@acme.com failed: 550 user unknown"},
        {"from": "news@other.com", "body": "newsletter"},
    ])
    assert got == {"replies": 1, "bounces": 1}
    assert db.scalar("SELECT replied_at FROM outreach WHERE id=?", (a,))
    assert db.scalar("SELECT status FROM outreach WHERE id=?", (fa,)) == "rejected"
    assert db.scalar("SELECT status FROM outreach WHERE id=?", (b,)) == "bounced"
    assert db.scalar("SELECT status FROM outreach WHERE id=?", (fb,)) == "rejected"
    assert db.is_suppressed("b@acme.com") and not db.is_suppressed("a@acme.com")
    assert db.scalar("SELECT status FROM leads WHERE id=1") == "replied"
    assert mailer.process_inbox(db, [{"from": "a@acme.com", "body": "again"}]) == {"replies": 0, "bounces": 0}


def test_message_has_html_part_with_unsubscribe_link(settings):
    msg = mailer.build_message(settings, "ann@acme.com", "Ann", "Subj", "Hi Ann,\n\nSee https://x.dev/p <b>.",
                               [("r.pdf", b"%PDF-1.4")])
    html_part = msg.get_body(("html",)).get_content()
    assert '<a href="https://x.dev/p"' in html_part and "&lt;b&gt;" in html_part
    assert "https://jobs.example.com/u/" in html_part
    assert msg.get_body(("plain",)) is not None
    assert [p.get_filename() for p in msg.iter_attachments()] == ["r.pdf"]


class FakeSMTP:
    instances: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls, self.sent = host, port, [], []
        self.drop_next = False
        FakeSMTP.instances.append(self)

    def ehlo(self):
        self.calls.append("ehlo")

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if password == "wrong":
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

    def send_message(self, msg):
        if self.drop_next:
            self.drop_next = False
            raise smtplib.SMTPServerDisconnected("closed")
        self.sent.append(msg)

    def quit(self):
        self.calls.append("quit")


def _gmail(settings, password="abcdefghijklmnop", port=587, ssl_=False):
    s = settings.secrets
    s.smtp_host, s.smtp_port, s.smtp_use_ssl = "smtp.gmail.com", port, ssl_
    s.smtp_username, s.smtp_password = "jane@gmail.com", password
    return settings


def test_smtp_starttls_login_and_reconnect(settings):
    FakeSMTP.instances = []
    t = mailer.SMTPTransport(_gmail(settings), smtp_cls=FakeSMTP, smtp_ssl_cls=FakeSMTP)
    first = FakeSMTP.instances[0]
    assert first.calls == ["ehlo", "starttls", "ehlo", ("login", "jane@gmail.com", "abcdefghijklmnop")]
    first.drop_next = True
    t.send(mailer.build_message(settings, "a@b.com", "A", "S", "B"))
    assert len(FakeSMTP.instances) == 2 and len(FakeSMTP.instances[1].sent) == 1, "reconnected after a drop"
    t.close()


def test_smtp_ssl_on_465_and_gmail_auth_hint(settings):
    FakeSMTP.instances = []
    mailer.SMTPTransport(_gmail(settings, port=465, ssl_=True), smtp_cls=None, smtp_ssl_cls=FakeSMTP)
    assert "starttls" not in FakeSMTP.instances[0].calls
    with pytest.raises(mailer.SMTPAuthError, match="App Password"):
        mailer.SMTPTransport(_gmail(settings, password="wrong"), smtp_cls=FakeSMTP, smtp_ssl_cls=FakeSMTP)


def test_provider_quota_stops_batch_and_keeps_rows_approved(settings, db):
    ids = _seed(db, ["a@acme.com", "b@acme.com", "c@acme.com"])

    class QuotaTransport(FakeTransport):
        def send(self, msg):
            if self.sent:
                raise smtplib.SMTPDataError(550, b"5.4.5 Daily user sending limit exceeded")
            self.sent.append(msg)

    summary = mailer.send_approved(db, settings, QuotaTransport(), log=lambda *_: None)
    assert summary.sent == 1 and summary.failed == 0 and "limiting" in summary.blocked_reason
    statuses = [db.one("SELECT status FROM outreach WHERE id=?", (i,))["status"] for i in ids]
    assert statuses == ["sent", "approved", "approved"]
