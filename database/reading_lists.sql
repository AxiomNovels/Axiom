-- Reading lists feature.
--
-- Run this once in the Supabase SQL editor (or via your migration tool of
-- choice). It is safe to re-run: every statement is idempotent.

create extension if not exists pgcrypto;

-- One row per list a user has created (e.g. "Favorites", "Currently reading").
create table if not exists public.reading_lists (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(trim(name)) > 0),
  created_at timestamptz not null default now(),
  unique (user_id, name)
);

create index if not exists reading_lists_user_id_idx
  on public.reading_lists (user_id);

-- Which novels are in which list. A novel can only sit in one of a given
-- user's lists at a time -- that's what makes "Move to..." a single action
-- instead of a remove-then-add.
create table if not exists public.reading_list_novels (
  id uuid primary key default gen_random_uuid(),
  reading_list_id uuid not null references public.reading_lists(id) on delete cascade,
  novel_id bigint not null references public.novels(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  added_at timestamptz not null default now(),
  unique (user_id, novel_id)
);

create index if not exists reading_list_novels_list_idx
  on public.reading_list_novels (reading_list_id);
create index if not exists reading_list_novels_user_idx
  on public.reading_list_novels (user_id);

alter table public.reading_lists enable row level security;
alter table public.reading_list_novels enable row level security;

drop policy if exists "Users manage their own reading lists" on public.reading_lists;
create policy "Users manage their own reading lists"
  on public.reading_lists
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users manage their own reading list novels" on public.reading_list_novels;
create policy "Users manage their own reading list novels"
  on public.reading_list_novels
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Give every newly created user a default "Favorites" list.
create or replace function public.handle_new_user_reading_list()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.reading_lists (user_id, name)
  values (new.id, 'Favorites')
  on conflict (user_id, name) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_reading_list on auth.users;
create trigger on_auth_user_created_reading_list
  after insert on auth.users
  for each row execute function public.handle_new_user_reading_list();

-- Backfill a "Favorites" list for any account that already existed before
-- this migration ran.
insert into public.reading_lists (user_id, name)
select u.id, 'Favorites'
from auth.users u
on conflict (user_id, name) do nothing;