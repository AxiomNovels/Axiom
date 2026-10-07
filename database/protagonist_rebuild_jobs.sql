-- Apply in Supabase before using Admin Hub's profile rebuild controls.
create table if not exists public.protagonist_rebuild_jobs (
  id uuid primary key default gen_random_uuid(),
  requested_by uuid not null references auth.users(id),
  mode text not null check (mode in ('outdated','all')),
  status text not null default 'queued' check (status in ('queued','running','completed')),
  total integer not null default 0, processed integer not null default 0,
  succeeded integer not null default 0, failed integer not null default 0,
  created_at timestamptz not null default now(), started_at timestamptz, finished_at timestamptz
);
create table if not exists public.protagonist_rebuild_items (
  id bigint generated always as identity primary key,
  job_id uuid not null references public.protagonist_rebuild_jobs(id) on delete cascade,
  novel_id bigint not null references public.novels(id) on delete cascade,
  status text not null default 'queued' check (status in ('queued','running','completed','failed')),
  error text, created_at timestamptz not null default now(), started_at timestamptz, finished_at timestamptz,
  unique(job_id, novel_id)
);
create index if not exists protagonist_rebuild_items_queue_idx on public.protagonist_rebuild_items(job_id,status,id);
alter table public.protagonist_rebuild_jobs enable row level security;
alter table public.protagonist_rebuild_items enable row level security;
revoke all on public.protagonist_rebuild_jobs, public.protagonist_rebuild_items from anon, authenticated;
grant all on public.protagonist_rebuild_jobs, public.protagonist_rebuild_items to service_role;
