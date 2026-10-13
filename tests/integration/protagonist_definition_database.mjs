// Real PostgreSQL semantics in isolation. Never uses a live Supabase project.
import { PGlite } from "@electric-sql/pglite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const db = new PGlite();
const seed = JSON.parse(readFileSync(new URL("../../backend/profiler/default_definition.json", import.meta.url), "utf8"));
const keys = seed.traits.map(t => t.key);
const legacy = ["impulsivity", "arrogance_pride", "kinship_friendship", "romantic_attachment", "sexual_desire", "selflessness"];
const user = "00000000-0000-0000-0000-000000000001";
await db.exec(`create role anon; create role authenticated; create role service_role;
  create function public.axiom_account_allowed() returns boolean language sql as 'select true';
  create table public.novels(id bigint primary key);
  create table public.profiles(id uuid primary key);
  create table public.protagonist_profiles(novel_id bigint unique references public.novels on delete cascade,
    protagonist_name text, ${[...new Set([...keys,...legacy])].map(k => `${k} smallint`).join(",")});
  insert into public.novels values (1),(2);
  insert into public.profiles values ('${user}');
`);
for (const file of ["protagonist_votes.sql", "protagonist_vote_controls.sql", "manage_protagonist_profile.sql"]) {
  if (file === "manage_protagonist_profile.sql") {
    // Match the uploaded schema: both old and current columns, with legacy defaults.
    await db.exec(`insert into public.protagonist_profiles(novel_id,protagonist_name,${[...new Set([...keys,...legacy])].join(",")})
      values(2,'Existing hero',${[...new Set([...keys,...legacy])].map(()=>40).join(",")});
      select public.cast_protagonist_vote(2,'${user}','arrogance_pride',100);`);
  }
  await db.exec(readFileSync(new URL(`../../database/${file}`, import.meta.url), "utf8"));
}
const getDefinition = async () => (await db.query("select public.get_protagonist_definition() d")).rows[0].d;
const summary = async () => (await db.query("select public.protagonist_vote_summary(1,$1) s", [user])).rows[0].s;
const update = async d => (await db.query("select public.update_protagonist_definition($1,$2,$3) d", [d.revision,d.instructions,d.traits])).rows[0].d;
const save = (d, value=20, generated=true) => db.query("select public.save_protagonist_profile(1,'Hero',$1,$2,$3)", [Object.fromEntries(d.traits.map(t=>[t.key,value])),d.revision,generated]);
const vote = (d, key, score=100) => db.query("select public.cast_protagonist_vote(1,$1,$2,$3,$4)",[user,key,score,d.revision]);
let d = await getDefinition();
assert.deepEqual(d, seed);
const existing = async () => (await db.query("select public.protagonist_vote_summary(2,$1) s",[user])).rows[0].s;
assert.equal((await existing()).profile.arrogance_pride,70);
assert.equal((await existing()).baseline.arrogance_pride,40);
assert.equal((await existing()).baseline.intelligence,40);
assert.equal((await existing()).my_votes.arrogance_pride,100);
assert.equal((await existing()).baseline.impulsivity,undefined);
await save(d);
await vote(d,"intelligence"); await vote(d,"charisma");
assert.equal((await summary()).profile.intelligence,60);
await db.exec("select public.set_protagonist_score_lock(1,true)");
const stale = structuredClone(d);
d.traits.find(t=>t.key==="intelligence").prompt += "\nNew criterion.";
d = await update(d);
let s = await summary();
assert.equal(s.profile.intelligence,null);
assert.equal(s.profile.charisma,60);
assert.equal(s.baseline.charisma,20);
assert.equal(s.baseline.intelligence,undefined);
assert.equal(s.my_votes.intelligence,undefined);
assert.equal(s.my_votes.charisma,100);
assert.equal(s.scores_locked,true);
assert.equal(s.eligible,false);
assert.equal((await existing()).profile.intelligence,null);
assert.equal((await existing()).profile.arrogance_pride,70);
assert.equal((await existing()).baseline.arrogance_pride,40);
await assert.rejects(update(stale),/changed/);
await assert.rejects(save(stale),/changed/);
await assert.rejects(vote(stale,"charisma"),/changed/);
await assert.rejects(save(d),/locked/);
await save(d,30,false); // Moderator may repair a locked profile.
await db.exec("select public.set_protagonist_score_lock(1,false)");
assert.equal((await summary()).profile.charisma,65);

// Add a trait: real nullable SQL column, unchanged defaults/votes and incomplete eligibility.
d.traits.push({key:"resilience",name:"Resilience",prompt:"0 gives up; 100 perseveres."});
d = await update(d);
s = await summary();
assert.equal(s.profile.resilience,null);
assert.equal(s.baseline.charisma,30);
assert.equal(s.profile.charisma,65);
await assert.rejects(vote(d,"charisma"),/all current/);
await save(d,10); await vote(d,"resilience");
assert.equal((await summary()).profile.resilience,55);
assert.equal((await summary()).profile.charisma,55);

// Rename clears data even though its stable storage key stays the same.
d.traits.find(t=>t.key==="resilience").name = "Determination";
d = await update(d);
assert.equal((await summary()).profile.resilience,null);
assert.equal((await summary()).baseline.resilience,undefined);
await save(d);
await vote(d,"resilience");
d.traits = d.traits.filter(t=>t.key!=="resilience");
d = await update(d);
assert.equal((await summary()).profile.resilience,undefined);
assert.equal((await summary()).my_votes.resilience,undefined);
assert.equal((await summary()).eligible,true);
assert.equal((await db.query("select count(*) n from information_schema.columns where table_name='protagonist_profiles' and column_name='resilience'")).rows[0].n,0);

// An edit to shared instructions invalidates every trait but preserves the name and lock state.
d.instructions += "\nUpdated shared instructions.";
d = await update(d);
s = await summary();
assert.ok(d.traits.every(t=>s.profile[t.key]===null));
assert.deepEqual(s.baseline,{}); assert.equal(s.vote_count,0); assert.equal(s.profile.protagonist_name,"Hero");
await save(d,0); assert.equal((await summary()).eligible,true);
const before = await getDefinition();
for (const trait of [
  {key:"id",name:"Reserved",prompt:"Invalid"},
  {key:"evil;drop table novels",name:"Injection",prompt:"Invalid"},
  {key:"intelligence",name:"Duplicate",prompt:"Invalid"},
  {key:"impulsivity",name:"Existing retired column",prompt:"Invalid"},
]) await assert.rejects(update({...d,traits:[...d.traits,trait]}));
assert.deepEqual(await getDefinition(),before);
assert.equal((await summary()).profile.charisma,0);
assert.deepEqual(await update(d),d); // No-op does not clear scores or increment revision.

// Force a failure after cleanup has begun: a dependent view prevents dropping the column.
await db.exec("create view public.keep_intelligence as select intelligence from public.protagonist_profiles");
await assert.rejects(update({...d,traits:d.traits.filter(t=>t.key!=="intelligence")}),/depend/);
await db.exec("rollback");
assert.deepEqual(await getDefinition(),d);
assert.equal((await summary()).profile.intelligence,0);
await db.exec("drop view public.keep_intelligence");

// Reapplying the new migration never restores seed prompts or resets current data.
await db.exec(readFileSync(new URL("../../database/manage_protagonist_profile.sql",import.meta.url),"utf8"));
assert.deepEqual(await getDefinition(),d);
assert.equal((await summary()).profile.intelligence,0);
for (const role of ["anon","authenticated"]) {
  await db.exec(`set role ${role}`);
  assert.deepEqual(await getDefinition(),d);
  await assert.rejects(update(d),/permission denied/);
  await assert.rejects(save(d),/permission denied/);
  await assert.rejects(db.exec("select * from public.protagonist_definition"),/permission denied/);
  await db.exec("reset role");
}
await db.exec("set role service_role");
await save(d);
await db.exec("reset role");
await db.close();
console.log("Dynamic definition database checks passed: DDL, cleanup, preservation, revisions, rollback, voting, locks, and permissions.");
