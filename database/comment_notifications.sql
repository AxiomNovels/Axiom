-- Apply after reviews.sql, review_replies.sql, and the existing reading-list
-- reviews/replies, list visibility, friendships, profiles, and inbox schema.
-- See docs/COMMENT_NOTIFICATIONS.md. Safe to reapply; no historical backfill.
begin;

create or replace function public.notify_comment_activity()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  target_user uuid;
  owner_user uuid;
  list_id uuid;
  list_visibility text;
  novel_id bigint;
  review_id bigint;
  reply_id bigint;
  context_name text;
  sender_name text;
  recipient uuid;
  notice_type text;
  notice_subject text;
  notice_body text;
  notice_data jsonb;
begin
  -- UPDATE is used only for adding a comment to a rating-only list review.
  -- Ordinary edits, retries of the same upsert, and rating changes are silent.
  if nullif(btrim(new.comment), '') is null then
    return new;
  end if;
  if tg_op = 'UPDATE' then
    if nullif(btrim(old.comment), '') is not null then
      return new;
    end if;
  end if;

  if exists (select 1 from auth.users u where u.id = new.user_id
      and u.raw_app_meta_data ->> 'axiom_banned' = 'true') then
    return new;
  end if;

  select p.username into sender_name from public.profiles p where p.id = new.user_id;
  sender_name := coalesce(sender_name, 'A reader');

  if tg_table_name = 'review_replies' then
    review_id := new.review_id;
    reply_id := new.id;
    select r.user_id, r.novel_id, n.title into target_user, novel_id, context_name
      from public.reviews r join public.novels n on n.id = r.novel_id
      where r.id = new.review_id;
    if new.parent_reply_id is not null then
      select p.user_id into target_user from public.review_replies p
        where p.id = new.parent_reply_id and p.review_id = new.review_id;
    end if;
  elsif tg_table_name = 'reading_list_review_replies' then
    review_id := new.review_id;
    reply_id := new.id;
    select r.user_id, r.reading_list_id into target_user, list_id
      from public.reading_list_reviews r where r.id = new.review_id;
    if new.parent_reply_id is not null then
      select p.user_id into target_user from public.reading_list_review_replies p
        where p.id = new.parent_reply_id and p.review_id = new.review_id;
    end if;
  elsif tg_table_name = 'reading_list_reviews' then
    review_id := new.id;
    list_id := new.reading_list_id;
  else
    return new;
  end if;

  if list_id is not null then
    select l.user_id, l.name, l.visibility into owner_user, context_name, list_visibility
      from public.reading_lists l where l.id = list_id;
  end if;

  notice_data := jsonb_strip_nulls(jsonb_build_object(
    'sender_id', new.user_id, 'sender_username', sender_name,
    'novel_id', novel_id, 'reading_list_id', list_id, 'owner_id', owner_user,
    'review_id', review_id, 'reply_id', reply_id
  ));

  -- DISTINCT sends one notice when the reply target is also the list owner.
  for recipient in select distinct id from unnest(array[target_user, owner_user]) as recipients(id)
      where id is not null and id <> new.user_id
  loop
    if exists (select 1 from auth.users u where u.id = recipient
        and u.raw_app_meta_data ->> 'axiom_banned' = 'true') then
      continue;
    end if;
    -- A former reviewer may no longer be allowed to see this list. Mirror
    -- routes.users._visible_list_levels before disclosing new activity.
    if list_id is not null and recipient <> owner_user then
      if list_visibility = 'public' then
        null;
      elsif list_visibility = 'friends' and exists (
        select 1 from public.friendships f where f.status = 'accepted'
          and ((f.user_id_1 = recipient and f.user_id_2 = owner_user)
            or (f.user_id_2 = recipient and f.user_id_1 = owner_user))
      ) then
        null;
      else
        continue;
      end if;
    end if;

    if recipient = target_user then
      notice_type := 'comment_reply';
      notice_subject := 'New reply to your comment';
      notice_body := sender_name || ' replied to your comment on '
        || case when list_id is null then 'the novel "' else 'the reading list "' end
        || coalesce(context_name, 'Untitled') || '".';
    else
      notice_type := 'reading_list_comment';
      notice_subject := 'New comment on your reading list';
      notice_body := sender_name || ' commented on your reading list "'
        || coalesce(context_name, 'Untitled') || '".';
    end if;

    begin
      insert into public.notifications(user_id, subject, body, type, data)
        values (recipient, notice_subject, notice_body, notice_type, notice_data);
    exception when others then
      -- Match core.notifications: delivery must never prevent a comment save.
      raise warning 'Comment notification delivery failed: %', sqlstate;
    end;
  end loop;
  return new;
exception when others then
  raise warning 'Comment notification preparation failed: %', sqlstate;
  return new;
end;
$$;

-- Trigger-only entry point; clients cannot call it as an RPC. Existing table
-- grants, ownership checks, and RLS (including banned-account rules) stay intact.
revoke all on function public.notify_comment_activity() from public, anon, authenticated, service_role;

drop trigger if exists review_replies_notify_comment on public.review_replies;
create trigger review_replies_notify_comment after insert on public.review_replies
  for each row execute function public.notify_comment_activity();

drop trigger if exists reading_list_replies_notify_comment on public.reading_list_review_replies;
create trigger reading_list_replies_notify_comment after insert on public.reading_list_review_replies
  for each row execute function public.notify_comment_activity();

drop trigger if exists reading_list_reviews_notify_comment on public.reading_list_reviews;
create trigger reading_list_reviews_notify_comment after insert or update of comment on public.reading_list_reviews
  for each row execute function public.notify_comment_activity();

commit;
