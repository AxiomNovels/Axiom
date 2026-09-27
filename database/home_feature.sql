-- One manually curated feature powers the Home page's Featured inquiry card.
create table if not exists public.home_feature (
  id boolean primary key default true check (id),
  novel_id bigint not null references public.novels(id) on delete restrict,
  inquiry text not null check (char_length(btrim(inquiry)) between 10 and 240),
  description text not null check (char_length(btrim(description)) between 10 and 500),
  tags text[] not null default '{}'::text[] check (cardinality(tags) <= 4),
  updated_at timestamptz not null default now()
);

alter table public.home_feature enable row level security;
drop policy if exists "Home feature is public" on public.home_feature;
create policy "Home feature is public" on public.home_feature for select using (true);

create or replace function public.set_home_feature_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;
drop trigger if exists home_feature_set_updated_at on public.home_feature;
create trigger home_feature_set_updated_at before update on public.home_feature
for each row execute function public.set_home_feature_updated_at();
