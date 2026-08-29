-- Run this migration in the Supabase SQL editor.
-- It makes the protagonist profile schema match the six measures rendered by
-- frontend/public/novel.js, then creates only Fang Yuan's profile.

begin;

alter table public.protagonist_profiles
  add column if not exists impulsivity smallint check (impulsivity between 0 and 100),
  add column if not exists arrogance_pride smallint check (arrogance_pride between 0 and 100),
  add column if not exists kinship_friendship smallint check (kinship_friendship between 0 and 100),
  add column if not exists romantic_attachment smallint check (romantic_attachment between 0 and 100),
  add column if not exists sexual_desire smallint check (sexual_desire between 0 and 100),
  add column if not exists selflessness smallint check (selflessness between 0 and 100);

comment on column public.protagonist_profiles.impulsivity is
  '0 = fully deliberate, 100 = acts without forethought';
comment on column public.protagonist_profiles.arrogance_pride is
  'Ego: 0 = humble, 100 = extremely egotistical';
comment on column public.protagonist_profiles.kinship_friendship is
  'Strength of bonds with family and friends';
comment on column public.protagonist_profiles.romantic_attachment is
  'Strength of romantic attachment';
comment on column public.protagonist_profiles.sexual_desire is
  'Prominence of sexual desire in the protagonist';
comment on column public.protagonist_profiles.selflessness is
  '0 = entirely self-interested, 100 = consistently self-sacrificing';

insert into public.protagonist_profiles (
  novel_id,
  protagonist_name,
  impulsivity,
  arrogance_pride,
  kinship_friendship,
  romantic_attachment,
  sexual_desire,
  selflessness
)
select
  id,
  'Fang Yuan',
  0,
  12,
  2,
  0,
  0,
  1
from public.novels
where lower(trim(title)) = 'reverend insanity'
on conflict (novel_id) do update set
  protagonist_name = excluded.protagonist_name,
  impulsivity = excluded.impulsivity,
  arrogance_pride = excluded.arrogance_pride,
  kinship_friendship = excluded.kinship_friendship,
  romantic_attachment = excluded.romantic_attachment,
  sexual_desire = excluded.sexual_desire,
  selflessness = excluded.selflessness;

-- Remove obsolete profile measures after the canonical values are in place.
alter table public.protagonist_profiles
  drop column if exists emotional_regulation,
  drop column if exists family_friend_bonds,
  drop column if exists partner_attachment,
  drop column if exists lustful_desire,
  drop column if exists intelligence,
  drop column if exists family_dynamics,
  drop column if exists individualism,
  drop column if exists collectivism,
  drop column if exists identity_change_growth,
  drop column if exists alienation_from_society,
  drop column if exists mental_health,
  drop column if exists anxiety,
  drop column if exists depression,
  drop column if exists toxic_relationships,
  drop column if exists emotional_repression,
  drop column if exists internal_consistency,
  drop column if exists adaptability,
  drop column if exists ambition,
  drop column if exists ruthlessness,
  drop column if exists emotional_attachment,
  drop column if exists strategic_thinking,
  drop column if exists long_term_planning,
  drop column if exists curiosity,
  drop column if exists compassion,
  drop column if exists manipulation;

commit;
