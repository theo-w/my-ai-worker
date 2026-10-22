-- Run in Supabase SQL Editor before deploying the topic-aware refresh code.
-- Additive migration: leaves existing knowledge rows intact.
-- The application now tracks recrawl metadata on source rows; add these columns
-- before deploying the updated application so Supabase REST upserts keep working.
alter table public.jarvis_game_knowledge
  add column if not exists last_checked_query text not null default '',
  add column if not exists last_check_status text not null default '';

create table if not exists public.jarvis_knowledge_changes (
  id text primary key,
  source_id text not null,
  topic_key text not null,
  query text not null default '',
  change_type text not null,
  old_title text,
  new_title text,
  old_snippet text,
  new_snippet text,
  source_url text not null,
  detected_at timestamptz not null default now(),
  reason text not null default ''
);

create index if not exists jarvis_knowledge_changes_topic_idx
  on public.jarvis_knowledge_changes (topic_key, detected_at desc);
create index if not exists jarvis_knowledge_changes_source_idx
  on public.jarvis_knowledge_changes (source_id, detected_at desc);

alter table public.jarvis_knowledge_changes enable row level security;
-- No anon/authenticated policies. Server-side Supabase secret is used only by Render.
