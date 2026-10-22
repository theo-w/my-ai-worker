# Supabase knowledge storage setup

The JARVIS knowledge base can use Supabase REST/PostgREST for durable storage.
The local JSON file remains a cache and fallback. The service reports whether
the active backend is Supabase or JSON fallback; do not treat fallback as durable.

## 1. Create the table
Open the intended Supabase project → SQL Editor, paste and run
`mvp/supabase_game_knowledge.sql`. It creates only
`public.jarvis_game_knowledge` and enables RLS without public policies.

## 2. Configure Render
For the existing `jarvis-loophole-playtest` web service, add these server-side
environment variables:
- `SUPABASE_URL`: Project URL, e.g. the URL shown in Project Settings → API.
- `SUPABASE_SERVICE_ROLE_KEY`: the new-format `sb_secret_...` key.

Never paste the key into chat, commit it, put it in frontend JavaScript, or
include it in logs. Render environment changes may restart/redeploy the service.

## 3. Verify
After deployment, use the authenticated dashboard knowledge panel or
`GET /api/knowledge` to inspect `storage_backend`, `record_count`, and
`storage_error`. A `json_fallback` status means Supabase connectivity/table
permissions are not working; data is still only in the local cache at that time.
The app does not claim a successful cloud write unless the Supabase request succeeds.

The adapter merges local-only cached records into an empty/partial remote table
during startup and uses URL-derived record IDs for idempotent upserts. It is a
single-instance MVP, not a multi-writer distributed storage design.
