import httpx
import respx

from jobhunt import discovery
from jobhunt.config import Company, SearchCfg

from .conftest import GREENHOUSE_JOBS, LEVER_JOBS


def test_html_to_text_handles_greenhouse_double_encoding():
    text = discovery.html_to_text("&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;")
    assert text == "Hello & welcome\n- Python"


@respx.mock
def test_discover_normalises_all_ats():
    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").mock(return_value=httpx.Response(200, json=GREENHOUSE_JOBS))
    respx.get("https://api.lever.co/v0/postings/globex").mock(return_value=httpx.Response(200, json=LEVER_JOBS))
    respx.get("https://api.ashbyhq.com/posting-api/job-board/initech").mock(return_value=httpx.Response(200, json={"jobs": [
        {"id": "a1", "title": "Data Engineer", "location": "Berlin", "isRemote": True, "department": "Data",
         "jobUrl": "https://jobs.ashbyhq.com/initech/a1", "descriptionPlain": "Spark and Airflow", "publishedAt": "2026-09-30"},
        {"id": "a2", "title": "Hidden", "isListed": False},
    ]}))
    respx.post("https://hooli.wd5.myworkdayjobs.com/wday/cxs/hooli/Careers/jobs").mock(side_effect=[
        httpx.Response(200, json={"jobPostings": [{"title": "SRE", "externalPath": "/job/NYC/SRE_R1", "locationsText": "NYC", "bulletFields": ["R1"]}]}),
        httpx.Response(200, json={"jobPostings": []}),
    ])
    respx.get("https://hooli.wd5.myworkdayjobs.com/wday/cxs/hooli/Careers/job/NYC/SRE_R1").mock(
        return_value=httpx.Response(200, json={"jobPostingInfo": {"jobDescription": "<p>Linux and Prometheus</p>"}}))
    respx.get("https://boards-api.greenhouse.io/v1/boards/broken/jobs").mock(return_value=httpx.Response(404))

    companies = [
        Company(name="Acme", domain="ACME.com", ats="greenhouse", board="acme"),
        Company(name="Globex", domain="globex.com", ats="lever", board="globex"),
        Company(name="Initech", domain="initech.com", ats="ashby", board="initech"),
        Company(name="Hooli", domain="hooli.com", ats="workday", board="hooli/5/Careers"),
        Company(name="Broken", domain="broken.com", ats="greenhouse", board="broken"),
    ]
    jobs, errors = discovery.discover(companies)
    by_title = {j["title"]: j for j in jobs}

    assert set(by_title) == {"Senior Backend Engineer", "Account Executive", "Platform Engineer", "Data Engineer", "SRE"}
    gh = by_title["Senior Backend Engineer"]
    assert gh["domain"] == "acme.com" and gh["external_id"] == "101" and "Kafka" in gh["description"]
    assert gh["department"] == "Engineering"
    lever = by_title["Platform Engineer"]
    assert "Docker" in lever["description"] and lever["posted_at"].startswith("2026")
    assert by_title["Data Engineer"]["location"] == "Berlin (Remote)"
    assert by_title["SRE"]["description"] == "Linux and Prometheus"
    assert len(errors) == 1 and "Broken" in errors[0]


def test_filters():
    s = SearchCfg(title_include=["engineer"], title_exclude=["staff"], locations=["remote", "new york"])
    assert discovery.passes_filters({"title": "Backend Engineer", "location": "New York, NY"}, s)
    assert not discovery.passes_filters({"title": "Staff Engineer", "location": "Remote"}, s)
    assert not discovery.passes_filters({"title": "Designer", "location": "Remote"}, s)
    assert not discovery.passes_filters({"title": "Engineer", "location": "London"}, s)
