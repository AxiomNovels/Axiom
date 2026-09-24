-- Apply after protagonist_votes.sql. Complete profiles from any source can vote.
begin;
select pg_advisory_xact_lock(718204619);
alter table public.protagonist_profiles add column if not exists scores_locked boolean not null default false;
revoke insert, update, delete on public.protagonist_profiles from anon, authenticated;

create or replace function public.protagonist_score_values(profile jsonb)
returns jsonb language sql immutable set search_path = '' as $$
  select jsonb_build_object('impulsivity', profile->'impulsivity',
    'arrogance_pride', profile->'arrogance_pride', 'kinship_friendship', profile->'kinship_friendship',
    'romantic_attachment', profile->'romantic_attachment', 'sexual_desire', profile->'sexual_desire',
    'selflessness', profile->'selflessness');
$$;

-- Baselines now follow explicit profile edits. Derived scores must never feed
-- back into the baseline, so recalculation marks its own writes locally.
drop trigger if exists protagonist_baselines_recalculate on public.protagonist_baselines;
create or replace function public.sync_protagonist_baseline()
returns trigger language plpgsql security definer set search_path = '' as $$
declare scores jsonb;
begin
  if current_setting('axiom.recalculating_protagonist', true) = 'true' then return new; end if;
  scores := public.protagonist_score_values(to_jsonb(new));
  if not public.valid_protagonist_scores(scores) then return new; end if;
  if TG_OP = 'UPDATE' and scores = public.protagonist_score_values(to_jsonb(old))
    and exists(select 1 from public.protagonist_baselines where novel_id=new.novel_id) then
    return new;
  end if;
  insert into public.protagonist_baselines(novel_id,scores) values(new.novel_id,scores)
  on conflict(novel_id) do update set scores=excluded.scores, generated_at=now();
  return new;
end;
$$;
drop trigger if exists protagonist_profile_write_lock on public.protagonist_profiles;
create trigger protagonist_profile_write_lock before insert or update or delete on public.protagonist_profiles
  for each statement execute function public.lock_protagonist_votes();
drop trigger if exists protagonist_profile_baseline on public.protagonist_profiles;
create trigger protagonist_profile_baseline after insert or update on public.protagonist_profiles
  for each row execute function public.sync_protagonist_baseline();

-- Preserve existing baselines and votes. Fill in only missing complete profiles.
insert into public.protagonist_baselines(novel_id,scores)
select p.novel_id,public.protagonist_score_values(to_jsonb(p)) from public.protagonist_profiles p
where public.valid_protagonist_scores(public.protagonist_score_values(to_jsonb(p)))
on conflict(novel_id) do nothing;

create or replace function public.recalculate_protagonist(p_novel_id bigint)
returns void language plpgsql security definer set search_path = '' as $$
declare entry record; calibrated integer; previous_setting text;
begin
  perform pg_advisory_xact_lock(718204619);
  if not exists(select 1 from public.protagonist_profiles p where p.novel_id=p_novel_id
    and not p.scores_locked and public.valid_protagonist_scores(public.protagonist_score_values(to_jsonb(p)))) then
    return;
  end if;
  previous_setting := current_setting('axiom.recalculating_protagonist',true);
  perform set_config('axiom.recalculating_protagonist','true',true);
  for entry in select key,value from public.protagonist_baselines b,
    lateral jsonb_each_text(b.scores) where b.novel_id=p_novel_id
  loop
    select round((entry.value::numeric + coalesce(sum(score),0))/(count(*)+1))
      into calibrated from public.protagonist_votes where novel_id=p_novel_id and trait=entry.key;
    execute format('update public.protagonist_profiles set %I=$1 where novel_id=$2',entry.key)
      using calibrated,p_novel_id;
  end loop;
  perform set_config('axiom.recalculating_protagonist',coalesce(previous_setting,''),true);
end;
$$;

create or replace function public.set_protagonist_score_lock(p_novel_id bigint,p_locked boolean)
returns void language plpgsql security definer set search_path = '' as $$
declare was_locked boolean;
begin
  perform pg_advisory_xact_lock(718204619);
  if p_locked is null then raise exception 'Supply a lock state' using errcode='22023'; end if;
  select scores_locked into was_locked from public.protagonist_profiles where novel_id=p_novel_id;
  if not found then raise exception 'Create a protagonist profile before locking scores' using errcode='P0001'; end if;
  update public.protagonist_profiles set scores_locked=p_locked where novel_id=p_novel_id;
  if was_locked and not p_locked then perform public.recalculate_protagonist(p_novel_id); end if;
end;
$$;

create or replace function public.cast_protagonist_vote(p_novel_id bigint,p_user_id uuid,p_trait text,p_score integer)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(718204619);
  if not exists(select 1 from public.protagonist_profiles p where p.novel_id=p_novel_id
    and public.valid_protagonist_scores(public.protagonist_score_values(to_jsonb(p)))) then
    raise exception 'Voting opens when all six protagonist scores are filled in' using errcode='P0001';
  end if;
  insert into public.protagonist_votes(novel_id,user_id,trait,score) values(p_novel_id,p_user_id,p_trait,p_score)
  on conflict(novel_id,user_id,trait) do update set score=excluded.score,updated_at=now();
end;
$$;

-- Keep the existing profiler entry point, but protect moderator-locked scores.
create or replace function public.save_gemini_protagonist(p_novel_id bigint,p_name text,p_scores jsonb)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(718204619);
  if p_scores is null or not public.valid_protagonist_scores(p_scores)
    or p_name is null or length(trim(p_name)) not between 1 and 200 then
    raise exception 'A complete profile is required' using errcode='22023';
  end if;
  if exists(select 1 from public.protagonist_profiles where novel_id=p_novel_id and scores_locked) then
    raise exception 'Protagonist scores are locked by a moderator' using errcode='P0001';
  end if;
  insert into public.protagonist_profiles(novel_id,protagonist_name,
    impulsivity,arrogance_pride,kinship_friendship,romantic_attachment,sexual_desire,selflessness)
  values(p_novel_id,trim(p_name),(p_scores->>'impulsivity')::smallint,(p_scores->>'arrogance_pride')::smallint,
    (p_scores->>'kinship_friendship')::smallint,(p_scores->>'romantic_attachment')::smallint,
    (p_scores->>'sexual_desire')::smallint,(p_scores->>'selflessness')::smallint)
  on conflict(novel_id) do update set protagonist_name=excluded.protagonist_name,
    impulsivity=excluded.impulsivity,arrogance_pride=excluded.arrogance_pride,
    kinship_friendship=excluded.kinship_friendship,romantic_attachment=excluded.romantic_attachment,
    sexual_desire=excluded.sexual_desire,selflessness=excluded.selflessness;
  -- Explicitly set the baseline even when new defaults equal current derived scores.
  insert into public.protagonist_baselines(novel_id,scores) values(p_novel_id,p_scores)
  on conflict(novel_id) do update set scores=excluded.scores,generated_at=now();
  perform public.recalculate_protagonist(p_novel_id);
end;
$$;

create or replace function public.protagonist_vote_summary(p_novel_id bigint,p_user_id uuid default null)
returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'eligible',exists(select 1 from public.protagonist_profiles p where p.novel_id=p_novel_id
      and public.valid_protagonist_scores(public.protagonist_score_values(to_jsonb(p)))),
    'scores_locked',coalesce((select scores_locked from public.protagonist_profiles where novel_id=p_novel_id),false),
    'baseline',(select scores from public.protagonist_baselines where novel_id=p_novel_id),
    'profile',(select to_jsonb(p) from public.protagonist_profiles p where novel_id=p_novel_id),
    'voter_count',(select count(distinct user_id) from public.protagonist_votes where novel_id=p_novel_id),
    'vote_count',(select count(*) from public.protagonist_votes where novel_id=p_novel_id),
    'my_votes',coalesce((select jsonb_object_agg(trait,score) from public.protagonist_votes
      where novel_id=p_novel_id and user_id=p_user_id),'{}'::jsonb),
    'distribution',coalesce((select jsonb_object_agg(trait,bins) from (
      select trait,jsonb_agg(jsonb_build_object('score',score,'count',n) order by score) bins
      from (select trait,score,count(*) n from public.protagonist_votes where novel_id=p_novel_id
        group by trait,score) counts group by trait) traits),'{}'::jsonb));
$$;
revoke all on function public.sync_protagonist_baseline(),public.set_protagonist_score_lock(bigint,boolean)
  from public,anon,authenticated;
grant execute on function public.set_protagonist_score_lock(bigint,boolean) to service_role;
commit;
