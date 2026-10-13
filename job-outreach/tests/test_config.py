from jobhunt.config import _env_secrets
from jobhunt.llm import GEMINI_BASE_URL, GEMINI_MODEL, OPENAI_BASE_URL

KEYS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_USE_SSL", "SENDER_EMAIL",
        "IMAP_HOST", "IMAP_USERNAME", "IMAP_PASSWORD", "LLM_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
        "LLM_BASE_URL", "LLM_MODEL", "LLM_REASONING_EFFORT", "LLM_RPM", "LLM_RPD")


def _env(monkeypatch, **values):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)
    return _env_secrets()


def test_gmail_app_password_defaults(monkeypatch):
    s = _env(monkeypatch, SMTP_USER="jane@gmail.com", SMTP_PASSWORD="abcd efgh ijkl mnop")
    assert (s.smtp_host, s.smtp_port, s.smtp_use_ssl) == ("smtp.gmail.com", 587, False)
    assert s.smtp_password == "abcdefghijklmnop", "spaces from Google's display are stripped"
    assert s.sender_email == "jane@gmail.com" and s.smtp_ready and s.uses_gmail
    assert (s.imap_host, s.imap_username, s.imap_password) == ("imap.gmail.com", "jane@gmail.com", "abcdefghijklmnop")


def test_custom_smtp_and_port_465(monkeypatch):
    s = _env(monkeypatch, SMTP_HOST="mail.out.dev", SMTP_PORT="465", SMTP_USERNAME="me@out.dev", SMTP_PASSWORD="pw",
             SENDER_EMAIL="Me@out.dev")
    assert s.smtp_use_ssl and s.smtp_username == "me@out.dev" and s.imap_host == "" and not s.uses_gmail
    assert not _env(monkeypatch, SMTP_PORT="465", SMTP_USE_SSL="false").smtp_use_ssl


def test_llm_defaults_to_gemini(monkeypatch):
    s = _env(monkeypatch, GEMINI_API_KEY="g-key")
    assert (s.llm_api_key, s.llm_base_url, s.llm_model, s.llm_reasoning_effort) == \
        ("g-key", GEMINI_BASE_URL, GEMINI_MODEL, "low")
    s = _env(monkeypatch, OPENAI_API_KEY="sk-x")
    assert (s.llm_base_url, s.llm_model, s.llm_reasoning_effort) == (OPENAI_BASE_URL, "gpt-4o-mini", "")
    s = _env(monkeypatch, LLM_API_KEY="k", LLM_BASE_URL="https://api.groq.com/openai/v1", LLM_MODEL="llama")
    assert (s.llm_model, s.llm_reasoning_effort) == ("llama", "")
