import time

import respx

from jobhunt import autopilot

from .test_pipeline_web import _mock_apify, web  # noqa: F401,F811  (fixture)


def _wait(client):
    for _ in range(300):
        st = client.get("/api/status").json()
        if not st["stage"]["running"]:
            return st
        time.sleep(0.05)
    raise AssertionError("stage did not finish")


@respx.mock
def test_api_full_flow(web):  # noqa: F811
    web_mod, client = web
    _mock_apify()
    ov = client.get("/api/overview").json()
    assert ov["targeting"]["seasons"] == ["Summer 2027", "Winter 2026"]
    assert any(s["name"].startswith("Your resume") and not s["ok"] for s in ov["setup"])

    r = client.post("/api/actions/discover").json()
    assert r["ok"] and r["message"] == "discover started"
    assert _wait(client)["stage"]["result"].startswith("discover: found: 3")

    data = client.get("/api/leads?source=linkedin_jobs").json()
    [lead] = data["leads"]
    assert lead["company"] == "Initech" and data["counts"]["new"] == 3

    r = client.post(f"/api/leads/{lead['id']}/tailor").json()
    assert r["ok"] and "deterministic" in r["message"]
    detail = client.get(f"/api/leads/{lead['id']}").json()
    assert detail["document"]["has_pdf"] is True and "Python" in detail["document"]["matched"]
    assert client.get(f"/api/files/{lead['id']}/resume.pdf").content[:4] == b"%PDF"
    assert client.get("/api/leads/999").status_code == 404

    web_mod.db.execute("UPDATE leads SET domain='initech.io' WHERE id=?", (lead["id"],))
    web_mod.db.upsert_contact({"company": "Initech", "domain": "initech.io", "name": "Ada Byron", "first_name": "Ada",
                               "email": "ada@initech.io", "email_confidence": 95, "source": "test"})
    client.post("/api/actions/queue")
    _wait(client)
    [row] = client.get("/api/outreach").json()["rows"]
    assert row["email"] == "ada@initech.io" and row["status"] == "draft"
    r = client.post(f"/api/outreach/{row['id']}", json={"action": "save", "subject": "New subject", "body": "Hi"}).json()
    assert r["ok"]
    assert client.post("/api/outreach/approve-all").json()["message"] == "approved 1 email(s)"
    assert client.get("/api/outreach?status=approved").json()["rows"][0]["subject"] == "New subject"

    r = client.post("/api/actions/send").json()
    assert not r["ok"] and "SMTP_HOST" in r["message"]
    s = client.get("/api/sending").json()
    assert s["approved"] == 1 and s["allowance"]["cap"] == 5
    assert client.post("/api/sending/suppress", json={"email": "x@y.com"}).json()["ok"]
    assert web_mod.db.is_suppressed("x@y.com")


def test_api_settings_and_resume(web, master):  # noqa: F811
    web_mod, client = web
    r = client.put("/api/settings", json={"seasons": ["Winter 2026", " "], "roles": ["ML Intern"], "per_tick": 50,
                                          "sources": ["companies", "bogus"], "auto_send": True}).json()
    assert r["ok"] and r["targeting"]["per_tick"] == 10 and r["targeting"]["sources"] == ["companies"]
    assert client.get("/api/settings").json()["targeting"]["seasons"] == ["Winter 2026"]
    assert not client.put("/api/settings", json={"roles": []}).json()["ok"]

    assert client.get("/api/resume").json()["resume"]["basics"]["name"] == "Alex Rivera"
    assert not client.put("/api/resume", json={"basics": {"name": "x"}}).json()["ok"]
    assert client.put("/api/resume", json=master).json()["ok"]
    assert client.get("/api/resume").json()["saved"] is True
    assert client.get("/api/resume/preview").content[:4] == b"%PDF"
    r = client.post("/api/resume/import", data={"text": "my resume"}).json()
    assert not r["ok"] and "LLM_API_KEY" in r["message"]
    assert client.delete("/api/resume").json()["resume"]["basics"]["name"] == "Alex Rivera"


def test_api_actions_start_autopilot(web, monkeypatch):  # noqa: F811
    _, client = web
    calls = []
    monkeypatch.setattr(autopilot, "start_background", lambda s, d, force_cycle=False: calls.append(force_cycle) or True)
    assert client.post("/api/actions/cycle").json()["ok"]
    assert client.post("/api/actions/tick").json()["ok"]
    assert calls == [True, False]
    assert client.post("/api/actions/nope").status_code == 404


def test_api_auth_and_cors(web, monkeypatch):  # noqa: F811
    _, client = web
    monkeypatch.setenv("DASHBOARD_PASSWORD", "pw")
    r = client.get("/api/me")
    assert r.status_code == 401 and "www-authenticate" not in r.headers, "no native browser prompt"
    assert client.get("/api/me", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer pw"}).json()["ok"]

    origin = "https://jobhunt-outreach.vercel.app"
    pre = client.options("/api/me", headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                                              "Access-Control-Request-Headers": "authorization"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == origin
    r = client.get("/api/me", headers={"Origin": origin, "Authorization": "Bearer pw"})
    assert r.headers["access-control-allow-origin"] == origin
    denied = client.get("/api/me", headers={"Origin": "https://evil.example", "Authorization": "Bearer pw"})
    assert "access-control-allow-origin" not in denied.headers
