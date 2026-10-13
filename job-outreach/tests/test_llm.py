import json

import httpx
import pytest
import respx

from jobhunt.llm import GEMINI_BASE_URL, GEMINI_MODEL, LLMClient, LLMError, LLMQuotaError, RateLimiter, parse_json


@respx.mock
def test_client_posts_openai_compatible_request():
    route = respx.post("https://llm.local/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content": '{"summary": "ok"}'}}]
    }))
    out = LLMClient("https://llm.local/v1/", "key", "m").complete_json("sys", "user")
    assert out == {"summary": "ok"}
    req = route.calls[0].request
    assert req.headers["Authorization"] == "Bearer key"
    body = json.loads(req.content)
    assert body["model"] == "m" and body["response_format"] == {"type": "json_object"}


@respx.mock
def test_client_wraps_http_errors():
    route = respx.post("https://llm.local/v1/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises(LLMError):
        LLMClient("https://llm.local/v1", "key", "m", sleep=lambda s: None).complete_json("s", "u")
    assert route.call_count == 5, "5xx is retried before giving up"


def test_parse_json_tolerates_code_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(LLMError):
        parse_json("no json here")


class Clock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class Store:
    def __init__(self):
        self.kv = {}

    def kv_get(self, k):
        return self.kv.get(k)

    def kv_set(self, k, v):
        self.kv[k] = v


def test_limiter_spaces_requests_and_enforces_daily_budget():
    clock, store = Clock(), Store()
    lim = RateLimiter(rpm=30, rpd=3, clock=clock, sleep=clock.sleep, today=lambda: "2026-10-13")
    for _ in range(3):
        lim.acquire(store)
    assert clock.slept == [2.0, 2.0], "30 rpm = one request every 2s"
    assert store.kv["llm_usage"]["count"] == 3
    with pytest.raises(LLMQuotaError):
        lim.acquire(store)
    fresh = RateLimiter(rpm=0, rpd=3, today=lambda: "2026-10-13")
    assert fresh.remaining(store) == 0, "the count survives a restart"
    assert RateLimiter(rpm=0, rpd=3, today=lambda: "2026-10-14").remaining(store) == 3, "new Pacific day"


@respx.mock
def test_gemini_429_retries_with_server_delay_then_succeeds():
    url = GEMINI_BASE_URL.rstrip("/") + "/chat/completions"
    route = respx.post(url).mock(side_effect=[
        httpx.Response(429, json={"error": {"code": 429, "details": [{"retryDelay": "7s"}]}}),
        httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]}),
    ])
    clock = Clock()
    lim = RateLimiter(rpm=60, rpd=100, clock=clock, sleep=clock.sleep)
    llm = LLMClient(GEMINI_BASE_URL, "g-key", GEMINI_MODEL, limiter=lim, reasoning_effort="low", sleep=clock.sleep)
    assert llm.complete_json("s", "u") == {"ok": True}
    assert clock.slept == [7.0], "waited the retryDelay Gemini asked for"
    body = json.loads(route.calls[1].request.content)
    assert body["model"] == GEMINI_MODEL and body["reasoning_effort"] == "low"


@respx.mock
def test_daily_quota_429_stops_for_the_day():
    url = GEMINI_BASE_URL.rstrip("/") + "/chat/completions"
    respx.post(url).mock(return_value=httpx.Response(429, json={"error": {"message": "Quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}}))
    store = Store()
    llm = LLMClient(GEMINI_BASE_URL, "g", GEMINI_MODEL, limiter=RateLimiter(0, 100), store=store)
    with pytest.raises(LLMQuotaError):
        llm.complete_json("s", "u")
    assert llm.remaining_today() == 0


@respx.mock
def test_retries_without_json_mode_when_rejected():
    route = respx.post("https://llm.local/v1/chat/completions").mock(side_effect=[
        httpx.Response(400, json={"error": {"message": "Invalid value for response_format"}}),
        httpx.Response(200, json={"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]}),
    ])
    assert LLMClient("https://llm.local/v1", "k", "m").complete_json("s", "u") == {"a": 1}
    assert "response_format" not in json.loads(route.calls[1].request.content)
