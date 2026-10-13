"""Where internship leads come from.

* hiring_posts  - people posting "we're hiring interns" on LinkedIn, found via
                  Google search through Apify. The poster is the contact.
* linkedin_jobs - LinkedIn internship listings via an Apify actor; used to learn
                  which companies are taking interns, then we email people there
                  directly instead of applying through the listing.
* companies     - your own list of companies to cold-email about internships.

All scraping runs inside Apify; nothing here logs into your LinkedIn account.
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import quote_plus, urlparse

import httpx

from .config import Secrets, Targeting

APIFY_BASE = "https://api.apify.com/v2"
INTERN_RE = re.compile(r"\b(intern|interns|internship|internships|co-?op|trainee)\b", re.IGNORECASE)


class SourceError(RuntimeError):
    pass


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    if not host or any(b in host for b in ("linkedin.com", "lnkd.in", "google.", "bit.ly")):
        return None
    return host


def detect_season(text: str, seasons: list[str]) -> str | None:
    low = (text or "").lower()
    for label in seasons:
        if all(w in low for w in label.lower().split()):
            return label
    for label in seasons:
        if label.split()[0].lower() in low:
            return label
    return None


def is_internship(text: str) -> bool:
    return bool(INTERN_RE.search(text or ""))


def run_actor(client: httpx.Client, token: str, actor: str, payload: dict, timeout_s: int = 240) -> list[dict]:
    r = client.post(
        f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items",
        params={"token": token, "timeout": timeout_s},
        json=payload,
        timeout=timeout_s + 30,
    )
    if r.status_code == 401:
        raise SourceError("Apify rejected the token (401)")
    if r.status_code == 402:
        raise SourceError("Apify account is out of credits (402)")
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def _pick(d: dict, *keys: str):
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None


# ---------------------------------------------------------------- linkedin jobs

def linkedin_search_urls(t: Targeting) -> list[str]:
    urls = []
    for role in t.roles:
        for loc in t.locations or [None]:
            u = f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(role)}&f_E=1&f_TPR=r2592000"
            if loc:
                u += f"&location={quote_plus(loc)}"
            urls.append(u)
    return urls


def linkedin_jobs(client: httpx.Client, secrets: Secrets, t: Targeting) -> list[dict]:
    items = run_actor(client, secrets.apify_token, secrets.apify_linkedin_jobs_actor, {
        "urls": linkedin_search_urls(t), "count": t.max_results_per_query, "scrapeCompany": True,
    })
    leads = []
    for it in items:
        title = _pick(it, "title", "jobTitle", "position") or ""
        company = _pick(it, "companyName", "company", "company_name")
        if isinstance(company, dict):
            company = company.get("name")
        description = _pick(it, "descriptionText", "description", "jobDescription") or ""
        url = _pick(it, "link", "jobUrl", "url", "applyUrl")
        leads.append({
            "source": "linkedin_jobs",
            "external_id": str(_pick(it, "id", "jobId", "trackingId") or url or f"{company}:{title}"),
            "company": company,
            "domain": domain_of(_pick(it, "companyWebsite", "companyWebsiteUrl", "website")),
            "title": title.strip(),
            "location": _pick(it, "location", "jobLocation", "place"),
            "url": url,
            "description": description,
            "posted_at": _pick(it, "postedAt", "publishedAt", "postedTime", "listedAt"),
            "poster_name": _pick(it, "jobPosterName", "posterName", "recruiterName"),
            "poster_url": _pick(it, "jobPosterProfileUrl", "posterProfileUrl", "recruiterUrl"),
        })
    return leads


# ---------------------------------------------------------------- hiring posts

def hiring_post_queries(t: Targeting) -> list[str]:
    queries = []
    for season in t.seasons or [""]:
        for role in t.roles:
            core = INTERN_RE.sub("", role).strip() or role
            q = f'site:linkedin.com/posts hiring intern "{season}" "{core}"' if season else \
                f'site:linkedin.com/posts hiring intern "{core}"'
            for loc in t.locations or [None]:
                queries.append(q + (f' "{loc}"' if loc else ""))
    return queries


_POST_RE = re.compile(r"linkedin\.com/posts/([^/_?#]+)_", re.IGNORECASE)
_NAME_RE = re.compile(r"^(.*?)(?:'s Post|\s+on LinkedIn|\s+posted|\s+-\s+LinkedIn|\s+\|)", re.IGNORECASE)


def parse_post(result: dict) -> dict | None:
    url = result.get("url") or ""
    m = _POST_RE.search(url)
    if not m:
        return None
    title = result.get("title") or ""
    nm = _NAME_RE.match(title)
    name = (nm.group(1) if nm else "").strip(" -#") or None
    snippet = result.get("description") or ""
    return {
        "source": "hiring_posts",
        "external_id": hashlib.sha1(url.split("?")[0].encode()).hexdigest()[:20],
        "company": None,
        "domain": None,
        "title": (title.split(":", 1)[1].strip() if ":" in title else title)[:200] or "Hiring post",
        "url": url.split("?")[0],
        "description": f"{title}\n{snippet}".strip(),
        "posted_at": result.get("date"),
        "poster_name": name,
        "poster_url": f"https://www.linkedin.com/in/{m.group(1)}",
    }


def hiring_posts(client: httpx.Client, secrets: Secrets, t: Targeting) -> list[dict]:
    items = run_actor(client, secrets.apify_token, secrets.apify_google_actor, {
        "queries": "\n".join(hiring_post_queries(t)),
        "resultsPerPage": min(max(t.max_results_per_query, 10), 100),
        "maxPagesPerQuery": 1,
        "mobileResults": False,
    })
    leads, seen = [], set()
    for page in items:
        for res in page.get("organicResults") or []:
            lead = parse_post(res)
            if lead and lead["external_id"] not in seen:
                seen.add(lead["external_id"])
                leads.append(lead)
    return leads


# ---------------------------------------------------------------- company list

def company_leads(t: Targeting) -> list[dict]:
    leads = []
    season = " / ".join(t.seasons) if t.seasons else "internship"
    for line in t.companies:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if not parts:
            continue
        domain = domain_of(parts[-1]) if "." in parts[-1] else None
        name = parts[0] if (len(parts) > 1 or not domain) else domain.split(".")[0].capitalize()
        leads.append({
            "source": "companies",
            "external_id": (domain or name).lower(),
            "company": name,
            "domain": domain,
            "title": f"{season} internship ({', '.join(t.roles[:2])})",
            "description": "Direct internship inquiry. Target roles: " + ", ".join(t.roles),
            "season": t.seasons[0] if t.seasons else None,
        })
    return leads


# ---------------------------------------------------------------- orchestration

def discover(secrets: Secrets, t: Targeting, client: httpx.Client | None = None) -> tuple[list[dict], list[str]]:
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(300.0))
    leads: list[dict] = []
    errors: list[str] = []
    try:
        if "companies" in t.sources:
            leads += company_leads(t)
        for name, fn in (("hiring_posts", hiring_posts), ("linkedin_jobs", linkedin_jobs)):
            if name not in t.sources:
                continue
            if not secrets.apify_token:
                errors.append(f"{name}: skipped, set APIFY_TOKEN")
                continue
            try:
                leads += fn(client, secrets, t)
            except (httpx.HTTPError, SourceError, ValueError) as exc:
                errors.append(f"{name}: {exc}")
    finally:
        if own:
            client.close()

    kept = []
    for lead in leads:
        text = f"{lead['title']}\n{lead.get('description') or ''}"
        if lead["source"] != "companies" and not is_internship(text):
            continue
        lead["season"] = lead.get("season") or detect_season(text, t.seasons)
        if t.require_season and lead["source"] != "companies" and not lead["season"]:
            continue
        kept.append(lead)
    return kept, errors
