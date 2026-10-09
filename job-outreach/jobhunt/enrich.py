"""Decision-maker lookup through B2B data providers (Apollo.io, Hunter.io).

Nothing here touches LinkedIn: contacts come from providers that license
business contact data for this purpose.
"""
from __future__ import annotations

import re

import httpx

from .config import Company, TargetsCfg

TIMEOUT = httpx.Timeout(30.0)

_ABBREV = {
    "vp": "vice president", "svp": "senior vice president", "cto": "chief technology officer",
    "eng": "engineering", "mgr": "manager", "sr": "senior", "dir": "director", "ta": "talent acquisition",
}


def _norm_title(t: str) -> set[str]:
    words = re.findall(r"[a-z]+", (t or "").lower())
    out: list[str] = []
    for w in words:
        out += _ABBREV.get(w, w).split()
    return set(out) - {"of", "the", "and", "a"}


def title_rank(title: str, targets: list[str]) -> int | None:
    """Index of the first target title matched (lower = better), or None."""
    have = _norm_title(title)
    for i, target in enumerate(targets):
        want = _norm_title(target)
        if want and want <= have:
            return i
    return None


class ProviderError(RuntimeError):
    pass


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

    def search(self, domain: str, titles: list[str], per_page: int = 25) -> list[dict]:
        body = {"q_organization_domains_list": [domain], "person_titles": titles, "per_page": per_page, "page": 1}
        try:
            data = self._post("/mixed_people/api_search", body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (404, 422):
                raise
            data = self._post("/mixed_people/search", body)
        return data.get("people") or []

    def reveal(self, person_id: str) -> dict:
        data = self._post("/people/match", {"id": person_id, "reveal_personal_emails": False})
        return data.get("person") or {}

    def find(self, company: Company, targets: TargetsCfg) -> list[dict]:
        ranked = []
        for p in self.search(company.domain, targets.titles):
            rank = title_rank(p.get("title", ""), targets.titles)
            if rank is not None:
                ranked.append((rank, p))
        ranked.sort(key=lambda x: x[0])
        out = []
        for _, p in ranked[: targets.max_contacts_per_company]:
            full = self.reveal(p["id"]) if p.get("id") else {}
            merged = {**p, **{k: v for k, v in full.items() if v}}
            email = merged.get("email")
            status = merged.get("email_status")
            if email and "domain.com" in email:  # Apollo's placeholder for locked emails
                email = None
            name = merged.get("name") or " ".join(x for x in [merged.get("first_name"), merged.get("last_name")] if x)
            out.append({
                "company": company.name,
                "domain": company.domain,
                "name": name.strip(),
                "first_name": merged.get("first_name"),
                "last_name": merged.get("last_name"),
                "title": merged.get("title"),
                "email": email if status in (None, "verified", "likely_to_engage") else None,
                "email_confidence": 95 if status == "verified" else (70 if email else None),
                "email_status": status,
                "linkedin_url": merged.get("linkedin_url"),
                "source": "apollo",
            })
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

    def domain_search(self, domain: str, limit: int = 50) -> list[dict]:
        return self._get("/domain-search", {"domain": domain, "type": "personal", "limit": limit}).get("emails") or []

    def email_finder(self, domain: str, first: str, last: str) -> tuple[str | None, int | None]:
        d = self._get("/email-finder", {"domain": domain, "first_name": first, "last_name": last})
        return d.get("email"), d.get("score")

    def find(self, company: Company, targets: TargetsCfg) -> list[dict]:
        ranked = []
        for e in self.domain_search(company.domain):
            rank = title_rank(e.get("position") or "", targets.titles)
            if rank is None:
                continue
            verified = (e.get("verification") or {}).get("status")
            if verified == "invalid":
                continue
            ranked.append((rank, -(e.get("confidence") or 0), e))
        ranked.sort(key=lambda x: (x[0], x[1]))
        out = []
        for _, _, e in ranked[: targets.max_contacts_per_company]:
            conf = e.get("confidence") or 0
            name = " ".join(x for x in [e.get("first_name"), e.get("last_name")] if x) or e["value"].split("@")[0]
            out.append({
                "company": company.name,
                "domain": company.domain,
                "name": name,
                "first_name": e.get("first_name"),
                "last_name": e.get("last_name"),
                "title": e.get("position"),
                "email": e["value"] if conf >= targets.min_email_confidence else None,
                "email_confidence": conf,
                "email_status": (e.get("verification") or {}).get("status"),
                "linkedin_url": e.get("linkedin"),
                "source": "hunter",
            })
        return out


def enrich_company(company: Company, targets: TargetsCfg, apollo: Apollo | None, hunter: Hunter | None) -> tuple[list[dict], list[str]]:
    contacts: list[dict] = []
    errors: list[str] = []
    for provider in (apollo, hunter):
        if provider is None or len([c for c in contacts if c.get("email")]) >= targets.max_contacts_per_company:
            continue
        try:
            for c in provider.find(company, targets):
                if not any(x["name"].lower() == c["name"].lower() for x in contacts):
                    contacts.append(c)
        except (httpx.HTTPError, ProviderError) as exc:
            errors.append(f"{company.name}: {type(provider).__name__} failed: {exc}")
    # Fill in missing emails with Hunter's finder when we know the person's name.
    if hunter:
        for c in contacts:
            if c.get("email") or not (c.get("first_name") and c.get("last_name")):
                continue
            try:
                email, score = hunter.email_finder(company.domain, c["first_name"], c["last_name"])
            except (httpx.HTTPError, ProviderError) as exc:
                errors.append(f"{company.name}: Hunter email-finder failed: {exc}")
                break
            if email and (score or 0) >= targets.min_email_confidence:
                c.update(email=email, email_confidence=score, email_status="hunter_finder")
    return contacts[: max(targets.max_contacts_per_company, 1) * 2], errors
