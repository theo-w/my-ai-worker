from unittest.mock import patch
import json

import pytest

from mvp.llm import OpenAICompatibleLLM, LLMConfigurationError
from mvp.executor import LLMWorkerExecutor


class DummyClient:
    model = "test-model"

    def complete(self, system_prompt, user_prompt):
        assert "verified evidence" in system_prompt
        assert '"goal": "Test a game"' in user_prompt
        return "Assumptions: market demand needs external validation."


def test_llm_worker_executor_returns_auditable_non_evidence_output():
    result = LLMWorkerExecutor(DummyClient()).execute(
        {"id": "research", "title": "Research market", "capability": "research"},
        "Test a game",
    )
    assert result.status == "completed"
    assert result.simulated is False
    assert result.metadata["mode"] == "llm"
    assert result.metadata["output_is_verified_evidence"] is False
    assert "external validation" in result.output


def test_llm_requires_explicit_environment_configuration():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(LLMConfigurationError):
            OpenAICompatibleLLM.from_environment()


def test_llm_rejects_non_https_endpoint():
    # 非回环主机走 http 必须被拒绝;回环(本机模型服务器)允许。
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAICompatibleLLM("http://model.example.com/v1", "key", "model")


def test_llm_allows_loopback_http_endpoint():
    client = OpenAICompatibleLLM("http://127.0.0.1:8000/v1", "key", "model")
    assert client.base_url == "http://127.0.0.1:8000/v1"


def test_llm_parses_chat_completion_response(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_ENABLED", "true")
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size=-1):
            return json.dumps({
                "choices": [{"message": {"content": "A structured worker result"}}]
            }).encode()

    with patch("mvp.llm.urlopen", return_value=Response()) as open_url:
        client = OpenAICompatibleLLM("https://llm.example/v1", "secret", "model")
        assert client.complete("system", "user") == "A structured worker result"
        request = open_url.call_args.args[0]
        assert request.full_url == "https://llm.example/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer secret"
