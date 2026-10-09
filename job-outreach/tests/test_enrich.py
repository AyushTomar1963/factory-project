import httpx
import respx

from jobhunt.config import Company, TargetsCfg
from jobhunt.enrich import Apollo, Hunter, enrich_company, title_rank

TARGETS = TargetsCfg(titles=["Engineering Manager", "VP of Engineering", "Head of Talent"],
                     max_contacts_per_company=2, min_email_confidence=80)
ACME = Company(name="Acme", domain="acme.com", ats="greenhouse", board="acme")


def test_title_rank_handles_abbreviations():
    t = TARGETS.titles
    assert title_rank("Senior Engineering Manager, Payments", t) == 0
    assert title_rank("VP, Engineering", t) == 1
    assert title_rank("Vice President of Engineering", t) == 1
    assert title_rank("Head of Talent Acquisition", t) == 2
    assert title_rank("Software Engineer", t) is None


@respx.mock
def test_hunter_domain_search_ranks_and_filters():
    respx.get("https://api.hunter.io/v2/domain-search").mock(return_value=httpx.Response(200, json={"data": {"emails": [
        {"value": "sam@acme.com", "first_name": "Sam", "last_name": "Hill", "position": "Software Engineer", "confidence": 99},
        {"value": "kim@acme.com", "first_name": "Kim", "last_name": "Ng", "position": "Head of Talent", "confidence": 95},
        {"value": "lee@acme.com", "first_name": "Lee", "last_name": "Fox", "position": "Engineering Manager", "confidence": 60},
        {"value": "bad@acme.com", "first_name": "Bad", "last_name": "Addr", "position": "VP Engineering", "confidence": 99,
         "verification": {"status": "invalid"}},
    ]}}))
    out = Hunter("k").find(ACME, TARGETS)
    assert [c["name"] for c in out] == ["Lee Fox", "Kim Ng"]
    assert out[0]["email"] is None, "below confidence floor"
    assert out[1]["email"] == "kim@acme.com"


@respx.mock
def test_apollo_search_then_reveal_and_hunter_fill():
    respx.post("https://api.apollo.io/api/v1/mixed_people/api_search").mock(return_value=httpx.Response(200, json={"people": [
        {"id": "p1", "first_name": "Ada", "title": "VP of Engineering"},
        {"id": "p2", "first_name": "Bob", "title": "Engineering Manager"},
        {"id": "p3", "first_name": "Cy", "title": "Recruiting Coordinator"},
    ]}))
    respx.post("https://api.apollo.io/api/v1/people/match").mock(side_effect=lambda req: httpx.Response(200, json={
        "person": {"p1": {"name": "Ada Byron", "first_name": "Ada", "last_name": "Byron", "email": "ada@acme.com",
                          "email_status": "verified", "linkedin_url": "https://linkedin.com/in/ada"},
                   "p2": {"name": "Bob Stone", "first_name": "Bob", "last_name": "Stone",
                          "email": "email_not_unlocked@domain.com", "email_status": None}}[
            __import__("json").loads(req.content)["id"]]}))
    respx.get("https://api.hunter.io/v2/domain-search").mock(return_value=httpx.Response(200, json={"data": {"emails": []}}))
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(200, json={"data": {"email": "bob@acme.com", "score": 91}}))

    contacts, errors = enrich_company(ACME, TARGETS, Apollo("k"), Hunter("k"))
    assert errors == []
    by = {c["name"]: c for c in contacts}
    assert list(by) == ["Bob Stone", "Ada Byron"], "manager ranks above VP per target order"
    assert by["Ada Byron"]["email"] == "ada@acme.com" and by["Ada Byron"]["linkedin_url"]
    assert by["Bob Stone"]["email"] == "bob@acme.com" and by["Bob Stone"]["email_status"] == "hunter_finder"


@respx.mock
def test_provider_errors_are_reported_not_raised():
    respx.post("https://api.apollo.io/api/v1/mixed_people/api_search").mock(return_value=httpx.Response(429))
    contacts, errors = enrich_company(ACME, TARGETS, Apollo("k"), None)
    assert contacts == [] and "rate limit" in errors[0]
