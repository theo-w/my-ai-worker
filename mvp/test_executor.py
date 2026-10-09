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
