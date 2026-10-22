import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mvp import server


ADMIN = "admin-secret-for-llm-smoke-tests-0001"


class FakeLLMClient:
    model = "test-model"

    def __init__(self, reply="JARVIS_LLM_OK", error=None):
        self.reply = reply
        self.error = error
        self.max_tokens_seen = None

    def complete(self, system_prompt, user_prompt, max_tokens=None):
        self.max_tokens_seen = max_tokens
        if self.error:
            raise self.error
        return self.reply


def request_json(base, path, token=None, payload=None):
    data = json.dumps(payload if payload is not None else {}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(base + path, data=data, headers=headers)
    try:
        response = urlopen(request, timeout=3)
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def serve(monkeypatch, client):
    monkeypatch.delenv("JARVIS_PUBLIC_DEMO", raising=False)
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", ADMIN)
    monkeypatch.delenv("JARVIS_WORKER_TOKENS", raising=False)
    monkeypatch.setattr(server, "WORKER_EXECUTOR", type("Executor", (), {"client": client})())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, f"http://127.0.0.1:{httpd.server_port}"


def close(httpd, thread):
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def test_llm_smoke_test_requires_admin_authentication(monkeypatch):
    client = FakeLLMClient()
    httpd, thread, base = serve(monkeypatch, client)
    try:
        status, result = request_json(base, "/api/llm/smoke-test", payload={})
        assert status == 401
        assert result["ok"] is False
        assert client.max_tokens_seen is None
    finally:
        close(httpd, thread)


def test_llm_smoke_test_uses_small_token_budget_and_returns_safe_status(monkeypatch):
    client = FakeLLMClient()
    httpd, thread, base = serve(monkeypatch, client)
    try:
        status, result = request_json(base, "/api/llm/smoke-test", ADMIN, {})
        assert status == 200
        assert result["ok"] is True
        assert result["status"] == "connected"
        assert result["model"] == "test-model"
        assert result["max_tokens"] == 64
        assert client.max_tokens_seen == 64
        assert "JARVIS_LLM_OK" not in json.dumps(result)
    finally:
        close(httpd, thread)


def test_llm_smoke_test_does_not_echo_provider_exception(monkeypatch):
    client = FakeLLMClient(error=RuntimeError("private provider detail"))
    httpd, thread, base = serve(monkeypatch, client)
    try:
        status, result = request_json(base, "/api/llm/smoke-test", ADMIN, {})
        assert status == 502
        assert result["status"] == "provider_error"
        assert result["error_type"] == "RuntimeError"
        assert "private provider detail" not in json.dumps(result)
    finally:
        close(httpd, thread)
