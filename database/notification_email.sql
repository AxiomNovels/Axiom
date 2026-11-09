-- Apply after admin_hub.sql and the existing Inbox notifications table.
-- Only new inserts queue mail.
begin;

create table if not exists public.notification_email_queue (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  subject text not null,
  body text not null,
  created_at timestamptz not null default now(),
  available_at timestamptz not null default now(),
  attempts integer not null default 0
);

alter table public.notification_email_queue enable row level security;
drop policy if exists axiom_banned_accounts on public.notification_email_queue;
create policy axiom_banned_accounts on public.notification_email_queue
  as restrictive for all to authenticated
  using (public.axiom_account_allowed()) with check (public.axiom_account_allowed());
revoke all on table public.notification_email_queue from public, anon, authenticated, service_role;
create index if not exists notification_email_queue_available_idx
  on public.notification_email_queue (available_at);

create or replace function public.queue_notification_email()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  insert into public.notification_email_queue (user_id, subject, body)
  values (new.user_id, new.subject, case
    when new.type in ('comment_reply', 'reading_list_comment') and new.data::jsonb ? 'reading_list_id'
      then 'You have new activity on a reading list.'
    else new.body
  end);
  return new;
exception when others then
  raise warning 'Could not queue inbox email: %', sqlstate;
  return new;
end;
$$;

revoke all on function public.queue_notification_email() from public, anon, authenticated, service_role;

drop trigger if exists notifications_queue_email on public.notifications;
create trigger notifications_queue_email after insert on public.notifications
  for each row execute function public.queue_notification_email();

create or replace function public.claim_notification_email()
returns table (id uuid, attempt integer, email text, subject text, body text)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  delete from public.notification_email_queue q
  where q.available_at <= now()
    and (q.created_at < now() - interval '7 days' or q.attempts >= 5);

  -- Resolve the current verified address when sending, including for welcome
  -- notices queued before the reader confirms their email.
  return query
  with candidate as (
    select q.id, u.email::text as email
    from public.notification_email_queue q
    join auth.users u on u.id = q.user_id
    where q.available_at <= now() and q.attempts < 5
      and q.created_at >= now() - interval '7 days'
      and u.email_confirmed_at is not null and nullif(btrim(u.email), '') is not null
      and (u.raw_app_meta_data ->> 'axiom_banned') is distinct from 'true'
    order by q.available_at, q.created_at, q.id
    limit 1
    for update of q skip locked
  )
  update public.notification_email_queue q
  set attempts = q.attempts + 1, available_at = now() + interval '5 minutes'
  from candidate c where q.id = c.id
  returning q.id, q.attempts, c.email, q.subject, q.body;
end;
$$;

create or replace function public.complete_notification_email(p_id uuid, p_attempt integer)
returns void
language sql
security definer
set search_path = pg_catalog, public
as $$
  delete from public.notification_email_queue where id = p_id and attempts = p_attempt;
$$;

revoke all on function public.claim_notification_email() from public, anon, authenticated, service_role;
revoke all on function public.complete_notification_email(uuid, integer) from public, anon, authenticated, service_role;
grant execute on function public.claim_notification_email() to service_role;
grant execute on function public.complete_notification_email(uuid, integer) to service_role;

commit;
