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
