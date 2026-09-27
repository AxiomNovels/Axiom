-- Run after deploying the protagonist-only application changes.
-- Permanently removes the retired profile scores. RESTRICT prevents removal
-- if another database object still depends on either table.
begin;
set local lock_timeout = '5s';
drop table if exists public.philosophy_profiles restrict;
drop table if exists public.storytelling_style_profiles restrict;
commit;

-- Both results should be NULL after a successful migration.
select to_regclass('public.philosophy_profiles') as philosophy_table,
       to_regclass('public.storytelling_style_profiles') as storytelling_table;
