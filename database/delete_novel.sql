-- Apply after the existing profile, reading-list, review/reply, Home feature,
-- protagonist voting/definition, rebuild, and admin_hub migrations.
-- notifications is the existing Inbox table. See docs/NOVEL_DELETION.md.
begin;

-- Upload history is an array rather than a foreign key. Keep stale concurrent
-- profile saves from restoring deleted IDs. Key locks serialize with deletion.
create or replace function public.validate_uploaded_novels()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  perform id from public.novels
    where id = any(new.novels_uploaded) order by id for key share;
  new.novels_uploaded := array(
    select entry.id from unnest(new.novels_uploaded) with ordinality entry(id, position)
    where exists (select 1 from public.novels n where n.id = entry.id)
    order by entry.position
  );
  return new;
end;
$$;
revoke all on function public.validate_uploaded_novels() from public, anon, authenticated;
drop trigger if exists profiles_validate_uploaded_novels on public.profiles;
create trigger profiles_validate_uploaded_novels
before insert or update of novels_uploaded on public.profiles
for each row execute function public.validate_uploaded_novels();

create or replace function public.delete_novel(p_novel_id bigint, p_actor_id uuid)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  target public.novels%rowtype;
  notified integer;
begin
  if not exists (
    select 1 from auth.users where id = p_actor_id
      and raw_app_meta_data->'axiom_special' = 'true'::jsonb
      and (raw_app_meta_data->'axiom_banned') is distinct from 'true'::jsonb
  ) then
    raise exception 'SPECIAL account access is required.' using errcode = '42501';
  end if;

  -- Match profile/vote/definition writers' lock ordering.
  perform pg_advisory_xact_lock(718204619);
  select * into target from public.novels where id = p_novel_id for update;
  if not found then
    raise exception 'Novel not found.' using errcode = 'P0002';
  end if;

  -- No API row limits; UNION deduplicates uploaders who also saved the novel.
  with uploaders as (
    update public.profiles
    set novels_uploaded = array_remove(novels_uploaded, p_novel_id)
    where p_novel_id = any(novels_uploaded) returning id
  ), recipients as (
    select id from uploaders
    union
    select user_id from public.reading_list_novels where novel_id = p_novel_id
  )
  insert into public.notifications(user_id, subject, body, type, data)
  select id, 'A novel was removed from Axiom',
    format('“%s” was deleted because it violated Axiom''s content policy. It has been removed from your reading lists and Uploaded Novels, wherever it appeared. Your account and other novels are unaffected.', target.title),
    'system', '{}'::jsonb from recipients;
  get diagnostics notified = row_count;

  -- Staging is optional on installations which only use direct uploads.
  if to_regclass('public.scrape_staging') is not null then
    execute 'delete from public.scrape_staging where published_novel_id = $1
      or source_url in (select link->>''url'' from jsonb_array_elements($2) link)'
      using p_novel_id, coalesce(nullif(to_jsonb(target)->'reading_links', 'null'::jsonb), '[]'::jsonb);
  end if;
  if to_regclass('public.review_likes') is not null then
    execute 'delete from public.review_likes where review_id in
      (select id from public.reviews where novel_id = $1)' using p_novel_id;
  end if;
  -- Home feature uses RESTRICT; older protagonist profile FKs use NO ACTION.
  delete from public.home_feature where novel_id = p_novel_id;
  delete from public.protagonist_baselines where novel_id = p_novel_id;
  delete from public.protagonist_profiles where novel_id = p_novel_id;
  update public.protagonist_rebuild_jobs j
  set total = greatest(0, j.total - case when i.status = 'not_needed' then 0 else 1 end),
      processed = greatest(0, j.processed - case when i.status in ('completed', 'failed') then 1 else 0 end),
      succeeded = greatest(0, j.succeeded - case when i.status = 'completed' then 1 else 0 end),
      failed = greatest(0, j.failed - case when i.status = 'failed' then 1 else 0 end)
  from public.protagonist_rebuild_items i
  where i.job_id = j.id and i.novel_id = p_novel_id;
  -- Cascades remove list membership, reviews, replies, reply likes, rebuild
  -- items and votes. Shared lists, user profiles and other novels survive.
  delete from public.novels where id = p_novel_id;
  return jsonb_build_object('deleted', true, 'notified_readers', notified);
end;
$$;

-- Only the backend service role can invoke this operation, even for admins.
revoke all on function public.delete_novel(bigint, uuid) from public, anon, authenticated;
grant execute on function public.delete_novel(bigint, uuid) to service_role;
revoke delete on public.novels from anon, authenticated;
notify pgrst, 'reload schema';
commit;
