import json

import httpx
import respx

from jobhunt import sources
from jobhunt.config import Secrets, Targeting

from .conftest import APIFY, GOOGLE_RESULTS, LINKEDIN_JOBS


def test_parse_post_extracts_author_profile():
    lead = sources.parse_post(GOOGLE_RESULTS[0]["organicResults"][0])
    assert lead["poster_url"] == "https://www.linkedin.com/in/priya-shah-12ab"
    assert lead["poster_name"] == "Priya Shah"
    assert lead["url"].endswith("activity-7100"), "tracking params stripped"
    assert sources.parse_post({"url": "https://example.com/x"}) is None


def test_season_and_internship_detection():
    assert sources.detect_season("Summer 2027 interns wanted", ["Winter 2026", "Summer 2027"]) == "Summer 2027"
    assert sources.detect_season("summer internship", ["Winter 2026", "Summer 2027"]) == "Summer 2027"
    assert sources.detect_season("full time", ["Summer 2027"]) is None
    assert sources.is_internship("Co-op student") and sources.is_internship("INTERNSHIP")
    assert not sources.is_internship("International sales")


def test_company_list_parsing():
    t = Targeting(companies=["Razorpay, razorpay.com", "zerodha.com", "Some Startup"], seasons=["Summer 2027"])
    leads = sources.company_leads(t)
    assert [(lead["company"], lead["domain"]) for lead in leads] == [
        ("Razorpay", "razorpay.com"), ("Zerodha", "zerodha.com"), ("Some Startup", None)]
    assert all(lead["season"] == "Summer 2027" for lead in leads)


def test_domain_of_ignores_social_hosts():
    assert sources.domain_of("https://www.initech.io/careers") == "initech.io"
    assert sources.domain_of("https://www.linkedin.com/company/x") is None


@respx.mock
def test_discover_merges_sources_and_drops_non_internships():
    google = respx.post(f"{APIFY}/apify~google-search-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(200, json=GOOGLE_RESULTS))
    jobs = respx.post(f"{APIFY}/curious_coder~linkedin-jobs-scraper/run-sync-get-dataset-items").mock(
        return_value=httpx.Response(200, json=LINKEDIN_JOBS))
    t = Targeting(seasons=["Summer 2027"], roles=["Backend Intern"], locations=["Bengaluru"], companies=["acme.com"])
    leads, errors = sources.discover(Secrets(apify_token="tok"), t)
    assert errors == []
    by_source = {}
    for lead in leads:
        by_source.setdefault(lead["source"], []).append(lead)
    assert len(by_source["hiring_posts"]) == 1, "the senior-engineers post is not an internship"
    assert by_source["hiring_posts"][0]["season"] == "Summer 2027"
    assert [j["company"] for j in by_source["linkedin_jobs"]] == ["Initech"]
    assert by_source["linkedin_jobs"][0]["domain"] == "initech.io"
    assert by_source["companies"][0]["domain"] == "acme.com"

    q = json.loads(google.calls[0].request.content)["queries"]
    assert 'site:linkedin.com/posts hiring intern "Summer 2027" "Backend" "Bengaluru"' in q
    urls = json.loads(jobs.calls[0].request.content)["urls"]
    assert "f_E=1" in urls[0] and "location=Bengaluru" in urls[0]
    assert google.calls[0].request.url.params["token"] == "tok"


def test_discover_without_token_reports_and_keeps_company_list():
    leads, errors = sources.discover(Secrets(), Targeting(companies=["acme.com"]))
    assert [lead["source"] for lead in leads] == ["companies"]
    assert len(errors) == 2 and all("APIFY_TOKEN" in e for e in errors)


@respx.mock
def test_apify_errors_are_reported():
    respx.post(url__regex=r".*/run-sync-get-dataset-items").mock(return_value=httpx.Response(402))
    leads, errors = sources.discover(Secrets(apify_token="t"), Targeting(sources=["hiring_posts"]))
    assert leads == [] and "out of credits" in errors[0]


def test_require_season_filters_posts():
    t = Targeting(seasons=["Winter 2026"], require_season=True, sources=[])
    assert sources.discover(Secrets(), t) == ([], [])
