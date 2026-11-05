-- Apply after the base public.novels table exists. Safe to reapply.
-- Keep novel IDs and all relationships intact; only genres are changed.
begin;

create or replace function public.canonicalize_novel_genres(p_genres text[])
returns text[]
language sql immutable strict
set search_path = pg_catalog
as $$
  select coalesce(array_agg(genre order by position), '{}'::text[])
  from (
    select genre, position,
           row_number() over (partition by genre order by position) as occurrence
    from (
      select case
               when lower(btrim(value, E' \t\n\r\f' || chr(11))) in ('nonfiction', 'non fiction', 'non-fiction')
               then 'Non-Fiction'
               else value
             end as genre,
             position
      from unnest(p_genres) with ordinality as entries(value, position)
    ) normalized
  ) numbered
  where genre is distinct from 'Non-Fiction' or occurrence = 1;
$$;

create or replace function public.normalize_novel_genres()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.genres := public.canonicalize_novel_genres(new.genres);
  return new;
end;
$$;

-- CREATE TRIGGER locks out concurrent writes until the backfill commits.
-- The invoker-security trigger preserves the table's grants and RLS policies.
drop trigger if exists normalize_novel_genres on public.novels;
create trigger normalize_novel_genres
before insert or update of genres on public.novels
for each row execute function public.normalize_novel_genres();

update public.novels
set genres = public.canonicalize_novel_genres(genres)
where genres is distinct from public.canonicalize_novel_genres(genres);

commit;
