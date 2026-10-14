-- Apply after protagonist_profile_measures.sql, protagonist_votes.sql, and
-- protagonist_vote_controls.sql. This replaces the previous trait model.
-- Existing profile values and votes are intentionally cleared: their meanings
-- cannot be safely mapped to the new seven traits.
-- Run BEFORE manage_protagonist_profile.sql. Once the Admin Hub owns the
-- definition, make changes there instead of running this legacy reset.
begin;
select pg_advisory_xact_lock(718204619);

do $$
begin
  if to_regclass('public.protagonist_definition') is not null then
    raise exception 'Protagonist traits are managed by the Admin Hub; v2 must run before manage_protagonist_profile.sql'
      using errcode = '55000';
  end if;
end;
$$;

delete from public.protagonist_votes;
delete from public.protagonist_baselines;

alter table public.protagonist_profiles
  add column if not exists intelligence smallint check (intelligence between 0 and 100),
  add column if not exists charisma smallint check (charisma between 0 and 100),
  add column if not exists moral_integrity smallint check (moral_integrity between 0 and 100),
  add column if not exists kinship_friendship smallint check (kinship_friendship between 0 and 100),
  add column if not exists romantic_attachment smallint check (romantic_attachment between 0 and 100),
  add column if not exists erotic_desire smallint check (erotic_desire between 0 and 100),
  add column if not exists arrogance_pride smallint check (arrogance_pride between 0 and 100);

-- No old score is comparable to the new rubric. Unlock and clear every profile
-- so the Admin Hub rebuild can establish a fresh baseline.
update public.protagonist_profiles set
  intelligence = null, charisma = null, moral_integrity = null,
  kinship_friendship = null, romantic_attachment = null, erotic_desire = null,
  arrogance_pride = null, scores_locked = false;

-- Preserve existing argument names (older installations use p_scores).
-- Replacing in place keeps dependent constraints, grants, and named calls intact.
do $migration$
declare argument_name text;
begin
  select proargnames[1] into argument_name from pg_catalog.pg_proc
    where oid = to_regprocedure('public.valid_protagonist_scores(jsonb)');
  execute format($definition$
create or replace function public.valid_protagonist_scores(%I jsonb)
returns boolean language sql immutable set search_path = '' as $$
  select jsonb_typeof($1) = 'object' and (select count(*) = 7 and bool_and(
    key = any(array['intelligence','charisma','moral_integrity','kinship_friendship',
      'romantic_attachment','erotic_desire','arrogance_pride'])
    and jsonb_typeof(value) = 'number' and value::text ~ '^(100|[0-9]{1,2})$'
  ) from jsonb_each($1));
$$;
$definition$, coalesce(argument_name, 'p_scores'));
end;
$migration$;

alter table public.protagonist_votes drop constraint if exists protagonist_votes_trait_check;
alter table public.protagonist_votes add constraint protagonist_votes_trait_check check (trait in
  ('intelligence','charisma','moral_integrity','kinship_friendship','romantic_attachment','erotic_desire','arrogance_pride'));

-- Preserve historical input names without dropping dependencies or named calls.
do $migration$
declare argument_name text;
begin
  select proargnames[1] into argument_name from pg_catalog.pg_proc
    where oid = to_regprocedure('public.protagonist_score_values(jsonb)');
  execute format($definition$
create or replace function public.protagonist_score_values(%I jsonb)
returns jsonb language sql immutable set search_path = '' as $$
  select jsonb_build_object('intelligence',$1->'intelligence','charisma',$1->'charisma',
    'moral_integrity',$1->'moral_integrity','kinship_friendship',$1->'kinship_friendship',
    'romantic_attachment',$1->'romantic_attachment','erotic_desire',$1->'erotic_desire',
    'arrogance_pride',$1->'arrogance_pride');
$$;
$definition$, coalesce(argument_name, 'p_rows'));
end;
$migration$;

create or replace function public.save_gemini_protagonist(p_novel_id bigint,p_name text,p_scores jsonb)
returns void language plpgsql security definer set search_path = '' as $save_profile$
begin
  perform pg_advisory_xact_lock(718204619);
  if p_scores is null or not public.valid_protagonist_scores(p_scores) or p_name is null or length(trim(p_name)) not between 1 and 200 then
    raise exception 'A complete seven-trait profile is required' using errcode = '22023';
  end if;
  if exists(select 1 from public.protagonist_profiles where novel_id=p_novel_id and scores_locked) then
    raise exception 'Protagonist scores are locked by a moderator' using errcode='P0001';
  end if;
  insert into public.protagonist_profiles(novel_id,protagonist_name,intelligence,charisma,moral_integrity,kinship_friendship,romantic_attachment,erotic_desire,arrogance_pride)
  values(p_novel_id,trim(p_name),(p_scores->>'intelligence')::smallint,(p_scores->>'charisma')::smallint,(p_scores->>'moral_integrity')::smallint,(p_scores->>'kinship_friendship')::smallint,(p_scores->>'romantic_attachment')::smallint,(p_scores->>'erotic_desire')::smallint,(p_scores->>'arrogance_pride')::smallint)
  on conflict(novel_id) do update set protagonist_name=excluded.protagonist_name,intelligence=excluded.intelligence,charisma=excluded.charisma,moral_integrity=excluded.moral_integrity,kinship_friendship=excluded.kinship_friendship,romantic_attachment=excluded.romantic_attachment,erotic_desire=excluded.erotic_desire,arrogance_pride=excluded.arrogance_pride;
  insert into public.protagonist_baselines(novel_id,scores) values(p_novel_id,p_scores)
  on conflict(novel_id) do update set scores=excluded.scores,generated_at=now();
  perform public.recalculate_protagonist(p_novel_id);
end;
$save_profile$;

create or replace function public.cast_protagonist_vote(p_novel_id bigint,p_user_id uuid,p_trait text,p_score integer)
returns void language plpgsql security definer set search_path = '' as $cast_vote$
begin
  perform pg_advisory_xact_lock(718204619);
  if not exists(select 1 from public.protagonist_profiles p where p.novel_id=p_novel_id and public.valid_protagonist_scores(public.protagonist_score_values(to_jsonb(p)))) then
    raise exception 'Voting opens when all seven protagonist scores are filled in' using errcode='P0001';
  end if;
  insert into public.protagonist_votes(novel_id,user_id,trait,score) values(p_novel_id,p_user_id,p_trait,p_score)
  on conflict(novel_id,user_id,trait) do update set score=excluded.score,updated_at=now();
end;
$cast_vote$;

alter table public.protagonist_profiles
  drop column if exists impulsivity,
  drop column if exists sexual_desire,
  drop column if exists selflessness,
  drop column if exists intellectual_drive,
  drop column if exists selflessness_selfishness,
  drop column if exists pragmatism_morality,
  drop column if exists individualist_collectivist,
  drop column if exists ambition,
  drop column if exists cautious_risk_taker,
  drop column if exists leadership;
commit;
