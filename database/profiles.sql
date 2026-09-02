-- Stores a public username for each account and links it back to the
-- Supabase Auth user. The auth.users table can't be queried directly by
-- the app, so this table lets the app look usernames up.
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text not null,
  created_at timestamptz not null default now()
);

-- Usernames must be unique, ignoring capitalization ("Alice" and "alice"
-- count as the same username).
create unique index profiles_username_unique_idx
  on public.profiles (lower(username));

alter table public.profiles enable row level security;

-- Usernames need to be publicly readable so the login form can figure out
-- which account a username belongs to. Only usernames are exposed this
-- way — email addresses are never stored in this table.
create policy "Usernames are publicly readable"
  on public.profiles for select
  using (true);

create policy "Users can insert their own profile"
  on public.profiles for insert
  with check (auth.uid() = id);

create policy "Users can update their own profile"
  on public.profiles for update
  using (auth.uid() = id);

-- Tracks which novels this user has personally added to the catalogue,
-- so the upload form can show them their own contribution history.
alter table public.profiles
  add column if not exists novels_uploaded bigint[] not null default '{}';