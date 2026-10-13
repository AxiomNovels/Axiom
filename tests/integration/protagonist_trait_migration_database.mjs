// Verify both sides of the merge together without contacting Supabase.
import { PGlite } from "@electric-sql/pglite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const sql = file => readFileSync(new URL(`../../database/${file}`, import.meta.url), "utf8");
const seed = JSON.parse(readFileSync(new URL("../../backend/profiler/default_definition.json", import.meta.url), "utf8"));
const legacy = ["impulsivity", "arrogance_pride", "kinship_friendship", "romantic_attachment", "sexual_desire", "selflessness"];
const user = "00000000-0000-0000-0000-000000000001";
for (const [argumentName, rowArgumentName] of [["p_scores", "p_rows"], ["scores", "profile"], ["p_scores", "p_row"], [null, null]]) {
  const db = new PGlite();
  const definition = async () => (await db.query("select public.get_protagonist_definition() d")).rows[0].d;
  const summary = async () => (await db.query("select public.protagonist_vote_summary(1,$1) s", [user])).rows[0].s;
  await db.exec(`create role anon; create role authenticated; create role service_role;
    create function public.axiom_account_allowed() returns boolean language sql as 'select true';
    create table public.novels(id bigint primary key, title text);
    create table public.profiles(id uuid primary key);
    create table public.protagonist_profiles(novel_id bigint unique references public.novels on delete cascade, protagonist_name text);
    insert into public.novels values (1,'Test novel');
    insert into public.profiles values ('${user}');`);
  // Supabase may already contain either historical argument name, or no name.
  // A dependent CHECK prevents a drop/recreate workaround from silently passing.
  await db.exec(`create function public.valid_protagonist_scores(${argumentName || ""} jsonb)
    returns boolean language sql immutable as 'select true';
    revoke all on function public.valid_protagonist_scores(jsonb) from public;
    grant execute on function public.valid_protagonist_scores(jsonb) to service_role;
    create table public.validator_dependency(scores jsonb check(public.valid_protagonist_scores(scores)));`);
  await db.exec(`create function public.protagonist_score_values(${rowArgumentName || ""} jsonb)
    returns jsonb language sql immutable as 'select $1';
    create function public.valid_protagonist_baseline(${argumentName || ""} jsonb)
    returns boolean language sql stable as 'select true';
    create view public.score_values_dependency as select public.protagonist_score_values('{}'::jsonb);
    create table public.baseline_dependency(scores jsonb check(public.valid_protagonist_baseline(scores)));`);
  const helpersBefore = (await db.query(`select oid from pg_proc where oid in (
    'public.protagonist_score_values(jsonb)'::regprocedure,
    'public.valid_protagonist_baseline(jsonb)'::regprocedure) order by oid`)).rows;
  const validatorBefore = (await db.query("select oid, proacl from pg_proc where oid='public.valid_protagonist_scores(jsonb)'::regprocedure")).rows[0];
  for (const file of ["protagonist_profile_measures.sql", "protagonist_votes.sql", "protagonist_vote_controls.sql"]) {
    await db.exec(sql(file));
  }
  await db.exec(sql("protagonist_vote_controls.sql"));
  assert.deepEqual((await db.query("select oid, proacl from pg_proc where oid='public.valid_protagonist_scores(jsonb)'::regprocedure")).rows[0], validatorBefore);
  await db.exec(`insert into public.protagonist_profiles(novel_id,protagonist_name,${legacy.join(",")})
    values(1,'Hero',${legacy.map(() => 40).join(",")});
    select public.cast_protagonist_vote(1,'${user}','arrogance_pride',100);
    select public.set_protagonist_score_lock(1,true);`);
  await db.exec(sql("protagonist_profile_traits_v2.sql"));
  let s = await summary();
  assert.equal(s.profile.protagonist_name, "Hero");
  assert.equal(s.eligible, false);
  assert.equal(s.scores_locked, false);
  assert.equal(s.vote_count, 0);
  assert.equal(s.baseline, null);
  assert.ok(seed.traits.every(t => s.profile[t.key] === null));
  assert.equal(s.profile.impulsivity, undefined);

  // The incoming seven-trait migration must work before enabling dynamic definitions.
  const scores = Object.fromEntries(seed.traits.map(t => [t.key, 20]));
  await db.query("select public.save_gemini_protagonist(1,'Hero',$1)", [scores]);
  await db.query("select public.cast_protagonist_vote(1,$1,'intelligence',100)", [user]);
  assert.equal((await summary()).profile.intelligence, 60);
  await db.exec(sql("manage_protagonist_profile.sql"));
  assert.deepEqual(await definition(), seed);
  assert.equal((await summary()).baseline.intelligence, 20);
  assert.equal((await summary()).profile.intelligence, 60);
  assert.equal((await summary()).my_votes.intelligence, 100);

  // Reapplying the legacy reset after Admin Hub setup must fail before touching data
  // or restoring unsafe, unversioned save/vote overloads.
  const before = await summary();
  for (const file of ["protagonist_profile_measures.sql", "protagonist_votes.sql", "protagonist_vote_controls.sql", "protagonist_profile_traits_v2.sql"]) {
    await assert.rejects(db.exec(sql(file)), /managed by the Admin Hub/);
    await db.exec("rollback");
    assert.deepEqual(await summary(), before);
    assert.deepEqual(await definition(), seed);
  }
  const signatures = (await db.query(`select
    to_regprocedure('public.save_gemini_protagonist(bigint,text,jsonb)') as old_save,
    to_regprocedure('public.cast_protagonist_vote(bigint,uuid,text,integer)') as old_vote`)).rows[0];
  assert.deepEqual(signatures, {old_save: null, old_vote: null});

  const custom = [{key: "resilience", name: "Resilience", prompt: "0 gives up; 100 perseveres."}];
  const revised = (await db.query("select public.update_protagonist_definition($1,$2,$3) d", [seed.revision, seed.instructions, custom])).rows[0].d;
  await assert.rejects(db.query("select public.save_gemini_protagonist(1,'Hero',$1,$2)", [scores, seed.revision]), /changed/);
  await db.query("select public.save_gemini_protagonist(1,'Hero',$1,$2)", [{resilience: 0}, revised.revision]);
  await db.query("select public.cast_protagonist_vote(1,$1,'resilience',100,$2)", [user, revised.revision]);
  assert.equal((await summary()).profile.resilience, 50);
  await db.exec(sql("manage_protagonist_profile.sql"));
  assert.deepEqual(await definition(), revised);
  assert.equal((await summary()).profile.resilience, 50);
  const validatorAfter = (await db.query("select oid, proargnames from pg_proc where oid='public.valid_protagonist_scores(jsonb)'::regprocedure")).rows[0];
  assert.equal(validatorAfter.oid, validatorBefore.oid);
  assert.deepEqual(validatorAfter.proargnames, [argumentName || "p_scores"]);
  assert.equal((await db.query(`select public.valid_protagonist_scores(${argumentName || "p_scores"} => $1) valid`, [{resilience: 20}])).rows[0].valid, true);
  await db.query("insert into public.validator_dependency values ($1)", [{resilience: 20}]);
  await assert.rejects(db.query("insert into public.validator_dependency values ($1)", [{resilience: 101}]), /check constraint/);
  assert.deepEqual((await db.query(`select oid from pg_proc where oid in (
    'public.protagonist_score_values(jsonb)'::regprocedure,
    'public.valid_protagonist_baseline(jsonb)'::regprocedure) order by oid`)).rows, helpersBefore);
  assert.deepEqual((await db.query(`select public.protagonist_score_values(${rowArgumentName || "p_rows"} => $1) scores`, [{resilience: 20, unrelated: 90}])).rows[0].scores, {resilience: 20});
  assert.equal((await db.query(`select public.valid_protagonist_baseline(${argumentName || "p_scores"} => '{}'::jsonb) valid`)).rows[0].valid, true);
  await db.query("insert into public.baseline_dependency values ($1)", [{resilience: 20}]);
  await assert.rejects(db.query("insert into public.baseline_dependency values ($1)", [{resilience: 101}]), /check constraint/);
  for (const role of ["anon", "authenticated"]) {
    await db.exec(`set role ${role}`);
    assert.deepEqual(await definition(), revised);
    await assert.rejects(db.query("select public.save_gemini_protagonist(1,'Hero',$1,$2)", [{resilience: 20}, revised.revision]), /permission denied/);
    await db.exec("reset role");
  }
  await db.close();
}
console.log("Merged migration checks passed: existing argument names/dependencies/grants, legacy reset, seven-trait voting, dynamic edits, preserved custom definitions, revision and permission guards.");
