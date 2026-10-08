-- Read-only inspection. Run in Supabase SQL Editor before changing constraints.
-- No country schema migration is required: the app still stores text names.

-- Column type, domain (if any), nullability, and default.
select column_name, data_type, domain_schema, domain_name, is_nullable, column_default
from information_schema.columns
where table_schema = 'public' and table_name = 'profiles' and column_name = 'country';

-- All profile constraints, including checks that reference multiple fields.
-- Also includes constraints on a domain used by the country column.
select c.conname, c.contype, pg_get_constraintdef(c.oid) as definition
from pg_constraint c
where c.conrelid = 'public.profiles'::regclass
   or c.contypid = (
       select atttypid from pg_attribute
       where attrelid = 'public.profiles'::regclass and attname = 'country'
   );

-- Triggers may enforce additional country validation.
select t.tgname, pg_get_triggerdef(t.oid) as trigger_definition,
       p.oid::regprocedure as function_name, pg_get_functiondef(p.oid) as function_definition
from pg_trigger t
join pg_proc p on p.oid = t.tgfoid
where t.tgrelid = 'public.profiles'::regclass and not t.tgisinternal;

-- RLS can also contain country conditions. Preserve ownership/banned-user rules.
select policyname, permissive, roles, cmd, qual, with_check
from pg_policies where schemaname = 'public' and tablename = 'profiles';

-- Find other application functions that mention country (for manual review).
select p.oid::regprocedure as function_name, pg_get_functiondef(p.oid) as definition
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.prokind = 'f' and p.prosrc ilike '%country%';

-- Audit legacy text without modifying any reader's data.
select country, count(*) as profile_count
from public.profiles where country is not null
group by country order by country;

-- Only if inspection identifies a country-only constraint that conflicts with
-- the new names: replace the placeholder with that exact returned name.
-- Do not drop a constraint that also protects other fields.
-- alter table public.profiles drop constraint "EXACT_OBSOLETE_COUNTRY_CONSTRAINT_NAME";
