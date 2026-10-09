import base64
import importlib
import json

import httpx
import pytest
import respx
import yaml
from fastapi.testclient import TestClient

from jobhunt import mailer, pipeline

from .conftest import GREENHOUSE_JOBS, LEVER_JOBS, ROOT


def _mock_ats():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(200, json=GREENHOUSE_JOBS))
    respx.get("https://api.lever.co/v0/postings/globex").mock(return_value=httpx.Response(200, json=LEVER_JOBS))


class FakeHunter:
    def find(self, company, targets):
        if company.domain == "acme.com":
            return [{"company": "Acme", "domain": "acme.com", "name": "Kim Ng", "first_name": "Kim", "title": "Engineering Manager",
                     "email": "kim@acme.com", "email_confidence": 97, "source": "hunter"}]
        return [{"company": "Globex", "domain": "globex.com", "name": "Lou Park", "first_name": "Lou", "title": "VP Engineering",
                 "email": None, "linkedin_url": "https://www.linkedin.com/in/loupark", "source": "hunter"}]

    def email_finder(self, *a):
        return None, None


@respx.mock
def test_end_to_end(settings, db, master):
    _mock_ats()
    res = pipeline.run_discover(settings, db, master)
    assert res.counts["fetched"] == 3 and res.errors == []
    statuses = {r["title"]: r["status"] for r in db.all("SELECT title, status FROM jobs")}
    assert statuses == {"Senior Backend Engineer": "shortlisted", "Account Executive": "filtered", "Platform Engineer": "shortlisted"}

    # re-running is idempotent
    assert pipeline.run_discover(settings, db, master).counts.get("new", 0) == 0

    res = pipeline.run_enrich(settings, db, hunter=FakeHunter())
    assert res.counts["contacts"] == 2

    res = pipeline.run_tailor(settings, db, master)
    assert res.counts["tailored"] == 2
    doc = db.one("SELECT * FROM documents d JOIN jobs j ON j.id=d.job_id WHERE j.title='Senior Backend Engineer'")
    assert doc["resume_pdf"].endswith(".pdf")
    with open(doc["resume_pdf"], "rb") as fh:
        assert fh.read(4) == b"%PDF"

    res = pipeline.run_queue(settings, db, master)
    assert res.counts == {"email_drafts": 1, "linkedin_drafts": 1}
    assert pipeline.run_queue(settings, db, master).counts == {}, "no duplicate drafts"

    email = db.one("SELECT * FROM outreach WHERE channel='email'")
    li = db.one("SELECT * FROM outreach WHERE channel='linkedin'")
    assert email["body"].startswith("Hi Kim,") and "Acme" in email["subject"]
    assert len(li["body"]) <= 300 and li["body"].startswith("Hi Lou,")

    # nothing goes out before approval
    t = mailer.DryRunTransport(settings.path(settings.secrets.output_dir) / "outbox")
    assert mailer.send_approved(db, settings, t, log=lambda *_: None).sent == 0
    pipeline.set_outreach_status(db, email["id"], "approved")
    with pytest.raises(ValueError):
        pipeline.set_outreach_status(db, email["id"], "done")

    sent = []

    class Capture:
        def send(self, msg):
            sent.append(msg)

        def close(self):
            pass

    s = mailer.send_approved(db, settings, Capture(), log=lambda *_: None)
    assert s.sent == 1
    attachments = [p.get_filename() for p in sent[0].iter_attachments()]
    assert attachments == ["jane-doe-resume.pdf"]
    assert db.scalar("SELECT status FROM outreach WHERE id=?", (email["id"],)) == "sent"
    assert db.scalar("SELECT status FROM jobs WHERE title='Senior Backend Engineer'") == "contacted"


@pytest.fixture
def web(tmp_path, monkeypatch):
    cfg = yaml.safe_load((ROOT / "config.example.yaml").read_text())
    cfg["candidate"]["resume"] = str(ROOT / "examples" / "master_resume.json")
    cfg["companies"] = [{"name": "Acme", "domain": "acme.com", "ats": "greenhouse", "board": "acme"}]
    cfg["search"]["locations"] = []
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("JOBHUNT_CONFIG", str(path))
    monkeypatch.setenv("JOBHUNT_DB", str(tmp_path / "web.db"))
    monkeypatch.setenv("JOBHUNT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "websecret")
    monkeypatch.setenv("SENDER_EMAIL", "jane@janedoe-careers.com")
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    import jobhunt.web as web_mod
    web_mod = importlib.reload(web_mod)
    return web_mod, TestClient(web_mod.app)


@respx.mock
def test_dashboard_flow(web):
    web_mod, client = web
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(200, json=GREENHOUSE_JOBS))
    assert client.get("/").status_code == 200
    r = client.post("/actions/discover")
    assert r.status_code == 200 and "shortlisted: 1" in r.text
    job_id = web_mod.db.scalar("SELECT id FROM jobs WHERE status='shortlisted'")
    r = client.post(f"/jobs/{job_id}/tailor")
    assert "tailored with deterministic" in r.text
    page = client.get(f"/jobs/{job_id}")
    assert "Rust" in page.text and "Resume PDF" in page.text
    assert client.get(f"/files/{job_id}/resume.pdf").content[:4] == b"%PDF"
    assert client.get("/jobs?status=all").status_code == 200

    web_mod.db.upsert_contact({"company": "Acme", "domain": "acme.com", "name": "Kim Ng", "first_name": "Kim",
                               "email": "kim@acme.com", "source": "test"})
    client.post("/actions/queue")
    oid = web_mod.db.scalar("SELECT id FROM outreach")
    assert "Approve for sending" in client.get("/outreach").text
    r = client.post(f"/outreach/{oid}", data={"action": "approve", "subject": "Edited subject", "body": "Edited body"})
    assert f"#{oid} approved" in r.text
    row = web_mod.db.one("SELECT * FROM outreach WHERE id=?", (oid,))
    assert (row["status"], row["subject"], row["body"]) == ("approved", "Edited subject", "Edited body")
    assert client.get("/sending").status_code == 200
    r = client.post("/actions/send")
    assert "Not sending" in r.text and "SMTP_HOST" in r.text
    assert web_mod.db.scalar("SELECT status FROM outreach WHERE id=?", (oid,)) == "approved"


def test_unsubscribe_one_click(web):
    web_mod, client = web
    token = mailer.unsubscribe_token("kim@acme.com", "websecret")
    page = client.get(f"/u/{token}")
    assert page.status_code == 200 and "Unsubscribe?" in page.text
    assert not web_mod.db.is_suppressed("kim@acme.com")
    r = client.post(f"/u/{token}", content="List-Unsubscribe=One-Click",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200 and "unsubscribed" in r.text
    assert web_mod.db.is_suppressed("kim@acme.com")
    assert client.get("/u/not-a-token").status_code == 404


def test_basic_auth_protects_dashboard_but_not_unsubscribe(web, monkeypatch):
    _, client = web
    monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
    assert client.get("/").status_code == 401
    good = base64.b64encode(b"me:pw").decode()
    assert client.get("/", headers={"Authorization": f"Basic {good}"}).status_code == 200
    assert client.get("/healthz").status_code == 200
    token = mailer.unsubscribe_token("x@acme.com", "websecret")
    assert client.get(f"/u/{token}").status_code == 200
