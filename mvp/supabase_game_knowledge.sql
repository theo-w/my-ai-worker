-- JARVIS game knowledge base (Supabase SQL Editor)
-- Creates an isolated table; does not alter existing tables or schemas.
create table if not exists public.jarvis_game_knowledge (
  id text primary key,
  title text not null,
  url text not null,
  snippet text not null,
  query text not null default '',
  provider text not null default 'unknown',
  published_at text,
  first_seen_at timestamptz,
  last_seen_at timestamptz,
  seen_count integer not null default 1,
  quality_accepted_at_capture boolean not null default false,
  knowledge_status text not null default 'source_backed_unverified',
  verification_note text not null default ''
);

create index if not exists jarvis_game_knowledge_last_seen_idx
  on public.jarvis_game_knowledge (last_seen_at desc);

create index if not exists jarvis_game_knowledge_url_idx
  on public.jarvis_game_knowledge (url);

alter table public.jarvis_game_knowledge enable row level security;

-- Do not add anon/authenticated policies. Server-side sb_secret key is used
-- only by the Render backend and bypasses RLS; never expose it in browser code.
