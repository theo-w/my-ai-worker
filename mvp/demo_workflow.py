"""Run a clearly labeled, authenticated end-to-end workforce trace demo.

Start the server first, configure JARVIS_ADMIN_TOKEN and JARVIS_WORKER_TOKENS,
then run this script with the same credentials in the environment. The demo
output is synthetic and is explicitly labeled as simulated; it is not evidence
of real research or factual correctness.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_json(base: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        base.rstrip("/") + path,
        data=data,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {detail}") from exc
    if not result.get("ok", False):
        raise RuntimeError(f"{path} failed: {result}")
    return result


def main() -> int:
    base = os.getenv("JARVIS_BASE_URL", "http://127.0.0.1:8765")
    admin = os.getenv("JARVIS_ADMIN_TOKEN", "").strip()
    worker_id = os.getenv("JARVIS_DEMO_WORKER_ID", "").strip()
    capability = os.getenv("JARVIS_DEMO_CAPABILITY", "research").strip()
    tokens_raw = os.getenv("JARVIS_WORKER_TOKENS", "").strip()

    if not admin:
        print("Missing JARVIS_ADMIN_TOKEN.", file=sys.stderr)
        return 2
    try:
        worker_tokens = json.loads(tokens_raw) if tokens_raw else {}
    except json.JSONDecodeError:
        print("JARVIS_WORKER_TOKENS must be a JSON object.", file=sys.stderr)
        return 2
    if not isinstance(worker_tokens, dict) or not worker_tokens:
        print("Set JARVIS_WORKER_TOKENS to a JSON object of worker_id: token.", file=sys.stderr)
        return 2
    if not worker_id:
        worker_id = next(iter(worker_tokens))
    worker_token = worker_tokens.get(worker_id)
    if not isinstance(worker_token, str) or not worker_token:
        print(f"No worker token configured for {worker_id!r}.", file=sys.stderr)
        return 2

    print("JARVIS workflow trace demo — synthetic worker output; not real research.")
    created = request_json(base, "/api/workforce/tasks", admin, {
        "title": "演示：评估一个 AI 原生游戏想法",
        "description": (
            "演示完整任务流程：员工领取任务、提交带模拟标签的输出，"
            "然后管理员记录结构化检查结果。不要将演示内容当成市场事实。"
        ),
        "capability": capability,
        "priority": 3,
        "success_criteria": {
            "required_sections": ["假设", "待验证证据", "下一步"],
            "demo_only": True,
        },
        "evidence_required": True,
    })
    task = created["task"]
    task_id = task["id"]
    print(f"1. Twin created task: {task_id} ({task['status']})")

    claimed_result = request_json(
        base, "/api/workforce/claim", worker_token, {"capabilities": [capability], "task_id": task_id}
    )
    claimed = claimed_result.get("task")
    if not claimed or claimed.get("id") != task_id:
        request_json(base, "/api/workforce/cancel", admin, {
            "task_id": task_id,
            "reason": "Demo could not claim the newly created task; avoid leaving orphaned demo work.",
        })
        raise RuntimeError(
            "Configured worker could not claim the demo task. Check JARVIS_WORKER_CAPABILITIES "
            "and JARVIS_DEMO_CAPABILITY; task was canceled."
        )
    lease_token = claimed.get("lease_token")
    if not lease_token:
        raise RuntimeError("Worker claim did not return a lease token.")
    print(f"2. Worker {worker_id!r} claimed task (attempt {claimed.get('attempts')}).")

    output = (
        "[SIMULATED DEMO OUTPUT — NOT REAL RESEARCH]\n"
        "假设：目标玩家可能对可组合规则的解谜玩法感兴趣。\n"
        "待验证证据：需要真实玩家访谈、竞品数据和原型测试；当前没有外部证据。\n"
        "下一步：列出 3 个可证伪假设并设计小规模验证。"
    )
    request_json(base, "/api/workforce/report", worker_token, {
        "task_id": task_id,
        "status": "completed",
        "output": output,
        "blocker": "",
        "lease_token": lease_token,
    })
    print("3. Worker submitted a result with an explicit SIMULATED label; task now awaits validation.")

    verification = {
        "accepted": True,
        "checker": "demo_structural_check",
        "checks": [
            {"name": "simulation_label_present", "passed": "[SIMULATED DEMO OUTPUT" in output},
            {"name": "limitations_disclosed", "passed": "没有外部证据" in output},
            {"name": "next_step_present", "passed": "下一步：" in output},
        ],
        "evidence": [],
        "notes": "Demo only: structural checks passed; no factual claim has been independently verified.",
        "verified_truth": False,
    }
    verification["accepted"] = all(item["passed"] for item in verification["checks"])
    request_json(base, "/api/workforce/verify", admin, {
        "task_id": task_id,
        "verification": verification,
    })
    print("4. Admin recorded structural verification; verified_truth remains false.")
    snapshot = request_json(base, "/api/workforce", admin)
    final = next((item for item in snapshot.get("tasks", []) if item.get("id") == task_id), None)
    if final is None:
        raise RuntimeError("Task missing from authenticated workforce snapshot.")
    print(f"5. Final task status: {final.get('status')}; verification: {final.get('verification')}")
    print(f"Open the trace view: {base.rstrip('/')}/trace")
    print("Select task ID " + task_id + " to inspect the input, output, history, and verification record.")
    print("Reminder: this demo proves the API workflow only, not real LLM execution or factual accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
