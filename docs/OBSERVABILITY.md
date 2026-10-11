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
- `employees`: worker identities seen in assignments and whether each currently has an assigned task.
- `tasks[].input.description`: task input sent by the coordinator.
- `tasks[].output`: output returned by the executor, with simulated envelope unwrapped for readability.
- `tasks[].provenance`: `simulated`, `executor_reported_live`, or `unknown`.
- `tasks[].history`, `feedback`, and `recent_events`: lifecycle and communication trace.
- `alerts`: expired leases, stale tasks (15 minutes without update), blocked tasks, and failed tasks.

## Important limitations

1. A worker is listed only after its identity appears in task assignments. An idle process that has never claimed work cannot be distinguished from an offline worker without a separate worker heartbeat/registration endpoint.
2. `executor_reported_live` means the executor reported a non-simulated result; it is **not** proof that the content is correct or independently verified.
3. The monitor displays task descriptions and outputs. Treat these as potentially sensitive business data; protect the admin token, avoid public exposure, and do not ship raw outputs to third-party log collectors without a data policy.
4. The current persistence backend is a local JSON store. For multiple server instances or production use, migrate to a transactional database and add explicit worker heartbeat, redaction, retention, and access audit controls.
