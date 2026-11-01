-- Apply after admin_hub.sql and before deploying the reader latency changes.
-- Return only display badge IDs; never expose auth records to browser roles.
begin;
create or replace function public.reader_special_badges(user_ids uuid[])
returns table(id uuid)
language sql stable security definer set search_path = ''
as $$
  select u.id from auth.users u
  where u.id = any(user_ids)
    and u.raw_app_meta_data -> 'axiom_special' = 'true'::jsonb
    and u.raw_app_meta_data -> 'axiom_banned' is distinct from 'true'::jsonb;
$$;
revoke all on function public.reader_special_badges(uuid[]) from public, anon, authenticated;
grant execute on function public.reader_special_badges(uuid[]) to service_role;
commit;
