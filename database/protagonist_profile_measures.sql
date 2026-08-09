-- Run in the Supabase SQL editor to add the revised protagonist measures.
-- Existing columns remain in place so this change can be deployed safely.
alter table public.protagonist_profiles
  add column if not exists emotional_regulation smallint check (emotional_regulation between 0 and 100),
  add column if not exists arrogance_pride smallint check (arrogance_pride between 0 and 100),
  add column if not exists family_friend_bonds smallint check (family_friend_bonds between 0 and 100),
  add column if not exists partner_attachment smallint check (partner_attachment between 0 and 100),
  add column if not exists lustful_desire smallint check (lustful_desire between 0 and 100),
  add column if not exists intelligence smallint check (intelligence between 0 and 100),
  add column if not exists family_dynamics smallint check (family_dynamics between 0 and 100),
  add column if not exists individualism smallint check (individualism between 0 and 100),
  add column if not exists collectivism smallint check (collectivism between 0 and 100),
  add column if not exists identity_change_growth smallint check (identity_change_growth between 0 and 100),
  add column if not exists alienation_from_society smallint check (alienation_from_society between 0 and 100),
  add column if not exists mental_health smallint check (mental_health between 0 and 100),
  add column if not exists anxiety smallint check (anxiety between 0 and 100),
  add column if not exists depression smallint check (depression between 0 and 100),
  add column if not exists toxic_relationships smallint check (toxic_relationships between 0 and 100),
  add column if not exists emotional_repression smallint check (emotional_repression between 0 and 100);

comment on column public.protagonist_profiles.emotional_regulation is
  '0 = hot-blooded, 100 = deliberate';

-- Give existing demo profiles useful starting values by translating their
-- original measures. These are editorial starting points, not final ratings;
-- any values already entered in the new columns are preserved.
update public.protagonist_profiles
set
  emotional_regulation = coalesce(emotional_regulation, (internal_consistency + adaptability) / 2),
  arrogance_pride = coalesce(arrogance_pride, (ambition + ruthlessness) / 2),
  family_friend_bonds = coalesce(family_friend_bonds, emotional_attachment),
  partner_attachment = coalesce(partner_attachment, emotional_attachment),
  lustful_desire = coalesce(lustful_desire, ((100 - internal_consistency) + ambition) / 2),
  intelligence = coalesce(intelligence, (strategic_thinking + long_term_planning + curiosity) / 3),
  family_dynamics = coalesce(family_dynamics, (emotional_attachment + compassion) / 2),
  individualism = coalesce(individualism, (ambition + curiosity + (100 - emotional_attachment)) / 3),
  collectivism = coalesce(collectivism, (compassion + emotional_attachment) / 2),
  identity_change_growth = coalesce(identity_change_growth, adaptability),
  alienation_from_society = coalesce(
    alienation_from_society,
    (manipulation + ruthlessness + (100 - compassion)) / 3
  ),
  anxiety = coalesce(anxiety, 100 - internal_consistency),
  depression = coalesce(depression, 100 - ambition),
  toxic_relationships = coalesce(toxic_relationships, (manipulation + ruthlessness) / 2),
  emotional_repression = coalesce(emotional_repression, 100 - emotional_attachment),
  mental_health = coalesce(
    mental_health,
    ((100 - internal_consistency) + (100 - ambition) +
      ((manipulation + ruthlessness) / 2) + (100 - emotional_attachment)) / 4
  );
