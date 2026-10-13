"""Client for any OpenAI-compatible /chat/completions endpoint.

The default is Google Gemini through its OpenAI-compatible endpoint, so a
free `GEMINI_API_KEY` from AI Studio is all that's needed. Free-tier quotas are
per Google Cloud project and enforced per minute and per day (the day resets at
midnight Pacific), so every client in the process shares one limiter that
spaces requests out, honours the server's retry hints on 429, and stops for
the rest of the day once the daily budget is used.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

import httpx

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-3.5-flash-lite"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"

_PACIFIC = ZoneInfo("America/Los_Angeles")


class LLMError(RuntimeError):
    pass


class LLMQuotaError(LLMError):
    """The daily request budget is used up; retry after midnight Pacific."""


class UsageStore(Protocol):
    def kv_get(self, key: str): ...
    def kv_set(self, key: str, value) -> None: ...


def is_gemini(base_url: str) -> bool:
    return "generativelanguage.googleapis.com" in base_url


class RateLimiter:
    """Requests-per-minute spacing plus a requests-per-day budget.

    The daily count is persisted through `store` (the app database) when one
    is given, so restarts on a free host don't reset it.
    """

    def __init__(self, rpm: int, rpd: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, today: Callable[[], str] | None = None):
        self.rpm, self.rpd = rpm, rpd
        self.clock, self.sleep = clock, sleep
        self.today = today or (lambda: datetime.now(_PACIFIC).date().isoformat())
        self.lock = threading.Lock()
        self.next_at = 0.0
        self.local = {"day": "", "count": 0, "exhausted": False}

    def _usage(self, store: UsageStore | None) -> dict:
        u = (store.kv_get("llm_usage") if store else None) or self.local
        if u.get("day") != self.today():
            u = {"day": self.today(), "count": 0, "exhausted": False}
        return u

    def _save(self, store: UsageStore | None, u: dict) -> None:
        self.local = u
        if store:
            store.kv_set("llm_usage", u)

    def remaining(self, store: UsageStore | None = None) -> int:
        u = self._usage(store)
        if u.get("exhausted"):
            return 0
        return max(0, self.rpd - u["count"]) if self.rpd > 0 else 1_000_000

    def acquire(self, store: UsageStore | None = None) -> None:
        with self.lock:
            u = self._usage(store)
            if u.get("exhausted") or (self.rpd > 0 and u["count"] >= self.rpd):
                raise LLMQuotaError(f"daily LLM budget used ({u['count']} requests); resets at midnight Pacific")
            if self.rpm > 0:
                wait = self.next_at - self.clock()
                if wait > 0:
                    self.sleep(wait)
                self.next_at = max(self.clock(), self.next_at) + 60.0 / self.rpm
            u["count"] += 1
            self._save(store, u)

    def mark_exhausted(self, store: UsageStore | None = None) -> None:
        with self.lock:
            u = self._usage(store)
            u["exhausted"] = True
            self._save(store, u)

    def back_off(self, seconds: float) -> None:
        with self.lock:
            self.next_at = max(self.next_at, self.clock() + seconds)


_limiters: dict[tuple, RateLimiter] = {}
_limiters_lock = threading.Lock()


def shared_limiter(base_url: str, api_key: str, rpm: int, rpd: int) -> RateLimiter:
    key = (base_url, api_key[-8:], rpm, rpd)
    with _limiters_lock:
        if key not in _limiters:
            _limiters[key] = RateLimiter(rpm, rpd)
        return _limiters[key]


def _retry_after(r: httpx.Response) -> float | None:
    """Seconds to wait from a Retry-After header or Gemini's RetryInfo detail."""
    header = r.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', r.text)
    return float(m.group(1)) if m else None


def _is_daily_quota(r: httpx.Response) -> bool:
    return bool(re.search(r"per ?day|PerDay|RequestsPerDay", r.text, re.IGNORECASE))


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, client: httpx.Client | None = None,
                 limiter: RateLimiter | None = None, store: UsageStore | None = None,
                 reasoning_effort: str = "", max_output_tokens: int = 0, max_retries: int = 4,
                 sleep: Callable[[float], None] = time.sleep):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.http = client or httpx.Client(timeout=httpx.Timeout(90.0))
        self.limiter = limiter or RateLimiter(0, 0)
        self.store = store
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self.sleep = sleep
        self.json_mode = True

    def remaining_today(self) -> int:
        return self.limiter.remaining(self.store)

    def _payload(self, system: str, user: str, temperature: float) -> dict:
        payload: dict = {
            "model": self.model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        if self.max_output_tokens:
            payload["max_tokens"] = self.max_output_tokens
        return payload

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire(self.store)
            try:
                r = self.http.post(
                    f"{self.base_url}/chat/completions",
                    json=self._payload(system, user, temperature),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            except httpx.HTTPError as exc:
                if attempt < self.max_retries:
                    self.sleep(min(2 ** attempt, 30))
                    continue
                raise LLMError(f"LLM request failed: {exc}") from exc

            if r.status_code == 429:
                if _is_daily_quota(r):
                    self.limiter.mark_exhausted(self.store)
                    raise LLMQuotaError("the provider's daily quota is used up; resets at midnight Pacific")
                if attempt < self.max_retries:
                    wait = _retry_after(r) or min(2 ** (attempt + 2), 60)
                    self.limiter.back_off(wait)
                    continue
            if r.status_code in (500, 502, 503, 504) and attempt < self.max_retries:
                self.sleep(min(2 ** (attempt + 1), 30))
                continue
            if r.status_code == 400 and self.json_mode and "response_format" in r.text:
                self.json_mode = False  # some compatible servers reject JSON mode; parse_json copes without it
                continue
            if r.status_code >= 400:
                raise LLMError(f"LLM request failed: HTTP {r.status_code} {r.text[:300]}")
            try:
                content = r.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"LLM returned an unexpected response: {exc}") from exc
            return parse_json(content or "")
        raise LLMError("LLM request failed: rate limited after retries")


def parse_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError("LLM did not return valid JSON")
