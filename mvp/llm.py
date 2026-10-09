"""OpenAI-compatible chat-completions adapter for JARVIS Workers.

This module uses only the Python standard library. It does not provide web
search or source verification; model-generated text is not research evidence.
"""
from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


class LLMConfigurationError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 45.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = max(1.0, float(timeout))
        if not self.base_url.startswith("https://"):
            raise ValueError("LLM base URL must use HTTPS.")

    @classmethod
    def from_environment(cls):
        base_url = os.getenv("JARVIS_LLM_BASE_URL", "").strip()
        api_key = os.getenv("JARVIS_LLM_API_KEY", "").strip()
        model = os.getenv("JARVIS_LLM_MODEL", "").strip()
        if not (base_url and api_key and model):
            raise LLMConfigurationError(
                "Configure JARVIS_LLM_BASE_URL, JARVIS_LLM_API_KEY and JARVIS_LLM_MODEL."
            )
        return cls(base_url, api_key, model)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        endpoint = self.base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }).encode("utf-8")
        request = Request(endpoint, data=payload, method="POST", headers={
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "JARVIS-Worker/0.8",
        })
        with urlopen(request, timeout=self.timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError("LLM provider returned HTTP " + str(response.status))
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise RuntimeError("LLM provider response exceeded 2 MB.")
        try:
            data = json.loads(raw.decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM provider returned an invalid chat-completions response.") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM provider returned empty content.")
        return content.strip()
