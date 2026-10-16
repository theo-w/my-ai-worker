from mvp.executor import RegistryWorkerExecutor, SimulatedWorkerExecutor
from mvp.twin import AutonomousProjectLoop


def test_simulated_executor_is_explicitly_marked():
    result = SimulatedWorkerExecutor().execute(
        {"id": "research", "title": "Research", "capability": "market_research"},
        "Evaluate a product",
    )
    assert result.status == "completed"
    assert result.simulated is True
    assert result.metadata["external_tools_used"] is False
    assert "[SIMULATED]" in result.output


def test_registered_executor_dispatches_by_capability():
    executor = RegistryWorkerExecutor({
        "analysis": lambda task, goal: f"Analyzed {goal} for {task['id']}"
    })
    result = executor.execute(
        {"id": "decision", "capability": "analysis"}, "Evaluate a product"
    )
    assert result.simulated is False
    assert result.metadata["mode"] == "registered_adapter"
    assert "Evaluate a product" in result.output


def test_missing_capability_blocks_project_task():
    tasks = [{"id": "research", "title": "Research", "capability": "live_web_search"}]
    executor = RegistryWorkerExecutor()
    report = AutonomousProjectLoop().run(
        "Find current market evidence", tasks,
        lambda task: executor.execute(task, "Find current market evidence").output,
    )
    assert report["status"] == "failed"
    assert tasks[0]["status"] == "blocked"
    assert "LookupError" in tasks[0]["output"]


def test_empty_adapter_output_is_rejected():
    executor = RegistryWorkerExecutor({"analysis": lambda task, goal: "   "})
    try:
        executor.execute({"id": "a", "capability": "analysis"}, "goal")
    except ValueError:
        pass
    else:
        raise AssertionError("empty output should not be accepted")


def test_hybrid_executor_never_uses_llm_as_research_substitute(monkeypatch):
    from mvp.executor import HybridWorkerExecutor, LLMWorkerExecutor
    class FakeLLM:
        model = "fake-model"
        def complete(self, system_prompt, user_prompt):
            return "Invented market summary"
    monkeypatch.delenv("JARVIS_SEARCH_ENDPOINT", raising=False)
    executor = HybridWorkerExecutor(LLMWorkerExecutor(FakeLLM()))
    try:
        executor.execute({"id": "research", "title": "Research market", "capability": "research"}, "Assess market")
    except LookupError as exc:
        assert "cannot substitute" in str(exc)
    else:
        raise AssertionError("research must not silently fall back to LLM prose")


def test_hybrid_executor_routes_analysis_to_llm(monkeypatch):
    from mvp.executor import HybridWorkerExecutor, LLMWorkerExecutor
    class FakeLLM:
        model = "fake-model"
        def complete(self, system_prompt, user_prompt):
            return "Analysis draft; facts remain unverified."
    monkeypatch.delenv("JARVIS_SEARCH_ENDPOINT", raising=False)
    executor = HybridWorkerExecutor(LLMWorkerExecutor(FakeLLM()))
    result = executor.execute(
        {"id": "analysis", "title": "Analyze tradeoffs", "capability": "analysis"},
        "Evaluate an AI-native game",
    )
    assert result.status == "completed"
    assert result.metadata["trust_level"] == "model_generated_unverified"
    assert result.metadata["verified_truth"] is False


def test_hybrid_executor_blocks_research_without_accepted_evidence(monkeypatch):
    import mvp.research as research
    from mvp.executor import HybridWorkerExecutor
    monkeypatch.setenv("JARVIS_SEARCH_ENDPOINT", "https://search.example/api")
    monkeypatch.setattr(research, "run_live_research", lambda query, limit=5: {
        "status": "no_results", "sources": [],
        "quality": {"items": []}, "synthesis": None, "llm_synthesis": None,
    })
    executor = HybridWorkerExecutor()
    try:
        executor.execute({"id": "research", "title": "Research", "capability": "research"}, "Assess market")
    except RuntimeError as exc:
        assert "no quality-accepted evidence" in str(exc)
    else:
        raise AssertionError("empty evidence must block research task")
