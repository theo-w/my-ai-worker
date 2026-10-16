"""Tests for capability readiness reporting exposed by the local API."""
from mvp import server
from mvp.executor import HybridWorkerExecutor, LLMWorkerExecutor, SimulatedWorkerExecutor


def _get_executor_status():
    class FakeHandler:
        path = "/api/executor/status"
        def _json(self, payload, code=200):
            self.payload = payload
            self.code = code
    handler = FakeHandler()
    server.Handler.do_GET(handler)
    return handler.payload


def test_executor_status_distinguishes_simulation_from_live_capabilities(monkeypatch):
    monkeypatch.delenv("JARVIS_SEARCH_ENDPOINT", raising=False)
    original = server.WORKER_EXECUTOR
    try:
        server.WORKER_EXECUTOR = SimulatedWorkerExecutor()
        status = _get_executor_status()
        assert status["mode"] == "simulated"
        assert status["search_configured"] is False
        assert status["llm_configured"] is False
        assert status["truth_policy"]["llm_output_is_verified"] is False
        assert status["capabilities"]["implementation"] == "no_code_execution_adapter_configured"
    finally:
        server.WORKER_EXECUTOR = original


def test_executor_status_reports_hybrid_readiness_without_overclaiming_truth(monkeypatch):
    monkeypatch.setenv("JARVIS_SEARCH_ENDPOINT", "https://search.example/api")
    original = server.WORKER_EXECUTOR
    try:
        server.WORKER_EXECUTOR = HybridWorkerExecutor()
        status = _get_executor_status()
        assert status["mode"] == "hybrid"
        assert status["search_configured"] is True
        assert status["llm_configured"] is False
        assert status["capabilities"]["research"] == "live_search"
        assert status["capabilities"]["analysis"] == "blocked_or_simulated_demo_only"
        assert status["truth_policy"]["search_snippet_is_verified_truth"] is False
        assert status["truth_policy"]["missing_required_tool_fails_closed"] is True
    finally:
        server.WORKER_EXECUTOR = original
