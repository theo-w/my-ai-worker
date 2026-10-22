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


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read a bounded integer setting; invalid values fall back safely."""
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, value))


class OpenAICompatibleLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 45.0,
        max_tokens: int = 768,
        hard_max_tokens: int = 4096,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = min(120.0, max(1.0, float(timeout)))
        self.hard_max_tokens = min(4096, max(64, int(hard_max_tokens)))
        self.max_tokens = min(self.hard_max_tokens, max(64, int(max_tokens)))
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
        timeout = _bounded_env_int("JARVIS_LLM_TIMEOUT_SECONDS", 45, 1, 120)
        hard_max_tokens = _bounded_env_int("JARVIS_LLM_HARD_MAX_TOKENS", 4096, 64, 4096)
        max_tokens = _bounded_env_int("JARVIS_LLM_MAX_TOKENS", 768, 64, hard_max_tokens)
        return cls(base_url, api_key, model, timeout=timeout, max_tokens=max_tokens,
                   hard_max_tokens=hard_max_tokens)

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> str:
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
            "max_tokens": min(self.hard_max_tokens, max(64, int(max_tokens))) if max_tokens is not None else self.max_tokens,
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
