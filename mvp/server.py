#!/usr/bin/env python3
"""Dependency-free local JARVIS Digital Workforce dashboard server."""
from __future__ import annotations

import json
import math
import hmac
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .run import WORKERS, evaluate, run_worker
    from .twin import DigitalTwin, AutonomousProjectLoop, PersistentTwinMemory
    from .executor import SimulatedWorkerExecutor, LLMWorkerExecutor, HybridWorkerExecutor
    from .llm import OpenAICompatibleLLM, LLMConfigurationError
    from .research import run_live_research, research_environment_status
    from .planning import plan_project, replan_failed_tasks, validate_plan
    from .accuracy import classify_output
    from .experience_design import create_design_brief
    from .game_action import interpret_and_validate_action
    from .model_handoff import interpret_handoff_and_validate_action
    from .workforce import WorkforceRegistry
except ImportError:  # Direct script execution from mvp/
    from run import WORKERS, evaluate, run_worker
    from twin import DigitalTwin, AutonomousProjectLoop, PersistentTwinMemory
    from executor import SimulatedWorkerExecutor, LLMWorkerExecutor, HybridWorkerExecutor
    from llm import OpenAICompatibleLLM, LLMConfigurationError
    from research import run_live_research, research_environment_status
    from planning import plan_project, replan_failed_tasks, validate_plan
    from accuracy import classify_output
    from experience_design import create_design_brief
    from game_action import interpret_and_validate_action
    from model_handoff import interpret_handoff_and_validate_action
    from workforce import WorkforceRegistry

ROOT = Path(__file__).parent
LOCK = threading.Lock()
TWIN = DigitalTwin()
MEMORY = PersistentTwinMemory()
PROJECT_LOOP = AutonomousProjectLoop()
WORKFORCE = WorkforceRegistry(path=os.getenv("JARVIS_WORKFORCE_STORE", "data/workforce.json"))
def _build_worker_executor():
    llm_executor = None
    if all(os.getenv(key, "").strip() for key in (
        "JARVIS_LLM_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_LLM_MODEL"
    )):
        try:
            llm_executor = LLMWorkerExecutor(OpenAICompatibleLLM.from_environment())
        except (ValueError, LLMConfigurationError):
            llm_executor = None
    # Use a capability router whenever either live integration is configured.
    # It fails closed for missing research/LLM providers; simulation is used only
    # when neither live integration is configured.
    if llm_executor is not None or os.getenv("JARVIS_SEARCH_ENDPOINT", "").strip():
        return HybridWorkerExecutor(llm_executor)
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
                    "mode": "hybrid" if isinstance(WORKER_EXECUTOR, HybridWorkerExecutor) else ("llm" if isinstance(WORKER_EXECUTOR, LLMWorkerExecutor) else "simulation"),
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

def validate_autonomous_request(body: dict) -> dict:
    """Validate untrusted API fields before planning or execution."""
    goal = body.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("A project goal is required.")
    goal = goal.strip()
    if len(goal) > 2000:
        raise ValueError("Project goal must be at most 2000 characters.")

    supplied_tasks = body.get("tasks")
    if supplied_tasks is not None:
        if not isinstance(supplied_tasks, list) or not supplied_tasks:
            raise ValueError("tasks must be a non-empty array when supplied.")
        validated = validate_plan(json.dumps({"tasks": supplied_tasks}, ensure_ascii=False))
        tasks = validated["tasks"]
        planning = {"mode": "user_supplied", "warnings": ["User-supplied tasks were schema-validated; execution outputs still require independent verification."]}
    else:
        tasks = None
        planning = None

    options = body.get("options", [])
    if not isinstance(options, list) or len(options) > 10:
        raise ValueError("options must be an array containing at most 10 items.")
    normalized_options = []
    for item in options:
        if not isinstance(item, dict):
            raise ValueError("Each option must be an object.")
        name = item.get("name")
        score = item.get("score", 0)
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            raise ValueError("Each option needs a non-empty name under 160 characters.")
        if isinstance(score, bool):
            raise ValueError("Option score must be a finite number.")
        try:
            score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError("Option score must be a finite number.") from exc
        if not math.isfinite(score):
            raise ValueError("Option score must be a finite number.")
        normalized_options.append({**item, "name": name.strip(), "score": score})

    actions = body.get("requested_actions", [])
    if not isinstance(actions, list) or len(actions) > 20 or any(
        not isinstance(action, str) or not action.strip() or len(action) > 100
        for action in actions
    ):
        raise ValueError("requested_actions must be an array of at most 20 non-empty action names.")

    return {
        "goal": goal,
        "tasks": tasks,
        "planning": planning,
        "options": normalized_options,
        "requested_actions": [action.strip() for action in actions],
    }



class WorkforceAuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _worker_tokens() -> dict[str, str]:
    raw = os.getenv("JARVIS_WORKER_TOKENS", "").strip()
    if raw:
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkforceAuthError(503, "JARVIS_WORKER_TOKENS must be valid JSON.") from exc
        if not isinstance(values, dict):
            raise WorkforceAuthError(503, "JARVIS_WORKER_TOKENS must be a JSON object.")
        for worker_id, token in values.items():
            if not isinstance(worker_id, str) or not worker_id.strip() or not isinstance(token, str) or len(token) < 24:
                raise WorkforceAuthError(503, "Each worker token must be at least 24 characters and have a worker ID.")
        return {key.strip(): value for key, value in values.items()}
    token, worker_id = os.getenv("JARVIS_WORKER_TOKEN", ""), os.getenv("JARVIS_WORKER_ID", "")
    if token or worker_id:
        if not worker_id.strip() or len(token) < 24:
            raise WorkforceAuthError(503, "Single-worker auth requires JARVIS_WORKER_ID and a token of at least 24 characters.")
        return {worker_id.strip(): token}
    return {}


def _worker_capabilities(worker_id: str) -> list[str]:
    raw = os.getenv("JARVIS_WORKER_CAPABILITIES", "").strip()
    if not raw:
        return []
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkforceAuthError(503, "JARVIS_WORKER_CAPABILITIES must be valid JSON.") from exc
    if not isinstance(mapping, dict):
        raise WorkforceAuthError(503, "JARVIS_WORKER_CAPABILITIES must map worker IDs to arrays.")
    capabilities = mapping.get(worker_id, [])
    if not isinstance(capabilities, list) or any(not isinstance(x, str) or not x.strip() for x in capabilities):
        raise WorkforceAuthError(503, "Worker capabilities must be an array of strings.")
    return sorted(set(x.strip() for x in capabilities))


def _live_provider_configuration_present() -> bool:
    """Return true if any external search/model credential or endpoint is configured."""
    return any(os.getenv(key, "").strip() for key in (
        "JARVIS_SEARCH_ENDPOINT", "JARVIS_SEARCH_API_KEY",
        "JARVIS_LLM_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_LLM_MODEL",
    ))


def authenticate_dashboard(headers) -> dict:
    """Protect state and execution APIs; public demo is an explicit local-only mode."""
    public_demo = os.getenv("JARVIS_PUBLIC_DEMO", "").strip().lower() in {"1", "true", "yes"}
    if public_demo:
        credentials_configured = any(os.getenv(key, "").strip() for key in (
            "JARVIS_ADMIN_TOKEN", "JARVIS_WORKER_TOKEN", "JARVIS_WORKER_ID",
            "JARVIS_WORKER_TOKENS", "JARVIS_WORKER_CAPABILITIES",
        ))
        if credentials_configured or _live_provider_configuration_present():
            raise WorkforceAuthError(
                503,
                "Public demo mode cannot be used with workforce credentials or live providers.",
            )
        return {"role": "demo", "worker_id": None}
    return authenticate_workforce(headers, "admin")


def authenticate_workforce(headers, required_role: str) -> dict:
    admin_token = os.getenv("JARVIS_ADMIN_TOKEN", "").strip()
    worker_tokens = _worker_tokens()
    if admin_token and len(admin_token) < 24:
        raise WorkforceAuthError(503, "JARVIS_ADMIN_TOKEN must be at least 24 characters.")
    if not admin_token and not worker_tokens:
        raise WorkforceAuthError(503, "Workforce API locked: configure admin/worker tokens.")
    scheme, _, candidate = headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not candidate:
        raise WorkforceAuthError(401, "Bearer token required.")
    actor = None
    if admin_token and hmac.compare_digest(candidate, admin_token):
        actor = {"role": "admin", "worker_id": None}
    else:
        for worker_id, token in worker_tokens.items():
            if hmac.compare_digest(candidate, token):
                actor = {"role": "worker", "worker_id": worker_id}
                break
    if actor is None:
        raise WorkforceAuthError(401, "Invalid bearer token.")
    if actor["role"] != required_role:
        raise WorkforceAuthError(403, required_role + " role required.")
    return actor


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
    def do_HEAD(self):
        # Route on the pathname only; tracking/query parameters must not cause 404s.
        self.path = urlsplit(self.path).path
        if self.path in ("/", "/index.html", "/playtest", "/trace"):
            page = "loophole.html" if self.path == "/playtest" else "trace.html" if self.path == "/trace" else "dashboard.html"
            try:
                size = (ROOT / page).stat().st_size
            except OSError:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self):
        # BaseHTTPRequestHandler includes query strings in self.path.
        self.path = urlsplit(self.path).path
        if self.path == "/api/workforce":
            try:
                authenticate_workforce(self.headers, "admin")
            except WorkforceAuthError as exc:
                self._json({"ok": False, "error": str(exc)}, exc.status)
                return
            self._json({"ok": True, **WORKFORCE.snapshot()})
            return
        if self.path == "/api/state":
            try:
                authenticate_dashboard(self.headers)
            except WorkforceAuthError as exc:
                self._json({"ok": False, "error": str(exc)}, exc.status)
                return
            with LOCK:
                self._json(dict(STATE))
            return
        if self.path == "/api/research/status":
            self._json(research_environment_status())
            return
        if self.path == "/api/executor/status":
            search_configured = bool(os.getenv("JARVIS_SEARCH_ENDPOINT", "").strip())
            llm_configured = getattr(WORKER_EXECUTOR, "client", None) is not None
            self._json({
                "mode": (
                    "simulated" if isinstance(WORKER_EXECUTOR, SimulatedWorkerExecutor)
                    else "hybrid" if isinstance(WORKER_EXECUTOR, HybridWorkerExecutor)
                    else "llm"
                ),
                "search_configured": search_configured,
                "llm_configured": llm_configured,
                "capabilities": {
                    "research": "live_search" if search_configured else "blocked_or_simulated_demo_only",
                    "analysis": "llm" if llm_configured else "blocked_or_simulated_demo_only",
                    "design": "llm" if llm_configured else "blocked_or_simulated_demo_only",
                    "implementation": "no_code_execution_adapter_configured",
                    "testing": "no_test_runner_adapter_configured",
                },
                "truth_policy": {
                    "llm_output_is_verified": False,
                    "search_snippet_is_verified_truth": False,
                    "missing_required_tool_fails_closed": True,
                },
            })
            return
        if self.path == "/api/llm/status":
            configured = isinstance(WORKER_EXECUTOR, (LLMWorkerExecutor, HybridWorkerExecutor))
            self._json({
                "configured": configured,
                "mode": ("hybrid" if isinstance(WORKER_EXECUTOR, HybridWorkerExecutor) else "llm") if configured else "simulated",
                "model": getattr(getattr(WORKER_EXECUTOR, "client", None), "model", None),
                "message": "Live worker routing configured; LLM outputs and search snippets are not independently verified facts."
                    if configured else
                    "LLM not configured; autonomous tasks use simulated execution.",
            })
            return
        if self.path in ("/", "/index.html", "/playtest", "/trace"):
            page = "loophole.html" if self.path == "/playtest" else "trace.html" if self.path == "/trace" else "dashboard.html"
            data = (ROOT / page).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self):
        # Query parameters must not prevent API route matching.
        self.path = urlsplit(self.path).path
        if self.path in ("/api/workforce/tasks", "/api/workforce/claim", "/api/workforce/report", "/api/workforce/feedback", "/api/workforce/approve", "/api/workforce/cancel", "/api/workforce/merge", "/api/workforce/retry", "/api/workforce/verify", "/api/workforce/maintain", "/api/workers/heartbeat"):
            role = "worker" if self.path in ("/api/workforce/claim", "/api/workforce/report", "/api/workers/heartbeat") else "admin"
            try:
                actor = authenticate_workforce(self.headers, role)
            except WorkforceAuthError as exc:
                self._json({"ok": False, "error": str(exc)}, exc.status)
                return
            body = self._read_json(max_bytes=131072)
            if body is None:
                return
            try:
                if self.path == "/api/workforce/maintain":
                    self._json({"ok": True, "maintenance": WORKFORCE.maintain()})
                elif self.path == "/api/workers/heartbeat":
                    worker_id = actor["worker_id"]
                    if body.get("worker_id") not in (None, worker_id):
                        self._json({"ok": False, "error": "Worker identity is derived from its token."}, 403)
                        return
                    status = body.get("status", "idle")
                    task_id = body.get("current_task_id")
                    if task_id is not None and not isinstance(task_id, str):
                        raise ValueError("current_task_id must be a string or null")
                    if status == "working":
                        if not isinstance(task_id, str) or not task_id:
                            raise ValueError("working heartbeat requires current_task_id")
                        WORKFORCE.renew_lease(task_id, worker_id, body.get("lease_token"))
                    lease_token = body.get("lease_token")
                    if lease_token is not None and not isinstance(lease_token, str):
                        raise ValueError("lease_token must be a string")
                    worker = WORKFORCE.heartbeat_worker(
                        worker_id, str(status), task_id,
                        str(body.get("progress", "")), str(body.get("last_error", "")),
                    )
                    worker["capabilities"] = _worker_capabilities(worker_id)
                    # The registry lock must cover the final capability update and
                    # persistence. Parallel heartbeat handlers otherwise race on
                    # the shared .tmp file used by WorkforceRegistry.save().
                    with WORKFORCE.lock:
                        WORKFORCE.workers[worker_id]["capabilities"] = worker["capabilities"]
                        WORKFORCE.save()
                    self._json({"ok": True, "worker": worker})
                elif self.path == "/api/workforce/tasks":
                    task = WORKFORCE.create_task(
                        title=str(body.get("title", "")),
                        description=str(body.get("description", "")),
                        capability=str(body.get("capability", "general")),
                        priority=body.get("priority", 3),
                        assigned_to=body.get("assigned_to"),
                        approval_required=bool(body.get("approval_required", False)),
                        success_criteria=body.get("success_criteria", {}),
                        evidence_required=bool(body.get("evidence_required", False)),
                    )
                    self._json({"ok": True, "task": task}, 201)
                elif self.path == "/api/workforce/claim":
                    worker_id = actor["worker_id"]
                    if body.get("worker_id") not in (None, worker_id):
                        self._json({"ok": False, "error": "Worker identity is derived from its token."}, 403)
                        return
                    allowed = _worker_capabilities(worker_id)
                    requested = body.get("capabilities", allowed)
                    if not isinstance(requested, list) or any(not isinstance(x, str) for x in requested):
                        raise ValueError("capabilities must be an array of strings")
                    capabilities = [x for x in requested if x in allowed]
                    task_id = body.get("task_id")
                    if task_id is not None and not isinstance(task_id, str):
                        raise ValueError("task_id must be a string")
                    task = WORKFORCE.claim(worker_id, capabilities, task_id=task_id)
                    self._json({"ok": True, "task": task, "message": "No eligible task" if task is None else "Task assigned"})
                elif self.path == "/api/workforce/report":
                    for key in ("task_id", "status"):
                        if not isinstance(body.get(key), str):
                            raise ValueError(key + " must be a string")
                    worker_id = actor["worker_id"]
                    if body.get("worker_id") not in (None, worker_id):
                        self._json({"ok": False, "error": "Worker identity is derived from its token."}, 403)
                        return
                    task = WORKFORCE.report(body["task_id"], worker_id, body["status"],
                                            str(body.get("output", "")), str(body.get("blocker", "")),
                                            body.get("lease_token"))
                    self._json({"ok": True, "task": task})
                elif self.path == "/api/workforce/verify":
                    task_id, verification = body.get("task_id"), body.get("verification")
                    if not isinstance(task_id, str) or not isinstance(verification, dict):
                        raise ValueError("task_id and verification object are required")
                    self._json({"ok": True, "task": WORKFORCE.record_verification(task_id, verification)})
                elif self.path == "/api/workforce/retry":
                    task_id, reason = body.get("task_id"), body.get("reason")
                    if not isinstance(task_id, str) or not isinstance(reason, str):
                        raise ValueError("task_id and reason are required")
                    self._json({"ok": True, "task": WORKFORCE.retry_task(task_id, reason)})
                elif self.path == "/api/workforce/cancel":
                    task_id, reason = body.get("task_id"), body.get("reason")
                    if not isinstance(task_id, str) or not isinstance(reason, str):
                        raise ValueError("task_id and reason must be strings")
                    self._json({"ok": True, "task": WORKFORCE.cancel_task(task_id, reason)})
                elif self.path == "/api/workforce/merge":
                    target_id, source_ids, reason = body.get("target_task_id"), body.get("source_task_ids"), body.get("reason")
                    if not isinstance(target_id, str) or not isinstance(source_ids, list) or not isinstance(reason, str):
                        raise ValueError("target_task_id, source_task_ids and reason are required")
                    self._json({"ok": True, **WORKFORCE.merge_tasks(target_id, source_ids, reason)})
                elif self.path == "/api/workforce/feedback":
                    for key in ("task_id", "actor", "message"):
                        if not isinstance(body.get(key), str):
                            raise ValueError(key + " must be a string")
                    item = WORKFORCE.feedback(body["task_id"], "digital-twin", body["message"],
                                              str(body.get("kind", "note")))
                    self._json({"ok": True, "feedback": item})
                else:
                    task_id = body.get("task_id")
                    if not isinstance(task_id, str):
                        raise ValueError("task_id must be a string")
                    self._json({"ok": True, "task": WORKFORCE.approve_task(task_id)})
            except (ValueError, TypeError) as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            except OSError:
                self._json({"ok": False, "error": "Unable to persist workforce state."}, 500)
            return
        protected_dashboard_routes = {
            "/api/run", "/api/prototype", "/api/autonomous", "/api/research",
            "/api/experience-design", "/api/game-action", "/api/model-handoff",
        }
        if self.path in protected_dashboard_routes:
            try:
                authenticate_dashboard(self.headers)
            except WorkforceAuthError as exc:
                self._json({"ok": False, "error": str(exc)}, exc.status)
                return
        if self.path not in ("/api/run", "/api/prototype", "/api/autonomous", "/api/research", "/api/experience-design", "/api/game-action", "/api/model-handoff"):
            self.send_error(404)
            return
        if self.path == "/api/model-handoff":
            body = self._read_json(max_bytes=131072)
            if body is None:
                return
            action = body.get("action")
            state = body.get("state", {})
            model_reply = body.get("model_reply")
            try:
                result = interpret_handoff_and_validate_action(action, state, model_reply)
            except ValueError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
                return
            self._json(result)
            return
        if self.path == "/api/game-action":
            body = self._read_json(max_bytes=65536)
            if body is None:
                return
            action = body.get("action")
            state = body.get("state", {})
            llm_client = getattr(WORKER_EXECUTOR, "client", None) if isinstance(WORKER_EXECUTOR, (LLMWorkerExecutor, HybridWorkerExecutor)) else None
            try:
                result = interpret_and_validate_action(action, state, llm_client)
            except (ValueError, RuntimeError, OSError) as exc:
                self._json({"ok": False, "error": "Action interpretation failed closed: " + type(exc).__name__}, 502)
                return
            self._json(result)
            return
        if self.path == "/api/experience-design":
            body = self._read_json(max_bytes=65536)
            if body is None:
                return
            source_game = body.get("source_game", "塞尔达传说：王国之泪")
            concept_name = body.get("concept_name", "潮痕档案馆")
            if not isinstance(source_game, str) or not isinstance(concept_name, str):
                self._json({"ok": False, "error": "source_game and concept_name must be strings."}, 400)
                return
            if len(source_game) > 160 or len(concept_name) > 160:
                self._json({"ok": False, "error": "source_game and concept_name must be at most 160 characters."}, 400)
                return
            llm_client = getattr(WORKER_EXECUTOR, "client", None) if isinstance(WORKER_EXECUTOR, (LLMWorkerExecutor, HybridWorkerExecutor)) else None
            try:
                brief = create_design_brief(source_game, concept_name, llm_client)
            except (ValueError, RuntimeError, OSError) as exc:
                self._json({"ok": False, "error": "Design brief generation failed: " + type(exc).__name__}, 502)
                return
            self._json({
                "ok": True,
                "brief": brief,
                "trust": {
                    "generation_mode": brief.get("generation", {}).get("mode", "unknown"),
                    "model_output_is_verified_research": False,
                    "player_perspectives_are_hypotheses": True,
                    "market_validated": False,
                    "playtested": False,
                },
            })
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
            try:
                request = validate_autonomous_request(body)
            except ValueError as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
                return
            goal = request["goal"]
            planner_client = getattr(WORKER_EXECUTOR, "client", None) if isinstance(WORKER_EXECUTOR, (LLMWorkerExecutor, HybridWorkerExecutor)) else None
            planning = request["planning"]
            if request["tasks"] is not None:
                tasks = request["tasks"]
            else:
                planning = plan_project(goal, planner_client)
                tasks = planning["tasks"]
            options = request["options"]
            actions = request["requested_actions"]
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

def supervise_workforce():
    """Continuously recover expired worker leases and persist supervisor events."""
    while True:
        try:
            WORKFORCE.maintain()
        except Exception as exc:
            # Supervisor failures must be visible in logs, not silently kill the loop.
            print("JARVIS workforce supervisor error:", type(exc).__name__, flush=True)
        time.sleep(5)


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    threading.Thread(target=supervise_workforce, name="jarvis-workforce-supervisor", daemon=True).start()
    print(f"JARVIS Dashboard listening on {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
