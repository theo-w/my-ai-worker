"""Integration tests for the automatic end-to-end feasibility gate."""
from unittest.mock import patch

from mvp import server
from mvp.executor import SimulatedWorkerExecutor


def _research_result(title, url, snippet):
    source = {"title": title, "url": url, "snippet": snippet, "provider": "test"}
    item = {
        "worker": "Live Research Adapter",
        "finding": snippet,
        "confidence": 0.75,
        "simulated": False,
        "source": source,
        "quality_accepted": True,
    }
    return {
        "ok": True,
        "status": "completed",
        "query": "test",
        "sources": [source],
        "evidence": [item],
        "quality": {"accepted": 1, "total": 1, "items": [item]},
        "synthesis": {"evidence_count": 1},
        "llm_synthesis": {"status": "skipped_by_orchestrator", "text": None},
    }


def test_main_run_creates_automatic_feasibility_assessment_and_counter_search(monkeypatch):
    monkeypatch.setenv("JARVIS_SEARCH_ENDPOINT", "https://search.example/api")
    monkeypatch.delenv("JARVIS_LLM_INPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_LLM_OUTPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_GAME_DEV_COST_PER_PERSON_WEEK_USD", raising=False)

    primary = _research_result("Primary market overview", "https://market.example/report", "Market context excerpt.")
    counter = _research_result("Limitations overview", "https://risk.example/limitations", "A counterpoint excerpt.")
    original_executor = server.WORKER_EXECUTOR
    try:
        server.WORKER_EXECUTOR = SimulatedWorkerExecutor()
        with patch("mvp.server.time.sleep"), patch(
            "mvp.server.run_live_research", side_effect=[primary, counter]
        ) as search, patch.object(
            server.GAME_KNOWLEDGE, "ingest_sources", return_value={"inserted": 0, "updated": 0}
        ):
            server.execute("评估 AI 原生游戏玩法是否值得做")

        assert search.call_count == 2
        assert all(call.kwargs.get("include_llm_synthesis") is False for call in search.call_args_list)
        state = server.STATE
        assert state["phase"] == "decision"
        assert state["feasibility"]["status"] == "completed_with_gaps"
        assert state["feasibility"]["report"]["counter_evidence_refs"] == ["C1"]
        assert state["feasibility"]["evaluation"]["decision"] == "INSUFFICIENT_EVIDENCE"
        assert state["decision"]["recommendation"] == "HOLD_FOR_EVIDENCE"
        assert all(row["status"] in {"completed", "blocked"} for row in state["agents"])
        assert state["feasibility"]["evaluation"]["verified_truth"] is False
    finally:
        server.WORKER_EXECUTOR = original_executor
