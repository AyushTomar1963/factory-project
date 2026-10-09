from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

AtsName = Literal["greenhouse", "lever", "ashby", "workday"]


class Company(BaseModel):
    name: str
    domain: str
    ats: AtsName
    board: str


class CandidateCfg(BaseModel):
    resume: str = "examples/master_resume.json"


class SearchCfg(BaseModel):
    title_include: list[str] = Field(default_factory=list)
    title_exclude: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    min_match_score: float = 0.25


class TargetsCfg(BaseModel):
    titles: list[str] = Field(
        default_factory=lambda: ["Engineering Manager", "Head of Engineering", "Head of Talent"]
    )
    max_contacts_per_company: int = 2
    min_email_confidence: int = 80


class WarmupStep(BaseModel):
    from_day: int
    cap: int


class OutreachCfg(BaseModel):
    daily_cap: int = 25
    warmup: list[WarmupStep] = Field(
        default_factory=lambda: [
            WarmupStep(from_day=0, cap=5),
            WarmupStep(from_day=7, cap=10),
            WarmupStep(from_day=14, cap=15),
            WarmupStep(from_day=21, cap=20),
        ]
    )
    min_delay_seconds: int = 90
    max_delay_seconds: int = 300
    recontact_after_days: int = 90
    max_bounce_rate: float = 0.05
    require_authentication: bool = True
    attach_resume: bool = True


class Secrets(BaseModel):
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    apollo_api_key: str = ""
    hunter_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_ssl: bool = False
    sender_name: str = ""
    sender_email: str = ""
    dkim_selector: str = ""
    sender_postal_address: str = ""
    public_base_url: str = "http://localhost:8000"
    unsubscribe_secret: str = "dev-only-secret"
    db_path: str = "data/jobhunt.db"
    output_dir: str = "data/output"

    @property
    def sender_domain(self) -> str:
        return self.sender_email.rsplit("@", 1)[-1].lower() if "@" in self.sender_email else ""


class Settings(BaseModel):
    candidate: CandidateCfg = Field(default_factory=CandidateCfg)
    search: SearchCfg = Field(default_factory=SearchCfg)
    companies: list[Company] = Field(default_factory=list)
    targets: TargetsCfg = Field(default_factory=TargetsCfg)
    outreach: OutreachCfg = Field(default_factory=OutreachCfg)
    secrets: Secrets = Field(default_factory=Secrets)
    base_dir: Path = Path(".")

    def path(self, p: str) -> Path:
        q = Path(p)
        return q if q.is_absolute() else self.base_dir / q


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


def _env_secrets() -> Secrets:
    e = os.environ.get
    return Secrets(
        llm_base_url=e("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_api_key=e("LLM_API_KEY", ""),
        llm_model=e("LLM_MODEL", "gpt-4o-mini"),
        apollo_api_key=e("APOLLO_API_KEY", ""),
        hunter_api_key=e("HUNTER_API_KEY", ""),
        smtp_host=e("SMTP_HOST", ""),
        smtp_port=int(e("SMTP_PORT", "587") or 587),
        smtp_username=e("SMTP_USERNAME", ""),
        smtp_password=e("SMTP_PASSWORD", ""),
        smtp_use_ssl=e("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes"),
        sender_name=e("SENDER_NAME", ""),
        sender_email=e("SENDER_EMAIL", ""),
        dkim_selector=e("DKIM_SELECTOR", ""),
        sender_postal_address=e("SENDER_POSTAL_ADDRESS", ""),
        public_base_url=e("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        unsubscribe_secret=e("UNSUBSCRIBE_SECRET", "dev-only-secret"),
        db_path=e("JOBHUNT_DB", "data/jobhunt.db"),
        output_dir=e("JOBHUNT_OUTPUT_DIR", "data/output"),
    )


def load_settings(config_path: str | Path | None = None) -> Settings:
    config_path = Path(config_path or os.environ.get("JOBHUNT_CONFIG", "config.yaml"))
    base_dir = config_path.resolve().parent if config_path.exists() else Path.cwd()
    load_dotenv(base_dir / ".env")
    raw = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    settings = Settings(**(raw or {}), secrets=_env_secrets(), base_dir=base_dir)
    return settings
