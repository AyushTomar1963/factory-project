import json
import os
from pathlib import Path

import pytest

from jobhunt.config import Secrets, Settings, Targeting
from jobhunt.db import DB

ROOT = Path(__file__).resolve().parent.parent
APIFY = "https://api.apify.com/v2/acts"


@pytest.fixture
def master() -> dict:
    return json.loads((ROOT / "examples" / "master_resume.json").read_text())


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(
        targeting=Targeting(
            seasons=["Summer 2027", "Winter 2026"], roles=["Backend Intern"], locations=[],
            companies=["Acme, acme.com"], sources=["hiring_posts", "linkedin_jobs", "companies"],
        ),
        secrets=Secrets(
            sender_name="Jane Doe", sender_email="jane@janedoe-careers.com",
            public_base_url="https://jobs.example.com", unsubscribe_secret="test-secret",
            apify_token="apify-test", db_path=str(tmp_path / "t.db"),
        ),
        base_dir=ROOT,
    )
    s.outreach.min_delay_seconds = 0
    s.outreach.max_delay_seconds = 0
    return s


TEST_PG = os.environ.get("TEST_DATABASE_URL", "")
TABLES = ("leads", "contacts", "documents", "outreach", "suppression", "send_log", "kv")


def reset_pg() -> None:
    """Run the suite against Postgres too: TEST_DATABASE_URL=postgresql://... pytest"""
    import psycopg

    with psycopg.connect(TEST_PG, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS " + ", ".join(TABLES))


@pytest.fixture
def db(settings) -> DB:
    if TEST_PG:
        reset_pg()
        settings.secrets.database_url = TEST_PG
    return DB(settings.db_target)


# Shapes returned by the Apify actors (apify~google-search-scraper, curious_coder~linkedin-jobs-scraper).
GOOGLE_RESULTS = [{
    "searchQuery": {"term": 'site:linkedin.com/posts hiring intern "Summer 2027" "Backend"'},
    "organicResults": [
        {"title": "Priya Shah on LinkedIn: We're hiring backend interns for Summer 2027! Python, PostgreSQL",
         "url": "https://www.linkedin.com/posts/priya-shah-12ab_hiring-interns-activity-7100?utm=x",
         "description": "We're hiring backend interns for Summer 2027 at Globex. DM me with your resume.",
         "date": "2026-09-30"},
        {"title": "Dan on LinkedIn: Our team is growing",
         "url": "https://www.linkedin.com/posts/dan-k_growth-activity-7101",
         "description": "We're hiring senior engineers."},
        {"title": "Not a post", "url": "https://example.com/blog", "description": "intern"},
    ],
}]

LINKEDIN_JOBS = [
    {"id": "4001", "title": "Software Engineering Intern (Summer 2027)", "companyName": "Initech",
     "companyWebsite": "https://www.initech.io", "location": "Remote", "link": "https://www.linkedin.com/jobs/view/4001",
     "descriptionText": "Backend internship. Python, Go and Docker.", "postedAt": "2026-10-01"},
    {"id": "4002", "title": "Senior Staff Engineer", "companyName": "Initech", "link": "https://www.linkedin.com/jobs/view/4002",
     "descriptionText": "10 years experience."},
]
