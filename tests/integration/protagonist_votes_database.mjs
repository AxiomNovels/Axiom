// Isolated PostgreSQL regression test (PGlite); never contacts Supabase.
// npm ci --prefix tests && npm run test:votes --prefix tests
import { PGlite } from "@electric-sql/pglite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const db = new PGlite();
const keys = ["impulsivity", "arrogance_pride", "kinship_friendship", "romantic_attachment", "sexual_desire", "selflessness"];
const user1 = "00000000-0000-0000-0000-000000000001";
const user2 = "00000000-0000-0000-0000-000000000002";
const scores = value => Object.fromEntries(keys.map(key => [key, value]));
await db.exec(`
  create role anon; create role authenticated; create role service_role;
  create table public.novels(id bigint primary key, title text);
  create table public.profiles(id uuid primary key, username text);
  create table public.protagonist_profiles(novel_id bigint unique references public.novels on delete cascade,
    protagonist_name text, ${keys.map(key => `${key} smallint`).join(",")});
  insert into public.novels values (1,'First novel'),(2,'Second novel'),(3,'Manual profile');
  insert into public.profiles values ('${user1}','Reader one'),('${user2}','Reader two');
  insert into public.protagonist_profiles values (3,'Manual hero',50,50,50,50,50,50);
`);
const migration = readFileSync(new URL("../../database/protagonist_votes.sql", import.meta.url), "utf8");
await db.exec(migration);
await db.exec(migration); // The migration is safely repeatable.
const summary = async id => (await db.query("select public.protagonist_vote_summary($1,$2) result", [id, user1])).rows[0].result;
const save = (id, value) => db.query("select public.save_gemini_protagonist($1,'Hero',$2)", [id, scores(value)]);
const vote = (id, user, trait, score) => db.query("select public.cast_protagonist_vote($1,$2,$3,$4)", [id, user, trait, score]);
assert.equal((await summary(3)).eligible, false);
await assert.rejects(vote(3, user1, "selflessness", 100), /Voting opens/);
const controls = readFileSync(new URL("../../database/protagonist_vote_controls.sql", import.meta.url), "utf8");
await db.exec(controls);
await db.exec(controls);
assert.equal((await summary(3)).eligible, true); // Complete legacy moderator profile.
await db.exec(`update public.protagonist_profiles set ${keys.map(key=>`${key}=0`).join(',')} where novel_id=3`);
assert.equal((await summary(3)).eligible, true);
assert.deepEqual((await summary(3)).baseline, scores(0));
await db.exec('select public.set_protagonist_score_lock(3,true)');
await vote(3, user1, 'selflessness', 100);
await vote(3, user2, 'selflessness', 100);
assert.equal((await summary(3)).profile.selflessness, 0);
assert.equal((await summary(3)).vote_count, 2);
assert.equal((await summary(3)).scores_locked, true);
await assert.rejects(save(3, 80), /locked by a moderator/);
await db.query('delete from public.protagonist_votes where novel_id=3 and user_id=$1', [user2]);
assert.equal((await summary(3)).profile.selflessness, 0);
await db.exec('update public.protagonist_profiles set selflessness=10 where novel_id=3');
assert.equal((await summary(3)).profile.selflessness, 10); // Moderator can edit locked scores.
await db.exec('select public.set_protagonist_score_lock(3,false)');
assert.equal((await summary(3)).profile.selflessness, 55); // Unlock includes collected votes.
assert.equal((await summary(3)).baseline.selflessness, 10); // No feedback into defaults.
await db.exec('update public.protagonist_profiles set impulsivity=null where novel_id=3');
assert.equal((await summary(3)).eligible, false);
await assert.rejects(vote(3,user1,'selflessness',0), /all six/);
await db.exec('update public.protagonist_profiles set impulsivity=0 where novel_id=3');
assert.equal((await summary(3)).eligible, true);
await db.exec('delete from public.protagonist_votes where novel_id=3');
for (const invalid of [{}, {...scores(50), selflessness:null}, {...scores(50), selflessness:1.5}, {...scores(50), selflessness:"50"}, {...scores(50), selflessness:101}, {...scores(50), unknown:1}]) {
  await assert.rejects(db.query("select public.save_gemini_protagonist(1,'Hero',$1)", [invalid]), /complete profile/);
}
await save(1, 20); await save(2, 0);
assert.equal((await summary(2)).eligible, true); // Zero is a valid complete baseline.
await vote(1, user1, "selflessness", 100);
assert.equal((await summary(1)).profile.selflessness, 60);
await vote(1, user1, "selflessness", 0); // Update, not an additional vote.
assert.equal((await summary(1)).vote_count, 1);
assert.equal((await summary(1)).profile.selflessness, 10);
await vote(1, user2, "selflessness", 100);
assert.equal((await summary(1)).profile.selflessness, 40);
assert.deepEqual((await summary(1)).distribution.selflessness, [{score:0,count:1},{score:100,count:1}]);
assert.deepEqual((await summary(1)).my_votes, {selflessness:0});
assert.equal((await summary(1)).profile.impulsivity, 20); // Unvoted traits stay at baseline.
await assert.rejects(vote(1, user1, "fake", 50));
await assert.rejects(vote(1, user1, "impulsivity", 101));
await save(1, 80); // New Gemini default preserves votes and recomputes.
assert.equal((await summary(1)).vote_count, 2);
assert.equal((await summary(1)).profile.selflessness, 60);
await db.query("delete from public.protagonist_votes where novel_id=1 and user_id=$1", [user2]);
assert.equal((await summary(1)).profile.selflessness, 40);
await vote(2, user1, "impulsivity", 100);
await db.query("delete from public.protagonist_votes where user_id=$1", [user1]);
assert.equal((await summary(1)).profile.selflessness, 80);
assert.equal((await summary(2)).profile.impulsivity, 0);
// Aggregation must not truncate at Supabase's usual 1,000-row response limit.
await db.exec(`insert into public.profiles select md5(i::text)::uuid, 'Reader ' || i from generate_series(1,1100) i;
  insert into public.protagonist_votes(novel_id,user_id,trait,score)
  select 1,md5(i::text)::uuid,'selflessness',100 from generate_series(1,1100) i;`);
assert.equal((await summary(1)).vote_count, 1100);
assert.equal((await summary(1)).distribution.selflessness[0].count, 1100);
await db.exec("delete from public.profiles where username like 'Reader %'"); // Cascades also recalculate.
assert.equal((await summary(1)).profile.selflessness, 80);
assert.equal((await summary(1)).vote_count, 0);
await db.exec("set role authenticated");
await assert.rejects(db.exec("select * from public.protagonist_votes"), /permission denied/);
await assert.rejects(db.exec("select public.cast_protagonist_vote(1,null,'selflessness',100)"), /permission denied/);
await assert.rejects(db.exec("select public.save_gemini_protagonist(1,'Forged','{}')"), /permission denied/);
await assert.rejects(db.exec("select public.protagonist_vote_summary(1,null)"), /permission denied/);
await assert.rejects(db.exec("select public.set_protagonist_score_lock(1,true)"), /permission denied/);
await db.exec("reset role");
await db.exec("delete from public.novels where id=1");
assert.equal((await summary(1)).eligible, false);
await db.close();
console.log("Database regression checks passed: eligibility, validation, recalculation, updates, deletes, cascades, complete distributions, and access control.");
