import { PGlite } from "@electric-sql/pglite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";

const db = new PGlite();
await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
  create schema auth; create table auth.users(id uuid primary key, created_at timestamptz default now());
  create table public.profiles(id uuid primary key references auth.users(id) on delete cascade, username text);
  create function public.axiom_account_allowed() returns boolean language sql as $$ select true $$;
  grant usage on schema public,auth to anon,authenticated,service_role;`);
const migration=readFileSync(new URL("../../database/analytics.sql",import.meta.url),"utf8");
await db.exec(migration); await db.exec(migration);
const user=randomUUID(), session=randomUUID();
await db.query("insert into auth.users(id) values($1)",[user]);
await db.query("insert into public.profiles values($1,'Reader')",[user]);
async function ingest(events) { await db.query("select public.analytics_ingest($1::jsonb)",[JSON.stringify(events)]); }
const base={session_id:session,user_id:user,country:"CA",source:"browser",kind:"page",path:"/novel.html"};
const view={...base,id:randomUUID(),event:"page_view"};
await ingest([view,view]);
assert.equal((await db.query("select count(*)::int n from public.analytics_events")).rows[0].n,1,"Retries deduplicate");
await db.query("update public.analytics_sessions set active_until=now()-interval '30 seconds' where id=$1",[session]);
await ingest([{...base,id:randomUUID(),event:"heartbeat",active_seconds:30}]);
await ingest([{...base,id:randomUUID(),event:"heartbeat",active_seconds:30}]);
let seconds=(await db.query("select sum(active_seconds)::int n from public.analytics_events")).rows[0].n;
assert.equal(seconds,30,"Concurrent tabs cannot credit the same elapsed interval twice");
await ingest([{id:randomUUID(),country:"CA",source:"frontend",kind:"asset",path:"/assets/*",event:"request",status:200,ip:"192.0.2.1"},
  {id:randomUUID(),country:"XX",source:"backend",kind:"api",path:"/api/other",event:"request",status:401}]);
const report=async country=>(await db.query("select public.analytics_report((now() at time zone 'UTC')::date,(now() at time zone 'UTC')::date,$1) data",[country])).rows[0].data;
let data=await report(null);
assert.equal(data.totals.page_views,1);assert.equal(data.totals.visits,1);assert.equal(data.totals.signed_in_accounts,1);
assert.equal(data.totals.frontend_requests,1);assert.equal(data.totals.backend_requests,1);assert.equal(data.totals.signups,1);
assert.equal(data.totals.active_seconds,30);assert.equal(data.daily.length,1);assert.equal(data.accounts[0].username,"Reader");
data=await report("CA");assert.equal(data.totals.backend_requests,0);assert.equal(data.totals.signups,null);
assert.equal(data.countries.length,1);assert.equal(data.pages[0].entrances,1);
assert(!JSON.stringify(data).includes("192.0.2.1"),"Raw IPs excluded from report");
for (const role of ["anon","authenticated"]) {
  await db.exec(`set role ${role}`);
  await assert.rejects(db.query("select * from public.analytics_events"),/permission denied/);
  await assert.rejects(db.query("select * from public.analytics_sessions"),/permission denied/);
  await assert.rejects(db.query("select * from public.analytics_ip_logs"),/permission denied/);
  await assert.rejects(report(null),/permission denied/);
  await assert.rejects(ingest([]),/permission denied/);
  await assert.rejects(db.query("select public.analytics_cleanup()"),/permission denied/);
  await db.exec("reset role");
}
await db.exec("update public.analytics_ip_logs set occurred_at=now()-interval '8 days'");
await db.exec("select public.analytics_cleanup()");
assert.equal((await db.query("select count(*)::int n from public.analytics_ip_logs")).rows[0].n,0);
await db.query("delete from auth.users where id=$1",[user]);
assert.equal((await db.query("select count(user_id)::int n from public.analytics_events")).rows[0].n,0);
await db.exec("update public.analytics_events set occurred_at=now()-interval '91 days'; update public.analytics_sessions set last_seen=now()-interval '91 days'; select public.analytics_cleanup()");
assert.equal((await db.query("select count(*)::int n from public.analytics_events")).rows[0].n,0);
assert.equal((await db.query("select count(*)::int n from public.analytics_sessions")).rows[0].n,0);
await assert.rejects(db.query("select public.analytics_report('2026-01-01','2026-12-31',null)"),/90 days/);
await db.close();
console.log("Analytics SQL: deduplication, time caps, aggregates, country filters, grants, deletion, retention passed.");
