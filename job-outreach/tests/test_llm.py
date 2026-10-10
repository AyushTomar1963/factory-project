import json

import httpx
import pytest
import respx

from jobhunt.llm import LLMClient, LLMError, parse_json


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
    respx.post("https://llm.local/v1/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises(LLMError):
        LLMClient("https://llm.local/v1", "key", "m").complete_json("s", "u")


def test_parse_json_tolerates_code_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(LLMError):
        parse_json("no json here")
