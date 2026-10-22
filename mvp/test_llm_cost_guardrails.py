import json
from unittest.mock import patch

import pytest

from mvp.llm import LLMConfigurationError, OpenAICompatibleLLM


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return json.dumps({
            "choices": [{"message": {"content": "ok"}}]
        }).encode("utf-8")


def test_environment_sets_bounded_token_and_timeout(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("JARVIS_LLM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("JARVIS_LLM_MODEL", "test-model")
    monkeypatch.setenv("JARVIS_LLM_MAX_TOKENS", "1200")
    monkeypatch.setenv("JARVIS_LLM_TIMEOUT_SECONDS", "18")

    client = OpenAICompatibleLLM.from_environment()

    assert client.max_tokens == 1200
    assert client.timeout == 18


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        ("JARVIS_LLM_MAX_TOKENS", "bad", 768),
        ("JARVIS_LLM_MAX_TOKENS", "2", 64),
        ("JARVIS_LLM_MAX_TOKENS", "99999", 4096),
        ("JARVIS_LLM_TIMEOUT_SECONDS", "bad", 45),
        ("JARVIS_LLM_TIMEOUT_SECONDS", "0", 1),
        ("JARVIS_LLM_TIMEOUT_SECONDS", "999", 120),
    ],
)
def test_invalid_and_out_of_range_environment_values_are_bounded(
    monkeypatch, name, value, expected
):
    monkeypatch.setenv("JARVIS_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("JARVIS_LLM_API_KEY", "not-a-real-key")
    monkeypatch.setenv("JARVIS_LLM_MODEL", "test-model")
    monkeypatch.setenv(name, value)

    client = OpenAICompatibleLLM.from_environment()

    if name == "JARVIS_LLM_MAX_TOKENS":
        assert client.max_tokens == expected
    else:
        assert client.timeout == expected


def test_complete_sends_max_tokens_and_configured_timeout():
    client = OpenAICompatibleLLM(
        "https://example.test/v1", "not-a-real-key", "test-model",
        timeout=12, max_tokens=256,
    )
    with patch("mvp.llm.urlopen", return_value=FakeResponse()) as mocked:
        assert client.complete("system", "user") == "ok"

    request = mocked.call_args.args[0]
    payload = json.loads(request.data.decode("utf-8"))
    assert payload["max_tokens"] == 256
    assert payload["model"] == "test-model"
    assert mocked.call_args.kwargs["timeout"] == 12


def test_missing_required_environment_variables_fail_closed(monkeypatch):
    for name in ("JARVIS_LLM_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(LLMConfigurationError):
        OpenAICompatibleLLM.from_environment()
