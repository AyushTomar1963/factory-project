"""Requisition discovery straight from public ATS job-board APIs.

These endpoints are published by the ATS vendors for exactly this purpose
(embedding job boards), return structured JSON, and need no authentication.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Callable

import httpx

from .config import Company, SearchCfg

USER_AGENT = "jobhunt/0.1 (+personal job search; contact via sender email)"
TIMEOUT = httpx.Timeout(20.0)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)  # Greenhouse double-encodes its HTML content
    text = re.sub(r"(?i)<\s*(br|/p|/li|/h\d|/div)\s*/?>", "\n", text)
    text = re.sub(r"(?i)<\s*li[^>]*>", "- ", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _ms_to_iso(ms: int | None) -> str | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(microsecond=0).isoformat()


def fetch_greenhouse(client: httpx.Client, company: Company) -> list[dict]:
    r = client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{company.board}/jobs", params={"content": "true"}
    )
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append({
            "external_id": str(j["id"]),
            "title": j.get("title", "").strip(),
            "location": (j.get("location") or {}).get("name"),
            "department": ", ".join(d.get("name", "") for d in j.get("departments") or []) or None,
            "url": j.get("absolute_url"),
            "description": html_to_text(j.get("content")),
            "posted_at": j.get("first_published") or j.get("updated_at"),
        })
    return jobs


def fetch_lever(client: httpx.Client, company: Company) -> list[dict]:
    r = client.get(f"https://api.lever.co/v0/postings/{company.board}", params={"mode": "json"})
    r.raise_for_status()
    jobs = []
    for j in r.json():
        cats = j.get("categories") or {}
        parts = [j.get("descriptionPlain") or html_to_text(j.get("description"))]
        for lst in j.get("lists") or []:
            parts.append(lst.get("text", ""))
            parts.append(html_to_text(lst.get("content")))
        parts.append(j.get("additionalPlain") or "")
        jobs.append({
            "external_id": j["id"],
            "title": j.get("text", "").strip(),
            "location": cats.get("location"),
            "department": cats.get("team") or cats.get("department"),
            "url": j.get("hostedUrl"),
            "description": "\n".join(p for p in parts if p).strip(),
            "posted_at": _ms_to_iso(j.get("createdAt")),
        })
    return jobs


def fetch_ashby(client: httpx.Client, company: Company) -> list[dict]:
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{company.board}")
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        location = j.get("location")
        if j.get("isRemote") and location and "remote" not in location.lower():
            location = f"{location} (Remote)"
        jobs.append({
            "external_id": j["id"],
            "title": j.get("title", "").strip(),
            "location": location,
            "department": j.get("department") or j.get("team"),
            "url": j.get("jobUrl"),
            "description": j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml")),
            "posted_at": j.get("publishedAt"),
        })
    return jobs


def fetch_workday(client: httpx.Client, company: Company, max_jobs: int = 200,
                  title_ok: Callable[[str], bool] | None = None) -> list[dict]:
    """board format: "<tenant>/<wd number>/<site>", e.g. "nvidia/5/NVIDIAExternalCareerSite".

    Workday's list endpoint has no descriptions, so each posting costs one extra
    request; `title_ok` skips that request for titles that would be filtered anyway."""
    try:
        tenant, wd, site = company.board.split("/", 2)
    except ValueError as exc:
        raise ValueError(f"workday board must be 'tenant/N/site', got {company.board!r}") from exc
    host = f"https://{tenant}.wd{wd}.myworkdayjobs.com"
    api = f"{host}/wday/cxs/{tenant}/{site}"
    jobs, offset = [], 0
    while offset < max_jobs:
        r = client.post(f"{api}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""})
        r.raise_for_status()
        page = r.json().get("jobPostings", [])
        if not page:
            break
        for p in page:
            path = p.get("externalPath", "")
            description = ""
            wanted = title_ok is None or title_ok(p.get("title", ""))
            detail = client.get(f"{api}{path}") if wanted else None
            if detail is not None and detail.status_code == 200:
                info = detail.json().get("jobPostingInfo", {})
                description = html_to_text(info.get("jobDescription"))
            jobs.append({
                "external_id": (p.get("bulletFields") or [path])[0],
                "title": p.get("title", "").strip(),
                "location": p.get("locationsText"),
                "department": None,
                "url": f"{host}/{site}{path}",
                "description": description,
                "posted_at": p.get("postedOn"),
            })
        offset += len(page)
    return jobs


FETCHERS: dict[str, Callable[[httpx.Client, Company], list[dict]]] = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
}


def passes_filters(job: dict, search: SearchCfg) -> bool:
    title = job["title"].lower()
    if search.title_include and not any(t.lower() in title for t in search.title_include):
        return False
    if any(t.lower() in title for t in search.title_exclude):
        return False
    if search.locations:
        loc = (job.get("location") or "").lower()
        if not any(l.lower() in loc for l in search.locations):
            return False
    return True


def discover(companies: list[Company], client: httpx.Client | None = None,
             search: SearchCfg | None = None) -> tuple[list[dict], list[str]]:
    """Return (jobs, errors). Each job dict carries company/domain/ats."""
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)
    out, errors = [], []
    try:
        for company in companies:
            try:
                if company.ats == "workday" and search is not None:
                    title_ok = lambda t: passes_filters({"title": t, "location": None}, search.model_copy(update={"locations": []}))
                    jobs = fetch_workday(client, company, title_ok=title_ok)
                else:
                    jobs = FETCHERS[company.ats](client, company)
                for job in jobs:
                    job.update(company=company.name, domain=company.domain.lower(), ats=company.ats)
                    out.append(job)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                errors.append(f"{company.name} ({company.ats}/{company.board}): {exc}")
    finally:
        if own:
            client.close()
    return out, errors
