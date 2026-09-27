-- Lightweight reader presence. Run once in the Supabase SQL editor.
-- A row is kept per account; the backend only updates it while a visible
-- Axiom tab is open, and considers a heartbeat fresh for two minutes.
begin;

alter table public.profiles
  add column if not exists online_status_visibility text not null default 'public'
  check (online_status_visibility in ('public', 'private'));

create table if not exists public.user_presence (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  last_heartbeat_at timestamptz not null default now()
);

create index if not exists user_presence_last_heartbeat_idx
  on public.user_presence (last_heartbeat_at desc);

alter table public.user_presence enable row level security;
revoke all on public.user_presence from public, anon, authenticated;
grant all on public.user_presence to service_role;

commit;
