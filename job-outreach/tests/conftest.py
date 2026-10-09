import json
from pathlib import Path

import pytest

from jobhunt.config import Company, Secrets, Settings
from jobhunt.db import DB

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def master() -> dict:
    return json.loads((ROOT / "examples" / "master_resume.json").read_text())


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(
        companies=[
            Company(name="Acme", domain="acme.com", ats="greenhouse", board="acme"),
            Company(name="Globex", domain="globex.com", ats="lever", board="globex"),
        ],
        secrets=Secrets(
            sender_name="Jane Doe", sender_email="jane@janedoe-careers.com",
            public_base_url="https://jobs.example.com", unsubscribe_secret="test-secret",
            db_path=str(tmp_path / "t.db"), output_dir=str(tmp_path / "out"),
        ),
        base_dir=ROOT,
    )
    s.search.title_include = ["engineer"]
    s.search.locations = []
    s.search.min_match_score = 0.2
    s.outreach.min_delay_seconds = 0
    s.outreach.max_delay_seconds = 0
    return s


@pytest.fixture
def db(settings) -> DB:
    return DB(settings.path(settings.secrets.db_path))


GREENHOUSE_JOBS = {
    "jobs": [
        {
            "id": 101, "title": "Senior Backend Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
            "location": {"name": "New York, NY"}, "departments": [{"name": "Engineering"}],
            "updated_at": "2026-10-01T00:00:00Z",
            "content": "&lt;p&gt;We use &lt;b&gt;Python&lt;/b&gt;, Go, PostgreSQL, Kafka and Kubernetes on AWS.&lt;/p&gt;"
                       "&lt;ul&gt;&lt;li&gt;Experience with Rust is a plus&lt;/li&gt;&lt;/ul&gt;",
        },
        {
            "id": 102, "title": "Account Executive", "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
            "location": {"name": "Remote"}, "departments": [], "content": "&lt;p&gt;Sell things.&lt;/p&gt;",
        },
    ]
}

LEVER_JOBS = [
    {
        "id": "abc-123", "text": "Platform Engineer", "hostedUrl": "https://jobs.lever.co/globex/abc-123",
        "categories": {"location": "Remote", "team": "Infrastructure"}, "createdAt": 1790000000000,
        "descriptionPlain": "Own our Terraform and Kubernetes platform.",
        "lists": [{"text": "Requirements", "content": "<li>Docker</li><li>AWS</li><li>Java</li>"}],
    }
]
