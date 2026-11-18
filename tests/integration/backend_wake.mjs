import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("../../frontend/public/script.js", import.meta.url), "utf8");
const monitor = source.slice(source.indexOf("async function monitorBackendWake()"), source.indexOf("const restoringBackendWakePage"));

async function exercise({ readyAfter = 2, homepage = true, directFails = false } = {}) {
  let now = 100_000;
  let checks = 0;
  let reloads = 0;
  let removed = false;
  const requests = [];
  const warnings = [];
  const storage = new Map();
  const context = {
    LOCAL_API_BASE: "http://localhost:8000", API_BASE: "https://axiom.test/__axiom/backend",
    BACKEND_WAKE_WINDOW_MS: 90_000, BACKEND_WAKE_DELAY_MS: 1_200,
    BACKEND_WAKE_POLL_MS: 4_000, BACKEND_WAKE_RELOAD_KEY: "reload",
    Date: { now: () => now }, URL, AbortSignal,
    sessionStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
    document: { body: { hasAttribute: () => false }, querySelector: () => homepage },
    renderBackendWakeOverlay() {}, removeBackendWakeOverlay() { removed = true; },
    console: { warn: (message) => warnings.push(message) },
    window: {
      AXIOM_RUNTIME_CONFIG: { backendWakeUrl: "https://backend.test/" },
      location: {
        reload() { reloads++; },
        replace() { assert.fail("Visitors must never be redirected to Render"); },
      },
      setTimeout(callback, delay) {
        if (delay === 4_000) { now += delay; callback(); }
        return 1;
      },
      clearTimeout() {},
    },
    async fetch(url, options) {
      requests.push({ url, options });
      if (url.startsWith("https://backend.test/")) {
        if (directFails) throw new Error("Network failure");
        // Do not let an opaque wake response count as API readiness.
        return { ok: true, json() { assert.fail("Opaque responses cannot be read"); } };
      }
      checks++;
      return { ok: checks >= readyAfter, json: async () => ({ status: "ok" }) };
    },
  };
  await runInNewContext(`${monitor}\nmonitorBackendWake();`, context);
  return { checks, reloads, removed, requests, warnings };
}

test("recovers through Cloudflare after a direct health wake without navigation", async () => {
  const result = await exercise();
  assert.equal(result.checks, 2);
  assert.equal(result.reloads, 0);
  assert(result.removed);
  assert.equal(result.warnings.length, 0);
  const wake = result.requests.find(({ url }) => url.startsWith("https://backend.test/"));
  assert.equal(wake.url, "https://backend.test/api/health");
  assert.equal(wake.options.credentials, "omit");
  assert.equal(wake.options.mode, "no-cors");
  assert.equal(wake.options.redirect, "error");
});

test("persistent proxy errors exhaust the window without accepting opaque wake responses", async () => {
  const result = await exercise({ readyAfter: Infinity });
  assert(result.checks > 2);
  assert.equal(result.reloads, 0);
  assert(result.removed);
  assert.equal(result.warnings.length, 1);
});

test("failed direct wakes do not prevent proxied readiness checks", async () => {
  const result = await exercise({ directFails: true });
  assert.equal(result.checks, 2);
  assert.equal(result.warnings.length, 0);
});

test("other pages retain the existing recovery reload after API readiness", async () => {
  const result = await exercise({ homepage: false });
  assert.equal(result.reloads, 1);
});
