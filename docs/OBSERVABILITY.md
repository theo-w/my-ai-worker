# Digital Twin / Employee Observability

The read-only monitor reports the live workforce queue and event history through
the authenticated administrator endpoint. It does not mutate tasks and never
prints bearer tokens.

## Run one snapshot

Set these environment variables in the same shell as the monitor process:

- `JARVIS_WORKFORCE_URL`: base URL of the running JARVIS server, for example `http://127.0.0.1:8765`
- `JARVIS_ADMIN_TOKEN`: administrator token configured on the server

Then run:

```bash
python -m mvp.monitor --once
```

## Poll continuously

```bash
python -m mvp.monitor --interval 5
```

The monitor emits one JSON object per poll, suitable for a terminal, log collector,
or later dashboard adapter. Stop it with Ctrl-C.

## Run the continuous supervisor as a process

With the JARVIS API already running and the same environment variables set:

```bash
python -m mvp.supervisor --interval-seconds 10
```

For a finite smoke test, add `--max-iterations 3`. Each cycle emits a JSON record;
Ctrl-C stops the process. The supervisor reclaims expired task leases and reports
worker/task health. It does **not** autonomously invent cancellation or merge
decisions unless an explicit `recovery_policy` is supplied by code.

## Fields

- `twin`: derived workflow status and counts by task status.
- `employees` / `workers`: worker identities from heartbeat registration as well as assignments, runtime status, progress, current task, last heartbeat age, and online/suspected-offline/heartbeat-missing state.
- `tasks[].input.description`: task input sent by the coordinator.
- `tasks[].output`: output returned by the executor, with simulated envelope unwrapped for readability.
- `tasks[].provenance`: `simulated`, `executor_reported_live`, or `unknown`.
- `tasks[].history`, `feedback`, and `recent_events`: lifecycle and communication trace.
- `alerts`: expired leases, stale tasks (15 minutes without update), blocked/failed tasks, missing heartbeats, and workers whose heartbeat is older than the default 30-second threshold.

## Lease renewal and late results

While an employee is executing a task, its authenticated `working` heartbeat must
include both the task ID and the lease token returned by claim. The server renews
only the matching, unexpired lease. Missing or stale tokens are rejected, and a
heartbeat cannot revive an expired lease. Task reports also run expiry maintenance
before accepting output, so a late result cannot win a race just because the
periodic supervisor has not run yet.

## Important limitations

1. Heartbeat state is a liveness signal, not proof of process death. The monitor labels stale workers as suspected offline; network delays and host pauses can cause false positives. The heartbeat endpoint registers a worker only after its first authenticated beat.
2. `executor_reported_live` means the executor reported a non-simulated result; it is **not** proof that the content is correct or independently verified.
3. The monitor displays task descriptions and outputs. Treat these as potentially sensitive business data; protect the admin token, avoid public exposure, and do not ship raw outputs to third-party log collectors without a data policy.
4. The current persistence backend is a local JSON store. For multiple server instances or production use, migrate to a transactional database and add redaction, retention, and access audit controls.

## Twin supervision loop

The monitor remains read-only. The coordinator exposes `supervise_once()`, which
collects a snapshot, runs bounded expired-lease maintenance, and optionally asks
a supplied recovery policy to propose validated cancellation or merge actions.

For a controlled repeated loop, call the supervisor from your own runtime:

```python
from mvp.supervisor import run_supervision_loop
from mvp.twin import DigitalTwinCoordinator

twin = DigitalTwinCoordinator(
    base_url="http://127.0.0.1:8765",
    admin_token="YOUR_ADMIN_TOKEN",
)
result = run_supervision_loop(
    twin,
    interval_seconds=10,
    max_iterations=6,
)
```

A standalone command-line supervisor is also available. Start the API server
first, then configure the same administrator credentials in the supervisor shell:

```bash
export JARVIS_WORKFORCE_URL="http://127.0.0.1:8765"
export JARVIS_ADMIN_TOKEN="YOUR_ADMIN_TOKEN"
python -m mvp.supervisor --interval-seconds 10 --max-iterations 6
```

Omit `--max-iterations` to keep supervising until Ctrl-C. Each cycle emits a
JSON record, including failures; this is a runtime utility, not a deployed
background service. Use a process manager and protected secret injection for
unattended operation.

Workers send authenticated heartbeats while executing. A `working` heartbeat
must include the current task ID and its current lease token; the server renews
that task's lease only if the worker identity and fencing token still match.
This prevents a legitimate long-running executor from being reclaimed simply
because its original lease duration elapsed.

You can also run it as a process after the workforce HTTP server is running:

```bash
export JARVIS_WORKFORCE_URL="http://127.0.0.1:8765"
export JARVIS_ADMIN_TOKEN="YOUR_ADMIN_TOKEN"
python -m mvp.supervisor --interval-seconds 10 --max-iterations 6
```

Omit `--max-iterations` to keep supervising until interrupted with Ctrl+C.
Each cycle is printed as one JSON line. The command only reclaims expired
leases and reports observable state unless an explicit recovery policy is wired
in; it does not autonomously invent task cancellations or merges.

`run_supervision_loop` is not started automatically on import. It supports a
stop event, a bounded iteration count, per-cycle result records, and recovery from
individual cycle errors. It does not invent an AI recovery policy: pass
`recovery_policy(report)` only when an explicit policy implementation is available.
Use a process manager for deployment, and configure secure secret injection,
logs, restart policy, and an external health check before running it unattended.

## Interactive workflow trace and acceptance view

When the JARVIS HTTP server is running, open `/trace` in the same browser session
(e.g. `http://127.0.0.1:8765/trace`). The main dashboard also links to this page.
Enter the configured administrator token in the page to read `/api/workforce`.
The token is held only in page memory, is not written to localStorage or the URL,
and is cleared when the page is closed.

When the goal loop applies an evidence gate or configured independent review, it also attempts to persist that verification record to the task history and global event stream. The record explicitly keeps `verified_truth=false`; accepted structural checks must not be confused with proof of factual truth. If persistence fails, the goal result includes a `verification_persistence_failed` event rather than silently claiming the audit was saved.

The view refreshes every five seconds by default and supports manual refresh and
task-state filters. A separate employee panel shows worker-reported status, last heartbeat,
current task, capabilities, progress, and last error; missing heartbeat is not treated as
proof that a worker is alive. Select a task to inspect its goal/input, assignment, output,
blocker/feedback fields, attempt count, task history, and the recent global event
timeline. The endpoint remains admin-authenticated; the trace page itself does not
embed credentials and does not mutate task state.

Use this view to verify real execution at milestones:
- a worker claims a task and receives a lease;
- the worker reports progress or a blocker;
- the twin recommends a replan or explicitly approves a retry;
- the task finishes and any evidence/verification result is reviewed.

A task status of `completed` is not by itself proof that its claims are true.
Review source evidence and verification state separately. The trace view shows
what the runtime has recorded; it does not claim that an unrecorded model action
occurred.

## Acceptance walkthrough: blocked → retry → completion → verification

A repeatable HTTP integration test now exercises the full observable lifecycle:
`test_acceptance_scenario_blocker_retry_completion_and_verification` in
`mvp/test_workforce_api_integration.py`. It creates a research task, lets an
authenticated employee claim it, records a temporary blocker, requires an
administrator-authorized retry, claims the task with a new lease token, records
a completion result, and then records an explicit structural verification.

When running the service locally, open `/trace`, enter the configured admin
token, and select the test-created task. Inspect:
1. the original blocker and its timestamp;
2. the twin/admin retry reason and attempt count;
3. the second claim and updated lease;
4. the final employee output;
5. the verification record and the separate `verified_truth: false` flag;
6. the global event timeline.

This scenario verifies the recorded workflow and API boundaries. It does not
assert that the sample research claim is factually true, and it does not replace
a live-model end-to-end acceptance run.
