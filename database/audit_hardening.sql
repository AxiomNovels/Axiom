-- Apply after profiles.sql, reading_lists.sql, review_replies.sql and admin_hub.sql.
-- This migration changes access rules, never deletes or rewrites user data.
begin;

-- The API publishes the appropriate public/friends-only profile fields. Direct
-- REST access must not bypass that filtering when new private columns are added.
drop policy if exists "Profiles are owner readable" on public.profiles;
create policy "Profiles are owner readable" on public.profiles
  as restrictive for select using (auth.uid() = id);

-- Deliberately a definer view: only the two public login fields are exposed.
create or replace view public.username_lookup with (security_barrier = true) as
  select id, username from public.profiles;
revoke all on public.username_lookup from public, anon, authenticated;
grant select on public.username_lookup to anon, authenticated, service_role;

drop policy if exists "Membership requires list ownership" on public.reading_list_novels;
create policy "Membership requires list ownership" on public.reading_list_novels
  as restrictive for all
  using (auth.uid() = user_id and exists (
    select 1 from public.reading_lists l
    where l.id = reading_list_id and l.user_id = auth.uid()
  ))
  with check (auth.uid() = user_id and exists (
    select 1 from public.reading_lists l
    where l.id = reading_list_id and l.user_id = auth.uid()
  ));

create or replace function public.keep_reply_thread()
returns trigger language plpgsql set search_path = public as $$
begin
  if new.parent_reply_id = new.id then
    raise exception 'A reply cannot be its own parent';
  end if;
  if tg_op = 'UPDATE' and
     (new.id, new.review_id, new.parent_reply_id, new.user_id) is distinct from
     (old.id, old.review_id, old.parent_reply_id, old.user_id) then
    raise exception 'A reply cannot change its thread or author';
  end if;
  return new;
end;
$$;
drop trigger if exists review_replies_keep_thread on public.review_replies;
create trigger review_replies_keep_thread before insert or update on public.review_replies
  for each row execute function public.keep_reply_thread();

-- Some installations have list discussions from an earlier schema. Apply the
-- same invariant there without inventing or altering the missing base table.
do $$ begin
  if to_regclass('public.reading_list_review_replies') is not null then
    execute 'drop trigger if exists list_review_replies_keep_thread on public.reading_list_review_replies';
    execute 'create trigger list_review_replies_keep_thread before insert or update on public.reading_list_review_replies for each row execute function public.keep_reply_thread()';
  end if;
end $$;
commit;
