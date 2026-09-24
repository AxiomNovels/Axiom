-- Apply after protagonist_profile_measures.sql and profiles.sql.
-- Existing profiles are deliberately NOT assumed to have Gemini provenance.
begin;

create or replace function public.valid_protagonist_scores(scores jsonb)
returns boolean language sql immutable set search_path = '' as $$
  select case when jsonb_typeof(scores) <> 'object' then false else
    (select count(*) = 6 and bool_and(
      key = any(array['impulsivity','arrogance_pride','kinship_friendship',
                       'romantic_attachment','sexual_desire','selflessness'])
      and jsonb_typeof(value) = 'number'
      and value::text ~ '^(100|[0-9]{1,2})$') from jsonb_each(scores)) end;
$$;

create table if not exists public.protagonist_baselines (
  novel_id bigint primary key references public.novels(id) on delete cascade,
  scores jsonb not null check (public.valid_protagonist_scores(scores)),
  generated_at timestamptz not null default now()
);
create table if not exists public.protagonist_votes (
  id bigint generated always as identity primary key,
  novel_id bigint not null references public.protagonist_baselines(novel_id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  trait text not null check (trait in ('impulsivity','arrogance_pride','kinship_friendship',
    'romantic_attachment','sexual_desire','selflessness')),
  score smallint not null check (score between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (novel_id, user_id, trait)
);
create index if not exists protagonist_votes_user_idx on public.protagonist_votes(user_id);
alter table public.protagonist_baselines enable row level security;
alter table public.protagonist_votes enable row level security;
-- Identities are available only through the authenticated admin API.
revoke all on public.protagonist_baselines, public.protagonist_votes from anon, authenticated;
grant all on public.protagonist_baselines, public.protagonist_votes to service_role;
grant usage, select on sequence public.protagonist_votes_id_seq to service_role;

create or replace function public.recalculate_protagonist(p_novel_id bigint)
returns void language plpgsql security definer set search_path = '' as $$
declare entry record; calibrated integer;
begin
  for entry in select key, value from public.protagonist_baselines b,
    lateral jsonb_each_text(b.scores) where b.novel_id = p_novel_id
  loop
    select round((entry.value::numeric + coalesce(sum(score),0)) / (count(*) + 1))
      into calibrated from public.protagonist_votes
      where novel_id = p_novel_id and trait = entry.key;
    execute format('update public.protagonist_profiles set %I = $1 where novel_id = $2', entry.key)
      using calibrated, p_novel_id;
  end loop;
end;
$$;

-- Serialize vote/baseline writes before their statements, including bulk deletes.
-- This prevents concurrent recalculations from losing another reader's vote.
create or replace function public.lock_protagonist_votes()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(718204619);
  return null;
end;
$$;
create or replace function public.protagonist_votes_changed()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if TG_OP = 'DELETE' then
    perform public.recalculate_protagonist(old.novel_id);
    return old;
  end if;
  perform public.recalculate_protagonist(new.novel_id);
  if TG_OP = 'UPDATE' and old.novel_id <> new.novel_id then
    perform public.recalculate_protagonist(old.novel_id);
  end if;
  return new;
end;
$$;
create or replace function public.protagonist_vote_batch_changed()
returns trigger language plpgsql security definer set search_path = '' as $$
declare affected bigint;
begin
  if TG_OP = 'DELETE' then
    for affected in select distinct novel_id from old_votes loop
      perform public.recalculate_protagonist(affected);
    end loop;
  elsif TG_OP = 'UPDATE' then
    for affected in select novel_id from old_votes union select novel_id from new_votes loop
      perform public.recalculate_protagonist(affected);
    end loop;
  else
    for affected in select distinct novel_id from new_votes loop
      perform public.recalculate_protagonist(affected);
    end loop;
  end if;
  return null;
end;
$$;
drop trigger if exists protagonist_votes_lock on public.protagonist_votes;
create trigger protagonist_votes_lock before insert or update or delete on public.protagonist_votes
  for each statement execute function public.lock_protagonist_votes();
drop trigger if exists protagonist_baselines_lock on public.protagonist_baselines;
create trigger protagonist_baselines_lock before insert or update or delete on public.protagonist_baselines
  for each statement execute function public.lock_protagonist_votes();
drop trigger if exists protagonist_votes_inserted on public.protagonist_votes;
create trigger protagonist_votes_inserted after insert on public.protagonist_votes
  referencing new table as new_votes for each statement execute function public.protagonist_vote_batch_changed();
drop trigger if exists protagonist_votes_updated on public.protagonist_votes;
create trigger protagonist_votes_updated after update on public.protagonist_votes
  referencing old table as old_votes new table as new_votes
  for each statement execute function public.protagonist_vote_batch_changed();
drop trigger if exists protagonist_votes_deleted on public.protagonist_votes;
create trigger protagonist_votes_deleted after delete on public.protagonist_votes
  referencing old table as old_votes for each statement execute function public.protagonist_vote_batch_changed();
drop trigger if exists protagonist_baselines_recalculate on public.protagonist_baselines;
create trigger protagonist_baselines_recalculate after insert or update on public.protagonist_baselines
  for each row execute function public.protagonist_votes_changed();

-- Only the server-side Gemini profiler calls this; manual edits never enable voting.
create or replace function public.save_gemini_protagonist(
  p_novel_id bigint, p_name text, p_scores jsonb)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(718204619);
  if p_scores is null or not public.valid_protagonist_scores(p_scores)
    or p_name is null or length(trim(p_name)) not between 1 and 200 then
    raise exception 'A complete Gemini profile is required' using errcode = '22023';
  end if;
  insert into public.protagonist_profiles(novel_id, protagonist_name,
    impulsivity, arrogance_pride, kinship_friendship, romantic_attachment, sexual_desire, selflessness)
  values (p_novel_id, trim(p_name), (p_scores->>'impulsivity')::smallint,
    (p_scores->>'arrogance_pride')::smallint, (p_scores->>'kinship_friendship')::smallint,
    (p_scores->>'romantic_attachment')::smallint, (p_scores->>'sexual_desire')::smallint,
    (p_scores->>'selflessness')::smallint)
  on conflict (novel_id) do update set protagonist_name = excluded.protagonist_name;
  insert into public.protagonist_baselines(novel_id, scores) values (p_novel_id, p_scores)
  on conflict (novel_id) do update set scores = excluded.scores, generated_at = now();
end;
$$;

create or replace function public.cast_protagonist_vote(
  p_novel_id bigint, p_user_id uuid, p_trait text, p_score integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(718204619);
  if not exists (select 1 from public.protagonist_baselines b
    join public.protagonist_profiles p on p.novel_id = b.novel_id
    where b.novel_id = p_novel_id) then
    raise exception 'Voting opens after Gemini saves a complete protagonist profile' using errcode = 'P0001';
  end if;
  insert into public.protagonist_votes(novel_id, user_id, trait, score)
    values(p_novel_id, p_user_id, p_trait, p_score)
  on conflict (novel_id, user_id, trait) do update
    set score = excluded.score, updated_at = now();
end;
$$;

-- Aggregation runs inside PostgreSQL, so distributions include every vote,
-- regardless of the API's page-size limit. Reader responses exclude identities.
create or replace function public.protagonist_vote_summary(p_novel_id bigint, p_user_id uuid default null)
returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'eligible', exists(select 1 from public.protagonist_baselines b
      join public.protagonist_profiles p on p.novel_id=b.novel_id where b.novel_id=p_novel_id),
    'baseline', (select scores from public.protagonist_baselines where novel_id=p_novel_id),
    'profile', (select to_jsonb(p) from public.protagonist_profiles p where novel_id=p_novel_id),
    'voter_count', (select count(distinct user_id) from public.protagonist_votes where novel_id=p_novel_id),
    'vote_count', (select count(*) from public.protagonist_votes where novel_id=p_novel_id),
    'my_votes', coalesce((select jsonb_object_agg(trait, score) from public.protagonist_votes
      where novel_id=p_novel_id and user_id=p_user_id), '{}'::jsonb),
    'distribution', coalesce((select jsonb_object_agg(trait, bins) from (
      select trait, jsonb_agg(jsonb_build_object('score', score, 'count', n) order by score) bins
      from (select trait, score, count(*) n from public.protagonist_votes
        where novel_id=p_novel_id group by trait,score) counts group by trait
    ) traits), '{}'::jsonb));
$$;

revoke all on function public.recalculate_protagonist(bigint),
  public.lock_protagonist_votes(), public.protagonist_votes_changed(),
  public.protagonist_vote_batch_changed(),
  public.save_gemini_protagonist(bigint,text,jsonb),
  public.cast_protagonist_vote(bigint,uuid,text,integer),
  public.protagonist_vote_summary(bigint,uuid) from public, anon, authenticated;
grant execute on function public.save_gemini_protagonist(bigint,text,jsonb),
  public.cast_protagonist_vote(bigint,uuid,text,integer),
  public.protagonist_vote_summary(bigint,uuid) to service_role;
commit;
