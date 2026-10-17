"""Authenticated polling runtime for an independently running digital employee.

The agent only claims capabilities authorized by the server token. It invokes an
injected executor, records provenance, and reports success or a blocker. A demo
executor is not silently substituted for missing live integrations.
"""
from __future__ import annotations

import json
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WorkforceAPIError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class DigitalEmployeeAgent:
    def __init__(self, base_url: str, token: str, capabilities: list[str],
                 executor, goal: str, timeout: float = 10.0,
                 heartbeat_interval: float = 10.0):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be an HTTP(S) URL")
        if not isinstance(token, str) or len(token) < 24:
            raise ValueError("worker token must be at least 24 characters")
        if not capabilities or any(not isinstance(x, str) or not x.strip() for x in capabilities):
            raise ValueError("at least one non-empty capability is required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.capabilities = sorted(set(x.strip() for x in capabilities))
        self.executor = executor
        self.goal = goal
        self.timeout = max(1.0, float(timeout))
        self.heartbeat_interval = max(0.1, float(heartbeat_interval))
        self.last_heartbeat_error = None

    def _request(self, path: str, payload: dict) -> dict:
        request = Request(
            self.base_url + path,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("error", "API request failed")
            except (ValueError, AttributeError):
                message = "API request failed"
            raise WorkforceAPIError(exc.code, str(message)) from exc
        except (URLError, TimeoutError) as exc:
            raise WorkforceAPIError(503, "Workforce API unavailable: " + str(exc)) from exc
        with response:
            try:
                result = json.loads(response.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise WorkforceAPIError(502, "Workforce API returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise WorkforceAPIError(response.status, str(result.get("error", "API request failed")))
        return result

    def _heartbeat(self, status: str, task_id: str | None = None,
                   progress: str = "", last_error: str = "",
                   lease_token: str | None = None) -> bool:
        try:
            self._request("/api/workers/heartbeat", {
                "status": status, "current_task_id": task_id,
                "lease_token": lease_token,
                "progress": progress[:500], "last_error": last_error[:1000],
            })
            self.last_heartbeat_error = None
            return True
        except Exception as exc:
            # Heartbeats are observability signals; their failure must not turn
            # a valid task result into a false task failure.
            self.last_heartbeat_error = type(exc).__name__
            return False

    def run_once(self) -> dict:
        """Claim and execute at most one task; returns idle/completed/blocked."""
        claimed = self._request(
            "/api/workforce/claim", {"capabilities": self.capabilities}
        ).get("task")
        if claimed is None:
            self._heartbeat("idle", progress="Polling for eligible work")
            return {"status": "idle", "task_id": None}
        task_id = claimed.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise WorkforceAPIError(502, "Claim response did not include a task ID.")
        stop_heartbeat = threading.Event()
        lease_token = claimed.get("lease_token")
        self._heartbeat("working", task_id, "Task claimed; preparing execution",
                        lease_token=lease_token)

        def heartbeat_loop():
            while not stop_heartbeat.wait(self.heartbeat_interval):
                self._heartbeat("working", task_id, "Executor is running",
                                lease_token=lease_token)

        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        try:
            result = self.executor.execute(claimed, self.goal)
            # Stop lease-renewal requests before submitting the terminal report.
            # Otherwise an in-flight heartbeat can race with completion and try
            # to renew a lease that has already been closed by the report.
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=min(1.0, self.heartbeat_interval))
            output = getattr(result, "output", None)
            metadata = getattr(result, "metadata", {})
            simulated = getattr(result, "simulated", False)
            if isinstance(result, dict):
                output = result.get("output", output)
                metadata = result.get("metadata", metadata)
                simulated = result.get("simulated", simulated)
            if not isinstance(output, str) or not output.strip():
                raise ValueError("Executor returned no usable output.")
            envelope = {
                "content": output,
                "simulated": bool(simulated),
                "metadata": metadata if isinstance(metadata, dict) else {},
            }
            report = self._request("/api/workforce/report", {
                "task_id": task_id, "status": "completed",
                "lease_token": claimed.get("lease_token"),
                "output": json.dumps(envelope, ensure_ascii=False),
            })
            return {"status": "completed", "task_id": task_id,
                    "task": report.get("task"), "simulated": bool(simulated)}
        except Exception as exc:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=min(1.0, self.heartbeat_interval))
            reason = type(exc).__name__ + ": " + str(exc)
            try:
                report = self._request("/api/workforce/report", {
                    "task_id": task_id, "status": "blocked",
                    "lease_token": claimed.get("lease_token"),
                    "output": "", "blocker": reason[:2900],
                })
            except Exception as report_exc:
                return {"status": "report_failed", "task_id": task_id,
                        "error": reason,
                        "report_error": type(report_exc).__name__ + ": " + str(report_exc)}
            self._heartbeat("blocked", task_id, "Task blocked", reason)
            return {"status": "blocked", "task_id": task_id,
                    "task": report.get("task"), "error": reason}
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=min(1.0, self.heartbeat_interval))
            if "report" in locals() and report.get("task", {}).get("status") in ("completed", "awaiting_validation"):
                self._heartbeat("idle", progress="Task completed")


def build_executor_from_environment():
    """Construct only explicitly configured executors; no silent live-mode fallback."""
    try:
        from .executor import HybridWorkerExecutor, LLMWorkerExecutor, SimulatedWorkerExecutor
        from .llm import OpenAICompatibleLLM
    except ImportError:
        from executor import HybridWorkerExecutor, LLMWorkerExecutor, SimulatedWorkerExecutor
        from llm import OpenAICompatibleLLM

    mode = os.getenv("JARVIS_WORKER_EXECUTOR_MODE", "hybrid").strip().lower()
    if mode == "simulated":
        return SimulatedWorkerExecutor()
    if mode == "llm":
        return LLMWorkerExecutor(OpenAICompatibleLLM.from_environment())
    if mode == "hybrid":
        try:
            llm = LLMWorkerExecutor(OpenAICompatibleLLM.from_environment())
        except Exception:
            llm = None
        return HybridWorkerExecutor(llm_executor=llm)
    raise ValueError("JARVIS_WORKER_EXECUTOR_MODE must be simulated, llm, or hybrid")


def main():
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Run an authenticated JARVIS digital employee.")
    parser.add_argument("--once", action="store_true", help="claim and process at most one task")
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    args = parser.parse_args()

    base_url = os.getenv("JARVIS_WORKFORCE_URL", "").strip()
    token = os.getenv("JARVIS_WORKER_TOKEN", "").strip()
    worker_id = os.getenv("JARVIS_WORKER_ID", "").strip()
    capabilities = [x.strip() for x in os.getenv("JARVIS_WORKER_CAPABILITIES_LIST", "").split(",") if x.strip()]
    goal = os.getenv("JARVIS_WORKER_GOAL", "Complete the assigned task with traceable evidence.")
    if not base_url or not token or not capabilities:
        parser.error("Set JARVIS_WORKFORCE_URL, JARVIS_WORKER_TOKEN, and JARVIS_WORKER_CAPABILITIES_LIST.")
    executor = build_executor_from_environment()
    agent = DigitalEmployeeAgent(base_url, token, capabilities, executor, goal)
    if worker_id:
        print(json.dumps({"configured_worker_id": worker_id, "identity_source": "server token"},
                         ensure_ascii=False))
    while True:
        result = agent.run_once()
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        if args.once or result["status"] in ("report_failed",):
            break
        time.sleep(max(0.5, args.poll_seconds))


if __name__ == "__main__":
    main()
