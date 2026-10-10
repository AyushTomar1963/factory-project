"""Turn a lead into people with email addresses, via Apollo.io and Hunter.io."""
from __future__ import annotations

import re

import httpx

from .config import TargetsCfg
from .sources import domain_of

TIMEOUT = httpx.Timeout(30.0)

_ABBREV = {
    "vp": "vice president", "svp": "senior vice president", "cto": "chief technology officer",
    "ceo": "chief executive officer", "eng": "engineering", "mgr": "manager", "sr": "senior",
    "dir": "director", "ta": "talent acquisition", "hr": "human resources", "cofounder": "co founder",
}


def _norm_title(t: str) -> set[str]:
    out: list[str] = []
    for w in re.findall(r"[a-z]+", (t or "").lower()):
        out += _ABBREV.get(w, w).split()
    return set(out) - {"of", "the", "and", "a", "&"}


def title_rank(title: str, targets: list[str]) -> int | None:
    have = _norm_title(title)
    for i, target in enumerate(targets):
        want = _norm_title(target)
        if want and want <= have:
            return i
    return None


class ProviderError(RuntimeError):
    pass


def _clean_apollo_email(email: str | None, status: str | None) -> str | None:
    if not email or "domain.com" in email or "not_unlocked" in email:
        return None
    return email if status in (None, "verified", "likely_to_engage", "extrapolated") else None


class Apollo:
    BASE = "https://api.apollo.io/api/v1"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.http = client or httpx.Client(timeout=TIMEOUT)
        self.headers = {"X-Api-Key": api_key, "Content-Type": "application/json", "Cache-Control": "no-cache"}

    def _post(self, path: str, body: dict) -> dict:
        r = self.http.post(f"{self.BASE}{path}", json=body, headers=self.headers)
        if r.status_code == 429:
            raise ProviderError("Apollo rate limit reached (HTTP 429)")
        r.raise_for_status()
        return r.json()

    def match_linkedin(self, linkedin_url: str) -> dict:
        return self._post("/people/match", {"linkedin_url": linkedin_url, "reveal_personal_emails": False}).get("person") or {}

    def reveal(self, person_id: str) -> dict:
        return self._post("/people/match", {"id": person_id, "reveal_personal_emails": False}).get("person") or {}

    def org_domain(self, name: str) -> str | None:
        data = self._post("/mixed_companies/search", {"q_organization_name": name, "per_page": 1, "page": 1})
        for org in (data.get("organizations") or []) + (data.get("accounts") or []):
            d = org.get("primary_domain") or domain_of(org.get("website_url"))
            if d:
                return d
        return None

    def search(self, domain: str, titles: list[str], per_page: int = 25) -> list[dict]:
        body = {"q_organization_domains_list": [domain], "person_titles": titles, "per_page": per_page, "page": 1}
        try:
            data = self._post("/mixed_people/api_search", body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (404, 422):
                raise
            data = self._post("/mixed_people/search", body)
        return data.get("people") or []

    @staticmethod
    def to_contact(p: dict, company: str | None, domain: str, source: str = "apollo") -> dict:
        name = p.get("name") or " ".join(x for x in [p.get("first_name"), p.get("last_name")] if x)
        email = _clean_apollo_email(p.get("email"), p.get("email_status"))
        return {
            "company": company or (p.get("organization") or {}).get("name"),
            "domain": domain,
            "name": (name or "").strip(),
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "title": p.get("title"),
            "email": email,
            "email_confidence": 95 if p.get("email_status") == "verified" else (70 if email else None),
            "email_status": p.get("email_status"),
            "linkedin_url": p.get("linkedin_url"),
            "source": source,
        }

    def company_contacts(self, company: str | None, domain: str, targets: TargetsCfg) -> list[dict]:
        ranked = sorted(
            ((title_rank(p.get("title", ""), targets.titles), p) for p in self.search(domain, targets.titles)),
            key=lambda x: (x[0] is None, x[0] or 0),
        )
        out = []
        for rank, p in ranked:
            if rank is None or len(out) >= targets.max_contacts_per_company:
                continue
            full = self.reveal(p["id"]) if p.get("id") else {}
            out.append(self.to_contact({**p, **{k: v for k, v in full.items() if v}}, company, domain))
        return out


class Hunter:
    BASE = "https://api.hunter.io/v2"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.key = api_key
        self.http = client or httpx.Client(timeout=TIMEOUT)

    def _get(self, path: str, params: dict) -> dict:
        r = self.http.get(f"{self.BASE}{path}", params={**params, "api_key": self.key})
        if r.status_code == 429:
            raise ProviderError("Hunter rate limit reached (HTTP 429)")
        r.raise_for_status()
        return r.json().get("data") or {}

    def domain_search(self, domain: str | None = None, company: str | None = None, limit: int = 50) -> dict:
        params = {"type": "personal", "limit": limit}
        params.update({"domain": domain} if domain else {"company": company})
        return self._get("/domain-search", params)

    def email_finder(self, domain: str, first: str, last: str) -> tuple[str | None, int | None]:
        d = self._get("/email-finder", {"domain": domain, "first_name": first, "last_name": last})
        return d.get("email"), d.get("score")

    def company_contacts(self, company: str | None, domain: str, targets: TargetsCfg) -> list[dict]:
        ranked = []
        for e in self.domain_search(domain).get("emails") or []:
            rank = title_rank(e.get("position") or "", targets.titles)
            if rank is None or (e.get("verification") or {}).get("status") == "invalid":
                continue
            ranked.append((rank, -(e.get("confidence") or 0), e))
        ranked.sort(key=lambda x: (x[0], x[1]))
        out = []
        for _, _, e in ranked[: targets.max_contacts_per_company]:
            conf = e.get("confidence") or 0
            out.append({
                "company": company, "domain": domain,
                "name": " ".join(x for x in [e.get("first_name"), e.get("last_name")] if x) or e["value"].split("@")[0],
                "first_name": e.get("first_name"), "last_name": e.get("last_name"), "title": e.get("position"),
                "email": e["value"] if conf >= targets.min_email_confidence else None,
                "email_confidence": conf, "email_status": (e.get("verification") or {}).get("status"),
                "linkedin_url": e.get("linkedin"), "source": "hunter",
            })
        return out


def _li_slug(url: str | None) -> str | None:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url or "", re.IGNORECASE)
    return m.group(1).lower() if m else None


def enrich_lead(lead: dict, targets: TargetsCfg, apollo: Apollo | None, hunter: Hunter | None) -> dict:
    """Returns {"company", "domain", "contacts": [...], "errors": [...]} for one lead."""
    company, domain = lead.get("company"), lead.get("domain")
    contacts: list[dict] = []
    errors: list[str] = []

    def guard(label, fn, *a):
        try:
            return fn(*a)
        except (httpx.HTTPError, ProviderError) as exc:
            errors.append(f"{label}: {exc}")
            return None

    # 1. The person who posted / owns the listing is the best contact.
    if lead.get("poster_url") and apollo:
        p = guard("apollo match", apollo.match_linkedin, lead["poster_url"]) or {}
        org = p.get("organization") or {}
        domain = domain or org.get("primary_domain") or domain_of(org.get("website_url"))
        company = company or org.get("name")
        if p and domain:
            contacts.append(Apollo.to_contact(p, company, domain, source="apollo:poster"))

    # 2. Work out the company domain from its name if we still don't have it.
    if not domain and company:
        if apollo:
            domain = guard("apollo org", apollo.org_domain, company)
        if not domain and hunter:
            domain = (guard("hunter company", hunter.domain_search, None, company) or {}).get("domain")

    # 3. Decision makers at the company.
    if domain:
        have_email = sum(1 for c in contacts if c.get("email"))
        for provider in (apollo, hunter):
            if provider is None or have_email >= targets.max_contacts_per_company:
                continue
            for c in guard(type(provider).__name__.lower(), provider.company_contacts, company, domain, targets) or []:
                if not any(x["name"].lower() == c["name"].lower() for x in contacts):
                    contacts.append(c)
                    have_email += bool(c.get("email"))
        if hunter:
            for c in contacts:
                if c.get("email") or not (c.get("first_name") and c.get("last_name")):
                    continue
                found = guard("hunter finder", hunter.email_finder, domain, c["first_name"], c["last_name"])
                if found and found[0] and (found[1] or 0) >= targets.min_email_confidence:
                    c.update(email=found[0], email_confidence=found[1], email_status="hunter_finder")

    # 4. No email anywhere: keep the poster as a LinkedIn-only contact.
    slug = _li_slug(lead.get("poster_url"))
    if slug and not any(_li_slug(c.get("linkedin_url")) == slug or c.get("source") == "apollo:poster" for c in contacts):
        name = lead.get("poster_name") or slug
        contacts.append({
            "company": company, "domain": domain or f"linkedin:{slug}",
            "name": name, "first_name": name.split()[0] if " " in name else None, "title": "Hiring post author",
            "linkedin_url": lead["poster_url"], "source": "post",
        })
    return {"company": company, "domain": domain, "contacts": contacts, "errors": errors}
