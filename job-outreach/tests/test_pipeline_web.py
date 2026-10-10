import base64
import importlib
import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
import yaml
from fastapi.testclient import TestClient

from jobhunt import autopilot, mailer, pipeline, render

from .conftest import APIFY, GOOGLE_RESULTS, LINKEDIN_JOBS, ROOT, TEST_PG, reset_pg


def _mock_apify():
    respx.post(f"{APIFY}/apify~google-search-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(200, json=GOOGLE_RESULTS))
    respx.post(f"{APIFY}/curious_coder~linkedin-jobs-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(200, json=LINKEDIN_JOBS))


class FakeApollo:
    PEOPLE = {
        "initech.io": [{"name": "Ada Byron", "first_name": "Ada", "title": "CTO", "email": "ada@initech.io",
                        "email_status": "verified", "email_confidence": 95, "source": "apollo"}],
        "acme.com": [{"name": "Kim Ng", "first_name": "Kim", "title": "Founder", "email": "kim@acme.com",
                      "email_status": None, "email_confidence": 97, "source": "apollo"}],
    }

    def match_linkedin(self, url):
        return {"name": "Priya Shah", "first_name": "Priya", "title": "Engineering Manager", "email": "priya@globex.com",
                "email_status": "verified", "linkedin_url": url, "organization": {"name": "Globex", "primary_domain": "globex.com"}}

    def org_domain(self, name):
        return {"Initech": "initech.io"}.get(name)

    def company_contacts(self, company, domain, targets):
        return [{**p, "company": company, "domain": domain} for p in self.PEOPLE.get(domain, [])]


class Capture:
    def __init__(self, *_):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)

    def close(self):
        pass


@respx.mock
def test_end_to_end_internship_pipeline(settings, db, master, monkeypatch):
    _mock_apify()
    res = pipeline.run_discover(settings, db, master)
    assert res.errors == []
    assert res.counts == {"found": 3, "new_companies": 1, "new_hiring_posts": 1, "new_linkedin_jobs": 1}
    assert pipeline.run_discover(settings, db, master).counts == {"found": 3}, "idempotent"

    res = pipeline.run_enrich(settings, db, apollo=FakeApollo())
    assert res.counts["enriched"] == 3 and res.counts["with_email"] == 3
    post = db.one("SELECT * FROM leads WHERE source='hiring_posts'")
    assert (post["company"], post["domain"]) == ("Globex", "globex.com"), "learned from the post author"

    res = pipeline.run_tailor(settings, db, master)
    assert res.counts["tailored"] == 3
    pdf = db.scalar("SELECT resume_pdf FROM documents WHERE lead_id=?", (post["id"],))
    assert bytes(pdf)[:4] == b"%PDF"

    res = pipeline.run_queue(settings, db, master)
    assert res.counts == {"email_drafts": 3}
    assert pipeline.run_queue(settings, db, master).counts == {}, "no duplicate drafts"
    priya = db.one("SELECT o.* FROM outreach o JOIN contacts c ON c.id=o.contact_id WHERE c.email='priya@globex.com'")
    assert priya["body"].startswith("Hi Priya,") and "LinkedIn post about hiring interns" in priya["body"]
    assert priya["subject"].startswith("Summer 2027 internship - Jane Doe")

    # auto-send off: nothing is approved or sent automatically
    assert pipeline.auto_approve(settings, db).counts == {}
    assert mailer.send_approved(db, settings, Capture(), log=lambda *_: None).sent == 0

    # auto-send on: the tick approves trusted drafts and sends per_tick of them
    db.kv_set("targeting", {"auto_send": True, "per_tick": 2})
    monkeypatch.setattr(mailer, "live_blockers", lambda s: [])
    transport = Capture()
    report = autopilot.tick(settings, db, transport_factory=lambda s: transport, sleep=lambda *_: None)
    assert any(line.startswith("auto-approve: approved: 3") for line in report["lines"]), report
    assert any(line.startswith("send: 2 sent") for line in report["lines"]), report
    assert len(transport.sent) == 2
    assert [a.get_filename() for a in transport.sent[0].iter_attachments()] == ["jane-doe-resume.pdf"]
    state = db.kv_get("autopilot")
    assert state["last_cycle"] and state["history"][0]["lines"] == report["lines"]

    # follow-ups after the configured gap, threaded onto the original
    old = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    db.execute("UPDATE outreach SET sent_at=? WHERE status='sent'", (old,))
    res = pipeline.run_followups(settings, db, master)
    assert res.counts == {"followups_approved": 2}
    assert pipeline.run_followups(settings, db, master).counts == {}, "only one follow-up per thread"
    f = db.one("SELECT * FROM outreach WHERE kind='followup' ORDER BY id LIMIT 1")
    assert f["subject"].startswith("Re: ") and f["parent_id"]


def test_load_master_prefers_saved_resume(settings, db, master):
    assert pipeline.load_master(settings, db)["basics"]["name"] == "Alex Rivera", "bundled student example"
    db.kv_set("master_resume", master)
    assert pipeline.load_master(settings, db)["basics"]["name"] == "Jane Doe"


def test_student_resume_puts_education_first():
    student = json.loads((ROOT / "examples" / "student_resume.json").read_text())
    html = render.resume_html(student)
    assert html.index("Education") < html.index("Projects") < html.index("Experience")
    assert "Dean&#39;s List" in html or "Dean's List" in html


# ---------------------------------------------------------------- web

@pytest.fixture
def web(tmp_path, monkeypatch):
    cfg = yaml.safe_load((ROOT / "config.example.yaml").read_text())
    cfg["candidate"]["resume"] = str(ROOT / "examples" / "student_resume.json")
    cfg["targeting"]["companies"] = ["Acme, acme.com"]
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv("JOBHUNT_CONFIG", str(path))
    monkeypatch.setenv("JOBHUNT_DB", str(tmp_path / "web.db"))
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "websecret")
    monkeypatch.setenv("SENDER_EMAIL", "jane@janedoe-careers.com")
    monkeypatch.setenv("APIFY_TOKEN", "tok")
    monkeypatch.setenv("CRON_SECRET", "cronsecret")
    for k in ("DASHBOARD_PASSWORD", "DATABASE_URL", "LLM_API_KEY", "APOLLO_API_KEY", "HUNTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    if TEST_PG:
        reset_pg()
        monkeypatch.setenv("DATABASE_URL", TEST_PG)
    import jobhunt.web as web_mod
    web_mod = importlib.reload(web_mod)
    return web_mod, TestClient(web_mod.app)


def _wait(web_mod):
    for _ in range(300):
        if not web_mod.stage_state["running"]:
            return
        time.sleep(0.05)
    raise AssertionError("stage did not finish")


@respx.mock
def test_dashboard_flow(web):
    web_mod, client = web
    _mock_apify()
    home = client.get("/")
    assert home.status_code == 200 and "Finish setup" in home.text and "Summer 2027" in home.text

    r = client.post("/actions/discover")
    assert "discover started" in r.text
    _wait(web_mod)
    assert "Last run: discover: found: 3" in client.get("/").text
    assert client.get("/leads").text.count('href="/leads/') >= 3
    lead_id = web_mod.db.scalar("SELECT id FROM leads WHERE source='linkedin_jobs'")

    r = client.post(f"/leads/{lead_id}/tailor")
    assert "resume crafted with deterministic" in r.text
    page = client.get(f"/leads/{lead_id}")
    assert "Software Engineering Intern" in page.text and "Resume PDF" in page.text
    assert client.get(f"/files/{lead_id}/resume.pdf").content[:4] == b"%PDF"
    assert "Alex Rivera" in client.get(f"/files/{lead_id}/resume.html").text

    web_mod.db.execute("UPDATE leads SET domain='initech.io' WHERE id=?", (lead_id,))
    web_mod.db.upsert_contact({"company": "Initech", "domain": "initech.io", "name": "Ada Byron", "first_name": "Ada",
                               "email": "ada@initech.io", "email_confidence": 95, "source": "test"})
    client.post("/actions/queue")
    _wait(web_mod)
    oid = web_mod.db.scalar("SELECT id FROM outreach")
    assert "Approve for sending" in client.get("/outreach").text
    r = client.post(f"/outreach/{oid}", data={"action": "approve", "subject": "Edited subject", "body": "Edited body"})
    assert f"#{oid} approved" in r.text
    row = web_mod.db.one("SELECT * FROM outreach WHERE id=?", (oid,))
    assert (row["status"], row["subject"], row["body"]) == ("approved", "Edited subject", "Edited body")
    assert client.get("/sending").status_code == 200
    r = client.post("/actions/send")
    assert "Not sending" in r.text and "SMTP_HOST" in r.text


def test_settings_page_saves_targeting(web):
    web_mod, client = web
    assert "Summer 2027" in client.get("/settings").text
    r = client.post("/settings", data={
        "seasons": "Winter 2026", "roles": "ML Intern\nBackend Intern", "locations": "Bengaluru\nRemote",
        "companies": "razorpay.com", "sources": ["hiring_posts", "companies"], "auto_send": "true",
        "per_tick": "4", "cycle_every_hours": "12", "tailor_per_cycle": "5", "max_results_per_query": "10",
        "followups_enabled": "true", "followup_after_days": "7",
    })
    assert "Auto-send is ON" in r.text
    t = pipeline.targeting(web_mod.settings, web_mod.db)
    assert t.seasons == ["Winter 2026"] and t.roles == ["ML Intern", "Backend Intern"]
    assert t.sources == ["hiring_posts", "companies"] and t.auto_send and t.per_tick == 4
    client.post("/settings", data={"roles": "ML Intern"})
    t = pipeline.targeting(web_mod.settings, web_mod.db)
    assert not t.auto_send and not t.followups_enabled, "unchecked boxes turn things off"


def test_resume_crafter_save_import_and_preview(web, monkeypatch, master):
    web_mod, client = web
    assert "bundled example" in client.get("/resume").text
    r = client.post("/resume/save", data={"resume_json": "{not json"})
    assert "Not saved" in r.text
    r = client.post("/resume/save", data={"resume_json": json.dumps(master)})
    assert "Saved" in r.text and web_mod.db.kv_get("master_resume")["basics"]["name"] == "Jane Doe"
    assert client.get("/resume/preview?fmt=pdf").content[:4] == b"%PDF"

    class FakeLLM:
        model = "fake"

        def complete_json(self, system, user, temperature=0):
            assert "Sam Lee" in user
            return {"basics": {"name": "Sam Lee", "email": "sam@uni.edu"},
                    "education": [{"institution": "State University", "area": "CS"}],
                    "skills": [{"name": "Languages", "keywords": ["Python", "Rust"]}]}

    monkeypatch.setattr(pipeline, "make_llm", lambda s: FakeLLM())
    text = "Sam Lee\nsam@uni.edu\nState University, CS\nSkills: Python"
    r = client.post("/resume/import", files={"file": ("resume.txt", text.encode(), "text/plain")})
    assert "Resume imported" in r.text and "1 item(s)" in r.text
    assert web_mod.db.kv_get("master_resume")["basics"]["name"] == "Sam Lee"
    assert web_mod.db.kv_get("master_resume_warnings") == ["skill 'Rust'"]
    assert "skill &#39;Rust&#39;" in client.get("/resume").text
    client.post("/resume/reset")
    assert pipeline.load_master(web_mod.settings, web_mod.db)["basics"]["name"] == "Alex Rivera"


def test_cron_tick_requires_secret(web, monkeypatch):
    web_mod, client = web
    calls = []
    monkeypatch.setattr(autopilot, "start_background", lambda s, d, force_cycle=False: calls.append(force_cycle) or True)
    assert client.get("/cron/tick").status_code == 401
    assert client.get("/cron/tick?key=wrong").status_code == 401
    assert client.get("/cron/tick?key=cronsecret").status_code == 202
    assert client.post("/cron/tick?cycle=1", headers={"Authorization": "Bearer cronsecret"}).status_code == 202
    assert calls == [False, True]
    web_mod.settings.secrets.cron_secret = ""
    assert client.get("/cron/tick?key=").status_code == 503


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


def test_basic_auth_protects_dashboard_but_not_public_routes(web, monkeypatch):
    _, client = web
    monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
    assert client.get("/").status_code == 401
    assert client.get("/resume").status_code == 401
    good = base64.b64encode(b"me:pw").decode()
    assert client.get("/", headers={"Authorization": f"Basic {good}"}).status_code == 200
    assert client.get("/healthz").status_code == 200
    token = mailer.unsubscribe_token("x@acme.com", "websecret")
    assert client.get(f"/u/{token}").status_code == 200
    assert client.get("/cron/tick?key=wrong").status_code == 401, "cron uses its own secret, not basic auth"
