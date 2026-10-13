-- Apply AFTER admin_hub.sql, protagonist_votes.sql, protagonist_vote_controls.sql,
-- and protagonist_profile_traits_v2.sql (the legacy-to-seven-trait reset).
-- One-time bootstrap; subsequent changes use the Admin Hub. Never re-run older migrations afterwards.
begin;
select pg_advisory_xact_lock(718204619);

create table if not exists public.protagonist_definition (
  id boolean primary key default true check (id),
  revision bigint not null default 1 check (revision > 0),
  instructions text not null,
  traits jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.protagonist_definition enable row level security;
revoke all on public.protagonist_definition from public, anon, authenticated;
grant select on public.protagonist_definition to service_role;
drop policy if exists axiom_banned_accounts on public.protagonist_definition;
create policy axiom_banned_accounts on public.protagonist_definition as restrictive
  for all to authenticated using (public.axiom_account_allowed()) with check (public.axiom_account_allowed());

insert into public.protagonist_definition(id,instructions,traits)
values(true, $instructions$Scores reflect recurring, narratively meaningful characterization, not genre assumptions or isolated moments.
Do not use 50 as a default when evidence is weak.$instructions$, $traits$[
  {
    "key": "intelligence",
    "name": "Intelligence",
    "prompt": "INTELLIGENCE: reasoning, learning, insight, strategy, and problem-solving ability.\n0 means profoundly poor judgment or understanding; 50 means capable and ordinary for the\nstory's context; 100 means exceptional intellect consistently drives the protagonist's choices.\nIntelligence is ability, not curiosity."
  },
  {
    "key": "charisma",
    "name": "Charisma",
    "prompt": "CHARISMA: ability to attract, persuade, inspire, charm, or socially influence others.\n0 means notably unable to connect or influence; 50 means mixed or situational social appeal;\n100 means exceptional influence, magnetism, or inspiration central to the story.\nRemember: charisma is social influence, not leadership."
  },
  {
    "key": "moral_integrity",
    "name": "Moral Integrity",
    "prompt": "MORAL_INTEGRITY: consistency in acting according to ethical principles, even at personal cost.\n0 means routinely cruel, exploitative, or unconstrained by moral concern; 50 means conflicted\nor selective principles; 100 means unusually principled conduct repeatedly upheld under pressure.\nMoral integrity is principled conduct, not kindness."
  },
  {
    "key": "kinship_friendship",
    "name": "Kinship and Friendship",
    "prompt": "KINSHIP_FRIENDSHIP: emotional investment, loyalty, and care toward family, friends, and found family.\n0 means detached or consistently dismissive; 50 means meaningful but balanced bonds; 100 means\nthese bonds are defining motivations that repeatedly shape major decisions."
  },
  {
    "key": "romantic_attachment",
    "name": "Romantic Attachment",
    "prompt": "ROMANTIC_ATTACHMENT: importance of romantic love, partnership, and attachment in the protagonist's life.\n0 means explicitly absent or irrelevant; 50 means a substantial relationship without dominating the story;\n100 means romance is a defining motivation and central driver of major choices.\nRomantic attachment and erotic desire are independent traits."
  },
  {
    "key": "erotic_desire",
    "name": "Erotic Desire",
    "prompt": "EROTIC_DESIRE: how strongly sexual attraction, desire, or pursuit is expressed as a meaningful motivation.\n0 means explicitly absent or irrelevant; 50 means recurring but balanced; 100 means sexual desire is a\ndefining and repeated driver. Do not infer this merely from romance, appearance, or genre.\nRomantic attachment and erotic desire are independent traits."
  },
  {
    "key": "arrogance_pride",
    "name": "Arrogance & Conceit",
    "prompt": "ARROGANCE_PRIDE: ego, superiority, status-consciousness, and resistance to admitting weakness.\n0 means defining humility; 50 means balanced confidence and humility; 100 means extreme conceit or\nsuperiority consistently shapes the protagonist's choices and relationships."
  }
]$traits$::jsonb)
on conflict(id) do nothing;

create or replace function public.get_protagonist_definition()
returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('revision',revision,'instructions',instructions,'traits',traits)
  from public.protagonist_definition where id;
$$;
revoke all on function public.get_protagonist_definition() from public;
grant execute on function public.get_protagonist_definition() to anon,authenticated,service_role;

-- Preserve historical input names without dropping dependencies or named calls.
do $migration$
declare argument_name text;
begin
  select proargnames[1] into argument_name from pg_catalog.pg_proc
    where oid = to_regprocedure('public.protagonist_score_values(jsonb)');
  execute format($definition$
create or replace function public.protagonist_score_values(%I jsonb)
returns jsonb language sql stable set search_path = '' as $$
  select coalesce(jsonb_object_agg(t->>'key',$1->(t->>'key')),'{}'::jsonb)
  from public.protagonist_definition d, lateral jsonb_array_elements(d.traits) t where d.id;
$$;
$definition$, coalesce(argument_name, 'p_rows'));
end;
$migration$;

-- Partial baselines preserve unchanged defaults while edited traits await rebuilding.
-- Preserve historical input names without dropping dependencies or named calls.
do $migration$
declare argument_name text;
begin
  select proargnames[1] into argument_name from pg_catalog.pg_proc
    where oid = to_regprocedure('public.valid_protagonist_baseline(jsonb)');
  execute format($definition$
create or replace function public.valid_protagonist_baseline(%I jsonb)
returns boolean language sql stable set search_path = '' as $$
  select case when jsonb_typeof($1) is distinct from 'object' then false else
    not exists(select 1 from jsonb_each($1) e where
      jsonb_typeof(e.value) <> 'number' or e.value::text !~ '^(100|[0-9]{1,2})$'
      or not exists(select 1 from public.protagonist_definition d,
        lateral jsonb_array_elements(d.traits) t where t->>'key'=e.key)) end;
$$;
$definition$, coalesce(argument_name, 'p_scores'));
end;
$migration$;
-- Preserve existing argument names (older installations use p_scores).
-- Replacing in place keeps dependent constraints, grants, and named calls intact.
do $migration$
declare argument_name text;
begin
  select proargnames[1] into argument_name from pg_catalog.pg_proc
    where oid = to_regprocedure('public.valid_protagonist_scores(jsonb)');
  execute format($definition$
create or replace function public.valid_protagonist_scores(%I jsonb)
returns boolean language sql stable set search_path = '' as $$
  select public.valid_protagonist_baseline($1) and
    (select count(*) from jsonb_object_keys(case when jsonb_typeof($1)='object' then $1 else '{}'::jsonb end))
      = (select jsonb_array_length(traits) from public.protagonist_definition where id);
$$;
$definition$, coalesce(argument_name, 'p_scores'));
end;
$migration$;

-- The uploaded schema may carry constraints from either the six- or ten-trait era.
do $$ declare c record; t jsonb;
begin
  for c in select conname from pg_constraint where conrelid='public.protagonist_baselines'::regclass and contype='c'
    and pg_get_constraintdef(oid) like '%valid_protagonist_scores%' loop
    execute format('alter table public.protagonist_baselines drop constraint %I',c.conname);
  end loop;
  for c in select conname from pg_constraint where conrelid='public.protagonist_votes'::regclass and contype='c'
    and pg_get_constraintdef(oid) like '%trait%' loop
    execute format('alter table public.protagonist_votes drop constraint %I',c.conname);
  end loop;
  for t in select jsonb_array_elements(traits) from public.protagonist_definition where id loop
    execute format('alter table public.protagonist_profiles add column if not exists %I smallint check (%I between 0 and 100)',t->>'key',t->>'key');
  end loop;
end $$;

create or replace function public.sync_protagonist_baseline()
returns trigger language plpgsql security definer set search_path = '' as $$
declare scores jsonb; previous_scores jsonb; baseline jsonb; entry record;
begin
  if current_setting('axiom.recalculating_protagonist',true)='true'
    or current_setting('axiom.changing_definition',true)='true' then return new; end if;
  scores := public.protagonist_score_values(to_jsonb(new));
  previous_scores := case when TG_OP='UPDATE' then public.protagonist_score_values(to_jsonb(old)) else '{}'::jsonb end;
  select b.scores into baseline from public.protagonist_baselines b where novel_id=new.novel_id;
  baseline := coalesce(baseline,'{}'::jsonb);
  for entry in select * from jsonb_each(scores) loop
    if not baseline ? entry.key or entry.value is distinct from previous_scores->entry.key then
      if entry.value='null'::jsonb then baseline := baseline-entry.key;
      else baseline := jsonb_set(baseline,array[entry.key],entry.value); end if;
    end if;
  end loop;
  insert into public.protagonist_baselines(novel_id,scores) values(new.novel_id,baseline)
    on conflict(novel_id) do update set scores=excluded.scores,generated_at=now();
  return new;
end;
$$;

create or replace function public.recalculate_protagonist(p_novel_id bigint)
returns void language plpgsql security definer set search_path = '' as $$
declare entry record; calibrated integer; previous_setting text;
begin
  perform pg_advisory_xact_lock(718204619);
  if current_setting('axiom.changing_definition',true)='true' then return; end if;
  if not exists(select 1 from public.protagonist_profiles where novel_id=p_novel_id and not scores_locked) then return; end if;
  previous_setting := current_setting('axiom.recalculating_protagonist',true);
  perform set_config('axiom.recalculating_protagonist','true',true);
  for entry in select e.* from public.protagonist_baselines b, lateral jsonb_each_text(b.scores) e
    where b.novel_id=p_novel_id loop
    select round((entry.value::numeric+coalesce(sum(score),0))/(count(*)+1)) into calibrated
      from public.protagonist_votes where novel_id=p_novel_id and trait=entry.key;
    execute format('update public.protagonist_profiles set %I=$1 where novel_id=$2',entry.key) using calibrated,p_novel_id;
  end loop;
  perform set_config('axiom.recalculating_protagonist',coalesce(previous_setting,''),true);
end;
$$;

-- Clean retired keys without disturbing defaults or votes for current measures.
select set_config('axiom.changing_definition','true',true);
delete from public.protagonist_votes v where not exists(select 1 from public.protagonist_definition d,
  lateral jsonb_array_elements(d.traits) t where t->>'key'=v.trait);
update public.protagonist_baselines b set scores=coalesce((select jsonb_object_agg(e.key,e.value)
  from jsonb_each(b.scores) e where exists(select 1 from public.protagonist_definition d,
    lateral jsonb_array_elements(d.traits) t where t->>'key'=e.key)),'{}'::jsonb);
insert into public.protagonist_baselines(novel_id,scores)
  select p.novel_id,jsonb_strip_nulls(public.protagonist_score_values(to_jsonb(p))) from public.protagonist_profiles p
  on conflict(novel_id) do update set scores=excluded.scores || public.protagonist_baselines.scores;
select set_config('axiom.changing_definition','',true);
alter table public.protagonist_baselines drop constraint if exists protagonist_baselines_dynamic_scores;
alter table public.protagonist_baselines add constraint protagonist_baselines_dynamic_scores check(public.valid_protagonist_baseline(scores));

create or replace function public.check_protagonist_vote_trait()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if not exists(select 1 from public.protagonist_definition d,lateral jsonb_array_elements(d.traits) t where t->>'key'=new.trait)
    then raise exception 'Unknown protagonist trait' using errcode='22023'; end if;
  return new;
end;
$$;
drop trigger if exists protagonist_vote_trait on public.protagonist_votes;
create trigger protagonist_vote_trait before insert or update on public.protagonist_votes
  for each row execute function public.check_protagonist_vote_trait();

create or replace function public.update_protagonist_definition(p_revision bigint,p_instructions text,p_traits jsonb)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare current_def public.protagonist_definition; trait_entry jsonb; old_trait jsonb; affected text[] := '{}';
  trait_key text; rules_changed boolean; previous_setting text;
begin
  perform pg_advisory_xact_lock(718204619);
  select * into strict current_def from public.protagonist_definition where id for update;
  if p_revision is distinct from current_def.revision then
    raise exception 'Protagonist definitions changed; reload before saving' using errcode='40001'; end if;
  if p_instructions is null or length(trim(p_instructions)) not between 1 and 20000
    or jsonb_typeof(p_traits) is distinct from 'array' then
    raise exception 'Supply scoring instructions and a trait list' using errcode='22023'; end if;
  if jsonb_array_length(p_traits) not between 1 and 50 then
    raise exception 'Supply between 1 and 50 traits' using errcode='22023'; end if;
  for trait_entry in select jsonb_array_elements(p_traits) loop
    trait_key := trait_entry->>'key';
    if jsonb_typeof(trait_entry) <> 'object' or (select count(*) from jsonb_object_keys(trait_entry)) <> 3
      or jsonb_typeof(trait_entry->'key') is distinct from 'string'
      or jsonb_typeof(trait_entry->'name') is distinct from 'string' or jsonb_typeof(trait_entry->'prompt') is distinct from 'string'
      or trait_key !~ '^[a-z][a-z0-9_]{0,47}$' or trait_key like 'pg\_%'
      or trait_key = any(array['id','novel_id','protagonist_name','scores_locked','created_at','updated_at'])
      or length(trim(trait_entry->>'name')) not between 1 and 100 or length(trim(trait_entry->>'prompt')) not between 1 and 12000 then
      raise exception 'Invalid trait key, name or prompt' using errcode='22023'; end if;
    if not exists(select 1 from jsonb_array_elements(current_def.traits) o where o->>'key'=trait_key)
      and exists(select 1 from information_schema.columns where table_schema='public' and table_name='protagonist_profiles' and column_name=trait_key) then
      raise exception 'Trait key conflicts with an existing profile column' using errcode='22023'; end if;
  end loop;
  if (select count(distinct t->>'key') from jsonb_array_elements(p_traits) t) <> jsonb_array_length(p_traits)
    or (select count(distinct lower(trim(t->>'name'))) from jsonb_array_elements(p_traits) t) <> jsonb_array_length(p_traits) then
    raise exception 'Trait keys and names must be unique' using errcode='22023'; end if;
  if p_traits=current_def.traits and p_instructions=current_def.instructions then return public.get_protagonist_definition(); end if;
  rules_changed := p_instructions is distinct from current_def.instructions;
  for old_trait in select jsonb_array_elements(current_def.traits) loop
    if rules_changed or not exists(select 1 from jsonb_array_elements(p_traits) t where t=old_trait) then
      affected := array_append(affected,old_trait->>'key');
    end if;
  end loop;
  -- Table locks and the same advisory lock used by vote/profile writes make DDL and cleanup atomic.
  lock table public.protagonist_profiles in access exclusive mode;
  previous_setting := current_setting('axiom.changing_definition',true);
  perform set_config('axiom.changing_definition','true',true);
  update public.protagonist_baselines set scores=scores-affected where scores ?| affected;
  delete from public.protagonist_votes where trait=any(affected);
  foreach trait_key in array affected loop
    if exists(select 1 from jsonb_array_elements(p_traits) t where t->>'key'=trait_key) then
      execute format('update public.protagonist_profiles set %I=null where %I is not null',trait_key,trait_key);
    else
      execute format('alter table public.protagonist_profiles drop column %I',trait_key);
    end if;
  end loop;
  for trait_entry in select jsonb_array_elements(p_traits) loop
    if not exists(select 1 from jsonb_array_elements(current_def.traits) o where o->>'key'=trait_entry->>'key') then
      execute format('alter table public.protagonist_profiles add column %I smallint check (%I between 0 and 100)',trait_entry->>'key',trait_entry->>'key');
    end if;
  end loop;
  update public.protagonist_definition set revision=revision+1,instructions=p_instructions,traits=p_traits,updated_at=now() where id;
  perform set_config('axiom.changing_definition',coalesce(previous_setting,''),true);
  perform pg_notify('pgrst','reload schema');
  return public.get_protagonist_definition();
end;
$$;


-- Old unversioned entry points must not be able to restore invalidated scores.
drop function if exists public.save_gemini_protagonist(bigint,text,jsonb);
create or replace function public.save_protagonist_profile(p_novel_id bigint,p_name text,p_scores jsonb,p_revision bigint,p_generated boolean)
returns void language plpgsql security definer set search_path = '' as $$
declare columns_sql text; values_sql text; updates_sql text;
begin
  perform pg_advisory_xact_lock(718204619);
  if p_revision is distinct from (select revision from public.protagonist_definition where id) then
    raise exception 'Protagonist definitions changed; regenerate or reload the profile' using errcode='40001'; end if;
  if not public.valid_protagonist_scores(p_scores) or p_name is null or length(trim(p_name)) not between 1 and 200 then
    raise exception 'A complete profile is required' using errcode='22023'; end if;
  if p_generated and exists(select 1 from public.protagonist_profiles where novel_id=p_novel_id and scores_locked) then
    raise exception 'Protagonist scores are locked by a moderator' using errcode='P0001'; end if;
  select string_agg(format('%I',t->>'key'),','),
    string_agg(format('($3->>%L)::smallint',t->>'key'),','),
    string_agg(format('%I=excluded.%I',t->>'key',t->>'key'),',')
    into columns_sql,values_sql,updates_sql from public.protagonist_definition d,lateral jsonb_array_elements(d.traits) t;
  execute format('insert into public.protagonist_profiles(novel_id,protagonist_name,%s) values($1,$2,%s) on conflict(novel_id) do update set protagonist_name=excluded.protagonist_name,%s',columns_sql,values_sql,updates_sql)
    using p_novel_id,trim(p_name),p_scores;
  insert into public.protagonist_baselines(novel_id,scores) values(p_novel_id,p_scores)
    on conflict(novel_id) do update set scores=excluded.scores,generated_at=now();
  if p_generated then perform public.recalculate_protagonist(p_novel_id); end if;
end;
$$;
create or replace function public.save_gemini_protagonist(p_novel_id bigint,p_name text,p_scores jsonb,p_revision bigint)
returns void language sql security definer set search_path = '' as $$
  select public.save_protagonist_profile(p_novel_id,p_name,p_scores,p_revision,true);
$$;

drop function if exists public.cast_protagonist_vote(bigint,uuid,text,integer);
create or replace function public.cast_protagonist_vote(p_novel_id bigint,p_user_id uuid,p_trait text,p_score integer,p_revision bigint)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform pg_advisory_xact_lock(718204619);
  if p_revision is distinct from (select revision from public.protagonist_definition where id) then
    raise exception 'Protagonist definitions changed; reload before voting' using errcode='40001'; end if;
  if not exists(select 1 from public.protagonist_profiles p where novel_id=p_novel_id
    and public.valid_protagonist_scores(public.protagonist_score_values(to_jsonb(p)))) then
    raise exception 'Voting opens when all current protagonist scores are filled in' using errcode='P0001'; end if;
  insert into public.protagonist_votes(novel_id,user_id,trait,score) values(p_novel_id,p_user_id,p_trait,p_score)
    on conflict(novel_id,user_id,trait) do update set score=excluded.score,updated_at=now();
end;
$$;

revoke all on function public.protagonist_score_values(jsonb),public.valid_protagonist_scores(jsonb),
  public.valid_protagonist_baseline(jsonb),public.check_protagonist_vote_trait(),
  public.update_protagonist_definition(bigint,text,jsonb),
  public.save_protagonist_profile(bigint,text,jsonb,bigint,boolean),
  public.save_gemini_protagonist(bigint,text,jsonb,bigint),public.cast_protagonist_vote(bigint,uuid,text,integer,bigint)
  from public,anon,authenticated;
grant execute on function public.protagonist_score_values(jsonb),public.valid_protagonist_scores(jsonb),
  public.valid_protagonist_baseline(jsonb),public.update_protagonist_definition(bigint,text,jsonb),
  public.save_protagonist_profile(bigint,text,jsonb,bigint,boolean),
  public.save_gemini_protagonist(bigint,text,jsonb,bigint),public.cast_protagonist_vote(bigint,uuid,text,integer,bigint) to service_role;
create or replace function public.protagonist_vote_summary(p_novel_id bigint,p_user_id uuid default null)
returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'revision',(select revision from public.protagonist_definition where id),
    'traits',(select traits from public.protagonist_definition where id),
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
notify pgrst, 'reload schema';
commit;
