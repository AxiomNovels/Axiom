-- Run once in the Supabase SQL editor before using the admin hub.
-- Bind the privilege to wafflehunter's existing account ID, never signup metadata.
begin;
do $$
declare owner_id uuid;
begin
  select id into strict owner_id from public.profiles where lower(username) = 'wafflehunter';
  update auth.users
    set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
      || '{"axiom_special":true}'::jsonb
    where id = owner_id;
end $$;

-- Ordinary clients must not bypass the admin API to edit catalog scores.
revoke insert, update, delete on public.protagonist_profiles,
  public.philosophy_profiles, public.storytelling_style_profiles from anon, authenticated;

-- Read current server-owned ban state, including for previously issued JWTs.
create or replace function public.axiom_account_allowed()
returns boolean language sql stable security definer set search_path = ''
as $$
  select not exists (
    select 1 from auth.users
    where id = auth.uid() and raw_app_meta_data ->> 'axiom_banned' = 'true'
  );
$$;
revoke all on function public.axiom_account_allowed() from public;
grant execute on function public.axiom_account_allowed() to authenticated;

-- Restrictive policies combine with existing ownership/privacy policies.
-- Apply to all currently RLS-protected public tables to cover direct requests.
do $$
declare entry record;
begin
  for entry in select tablename from pg_tables
    where schemaname = 'public' and rowsecurity
  loop
    execute format('drop policy if exists axiom_banned_accounts on public.%I', entry.tablename);
    execute format('create policy axiom_banned_accounts on public.%I as restrictive for all to authenticated using (public.axiom_account_allowed()) with check (public.axiom_account_allowed())', entry.tablename);
  end loop;
end $$;
commit;

-- Later, grant your co-developer access using their verified account UUID:
-- update auth.users set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
--   || '{"axiom_special":true}'::jsonb where id = 'CO_DEVELOPER_ACCOUNT_UUID';
-- To revoke, use {"axiom_special":false} instead.
