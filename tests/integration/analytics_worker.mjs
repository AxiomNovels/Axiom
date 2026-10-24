import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const source=readFileSync(new URL("../../frontend/worker.js",import.meta.url),"utf8");
const worker=(await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`)).default;
const base={API_BASE:"https://backend.test",ANALYTICS_ENABLED:"true",ANALYTICS_EDGE_SECRET:"private-test-secret",
  ASSETS:{fetch:async()=>new Response("asset",{status:200})}};

test("runtime config exposes only public settings",async()=>{
  const response=await worker.fetch(new Request("https://axiom.test/runtime-config.js"),base,{waitUntil(){}});
  const text=await response.text();
  assert(text.includes("/__axiom/backend"));assert(text.includes("analyticsEnabled: true"));assert(!text.includes(base.ANALYTICS_EDGE_SECRET));
});
test("disabled deployment keeps original API base and performs no collection",async()=>{
  const env={...base,ANALYTICS_ENABLED:"false"};let calls=0;
  const response=await worker.fetch(new Request("https://axiom.test/runtime-config.js"),env,{waitUntil(){calls++;}});
  assert((await response.text()).includes("https://backend.test"));assert.equal(calls,0);
});
test("asset counts are background work and use trusted country/IP",async()=>{
  const original=globalThis.fetch;const calls=[];const pending=[];
  globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response("{}",{status:202});};
  try {
    const request=new Request("https://axiom.test/assets/cover.png?private=value",{headers:{"CF-Connecting-IP":"192.0.2.1","X-Axiom-Country":"US"}});
    Object.defineProperty(request,"cf",{value:{country:"CA"}});
    const response=await worker.fetch(request,base,{waitUntil(promise){pending.push(promise);}});
    assert.equal(await response.text(),"asset");await Promise.all(pending);
    assert.equal(calls.length,1);const body=JSON.parse(calls[0].init.body);
    assert.equal(body.country,"CA");assert.equal(body.ip,"192.0.2.1");assert.equal(body.kind,"asset");assert(!body.path.includes("private"));
  } finally {globalThis.fetch=original;}
});
test("API proxy overwrites spoofed trust headers and does not double count",async()=>{
  const original=globalThis.fetch;const calls=[];
  globalThis.fetch=async(url,init)=>{calls.push({url,init});return new Response("{}",{status:200});};
  try {
    const request=new Request("https://axiom.test/__axiom/backend/api/search?q=novel",{headers:{"X-Axiom-Edge-Secret":"attacker","X-Axiom-Country":"US",Authorization:"Bearer reader"}});
    Object.defineProperty(request,"cf",{value:{country:"CA"}});
    await worker.fetch(request,base,{waitUntil(){throw new Error("Proxy must not double-count");}});
    assert.equal(calls.length,1);assert.equal(calls[0].url,"https://backend.test/api/search?q=novel");
    assert.equal(calls[0].init.headers.get("X-Axiom-Edge-Secret"),base.ANALYTICS_EDGE_SECRET);
    assert.equal(calls[0].init.headers.get("X-Axiom-Country"),"CA");
    assert.equal(calls[0].init.headers.get("Authorization"),"Bearer reader");
    assert.equal((await worker.fetch(new Request("https://axiom.test/__axiom/backend/api/analytics/edge"),base,{})).status,404);
  } finally {globalThis.fetch=original;}
});
test("browser collector rejects other origins",async()=>{
  const response=await worker.fetch(new Request("https://axiom.test/__axiom/events",{method:"POST",headers:{Origin:"https://attacker.test"}}),base,{});
  assert.equal(response.status,403);
});
