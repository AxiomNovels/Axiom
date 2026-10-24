-- Stage 1 analytics. Apply AFTER profiles.sql and admin_hub.sql.
-- No browser/database grants: collection and reports go through the backend.
begin;
create table if not exists public.analytics_sessions (
  id uuid primary key,
  started_at timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  active_until timestamptz not null default now(),
  user_id uuid references auth.users(id) on delete set null,
  country text not null default 'XX',
  entry_page text not null,
  exit_page text not null
);
create table if not exists public.analytics_events (
  id uuid primary key,
  occurred_at timestamptz not null default now(),
  session_id uuid references public.analytics_sessions(id) on delete cascade,
  user_id uuid references auth.users(id) on delete set null,
  event text not null check (event in ('page_view','heartbeat','request')),
  path text not null check (length(path) <= 240),
  country text not null default 'XX' check (country ~ '^[A-Z]{2}$'),
  source text not null check (source in ('browser','frontend','backend')),
  kind text not null default 'page',
  status integer,
  active_seconds integer not null default 0 check (active_seconds between 0 and 30)
);
create index if not exists analytics_events_time on public.analytics_events(occurred_at);
create index if not exists analytics_events_session on public.analytics_events(session_id, occurred_at);
create index if not exists analytics_sessions_time on public.analytics_sessions(started_at);
create table if not exists public.analytics_ip_logs (
  event_id uuid primary key references public.analytics_events(id) on delete cascade,
  occurred_at timestamptz not null default now(),
  ip inet not null
);
create index if not exists analytics_ip_time on public.analytics_ip_logs(occurred_at);

alter table public.analytics_sessions enable row level security;
alter table public.analytics_events enable row level security;
alter table public.analytics_ip_logs enable row level security;
revoke all on public.analytics_sessions, public.analytics_events, public.analytics_ip_logs from public, anon, authenticated;
grant all on public.analytics_sessions, public.analytics_events, public.analytics_ip_logs to service_role;
do $$ declare t text; begin
  foreach t in array array['analytics_sessions','analytics_events','analytics_ip_logs'] loop
    execute format('drop policy if exists axiom_banned_accounts on public.%I',t);
    execute format('create policy axiom_banned_accounts on public.%I as restrictive for all to authenticated using (public.axiom_account_allowed()) with check (public.axiom_account_allowed())',t);
  end loop;
end $$;

create or replace function public.analytics_ingest(p_events jsonb)
returns void language plpgsql security definer set search_path = '' as $$
declare e jsonb; sid uuid; uid uuid; credited integer; previous timestamptz; inserted integer;
begin
  if jsonb_array_length(p_events) > 100 then raise exception 'Batch too large'; end if;
  for e in select value from jsonb_array_elements(p_events) loop
    sid := nullif(e->>'session_id','')::uuid;
    uid := nullif(e->>'user_id','')::uuid;
    credited := 0;
    if sid is not null then
      insert into public.analytics_sessions(id,user_id,country,entry_page,exit_page)
        values(sid,uid,e->>'country',e->>'path',e->>'path') on conflict do nothing;
      select active_until into previous from public.analytics_sessions where id=sid for update;
      if e->>'event' = 'heartbeat' then
        credited := least(30, greatest(0, coalesce((e->>'active_seconds')::integer,0)),
          greatest(0,floor(extract(epoch from clock_timestamp()-previous))::integer));
      end if;
    end if;
    insert into public.analytics_events(id,session_id,user_id,event,path,country,source,kind,status,active_seconds)
      values((e->>'id')::uuid,sid,uid,e->>'event',e->>'path',e->>'country',e->>'source',e->>'kind',
        nullif(e->>'status','')::integer,credited) on conflict do nothing;
    get diagnostics inserted = row_count;
    if inserted = 0 then continue; end if;
    if sid is not null then
      update public.analytics_sessions set last_seen=now(), active_until=clock_timestamp(),
        exit_page=e->>'path', user_id=coalesce(uid,user_id) where id=sid;
    end if;
    if nullif(e->>'ip','') is not null then
      insert into public.analytics_ip_logs(event_id,ip) values((e->>'id')::uuid,(e->>'ip')::inet);
    end if;
  end loop;
end $$;

create or replace function public.analytics_cleanup()
returns void language plpgsql security definer set search_path = '' as $$ begin
  delete from public.analytics_ip_logs where occurred_at < now()-interval '7 days';
  delete from public.analytics_events where occurred_at < now()-interval '90 days';
  delete from public.analytics_sessions s where s.last_seen < now()-interval '90 days'
    and not exists(select 1 from public.analytics_events e where e.session_id=s.id);
end $$;

create or replace function public.analytics_report(p_start date, p_end date, p_country text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare result jsonb;
begin
  if p_end < p_start or p_end-p_start > 89 then raise exception 'Choose up to 90 days'; end if;
  with e as (
    select * from public.analytics_events where occurred_at >= p_start::timestamp at time zone 'UTC'
      and occurred_at < (p_end+1)::timestamp at time zone 'UTC'
      and (p_country is null or country=p_country)
  ), s as (
    select * from public.analytics_sessions where started_at >= p_start::timestamp at time zone 'UTC'
      and started_at < (p_end+1)::timestamp at time zone 'UTC'
      and (p_country is null or country=p_country)
  ), prev as (
    select * from public.analytics_events where occurred_at >= (p_start-(p_end-p_start+1))::timestamp at time zone 'UTC'
      and occurred_at < p_start::timestamp at time zone 'UTC' and (p_country is null or country=p_country)
  ), daily as (
    select (occurred_at at time zone 'UTC')::date bucket_date,
      count(*) filter(where event='page_view') page_views,
      count(*) filter(where event='request' and source='frontend') frontend_requests,
      count(*) filter(where event='request' and source='backend') backend_requests,
      coalesce(sum(active_seconds),0) active_seconds from e group by 1
  ), countries as (
    select country, count(*) filter(where event='page_view') page_views,
      count(*) filter(where event='request') requests, count(distinct session_id) engaged_sessions,
      coalesce(sum(active_seconds),0) active_seconds from e group by country
  )
  select jsonb_build_object(
    'totals',jsonb_build_object('page_views',(select count(*) from e where event='page_view'),
      'visits',(select count(*) from s),'anonymous_visits',(select count(*) from s where user_id is null),
      'signed_in_accounts',(select count(distinct user_id) from e),
      'frontend_requests',(select count(*) from e where event='request' and source='frontend'),
      'backend_requests',(select count(*) from e where event='request' and source='backend'),
      'active_seconds',(select coalesce(sum(active_seconds),0) from e),
      'engaged_sessions',(select count(distinct session_id) from e),
      'signups',case when p_country is null then (select count(*) from auth.users where created_at >= p_start::timestamp at time zone 'UTC' and created_at < (p_end+1)::timestamp at time zone 'UTC') else null end),
    'previous',jsonb_build_object('page_views',(select count(*) from prev where event='page_view'),
      'requests',(select count(*) from prev where event='request'), 'active_seconds',(select coalesce(sum(active_seconds),0) from prev)),
    'daily',coalesce((select jsonb_agg(jsonb_build_object('date',d.bucket_date::date,'page_views',coalesce(a.page_views,0),
      'frontend_requests',coalesce(a.frontend_requests,0),'backend_requests',coalesce(a.backend_requests,0),
      'active_seconds',coalesce(a.active_seconds,0),'visits',(select count(*) from s where (started_at at time zone 'UTC')::date=d.bucket_date::date),
      'signups',case when p_country is null then (select count(*) from auth.users where (created_at at time zone 'UTC')::date=d.bucket_date::date) else null end) order by d.bucket_date)
      from generate_series(p_start::timestamp,p_end::timestamp,interval '1 day') d(bucket_date) left join daily a on a.bucket_date=d.bucket_date::date),'[]'::jsonb),
    'hourly',coalesce((select jsonb_agg(to_jsonb(h) order by h.hour) from (
      select extract(hour from occurred_at at time zone 'UTC')::integer "hour",
      count(*) filter(where event='page_view') page_views, count(*) filter(where event='request') requests from e group by 1) h),'[]'::jsonb),
    'countries',coalesce((select jsonb_agg(to_jsonb(c) order by c.page_views desc,c.country) from countries c),'[]'::jsonb),
    'pages',coalesce((select jsonb_agg(to_jsonb(p)) from (select path,count(*) page_views,
      (select count(*) from s where entry_page=e.path) entrances,
      (select count(*) from s where exit_page=e.path) last_pages
      from e where event='page_view' group by path order by count(*) desc limit 100) p),'[]'::jsonb),
    'request_types',coalesce((select jsonb_agg(to_jsonb(r)) from (select source,kind,count(*) requests from e where event='request' group by source,kind) r),'[]'::jsonb),
    'accounts',coalesce((select jsonb_agg(to_jsonb(a)) from (select e.user_id,
      coalesce(p.username,'Deleted account') username,count(distinct session_id) sessions,
      count(*) filter(where event='page_view') page_views,sum(active_seconds) active_seconds
      from e left join public.profiles p on p.id=e.user_id where e.user_id is not null
      group by e.user_id,p.username order by sum(active_seconds) desc limit 100) a),'[]'::jsonb),
    'latest_event',(select max(occurred_at) from public.analytics_events)
  ) into result;
  return result;
end $$;
revoke all on function public.analytics_ingest(jsonb),public.analytics_cleanup(),public.analytics_report(date,date,text) from public,anon,authenticated;
grant execute on function public.analytics_ingest(jsonb),public.analytics_cleanup(),public.analytics_report(date,date,text) to service_role;
commit;
-- Schedule SELECT public.analytics_cleanup() hourly using Supabase Cron.
-- This is required even during periods without website traffic. See ANALYTICS.md.
