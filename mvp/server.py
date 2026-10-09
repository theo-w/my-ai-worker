#!/usr/bin/env python3
"""Dependency-free local JARVIS Digital Workforce dashboard server."""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from .run import WORKERS, evaluate, run_worker
    from .twin import DigitalTwin, AutonomousProjectLoop, PersistentTwinMemory
    from .executor import SimulatedWorkerExecutor, LLMWorkerExecutor
    from .llm import OpenAICompatibleLLM, LLMConfigurationError
    from .research import run_live_research, research_environment_status
    from .planning import plan_project, replan_failed_tasks
    from .accuracy import classify_output
except ImportError:  # Direct script execution from mvp/
    from run import WORKERS, evaluate, run_worker
    from twin import DigitalTwin, AutonomousProjectLoop, PersistentTwinMemory
    from executor import SimulatedWorkerExecutor, LLMWorkerExecutor
    from llm import OpenAICompatibleLLM, LLMConfigurationError
    from research import run_live_research, research_environment_status
    from planning import plan_project, replan_failed_tasks
    from accuracy import classify_output

ROOT = Path(__file__).parent
LOCK = threading.Lock()
TWIN = DigitalTwin()
MEMORY = PersistentTwinMemory()
PROJECT_LOOP = AutonomousProjectLoop()
def _build_worker_executor():
    if all(os.getenv(key, "").strip() for key in (
        "JARVIS_LLM_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_LLM_MODEL"
    )):
        try:
            return LLMWorkerExecutor(OpenAICompatibleLLM.from_environment())
        except (ValueError, LLMConfigurationError):
            return SimulatedWorkerExecutor()
    return SimulatedWorkerExecutor()


WORKER_EXECUTOR = _build_worker_executor()
STATE = {
    "goal": "评估一个 AI 原生游戏机会",
    "business_context": "用最小成本验证一个业务机会，只有值得做才进入 Prototype。",
    "phase": "idle",
    "agents": [],
    "evidence": [],
    "decision": None,
    "twin": TWIN.snapshot("评估一个 AI 原生游戏机会", WORKERS),
    "prototype": None,
}

def reset(goal: str):
    team = TWIN.form_team(goal, WORKERS)
    with LOCK:
        STATE["goal"] = goal
        STATE["phase"] = "planning"
        STATE["agents"] = [
            {"id": i, "worker": w, "capability": c, "status": "queued",
             "progress": 0, "task": c, "input": goal, "output": "", "evidence": []}
            for i, (w, c) in enumerate(team)
        ]
        STATE["evidence"] = []
        STATE["decision"] = None
        STATE["prototype"] = None
        STATE["twin"] = TWIN.snapshot(goal, team)

def execute(goal: str):
    """Run the Dashboard workforce using the configured executor.

    Simulated outputs may populate the demo evidence stream. LLM outputs are
    displayed as task artifacts, never promoted to source-backed evidence.
    """
    reset(goal)
    time.sleep(.1)
    with LOCK:
        STATE["phase"] = "team"
        for agent in STATE["agents"]:
            agent["status"] = "ready"

    with LOCK:
        planned = [(a["worker"], a["capability"]) for a in STATE["agents"]]

    for idx, (worker, capability) in enumerate(planned):
        with LOCK:
            agent = STATE["agents"][idx]
            agent["status"] = "running"
            agent["progress"] = 20

        try:
            if isinstance(WORKER_EXECUTOR, SimulatedWorkerExecutor):
                items = run_worker(worker, capability, goal)
                output = " [SIMULATED] ".join(item.finding for item in items)
                result_data = {
                    "mode": "simulation",
                    "simulated": True,
                    "output_is_verified_evidence": False,
                }
            else:
                task = {
                    "id": str(idx),
                    "title": capability.replace("_", " "),
                    "capability": capability,
                    "worker": worker,
                }
                result = WORKER_EXECUTOR.execute(task, goal)
                output = result.output
                result_data = result.to_dict()
                # LLM prose is a task artifact, not source-backed evidence.
                items = []

            with LOCK:
                agent = STATE["agents"][idx]
                agent["progress"] = 70
                agent["output"] = output
                agent["execution"] = result_data
                agent["evidence"] = [item.__dict__ for item in items]
                agent["status"] = "completed"
                agent["progress"] = 100
                STATE["evidence"].extend(item.__dict__ for item in items)
        except Exception as exc:
            with LOCK:
                agent = STATE["agents"][idx]
                agent["status"] = "blocked"
                agent["progress"] = 100
                agent["output"] = "执行失败：" + type(exc).__name__
                agent["execution"] = {
                    "mode": "llm" if isinstance(WORKER_EXECUTOR, LLMWorkerExecutor) else "simulation",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                }

    with LOCK:
        STATE["phase"] = "evaluation"
    time.sleep(.1)
    evidence = [type("E", (), item) for item in STATE["evidence"]]
    # Only the explicit simulated executor may use the demo handoff.
    decision = evaluate(
        goal, evidence,
        demo_mode=isinstance(WORKER_EXECUTOR, SimulatedWorkerExecutor),
    )
    with LOCK:
        STATE["decision"] = decision.__dict__
        STATE["phase"] = "decision"

class Handler(BaseHTTPRequestHandler):
    def _json(self, payload, code=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self, max_bytes=1048576):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            self._json({"ok": False, "error": "Invalid Content-Length."}, 400)
            return None
        if length < 0:
            self._json({"ok": False, "error": "Invalid Content-Length."}, 400)
            return None
        if length > max_bytes:
            self._json({"ok": False, "error": "Request body too large."}, 413)
            return None
        try:
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json({"ok": False, "error": "Malformed JSON request body."}, 400)
            return None
        if not isinstance(body, dict):
            self._json({"ok": False, "error": "JSON request body must be an object."}, 400)
            return None
        return body
    def do_GET(self):
        if self.path == "/api/state":
            with LOCK:
                self._json(dict(STATE))
            return
        if self.path == "/api/research/status":
            self._json(research_environment_status())
            return
        if self.path == "/api/llm/status":
            configured = isinstance(WORKER_EXECUTOR, LLMWorkerExecutor)
            self._json({
                "configured": configured,
                "mode": "llm" if configured else "simulated",
                "model": getattr(getattr(WORKER_EXECUTOR, "client", None), "model", None),
                "message": "LLM worker configured; outputs are not independently verified evidence."
                    if configured else
                    "LLM not configured; autonomous tasks use simulated execution.",
            })
            return
        if self.path in ("/", "/index.html"):
            data = (ROOT / "dashboard.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path not in ("/api/run", "/api/prototype", "/api/autonomous", "/api/research"):
            self.send_error(404)
            return
        if self.path == "/api/research":
            body = self._read_json()
            if body is None:
                return
            query = str(body.get("query", body.get("goal", ""))).strip()
            try:
                limit = max(1, min(int(body.get("limit", 5)), 10))
            except (TypeError, ValueError):
                limit = 5
            result = run_live_research(query, limit)
            code = 400 if result.get("status") == "invalid_request" else 200
            self._json(result, code)
            return
        if self.path == "/api/autonomous":
            body = self._read_json()
            if body is None:
                return
            goal = str(body.get("goal", "")).strip()
            if not goal:
                self._json({"ok": False, "error": "A project goal is required."}, 400)
                return
            planner_client = getattr(WORKER_EXECUTOR, "client", None) if isinstance(WORKER_EXECUTOR, LLMWorkerExecutor) else None
            planning = None
            supplied_tasks = body.get("tasks")
            if isinstance(supplied_tasks, list) and supplied_tasks:
                tasks = supplied_tasks
                planning = {"mode": "user_supplied", "warnings": []}
            else:
                planning = plan_project(goal, planner_client)
                tasks = planning["tasks"]
            options = body.get("options") or []
            actions = body.get("requested_actions") or []
            # The default executor is explicitly simulated. A real capability
            # adapter can replace it without changing the project-loop contract.
            def executor(task):
                result = WORKER_EXECUTOR.execute(task, goal)
                task["execution"] = result.to_dict()
                return result.output
            def replanner(replan_goal, failed_tasks, iteration):
                existing_ids = {str(task.get("id")) for task in tasks}
                return replan_failed_tasks(
                    replan_goal, failed_tasks, iteration, planner_client, existing_ids
                )
            report = PROJECT_LOOP.run(
                goal, tasks, executor, options, actions,
                replanner=replanner if planner_client is not None else None,
            )
            if report["status"] == "completed" and report.get("recommendation"):
                MEMORY.record_decision(goal, report["recommendation"], report.get("options", []))
            task_rows = report.get("tasks", tasks)
            trust_counts = {}
            for task in task_rows:
                execution = task.get("execution") or {}
                metadata = execution.get("metadata") or {}
                level = metadata.get("trust_level")
                if not level:
                    level = "simulated" if execution.get("simulated", True) else "tool_output_unverified"
                trust_counts[level] = trust_counts.get(level, 0) + 1
            unverified_count = sum(
                count for level, count in trust_counts.items()
                if level != "quality_gated_source"
            )
            accuracy = {
                "trust_counts": trust_counts,
                "unverified_task_outputs": unverified_count,
                "factual_decision_authorized": False,
                "note": "Task completion is not proof of factual correctness. LLM and tool outputs require independent evidence checks; this endpoint does not authorize consequential business decisions.",
            }
            self._json({"ok": True, "planning": planning, "report": report, "accuracy": accuracy, "memory": {
                "decision_count": len(MEMORY.decisions),
                "lesson_count": len(MEMORY.lessons),
                "preference_count": len(MEMORY.preferences),
            }})
            return
        if self.path == "/api/prototype":
            with LOCK:
                if not STATE["decision"] or STATE["decision"]["recommendation"] not in {"GO_TO_PROTOTYPE", "DEMO_GO_TO_PROTOTYPE"}:
                    self._json({"ok": False, "error": "Prototype requires a GO_TO_PROTOTYPE or DEMO_GO_TO_PROTOTYPE decision."}, 409)
                    return
                demo_mode = STATE["decision"]["recommendation"] == "DEMO_GO_TO_PROTOTYPE"
                STATE["prototype"] = {
                    "status": "planned",
                    "mode": "demo" if demo_mode else "evidence-backed",
                    "notice": "Demo handoff only; simulated evidence is not a business approval." if demo_mode else "Evidence-backed prototype handoff.",
                    "name": "AI Game Prototype Sprint",
                    "steps": [
                        "Define business success criteria",
                        "Design the smallest playable AI-native loop",
                        "Implement the AI interaction prototype",
                        "Run simulated player playtest",
                        "Evaluate, learn, and iterate",
                    ],
                }
                STATE["phase"] = "prototype"
            self._json({"ok": True, "prototype": STATE["prototype"]})
            return
        body = self._read_json()
        if body is None:
            return
        goal = str(body.get("goal", "")).strip() or "评估一个 AI 原生游戏机会"
        with LOCK:
            if STATE["phase"] in {"planning", "team", "evaluation"}:
                self._json({"ok": False, "error": "A run is already in progress."}, 409)
                return
            STATE["phase"] = "planning"  # Reserve atomically before starting the worker thread.
        threading.Thread(target=execute, args=(goal,), daemon=True).start()
        self._json({"ok": True})

if __name__ == "__main__":
    print("JARVIS Dashboard: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
