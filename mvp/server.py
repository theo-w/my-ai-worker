#!/usr/bin/env python3
"""Dependency-free local JARVIS Digital Workforce dashboard server."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from run import WORKERS, evaluate, run_worker
from twin import DigitalTwin, AutonomousProjectLoop, PersistentTwinMemory

ROOT = Path(__file__).parent
LOCK = threading.Lock()
TWIN = DigitalTwin()
MEMORY = PersistentTwinMemory()
PROJECT_LOOP = AutonomousProjectLoop()
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
    reset(goal)
    time.sleep(.25)
    with LOCK:
        STATE["phase"] = "team"
        for a in STATE["agents"]:
            a["status"] = "ready"
    for idx, (worker, capability) in enumerate(
        (tuple((a["worker"], a["capability"]) for a in STATE["agents"]))
    ):
        with LOCK:
            a = STATE["agents"][idx]
            a["status"] = "running"
            a["progress"] = 20
        time.sleep(.35)
        items = run_worker(worker, capability, goal)
        with LOCK:
            a["progress"] = 70
            a["output"] = "完成任务并生成候选证据。"
            a["evidence"] = [e.__dict__ for e in items]
            a["status"] = "completed"
            a["progress"] = 100
            STATE["evidence"].extend(e.__dict__ for e in items)
        time.sleep(.2)
    with LOCK:
        STATE["phase"] = "evaluation"
    time.sleep(.3)
    decision = evaluate(goal, [type("E", (), e) for e in STATE["evidence"]])
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

    def do_GET(self):
        if self.path == "/api/state":
            with LOCK:
                self._json(dict(STATE))
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
        if self.path not in ("/api/run", "/api/prototype", "/api/autonomous"):
            self.send_error(404)
            return
        if self.path == "/api/autonomous":
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            goal = str(body.get("goal", "")).strip()
            if not goal:
                self._json({"ok": False, "error": "A project goal is required."}, 400)
                return
            tasks = body.get("tasks") or [
                {"id": "research", "title": "Gather and validate evidence", "status": "queued"},
                {"id": "analysis", "title": "Compare options and risks", "status": "queued"},
                {"id": "checkpoint", "title": "Prepare a decision report", "status": "queued"},
            ]
            options = body.get("options") or []
            actions = body.get("requested_actions") or []
            # The executor contract is intentionally explicit: this MVP does not
            # pretend to perform external research or tool calls.
            def executor(task):
                return "Simulated execution only; connect a real worker/tool adapter to perform this task."
            report = PROJECT_LOOP.run(goal, tasks, executor, options, actions)
            if report["status"] == "completed" and report.get("recommendation"):
                MEMORY.record_decision(goal, report["recommendation"], report.get("options", []))
            self._json({"ok": True, "report": report, "memory": {
                "decision_count": len(MEMORY.decisions),
                "lesson_count": len(MEMORY.lessons),
                "preference_count": len(MEMORY.preferences),
            }})
            return
        if self.path == "/api/prototype":
            with LOCK:
                if not STATE["decision"] or STATE["decision"]["recommendation"] != "GO_TO_PROTOTYPE":
                    self._json({"ok": False, "error": "Prototype requires a GO_TO_PROTOTYPE decision."}, 409)
                    return
                STATE["prototype"] = {
                    "status": "planned",
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
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        goal = str(body.get("goal", "")).strip() or "评估一个 AI 原生游戏机会"
        with LOCK:
            if STATE["phase"] in {"planning", "team", "evaluation"}:
                self._json({"ok": False, "error": "A run is already in progress."}, 409)
                return
        threading.Thread(target=execute, args=(goal,), daemon=True).start()
        self._json({"ok": True})

if __name__ == "__main__":
    print("JARVIS Dashboard: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
