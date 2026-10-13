-- Apply AFTER admin_hub.sql, protagonist_votes.sql and protagonist_vote_controls.sql.
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
values(true, $instructions$SCORING RULES
- Use absolute 0-100 scales, not comparisons with other characters. The anchors below
  are authoritative; interpolate between them only when the evidence genuinely falls
  between two anchors.
- 0 means explicit, narratively meaningful absence where the trait is a presence/absence
  measure. Never assign 0 merely because the synopsis or comments do not mention a trait.
- For spectrum measures, 0 and 100 represent the two opposing behavioral poles described
  below. Do not interpret either endpoint as inherently good or bad.
- 20 is the cautious limited-evidence region when a trait is outside the main storyline,
  barely discussed, or supported by unclear evidence and nothing contradicts a low score.
- Score and confidence are different. Sparse/conflicting evidence lowers confidence. It
  does not prove a trait is absent. A score of 50 is not a default for uncertainty.
- Judge how strongly the trait shapes identity, behavior, relationships, and decisions,
  not how often a keyword occurs.
- Do not infer a trait merely from genre, tags, character archetypes, or the absence of
  explicit evidence. Use those only as contextual evidence.
- Distinguish traits that may look similar. For example, intellectual drive is about
  motivation to understand or discover, ambition is about pursuing advancement, and
  leadership is about directing or organizing other people.
- Treat reader comments as fallible opinions. Do not invent plot facts.

For spectrum measures, give the score according to the stated direction. For intellectual drive and leadership, treat 0 as genuine absence and higher values as increasing narrative importance rather than merely uncertainty. Do not use 50 as a default when evidence is weak.$instructions$, $traits$[
  {
    "key": "intellectual_drive",
    "name": "Intellectual Drive",
    "prompt": "INTELLECTUAL_DRIVE (0 absent -> 100 major intellectual theme)\nMeasures how strongly the protagonist is motivated by curiosity, understanding,\ninvestigation, learning, experimentation, discovery, or solving intellectual problems.\nThis is NOT a measure of intelligence, education, competence, or how knowledgeable the\nprotagonist happens to be.\n\n0 means the protagonist shows no meaningful interest in exploring, understanding, or\ndiscovering things, and intellectual exploration is not part of their characterization.\n10 means there is almost no intellectual curiosity, with only isolated practical learning.\n20 means intellectual curiosity is weak, incidental, or supported mainly by limited evidence.\n30 means the protagonist sometimes investigates, learns, or asks questions beyond immediate\nnecessity, but intellectual exploration remains secondary.\n40 means curiosity or learning regularly influences behavior but is not a major motivation.\n50 means intellectual exploration is a clear recurring motivation alongside other goals.\n60 means the protagonist frequently seeks knowledge, investigates systems, experiments,\nor pursues understanding even when doing so is not strictly necessary.\n70 means intellectual discovery or understanding materially shapes major decisions and plot\ndevelopment.\n80 means curiosity, investigation, experimentation, or mastery of knowledge is one of the\nprotagonist's principal motivations.\n90 means intellectual exploration is a defining part of the protagonist's identity and\ndrives many major choices, sacrifices, or conflicts.\n100 means the pursuit of understanding, discovery, knowledge, or intellectual mastery is\none of the dominant themes of the protagonist's story and virtually inseparable from\ntheir major decisions.\n\nDo not score highly simply because the protagonist is clever, strategic, educated, or\ngood at solving problems. A highly intelligent character can have low intellectual drive\nif they rarely care about learning or discovering things.\n\nIntellectual drive measures desire to learn, investigate, understand, or discover; it does not measure intelligence or competence."
  },
  {
    "key": "arrogance_pride",
    "name": "Arrogance & Pride",
    "prompt": "ARROGANCE_PRIDE (0 humble -> 100 extremely egotistical)\nMeasures the protagonist's pride, ego, status-consciousness, sense of superiority, and\nresistance to admitting weakness or inferiority.\n\n0 means explicit, defining humility and little concern for status or superiority.\n10 means very modest, with rare or minor expressions of pride.\n20 means generally humble, or evidence of ego is weak and limited.\n30 means occasional pride, competitiveness, sensitivity to disrespect, or desire to prove\nthemselves.\n40 means pride sometimes affects behavior or decisions but remains secondary.\n50 means confidence and humility are broadly balanced.\n60 means the protagonist is often proud, status-conscious, or sensitive to challenges to\ntheir competence or dignity.\n70 means arrogance or pride regularly shapes conflict, judgment, relationships, or choices.\n80 means the protagonist commonly assumes superiority, strongly resists humiliation, or\nplaces substantial importance on status and personal greatness.\n90 means overwhelming ego or pride governs many major choices and relationships.\n100 means unquestioned superiority or extreme ego is a defining feature of virtually every\nmajor decision and interaction.\n\nConfidence or competence alone does not establish arrogance. Score based on the\nprotagonist's attitude toward their own status, superiority, and importance."
  },
  {
    "key": "kinship_friendship",
    "name": "Kinship and Friendship",
    "prompt": "KINSHIP_FRIENDSHIP (0 detached -> 100 deeply devoted)\nMeasures how strongly the protagonist values and prioritizes friends, family, comrades,\ncompanions, and other close personal bonds.\n\n0 means explicit, defining detachment or absence of meaningful bonds.\n10 means the protagonist is nearly isolated, with at most one faint or weak bond.\n20 means relationships are outside the main story, unclear, or only weakly meaningful.\n30 means a few bonds matter emotionally but rarely determine important choices.\n40 means friendships or family relationships sometimes motivate meaningful action.\n50 means close relationships and personal priorities receive roughly equal weight.\n60 means relationships frequently affect risks, loyalties, priorities, or major decisions.\n70 means protecting or supporting close people is a major recurring motivation.\n80 means deep loyalty to friends, family, or comrades drives major sacrifices and decisions.\n90 means the protagonist repeatedly accepts severe losses, danger, or setbacks for loved\nones or close companions.\n100 means devotion to close relationships dominates virtually every major choice, with the\nprotagonist consistently prioritizing loved ones or comrades above personal interests.\n\nDo not equate having many acquaintances with high kinship/friendship. The measure concerns\nemotional importance, loyalty, and willingness to act for close relationships."
  },
  {
    "key": "romantic_attachment",
    "name": "Romantic Attachment",
    "prompt": "ROMANTIC_ATTACHMENT (0 unattached -> 100 romance-driven)\nMeasures how strongly romantic love, attachment to a partner, or pursuit of a romantic\nrelationship motivates the protagonist.\n\n0 means explicit absence: the protagonist's romantic life is genuinely irrelevant to their\ncharacterization and the story establishes this as meaningful.\n10 means the protagonist is almost entirely unattached, with only an ambiguous or negligible\nromantic element.\n20 means romance is outside the main story, evidence is unclear, or attraction has little\nmeaningful influence.\n30 means minor attraction or an early/limited romantic bond with little effect on the plot.\n40 means a recurring romantic relationship or attachment exists but remains secondary.\n50 means romance is a clear and regular motivation alongside other major priorities.\n60 means romantic attachment materially shapes several important decisions.\n70 means romantic love or pursuit is one of the protagonist's principal motivations.\n80 means love repeatedly outweighs safety, strategy, ambition, duty, or other major goals.\n90 means nearly every defining choice is substantially influenced by a romantic partner or\nromantic attachment.\n100 means romance wholly dominates the protagonist's major motivations and decisions.\n\nEvidence floors:\n- Confirmed slow/minor romance: generally >=25.\n- Recurring partner, spouse, or significant romantic attachment: generally >=40.\n- Romance materially motivating major decisions: generally >=60.\n\nA slow romance describes pacing, not weakness. Do not infer low romantic attachment merely\nbecause romance develops gradually. Explicit relationship evidence outweighs generic labels\nsuch as \"slow romance\" or \"not romance-focused.\""
  },
  {
    "key": "selflessness_selfishness",
    "name": "Selfishness / Selflessness",
    "prompt": "SELFLESSNESS_SELFISHNESS (0 self-interested -> 100 self-sacrificing)\nMeasures the degree to which the protagonist prioritizes other people's welfare over their\nown interests, resources, safety, ambitions, and opportunities.\n\n0 means explicit, defining refusal to sacrifice for others and a consistent prioritization\nof personal interests.\n10 means the protagonist nearly always prioritizes themselves and rarely accepts meaningful\ncosts for other people.\n20 means the protagonist is mostly self-interested, or altruism is weakly evidenced.\n30 means the protagonist helps others at little personal cost but rarely gives up something\nimportant for them.\n40 means recurring generosity or concern for others exists, but personal goals usually come\nfirst.\n50 means the protagonist balances their own interests and the interests of others.\n60 means the protagonist often accepts meaningful inconvenience, risk, expense, or lost\nopportunities for other people.\n70 means the protagonist regularly sacrifices meaningful resources, opportunities, safety,\nor goals for others.\n80 means other people's welfare usually outweighs the protagonist's own ambition or comfort.\n90 means the protagonist repeatedly accepts severe personal loss, danger, or deprivation\nfor other people.\n100 means extreme self-sacrifice is defining: the protagonist consistently places others'\nwelfare above their own survival, ambitions, freedom, or happiness.\n\nHelping others does not automatically imply high selflessness. Consider the personal cost\nand whether the protagonist's behavior is genuinely other-directed rather than transactional,\nstrategic, obligatory, or motivated by reputation."
  },
  {
    "key": "pragmatism_morality",
    "name": "Pragmatism / Morality",
    "prompt": "PRAGMATISM_MORALITY (0 pragmatic/amoral -> 100 principled/moral)\nMeasures how strongly the protagonist adheres to moral principles, ethical rules, ideals,\nor a consistent conception of right and wrong when those principles conflict with practical\nadvantage.\n\n0 means the protagonist is strongly pragmatic or amoral, readily abandoning moral principles\nwhenever doing so advances their goals.\n10 means practical outcomes overwhelmingly determine decisions, with little resistance to\nmorally questionable methods.\n20 means the protagonist is generally pragmatic and flexible about moral boundaries.\n30 means the protagonist has some moral limits but frequently compromises them for practical\nreasons.\n40 means morality matters but is often negotiable when stakes are high.\n50 means practical considerations and moral principles are broadly balanced.\n60 means the protagonist usually tries to preserve moral principles even when doing so is\ncostly or inefficient.\n70 means ethical principles regularly constrain important decisions and methods.\n80 means the protagonist strongly prioritizes doing what they believe is right even at\nsubstantial practical cost.\n90 means a consistent moral code governs most major choices, even when violating it would\nproduce obvious personal or strategic benefits.\n100 means principled morality is defining: the protagonist would accept extreme personal loss,\ndanger, or failure rather than knowingly violate their core ethical principles.\n\nJudge the protagonist's behavior when morality conflicts with practical advantage. Being\nkind, heroic, or helpful is not by itself sufficient for a high score, and being effective\nor strategic is not by itself sufficient for a low score.\n\nDo not treat \"pragmatic\" as synonymous with intelligent, rational, cautious, or strategic.\nA protagonist can be highly strategic while still being strongly principled.\n\nPragmatism/morality measures willingness to compromise moral principles for practical outcomes; it is not simply a measure of whether the protagonist is nice or effective."
  },
  {
    "key": "individualist_collectivist",
    "name": "Individualist / Collectivist",
    "prompt": "INDIVIDUALIST_COLLECTIVIST (0 individualist -> 100 collectivist)\nMeasures whether the protagonist primarily understands themselves and makes decisions as an\nindependent individual or as a member of a group, community, family, organization, culture,\nor collective.\n\n0 means extreme individualism: personal autonomy and independent goals dominate, and the\nprotagonist strongly resists obligations or identity based on groups.\n10 means the protagonist is highly self-directed and rarely allows group expectations to\nconstrain important choices.\n20 means the protagonist generally prioritizes personal autonomy but maintains some meaningful\ngroup ties.\n30 means the protagonist is mostly independent while accepting some obligations to groups or\ncommunities.\n40 means individual priorities usually come first, but group identity and obligations are\nmeaningful.\n50 means individual autonomy and collective belonging have roughly equal importance.\n60 means the protagonist regularly considers the needs, expectations, or interests of their\ngroup alongside their own.\n70 means group loyalty, community identity, or collective goals frequently influence major\ndecisions.\n80 means the protagonist strongly identifies with and prioritizes a family, community,\nfaction, nation, organization, or other collective.\n90 means collective welfare and group obligations routinely outweigh personal preferences,\nambitions, or safety.\n100 means collectivism is defining: the protagonist's identity and virtually all major\ndecisions are fundamentally organized around belonging to and serving a collective.\n\nA protagonist can have strong friendships or be highly selfless without being collectivist.\nThis measure concerns the broader basis of identity, obligation, and decision-making rather\nthan simply whether the protagonist cares about other people.\n\nLikewise, independence does not necessarily mean selfishness. A highly individualistic\nprotagonist may sacrifice heavily for others while still resisting group identity or\ninstitutional obligations.\n\nIndividualist/collectivist measures the protagonist's relationship to group identity, obligations, and collective goals; it is not simply a measure of kindness or friendship."
  },
  {
    "key": "ambition",
    "name": "Ambition",
    "prompt": "AMBITION (0 little ambition -> 100 extremely power-hungry/ambitious)\nMeasures how strongly the protagonist actively pursues advancement, power, status, wealth,\ninfluence, achievement, mastery, or a substantially better position.\n\n0 means the protagonist has virtually no meaningful desire for advancement and is content\nwith their existing circumstances.\n10 means advancement is rarely desired and the protagonist generally accepts their position.\n20 means ambition is weak, secondary, or supported mainly by limited evidence.\n30 means the protagonist has some aspirations but rarely allows them to drive major decisions.\n40 means advancement is a recurring goal but remains secondary to other motivations.\n50 means the protagonist consistently wants to improve their position, abilities, status, or\ncircumstances but balances this against other major priorities.\n60 means ambition frequently influences important choices and the protagonist actively seeks\nopportunities for advancement.\n70 means becoming stronger, more successful, influential, wealthy, skilled, or powerful is\na major recurring motivation.\n80 means ambition is one of the protagonist's principal motivations and regularly outweighs\ncomfort, safety, relationships, or other competing interests.\n90 means relentless advancement or power acquisition governs most major choices and the\nprotagonist is willing to accept substantial costs to keep progressing.\n100 means extreme ambition or hunger for power is defining: continual advancement, mastery,\nstatus, or power acquisition dominates virtually every major decision.\n\nDo not equate competence or natural power with ambition. A protagonist can become extremely\npowerful while having little desire for power, and an ambitious protagonist may begin weak.\n\n\"Power\" should be interpreted broadly according to the story: physical strength, magical\npower, social influence, wealth, political authority, knowledge, status, or other meaningful\nforms of advancement.\n\nAmbition measures desire for advancement, power, status, achievement, or improvement; it does not measure how powerful the protagonist already is."
  },
  {
    "key": "cautious_risk_taker",
    "name": "Cautious / Risk-taker",
    "prompt": "CAUTIOUS_RISK_TAKER (0 cautious -> 100 risk-taking/reckless)\nMeasures the protagonist's willingness to accept uncertainty, danger, loss, or potentially\nsevere consequences in pursuit of an objective.\n\n0 means extreme caution: the protagonist consistently avoids unnecessary danger and strongly\nprioritizes minimizing uncertainty and potential losses.\n10 means the protagonist is highly cautious and takes serious risks only under exceptional\ncircumstances.\n20 means the protagonist generally avoids unnecessary risks, with limited evidence of\nrisk-taking.\n30 means the protagonist is somewhat cautious but will accept manageable risks when justified.\n40 means the protagonist usually weighs risks carefully but sometimes accepts substantial\nuncertainty.\n50 means caution and risk-taking are broadly balanced.\n60 means the protagonist regularly accepts significant risks when opportunities or goals\njustify them.\n70 means the protagonist frequently chooses dangerous or uncertain approaches despite safer\nalternatives.\n80 means the protagonist actively embraces major risks and often treats danger as an\nacceptable or desirable cost of pursuing their goals.\n90 means extreme risk-taking is common: the protagonist repeatedly accepts severe danger,\nuncertainty, or potentially catastrophic consequences.\n100 means reckless risk-taking is defining, with the protagonist routinely choosing highly\ndangerous courses of action despite obvious and substantial consequences.\n\nDistinguish this from impulsivity. A protagonist can be highly deliberate and calculating\nwhile still being an extreme risk-taker. Likewise, an impulsive protagonist may sometimes\nmake surprisingly cautious choices.\n\nJudge willingness to accept risk, not simply how dangerous the protagonist's circumstances\nare. Being placed in dangerous situations does not itself establish that the protagonist\nis a risk-taker.\n\nCautious/risk-taker measures willingness to accept danger and uncertainty; it does not measure impulsivity."
  },
  {
    "key": "leadership",
    "name": "Leadership",
    "prompt": "LEADERSHIP (0 non-leader -> 100 defining leader)\nMeasures how strongly the protagonist takes responsibility for directing, organizing,\nmotivating, protecting, coordinating, or governing other people.\n\n0 means the protagonist does not meaningfully lead others and consistently avoids leadership\nresponsibilities when they arise.\n10 means the protagonist almost always follows others and has little interest in directing\nor organizing people.\n20 means leadership is outside the main story, unclear, or limited to isolated situations.\n30 means the protagonist occasionally takes charge in small or temporary situations.\n40 means the protagonist sometimes organizes or directs others, but leadership remains\nsecondary.\n50 means the protagonist regularly takes responsibility for coordinating or directing\nothers, while also functioning comfortably as a peer or follower.\n60 means leadership frequently affects the protagonist's role, relationships, and decisions.\n70 means the protagonist becomes a significant leader whose decisions materially affect a\ngroup, organization, party, community, or faction.\n80 means leadership is one of the protagonist's principal roles and they regularly accept\nresponsibility for other people's actions, welfare, or direction.\n90 means the protagonist is a major leader whose ability to organize, command, inspire, or\ngovern others drives much of the story.\n100 means leadership is defining: the protagonist's identity and virtually all major choices\nare deeply connected to directing, protecting, organizing, or governing others.\n\nDo not score leadership based solely on charisma, popularity, competence, or power. A\nprotagonist can be charismatic without leading anyone, or be an excellent leader despite\nbeing socially awkward.\n\nSimilarly, commanding someone under duress or temporarily taking charge during an emergency\ndoes not establish high leadership unless the behavior is recurring or narratively meaningful.\n\nLeadership measures responsibility for directing or organizing other people; it is not simply charisma, competence, popularity, or power."
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

create or replace function public.protagonist_score_values(profile jsonb)
returns jsonb language sql stable set search_path = '' as $$
  select coalesce(jsonb_object_agg(t->>'key',profile->(t->>'key')),'{}'::jsonb)
  from public.protagonist_definition d, lateral jsonb_array_elements(d.traits) t where d.id;
$$;

-- Partial baselines preserve unchanged defaults while edited traits await rebuilding.
create or replace function public.valid_protagonist_baseline(scores jsonb)
returns boolean language sql stable set search_path = '' as $$
  select case when jsonb_typeof(scores) is distinct from 'object' then false else
    not exists(select 1 from jsonb_each(scores) e where
      jsonb_typeof(e.value) <> 'number' or e.value::text !~ '^(100|[0-9]{1,2})$'
      or not exists(select 1 from public.protagonist_definition d,
        lateral jsonb_array_elements(d.traits) t where t->>'key'=e.key)) end;
$$;
create or replace function public.valid_protagonist_scores(scores jsonb)
returns boolean language sql stable set search_path = '' as $$
  select public.valid_protagonist_baseline(scores) and
    (select count(*) from jsonb_object_keys(case when jsonb_typeof(scores)='object' then scores else '{}'::jsonb end))
      = (select jsonb_array_length(traits) from public.protagonist_definition where id);
$$;

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
