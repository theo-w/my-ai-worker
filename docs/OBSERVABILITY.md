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
