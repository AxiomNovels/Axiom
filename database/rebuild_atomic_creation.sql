-- Apply after protagonist_rebuild_jobs.sql. No existing jobs are removed.
begin;
create or replace function public.create_protagonist_rebuild(
  p_requested_by uuid, p_include_complete boolean, p_novel_ids bigint[]
) returns jsonb language plpgsql security definer set search_path = public as $$
declare job public.protagonist_rebuild_jobs;
begin
  -- Serializes the check and insertion, including across API workers.
  perform pg_advisory_xact_lock(241017, 2);
  if exists (select 1 from public.protagonist_rebuild_jobs where status in ('queued','running')) then
    raise exception 'A protagonist-profile rebuild is already running.' using errcode = 'P0001';
  end if;
  insert into public.protagonist_rebuild_jobs(requested_by, mode, total)
  values (p_requested_by, case when p_include_complete then 'all' else 'outdated' end,
    (select count(*) from public.novels where id = any(p_novel_ids))) returning * into job;
  insert into public.protagonist_rebuild_items(job_id, novel_id, status)
  select job.id, id, case when id = any(p_novel_ids) then 'queued' else 'not_needed' end
  from public.novels;
  return to_jsonb(job);
end;
$$;
revoke all on function public.create_protagonist_rebuild(uuid, boolean, bigint[]) from public, anon, authenticated;
grant execute on function public.create_protagonist_rebuild(uuid, boolean, bigint[]) to service_role;
commit;
