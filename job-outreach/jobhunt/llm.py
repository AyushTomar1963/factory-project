"""Thin client for any OpenAI-compatible /chat/completions endpoint."""
from __future__ import annotations

import json
import re

import httpx


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.http = client or httpx.Client(timeout=httpx.Timeout(90.0))

    def complete_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            r = self.http.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        return parse_json(content)


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
