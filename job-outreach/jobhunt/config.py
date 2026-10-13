from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .llm import GEMINI_BASE_URL, GEMINI_MODEL, OPENAI_BASE_URL, OPENAI_MODEL, is_gemini

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_HOSTS = {"smtp.gmail.com", "smtp.googlemail.com"}


class CandidateCfg(BaseModel):
    resume: str = "examples/student_resume.json"


class Targeting(BaseModel):
    """What to look for. Editable from the dashboard (stored in the DB), with
    these values as defaults."""
    seasons: list[str] = Field(default_factory=lambda: ["Summer 2027", "Winter 2026"])
    roles: list[str] = Field(default_factory=lambda: ["Software Engineering Intern", "Backend Intern", "Data Science Intern"])
    locations: list[str] = Field(default_factory=list)
    # "Company Name, domain.com" or just "domain.com", one per line in the UI
    companies: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=lambda: ["hiring_posts", "linkedin_jobs", "companies"])
    max_results_per_query: int = 25
    require_season: bool = False
    auto_send: bool = False
    cycle_every_hours: int = 24
    per_tick: int = 3
    tailor_per_cycle: int = 15
    followups_enabled: bool = True
    followup_after_days: int = 5


class TargetsCfg(BaseModel):
    """Who to email at a company, best first."""
    titles: list[str] = Field(default_factory=lambda: [
        "Founder", "Co-Founder", "CTO", "Head of Engineering", "Engineering Manager",
        "VP of Engineering", "Talent Acquisition", "Technical Recruiter", "Recruiter", "HR Manager",
    ])
    max_contacts_per_company: int = 2
    min_email_confidence: int = 80


class WarmupStep(BaseModel):
    from_day: int
    cap: int


class OutreachCfg(BaseModel):
    daily_cap: int = 25
    warmup: list[WarmupStep] = Field(default_factory=lambda: [
        WarmupStep(from_day=0, cap=5), WarmupStep(from_day=7, cap=10),
        WarmupStep(from_day=14, cap=15), WarmupStep(from_day=21, cap=20),
    ])
    min_delay_seconds: int = 20
    max_delay_seconds: int = 60
    recontact_after_days: int = 90
    max_bounce_rate: float = 0.05
    require_authentication: bool = True
    attach_resume: bool = True


class Secrets(BaseModel):
    llm_base_url: str = GEMINI_BASE_URL
    llm_api_key: str = ""
    llm_model: str = GEMINI_MODEL
    # Conservative defaults for the Gemini free tier. Google shows your
    # project's real limits in AI Studio; raise these to match.
    llm_rpm: int = 10
    llm_rpd: int = 200
    llm_reasoning_effort: str = ""
    llm_max_output_tokens: int = 0
    apify_token: str = ""
    apify_linkedin_jobs_actor: str = "curious_coder~linkedin-jobs-scraper"
    apify_google_actor: str = "apify~google-search-scraper"
    apollo_api_key: str = ""
    hunter_api_key: str = ""
    smtp_host: str = GMAIL_SMTP_HOST
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = False
    imap_host: str = ""
    imap_username: str = ""
    imap_password: str = ""
    sender_name: str = ""
    sender_email: str = ""
    dkim_selector: str = ""
    sender_postal_address: str = ""
    public_base_url: str = "http://localhost:8000"
    unsubscribe_secret: str = "dev-only-secret"
    cron_secret: str = ""
    database_url: str = ""
    db_path: str = "data/jobhunt.db"

    @property
    def smtp_ready(self) -> bool:
        return bool(self.smtp_host and self.smtp_username and self.smtp_password and self.sender_email)

    @property
    def uses_gmail(self) -> bool:
        return self.smtp_host.lower() in GMAIL_SMTP_HOSTS

    @property
    def sender_domain(self) -> str:
        return self.sender_email.rsplit("@", 1)[-1].lower() if "@" in self.sender_email else ""


class Settings(BaseModel):
    candidate: CandidateCfg = Field(default_factory=CandidateCfg)
    targeting: Targeting = Field(default_factory=Targeting)
    targets: TargetsCfg = Field(default_factory=TargetsCfg)
    outreach: OutreachCfg = Field(default_factory=OutreachCfg)
    secrets: Secrets = Field(default_factory=Secrets)
    base_dir: Path = Path(".")

    def path(self, p: str) -> Path:
        q = Path(p)
        return q if q.is_absolute() else self.base_dir / q

    @property
    def db_target(self) -> str:
        return self.secrets.database_url or str(self.path(self.secrets.db_path))


def load_dotenv(path: Path) -> None:
    """Minimal .env loader; existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _llm_env(e) -> dict:
    """LLM_API_KEY, GEMINI_API_KEY or OPENAI_API_KEY, in that order. An
    OPENAI_API_KEY on its own (no LLM_BASE_URL) keeps pointing at OpenAI."""
    key = e("LLM_API_KEY") or e("GEMINI_API_KEY") or e("OPENAI_API_KEY") or ""
    only_openai = bool(e("OPENAI_API_KEY")) and not (e("LLM_API_KEY") or e("GEMINI_API_KEY"))
    base = e("LLM_BASE_URL") or (OPENAI_BASE_URL if only_openai else GEMINI_BASE_URL)
    gemini = is_gemini(base)
    return {
        "llm_api_key": key.strip(),
        "llm_base_url": base,
        "llm_model": e("LLM_MODEL") or (GEMINI_MODEL if gemini else OPENAI_MODEL),
        "llm_rpm": _int(e("LLM_RPM"), 10),
        "llm_rpd": _int(e("LLM_RPD"), 200),
        # Gemini spends "thinking" tokens by default; low keeps them small.
        "llm_reasoning_effort": e("LLM_REASONING_EFFORT", "low" if gemini else ""),
        "llm_max_output_tokens": _int(e("LLM_MAX_OUTPUT_TOKENS"), 0),
    }


def _env_secrets() -> Secrets:
    e = os.environ.get
    defaults = Secrets()
    smtp_user = e("SMTP_USER") or e("SMTP_USERNAME") or ""
    # Gmail shows App Passwords as four groups of four; spaces are not part of it.
    smtp_password = re.sub(r"\s+", "", e("SMTP_PASSWORD", ""))
    smtp_host = e("SMTP_HOST") or GMAIL_SMTP_HOST
    smtp_port = _int(e("SMTP_PORT"), 587)
    use_ssl = e("SMTP_USE_SSL")
    imap_default = "imap.gmail.com" if smtp_host.lower() in GMAIL_SMTP_HOSTS and smtp_user else ""
    return Secrets(
        **_llm_env(e),
        apify_token=e("APIFY_TOKEN", ""),
        apify_linkedin_jobs_actor=e("APIFY_LINKEDIN_JOBS_ACTOR", defaults.apify_linkedin_jobs_actor),
        apify_google_actor=e("APIFY_GOOGLE_ACTOR", defaults.apify_google_actor),
        apollo_api_key=e("APOLLO_API_KEY", ""),
        hunter_api_key=e("HUNTER_API_KEY", ""),
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=smtp_user,
        smtp_password=smtp_password,
        # Port 465 is implicit TLS; 587 (and 25/2525) use STARTTLS.
        smtp_use_ssl=use_ssl.lower() in ("1", "true", "yes") if use_ssl else smtp_port == 465,
        imap_host=e("IMAP_HOST") or imap_default,
        imap_username=e("IMAP_USERNAME") or smtp_user,
        imap_password=re.sub(r"\s+", "", e("IMAP_PASSWORD", "")) or smtp_password,
        sender_name=e("SENDER_NAME", ""),
        # Gmail rewrites From to the signed-in account, so default to it.
        sender_email=e("SENDER_EMAIL") or (smtp_user if "@" in smtp_user else ""),
        dkim_selector=e("DKIM_SELECTOR", ""),
        sender_postal_address=e("SENDER_POSTAL_ADDRESS", ""),
        public_base_url=e("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        unsubscribe_secret=e("UNSUBSCRIBE_SECRET", "dev-only-secret"),
        cron_secret=e("CRON_SECRET", ""),
        database_url=e("DATABASE_URL", ""),
        db_path=e("JOBHUNT_DB", "data/jobhunt.db"),
    )


def load_settings(config_path: str | Path | None = None) -> Settings:
    config_path = Path(config_path or os.environ.get("JOBHUNT_CONFIG", "config.yaml"))
    base_dir = config_path.resolve().parent if config_path.exists() else Path.cwd()
    load_dotenv(base_dir / ".env")
    raw = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    return Settings(**(raw or {}), secrets=_env_secrets(), base_dir=base_dir)


def effective_targeting(settings: Settings, db) -> Targeting:
    """Dashboard edits (stored in the DB) override the YAML defaults."""
    saved = db.kv_get("targeting") or {}
    return settings.targeting.model_copy(update={k: v for k, v in saved.items() if k in Targeting.model_fields})
