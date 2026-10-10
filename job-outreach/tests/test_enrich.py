import json

import httpx
import respx

from jobhunt.config import TargetsCfg
from jobhunt.enrich import Apollo, Hunter, enrich_lead, title_rank

TARGETS = TargetsCfg(titles=["Founder", "CTO", "Engineering Manager", "VP of Engineering", "Talent Acquisition"],
                     max_contacts_per_company=2, min_email_confidence=80)
APOLLO = "https://api.apollo.io/api/v1"
HUNTER = "https://api.hunter.io/v2"


def test_title_rank_handles_abbreviations():
    t = TARGETS.titles
    assert title_rank("Co-Founder & CEO", t) == 0
    assert title_rank("CTO", t) == 1
    assert title_rank("Chief Technology Officer", t) == 1
    assert title_rank("Senior Engineering Manager, Payments", t) == 2
    assert title_rank("VP, Engineering", t) == 3
    assert title_rank("Head of TA", t) == 4
    assert title_rank("Talent Acquisition Lead", t) == 4
    assert title_rank("Software Engineer", t) is None


@respx.mock
def test_hunter_company_contacts_rank_and_filter():
    respx.get(f"{HUNTER}/domain-search").mock(return_value=httpx.Response(200, json={"data": {"emails": [
        {"value": "sam@acme.com", "first_name": "Sam", "last_name": "Hill", "position": "Software Engineer", "confidence": 99},
        {"value": "kim@acme.com", "first_name": "Kim", "last_name": "Ng", "position": "Talent Acquisition", "confidence": 95},
        {"value": "lee@acme.com", "first_name": "Lee", "last_name": "Fox", "position": "Engineering Manager", "confidence": 60},
        {"value": "bad@acme.com", "first_name": "Bad", "last_name": "Addr", "position": "CTO", "confidence": 99,
         "verification": {"status": "invalid"}},
    ]}}))
    out = Hunter("k").company_contacts("Acme", "acme.com", TARGETS)
    assert [c["name"] for c in out] == ["Lee Fox", "Kim Ng"]
    assert out[0]["email"] is None, "below confidence floor"
    assert out[1]["email"] == "kim@acme.com"


@respx.mock
def test_hiring_post_author_is_matched_first():
    """A LinkedIn post author is resolved via Apollo, which also tells us the company."""
    def match(req):
        body = json.loads(req.content)
        if "id" in body:
            return httpx.Response(200, json={"person": {"name": "Ada Lin", "first_name": "Ada", "title": "Founder",
                                                        "email": "ada@globex.com", "email_status": "verified"}})
        assert body["linkedin_url"] == "https://www.linkedin.com/in/priya-shah"
        return httpx.Response(200, json={"person": {
            "id": "p9", "name": "Priya Shah", "first_name": "Priya", "last_name": "Shah", "title": "Engineering Manager",
            "email": "priya@globex.com", "email_status": "verified", "linkedin_url": body["linkedin_url"],
            "organization": {"name": "Globex", "primary_domain": "globex.com"}}})
    respx.post(f"{APOLLO}/people/match").mock(side_effect=match)
    respx.post(f"{APOLLO}/mixed_people/api_search").mock(return_value=httpx.Response(200, json={"people": [
        {"id": "p1", "first_name": "Ada", "title": "Founder"}]}))
    lead = {"source": "hiring_posts", "poster_url": "https://www.linkedin.com/in/priya-shah", "poster_name": "Priya Shah"}
    out = enrich_lead(lead, TARGETS, Apollo("k"), None)
    assert (out["company"], out["domain"]) == ("Globex", "globex.com")
    assert out["contacts"][0]["email"] == "priya@globex.com" and out["contacts"][0]["source"] == "apollo:poster"
    assert [c["name"] for c in out["contacts"]] == ["Priya Shah", "Ada Lin"]
    assert out["errors"] == []


@respx.mock
def test_company_name_is_resolved_to_domain_then_people_found():
    respx.post(f"{APOLLO}/mixed_companies/search").mock(return_value=httpx.Response(200, json={
        "organizations": [{"name": "Initech", "website_url": "https://www.initech.io"}]}))
    respx.post(f"{APOLLO}/mixed_people/api_search").mock(return_value=httpx.Response(404))
    respx.post(f"{APOLLO}/mixed_people/search").mock(return_value=httpx.Response(200, json={"people": [
        {"id": "p1", "first_name": "Ada", "title": "CTO"},
        {"id": "p2", "first_name": "Bob", "title": "Founder"},
        {"id": "p3", "first_name": "Cy", "title": "Account Executive"},
    ]}))
    respx.post(f"{APOLLO}/people/match").mock(side_effect=lambda req: httpx.Response(200, json={"person": {
        "p1": {"name": "Ada Byron", "first_name": "Ada", "last_name": "Byron", "email": "ada@initech.io", "email_status": "verified"},
        "p2": {"name": "Bob Stone", "first_name": "Bob", "last_name": "Stone", "email": "email_not_unlocked@domain.com"},
    }[json.loads(req.content)["id"]]}))
    respx.get(f"{HUNTER}/domain-search").mock(return_value=httpx.Response(200, json={"data": {"emails": []}}))
    respx.get(f"{HUNTER}/email-finder").mock(return_value=httpx.Response(200, json={"data": {"email": "bob@initech.io", "score": 91}}))

    out = enrich_lead({"source": "linkedin_jobs", "company": "Initech"}, TARGETS, Apollo("k"), Hunter("k"))
    assert out["domain"] == "initech.io"
    by = {c["name"]: c for c in out["contacts"]}
    assert list(by) == ["Bob Stone", "Ada Byron"], "founder ranks above CTO"
    assert by["Bob Stone"]["email"] == "bob@initech.io" and by["Bob Stone"]["email_status"] == "hunter_finder"
    assert by["Ada Byron"]["email"] == "ada@initech.io"


def test_post_author_kept_as_linkedin_contact_without_providers():
    lead = {"source": "hiring_posts", "poster_url": "https://www.linkedin.com/in/dan-k", "poster_name": "Dan K"}
    out = enrich_lead(lead, TARGETS, None, None)
    [c] = out["contacts"]
    assert c["linkedin_url"] == lead["poster_url"] and c["domain"] == "linkedin:dan-k" and not c.get("email")


@respx.mock
def test_provider_errors_are_reported_not_raised():
    respx.post(f"{APOLLO}/mixed_people/api_search").mock(return_value=httpx.Response(429))
    out = enrich_lead({"source": "companies", "company": "Acme", "domain": "acme.com"}, TARGETS, Apollo("k"), None)
    assert out["contacts"] == [] and "rate limit" in out["errors"][0]
