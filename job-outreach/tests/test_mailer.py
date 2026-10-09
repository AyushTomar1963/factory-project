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


def _seed(db, emails):
    db.execute("INSERT INTO jobs (id, company, domain, ats, external_id, title, discovered_at, status) "
               "VALUES (1,'Acme','acme.com','greenhouse','1','Engineer',?,'tailored')", (now_iso(),))
    ids = []
    for i, e in enumerate(emails):
        cid = db.upsert_contact({"company": "Acme", "domain": "acme.com", "name": f"P{i}", "email": e, "source": "test"})
        cur = db.execute("INSERT INTO outreach (job_id, contact_id, channel, subject, body, status, created_at, approved_at) "
                         "VALUES (1,?,'email','Hi','Body','approved',?,?)", (cid, now_iso(), now_iso()))
        ids.append(cur.lastrowid)
    return ids


def test_token_roundtrip_and_tamper():
    t = mailer.unsubscribe_token("Ann@Acme.com", "s")
    assert mailer.verify_token(t, "s") == "ann@acme.com"
    assert mailer.verify_token(t, "other") is None
    assert mailer.verify_token(t[:-2] + "xx", "s") is None
    assert mailer.verify_token("garbage", "s") is None


def test_message_has_one_click_unsubscribe(settings, tmp_path):
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    msg = mailer.build_message(settings, "ann@acme.com", "Ann", "Subj", "Hello", [pdf])
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
