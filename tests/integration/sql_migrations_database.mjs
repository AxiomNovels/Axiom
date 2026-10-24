// Execute every checked-in SQL file against isolated PostgreSQL with Supabase
// auth/role prerequisites. No network, real credentials, or live data are used.
import { PGlite } from "@electric-sql/pglite";
import { pgcrypto } from "@electric-sql/pglite/contrib/pgcrypto";
import { readFileSync, readdirSync } from "node:fs";
import assert from "node:assert/strict";

const directory = new URL("../../database/", import.meta.url);
const db = new PGlite({extensions: {pgcrypto}});
const applied = new Set();
const owner = "00000000-0000-0000-0000-000000000001";
const reader = "00000000-0000-0000-0000-000000000002";
const apply = async file => {
  try { await db.exec(readFileSync(new URL(file, directory), "utf8")); }
  catch (error) { throw new Error(`${file}: ${error.message}`, {cause: error}); }
  applied.add(file);
};

// These objects belong to Supabase/the existing application, not these migrations.
await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
  create schema auth;
  create table auth.users(id uuid primary key, raw_app_meta_data jsonb default '{}'::jsonb);
  create function auth.uid() returns uuid language sql stable as
    $$select nullif(current_setting('request.jwt.claim.sub', true),'')::uuid$$;
  grant usage on schema public, auth to anon, authenticated, service_role;
  alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
  alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
  create table public.novels(id bigint primary key, title text);
  create table public.protagonist_profiles(novel_id bigint unique references public.novels(id), protagonist_name text);
  create table public.philosophy_profiles(novel_id bigint);
  create table public.storytelling_style_profiles(novel_id bigint);
  insert into auth.users(id) values ('${owner}'),('${reader}');
  insert into public.novels values (1,'Reverend Insanity'),(2,'Another novel');`);

await apply("profiles.sql"); // A one-time base migration; not intended for reapplication.
await db.exec(`alter table public.profiles add column country text;
  insert into public.profiles(id,username,country) values
    ('${owner}','wafflehunter','Canada'),('${reader}','Reader','Canada');`);
await assert.rejects(db.query("insert into public.profiles(id,username) values (gen_random_uuid(),'WAFFLEHUNTER')"), /unique constraint/);
await apply("country_checks.sql"); // Inspection only.
for (const file of ["reading_lists.sql", "reviews.sql", "review_half_ratings.sql",
  "review_minimum_half_star.sql", "review_deletes.sql", "review_replies.sql",
  "user_presence.sql", "home_feature.sql"]) {
  await apply(file);
  await apply(file);
}
assert.equal((await db.query("select count(*)::int n from public.reading_lists where name='Favorites'")).rows[0].n, 2);
await db.exec("insert into auth.users(id) values ('00000000-0000-0000-0000-000000000003')");
assert.equal((await db.query("select count(*)::int n from public.reading_lists where name='Favorites'")).rows[0].n, 3);
await db.query("insert into public.reviews(id,novel_id,user_id,rating,comment) values (1,1,$1,2.5,'Original review'),(2,2,$1,4,'Other review')", [owner]);
for (const rating of [0, 1.1, 5.5]) {
  await assert.rejects(db.query("insert into public.reviews(novel_id,user_id,rating) values (1,$1,$2)", [reader, rating]), /check constraint/);
}
await db.query("insert into public.review_replies(id,review_id,user_id,comment) values (1,1,$1,'First reply')", [reader]);
await db.query("insert into public.review_replies(id,review_id,parent_reply_id,user_id,comment) values (2,1,1,$1,'Nested reply')", [owner]);
await assert.rejects(db.query("insert into public.review_replies(review_id,parent_reply_id,user_id,comment) values (2,1,$1,'Wrong review')", [owner]), /same review/);
await db.query("insert into public.review_reply_likes(reply_id,user_id) values (2,$1)", [reader]);
await db.exec("update public.review_replies set comment='Edited reply' where id=2");
await db.exec("insert into public.home_feature(novel_id,inquiry,description) values (1,'A test inquiry','A test feature description')");
await db.exec("update public.home_feature set inquiry='An updated inquiry' where id");

for (const file of ["protagonist_profile_measures.sql", "protagonist_votes.sql",
  "protagonist_vote_controls.sql", "protagonist_profile_traits_v2.sql",
  "protagonist_rebuild_jobs.sql", "admin_hub.sql", "manage_protagonist_profile.sql",
  "remove_retired_profiles.sql"]) await apply(file);
for (const file of ["protagonist_rebuild_jobs.sql", "admin_hub.sql", "manage_protagonist_profile.sql", "remove_retired_profiles.sql"]) await apply(file);
for (const file of ["audit_hardening.sql", "rebuild_atomic_creation.sql", "analytics.sql"]) {
  await apply(file);
  await apply(file);
}
// Private profile fields cannot be read through the direct REST table, even
// with the original permissive public SELECT policy still installed.
await db.exec("alter table public.profiles add column discord_username text");
await db.query("update public.profiles set discord_username='private-handle' where id=$1", [owner]);
await db.query("select set_config('request.jwt.claim.sub',$1,false)", [reader]);
await db.exec("set role authenticated");
assert.deepEqual((await db.query("select id from public.profiles")).rows.map(r => r.id), [reader]);
assert.equal((await db.query("select count(*)::int n from public.username_lookup")).rows[0].n, 2);
await assert.rejects(db.query("select discord_username from public.username_lookup"), /does not exist/);
await db.exec("reset role");
const ownerList = (await db.query("select id from public.reading_lists where user_id=$1", [owner])).rows[0].id;
const readerList = (await db.query("select id from public.reading_lists where user_id=$1", [reader])).rows[0].id;
await db.exec("set role authenticated");
await assert.rejects(db.query("insert into public.reading_list_novels(reading_list_id,novel_id,user_id) values ($1,1,$2)", [ownerList, reader]), /row-level security/);
await db.query("insert into public.reading_list_novels(reading_list_id,novel_id,user_id) values ($1,1,$2)", [readerList, reader]);
await assert.rejects(db.query("update public.reading_list_novels set reading_list_id=$1 where user_id=$2", [ownerList, reader]), /row-level security/);
await assert.rejects(db.query("update public.review_replies set parent_reply_id=2 where id=1"), /cannot change/);
await assert.rejects(db.query("update public.review_replies set parent_reply_id=1 where id=1"), /own parent/);
await db.query("update public.review_replies set comment='Safe edit' where id=1");
await db.exec("reset role; set role anon");
await db.query("select set_config('request.jwt.claim.sub','',false)");
assert.equal((await db.query("select count(*)::int n from public.profiles")).rows[0].n, 0);
assert.equal((await db.query("select count(*)::int n from public.username_lookup")).rows[0].n, 2);
await assert.rejects(db.query("select public.create_protagonist_rebuild($1,true,array[1,2]::bigint[])", [owner]), /permission denied/);
await db.exec("reset role; set role service_role");
const job = (await db.query("select public.create_protagonist_rebuild($1,false,array[1]::bigint[]) job", [owner])).rows[0].job;
assert.equal(job.total, 1);
assert.deepEqual((await db.query("select status from public.protagonist_rebuild_items where job_id=$1 order by novel_id", [job.id])).rows.map(r => r.status), ['queued','not_needed']);
await assert.rejects(db.query("select public.create_protagonist_rebuild($1,true,array[1,2]::bigint[])", [owner]), /already running/);
assert.equal((await db.query("select count(*)::int n from public.protagonist_rebuild_jobs")).rows[0].n, 1);
await db.exec("reset role");
assert.equal((await db.query("select raw_app_meta_data->>'axiom_special' special from auth.users where id=$1", [owner])).rows[0].special, "true");
assert.equal((await db.query("select to_regclass('public.philosophy_profiles') t")).rows[0].t, null);
assert.equal((await db.query("select to_regclass('public.storytelling_style_profiles') t")).rows[0].t, null);
const definition = (await db.query("select public.get_protagonist_definition() d")).rows[0].d;
assert.equal(definition.traits.length, 7);
// The HTTP API calls these functions by argument name. Preserve its contracts.
for (const [signature, names] of [
  ["public.save_gemini_protagonist(bigint,text,jsonb,bigint)", ["p_novel_id", "p_name", "p_scores", "p_revision"]],
  ["public.save_protagonist_profile(bigint,text,jsonb,bigint,boolean)", ["p_novel_id", "p_name", "p_scores", "p_revision", "p_generated"]],
  ["public.cast_protagonist_vote(bigint,uuid,text,integer,bigint)", ["p_novel_id", "p_user_id", "p_trait", "p_score", "p_revision"]],
  ["public.set_protagonist_score_lock(bigint,boolean)", ["p_novel_id", "p_locked"]],
  ["public.protagonist_vote_summary(bigint,uuid)", ["p_novel_id", "p_user_id"]],
  ["public.update_protagonist_definition(bigint,text,jsonb)", ["p_revision", "p_instructions", "p_traits"]],
]) {
  assert.deepEqual((await db.query("select proargnames from pg_proc where oid=$1::regprocedure", [signature])).rows[0].proargnames, names, signature);
}
await db.query("select public.save_gemini_protagonist(1,'Hero',$1,$2)", [Object.fromEntries(definition.traits.map(t => [t.key, 20])), definition.revision]);
await db.query("select public.cast_protagonist_vote(1,$1,'intelligence',100,$2)", [reader, definition.revision]);
assert.equal((await db.query("select intelligence from public.protagonist_profiles where novel_id=1")).rows[0].intelligence, 60);

// Exercise the real Admin Hub ban predicate and RLS, not an always-true stub.
await db.query("select set_config('request.jwt.claim.sub',$1,false)", [owner]);
await db.exec("set role authenticated");
assert.equal((await db.query("select count(*)::int n from public.reading_lists")).rows[0].n, 1);
assert.equal((await db.query("select count(*)::int n from public.reviews")).rows[0].n, 2);
await assert.rejects(db.query("select public.update_protagonist_definition($1,$2,$3)", [definition.revision, definition.instructions, definition.traits]), /permission denied/);
await db.exec("reset role");
await db.query("update auth.users set raw_app_meta_data=raw_app_meta_data || '{\"axiom_banned\":true}'::jsonb where id=$1", [owner]);
await db.exec("set role authenticated");
assert.equal((await db.query("select count(*)::int n from public.reading_lists")).rows[0].n, 0);
assert.equal((await db.query("select count(*)::int n from public.reviews")).rows[0].n, 0);
await assert.rejects(db.query("insert into public.reviews(novel_id,user_id,rating) values (1,$1,3)", [owner]), /row-level security/);
await db.exec("reset role");

// The protagonist migrations must leave unrelated reviews and lists untouched.
assert.equal((await db.query("select comment from public.reviews where id=1")).rows[0].comment, "Original review");
assert.equal((await db.query("select count(*)::int n from public.reading_lists")).rows[0].n, 3);
await db.exec("delete from public.reviews where id=1");
assert.equal((await db.query("select count(*)::int n from public.review_replies")).rows[0].n, 0);
assert.equal((await db.query("select count(*)::int n from public.review_reply_likes")).rows[0].n, 0);
// Inbox and scraper tables predate the checked-in migrations.
await db.exec(`alter table public.novels add column reading_links jsonb default '[]';
  create table public.notifications (
    id uuid primary key default gen_random_uuid(), user_id uuid references auth.users(id),
    subject text not null, body text not null, type text not null default 'system',
    data jsonb not null default '{}', is_read boolean not null default false);
  create table public.scrape_staging(id bigint primary key, published_novel_id bigint,
    source_url text, raw_payload jsonb);
  create table public.review_likes(review_id bigint references public.reviews(id), user_id uuid);
  update auth.users set raw_app_meta_data = raw_app_meta_data - 'axiom_banned';`);
await apply("delete_novel.sql");
await apply("delete_novel.sql");
const removeNovel = (id, actor = owner) => db.query("select public.delete_novel($1,$2) result", [id, actor]);
// Exercise cleanup with real current trait/vote triggers and a NO ACTION profile FK.
await db.exec(`update public.novels set reading_links='[{"url":"https://example.test/novel/1"}]' where id=1;
  insert into public.scrape_staging values
    (1,1,'https://example.test/old','{}'),
    (2,null,'https://example.test/novel/1','{"title":"Staged duplicate"}'),
    (3,2,'https://example.test/novel/2','{}');`);
await db.query("update public.profiles set novels_uploaded=array[1,2,1]::bigint[] where id=$1", [reader]);
await db.query("insert into public.reviews(id,novel_id,user_id,rating) values (10,1,$1,4)", [reader]);
await db.query("insert into public.review_replies(id,review_id,user_id,comment) values (10,10,$1,'Delete me')", [owner]);
await db.query("insert into public.review_reply_likes(reply_id,user_id) values (10,$1)", [reader]);
await db.query("insert into public.review_likes values (10,$1),(2,$1)", [reader]);
// One uploader-only user, one list-only user and one user in both groups.
await db.query("update public.profiles set novels_uploaded=array[1]::bigint[] where id=$1", [owner]);
const third = '00000000-0000-0000-0000-000000000003';
await db.query("insert into public.reading_list_novels(reading_list_id,novel_id,user_id) select id,1,user_id from public.reading_lists where user_id=$1", [third]);
await db.query("insert into public.reading_list_novels(reading_list_id,novel_id,user_id) values ($1,2,$2)", [readerList, reader]);
for (const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`);
  await assert.rejects(removeNovel(1), /permission denied/);
  await assert.rejects(db.exec('delete from public.novels where id=1'), /permission denied/);
  await db.exec('reset role');
}
await db.exec('set role service_role');
await assert.rejects(removeNovel(1, reader), /SPECIAL/);
await db.exec('reset role');
await db.query("update auth.users set raw_app_meta_data = raw_app_meta_data || '{\"axiom_banned\":true}' where id=$1", [owner]);
await db.exec('set role service_role');
await assert.rejects(removeNovel(1), /SPECIAL/);
await db.exec('reset role');
await db.query("update auth.users set raw_app_meta_data = raw_app_meta_data - 'axiom_banned' where id=$1", [owner]);
// Failed notice delivery rolls back upload cleanup and leaves all novel data.
await db.exec("alter table public.notifications add constraint fail_delivery check (false)");
await db.exec('set role service_role');
await assert.rejects(removeNovel(1), /fail_delivery/);
await db.exec('reset role');
assert.deepEqual((await db.query('select novels_uploaded from public.profiles where id=$1', [reader])).rows[0].novels_uploaded, [1,2,1]);
assert.equal((await db.query('select count(*)::int n from public.novels')).rows[0].n, 2);
await db.exec('alter table public.notifications drop constraint fail_delivery');
// Failure late in cleanup rolls back notices too.
await db.exec('create table public.deletion_blocker(novel_id bigint references public.novels(id)); insert into public.deletion_blocker values (1)');
await db.exec('set role service_role');
await assert.rejects(removeNovel(1), /foreign key/);
await db.exec('reset role');
assert.equal((await db.query('select count(*)::int n from public.notifications')).rows[0].n, 0);
assert.equal((await db.query('select count(*)::int n from public.protagonist_votes where novel_id=1')).rows[0].n, 1);
await db.exec('drop table public.deletion_blocker; set role service_role');
assert.deepEqual((await removeNovel(1)).rows[0].result, {deleted:true,notified_readers:3});
await assert.rejects(removeNovel(1), /Novel not found/);
await db.exec('reset role');
for (const table of ['novels','protagonist_profiles','protagonist_baselines','protagonist_votes','reading_list_novels','reviews','protagonist_rebuild_items','home_feature']) {
  const column = table === 'novels' ? 'id' : 'novel_id';
  assert.equal((await db.query(`select count(*)::int n from public.${table} where ${column}=1`)).rows[0].n, 0, table);
}
for (const table of ['review_replies','review_reply_likes']) {
  assert.equal((await db.query(`select count(*)::int n from public.${table}`)).rows[0].n, 0, table);
}
assert.deepEqual((await db.query('select id from public.scrape_staging')).rows, [{id:3}]);
assert.equal((await db.query('select count(*)::int n from public.review_likes')).rows[0].n, 1);
assert.equal((await db.query('select count(*)::int n from public.reading_lists')).rows[0].n, 3);
assert.equal((await db.query('select count(*)::int n from public.reading_list_novels where novel_id=2')).rows[0].n, 1);
assert.equal((await db.query('select comment from public.reviews where id=2')).rows[0].comment, 'Other review');
assert.deepEqual((await db.query('select novels_uploaded from public.profiles where id=$1', [reader])).rows[0].novels_uploaded, [2]);
await db.query('update public.profiles set novels_uploaded=array[1,2]::bigint[] where id=$1', [reader]);
assert.deepEqual((await db.query('select novels_uploaded from public.profiles where id=$1', [reader])).rows[0].novels_uploaded, [2]);
const notices = (await db.query('select * from public.notifications')).rows;
assert.equal(notices.length, 3);
assert.equal(new Set(notices.map(n => n.user_id)).size, 3);
for (const notice of notices) {
  assert.equal(notice.is_read, false);
  assert.equal(notice.type, 'system');
  assert.deepEqual(notice.data, {});
  assert.match(notice.body, /Reverend Insanity.*violated Axiom's content policy/);
}
// Recipient delivery is not truncated at PostgREST's usual 1,000-row limit.
await db.exec(`insert into auth.users(id) select md5('delete-reader-' || i)::uuid from generate_series(1,1100) i;
  insert into public.profiles(id,username,novels_uploaded)
  select md5('delete-reader-' || i)::uuid, 'Deletion reader ' || i, array[2]::bigint[] from generate_series(1,1100) i;
  drop table public.scrape_staging;
  set role service_role;`);
assert.deepEqual((await removeNovel(2)).rows[0].result, {deleted:true,notified_readers:1101});
await db.exec('reset role');
assert.equal((await db.query('select count(*)::int n from public.notifications')).rows[0].n, 1104);
assert.equal((await db.query('select count(*)::int n from public.profiles where cardinality(novels_uploaded)>0')).rows[0].n, 0);
assert.deepEqual([...applied].sort(), readdirSync(directory).filter(name => name.endsWith(".sql")).sort());
await db.close();
console.log(`All ${applied.size} SQL files executed successfully: ordered installation, repeatable migrations, constraints, triggers, RLS, bans, and preservation checks.`);
