# Game Mechanics Knowledge Base (MVP)

## Intended workflow

1. Before a run, retrieve relevant prior records using lexical token overlap and Chinese bigrams.
2. Run live research for the current question anyway; prior memory is context, not a replacement for fresh evidence.
3. Store source title, URL, excerpt, provider, query, timestamps, deduplication key, and quality-gate status.
4. Pass prior records into design synthesis as explicitly unverified historical context, alongside current sources.
5. Allow the user to search the library from the dashboard or authenticated API.

## Trust and freshness rules

- A search result is a lead, not a verified fact. Records remain `source_backed_unverified`.
- Passing the current source-quality gate is recorded as metadata, not proof that a page is true or a source is independent.
- URL fragments are removed for deduplication; repeated URLs update the existing record and increment `seen_count`.
- Retrieval scores are relevance heuristics only. They are not confidence or truth scores.
- Old records should be compared with current research; they must not suppress fresh searches or be treated as timeless truths.
- The library currently stores source records, not an automatically trusted summary of every model answer. Decision reports and playtest outcomes should be added later with their own provenance and verification state.

## API

- `GET /api/knowledge` — authenticated summary.
- `POST /api/knowledge/search` — authenticated retrieval. JSON body: `{"query":"NPC 记忆 留存","limit":8}`.
- The current execution state also exposes `knowledge.retrieved` and `knowledge.ingest` for dashboard display.

## Storage caveat

The default store path is `data/game_knowledge.json`; override it with `JARVIS_GAME_KNOWLEDGE_PATH`. This is JSON-backed and works for local development. Render's current service is on the free plan and no persistent disk or Postgres instance is configured in the workspace. Therefore, records written to the default container filesystem may be lost during restart/redeploy. Do not treat cloud persistence as guaranteed until a persistent disk or database is deliberately provisioned and configured.

## Current limitations

- Retrieval is lexical, not embedding/vector search or a knowledge graph.
- Search snippets are retained; the system does not yet fetch and re-verify the full source page on every reuse.
- Freshness decay, conflict detection, canonical topic/game/mechanic entities, decision history, and verified playtest outcomes are future improvements.
- The store is process-local JSON with a thread lock; it is suitable for a single-instance MVP, not multi-instance concurrent writes.