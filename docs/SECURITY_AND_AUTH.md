# Security and Authentication

## MVP authentication model

The API uses bearer tokens configured as server-side environment secrets.

- `JARVIS_ADMIN_TOKEN`: trusted administrator credential. Can create tasks, inspect all tasks, retry eligible tasks, and approve/reject approval-gated results.
- `JARVIS_WORKER_TOKEN`: worker credential. Can inspect queued/assigned work, accept work only as `JARVIS_WORKER_ID`, and report events only for tasks assigned to that identity.
- `JARVIS_WORKER_ID`: identity represented by the configured worker token (defaults to `worker-1`).

Every route except `GET /health` requires `Authorization: Bearer <token>`. Task APIs fail closed if tokens are not configured. Use distinct, high-entropy secrets and store them in the hosting provider's secret manager; never commit real credentials to Git. Use HTTPS for all remote requests.

## Generate local secrets

Generate two independent values locally; do not share or commit the output:

```bash
node -e "console.log(require('node:crypto').randomBytes(32).toString('base64url'))"
node -e "console.log(require('node:crypto').randomBytes(32).toString('base64url'))"
```

Set them as `JARVIS_ADMIN_TOKEN` and `JARVIS_WORKER_TOKEN` in your local shell or deployment secret manager. Never paste real secrets into issues, chat, source files, or logs.

## Limitations before public deployment

This is a minimum API credential layer, not a full identity platform. It does not yet provide individual user accounts, SSO, short-lived tokens, token rotation, rate limiting, or per-worker credentials. The worker token represents one configured worker identity, so do not distribute it to multiple independent workers. Persistent JSON storage is suitable only for the single-instance MVP, not concurrent production workloads.

Before opening the service to the public internet, add robust rate limits, stronger per-worker credentials, secret rotation, request-size and input validation review, deployment TLS verification, production database storage, and end-to-end security testing.
