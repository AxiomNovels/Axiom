// run_worker_first keeps asset request counts visible to first-party analytics.
const analyticsOn = (env) => env.ANALYTICS_ENABLED === "true" && !!env.ANALYTICS_EDGE_SECRET;

function edgeHeaders(request, env) {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.set("X-Axiom-Edge-Secret", env.ANALYTICS_EDGE_SECRET);
  headers.set("X-Axiom-Country", /^[A-Z]{2}$/.test(request.cf?.country || "") ? request.cf.country : "XX");
  headers.set("X-Axiom-Client-IP", request.headers.get("CF-Connecting-IP") || "");
  return headers;
}

async function proxyAnalytics(request, env, path) {
  // Keep browser requests on the first-party origin, and add trusted location metadata.
  const target = `${env.API_BASE.replace(/\/+$/, "")}${path}`;
  const headers = edgeHeaders(request, env);
  const init = { method: request.method, headers, redirect: "manual", signal: AbortSignal.timeout(15000) };
  if (!["GET", "HEAD"].includes(request.method)) init.body = request.body;
  return fetch(target, init);
}

async function logFrontendRequest(request, response, env) {
  try {
    const url = new URL(request.url);
    const page = url.pathname === "/" || !url.pathname.split("/").pop().includes(".") || url.pathname.endsWith(".html");
    const result = await fetch(`${env.API_BASE.replace(/\/+$/, "")}/api/analytics/edge`, {
      method: "POST", headers: { "Content-Type": "application/json", "X-Axiom-Edge-Secret": env.ANALYTICS_EDGE_SECRET },
      body: JSON.stringify({ path: url.pathname.length <= 240 ? url.pathname : "/other",
        country: /^[A-Z]{2}$/.test(request.cf?.country || "") ? request.cf.country : "XX",
        ip: request.headers.get("CF-Connecting-IP") || null, kind: page ? "page" : "asset", status: response.status }),
      signal: AbortSignal.timeout(4000),
    });
    if (!result.ok) console.warn("Analytics request collection unavailable:", result.status);
  } catch { console.warn("Analytics request collection unavailable"); }
}

const worker = {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (analyticsOn(env) && url.pathname.startsWith("/__axiom/backend/api/")) {
      const path = url.pathname.slice("/__axiom/backend".length);
      // Edge intake is private even though the general API proxy is public.
      if (path.startsWith("/api/analytics/edge")) return new Response("Not found", { status: 404 });
      return proxyAnalytics(request, env, path + url.search);
    }
    if (url.pathname === "/__axiom/events") {
      if (!analyticsOn(env) || request.method !== "POST") return new Response(null, { status: 404 });
      if (request.headers.get("Origin") !== url.origin) return new Response(null, { status: 403 });
      return proxyAnalytics(request, env, "/api/analytics/events");
    }
    const response = await worker.serve(request, env);
    if (analyticsOn(env) && !["/runtime-config.js", "/favicon.ico", "/robots.txt"].includes(url.pathname)
        && !url.pathname.startsWith("/__axiom/")) ctx.waitUntil(logFrontendRequest(request, response, env));
    return response;
  },
  async serve(request, env) {
    const url = new URL(request.url);
    const siteOrigin = "https://axiomnovels.com";
    const sitemapPaths = ["/", "/finder.html", "/readers.html", "/quiz/"];
    const noindexPaths = new Set([
      "/activity.html", "/admin.html", "/friends.html", "/inbox.html", "/list.html", "/lists.html",
      "/login.html", "/profile.html", "/search.html", "/shared-list.html", "/signup.html",
      "/under-construction.html", "/upload.html", "/user.html", "/vote.html",
      "/mission.html", "/team.html", "/protagonist-profile-info.html",
    ]);

    if (url.pathname === "/sitemap.xml") {
      const paths = new Set(sitemapPaths);
      const apiBase = (env.API_BASE || "").replace(/\/+$/, "");
      try {
        const catalogue = await fetch(`${apiBase}/api/novels`, { signal: AbortSignal.timeout(4000) });
        if (catalogue.ok) {
          const novels = await catalogue.json();
          for (const novel of Array.isArray(novels) ? novels : []) {
            if (Number.isInteger(Number(novel.id))) paths.add(`/novel.html?id=${encodeURIComponent(novel.id)}`);
          }
        }
      } catch {
        // Keep the known static pages in the sitemap if the API is unavailable.
      }
      const escapeXml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" })[character]);
      const body = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${[...paths].map((pathname) => `  <url><loc>${escapeXml(`${siteOrigin}${pathname}`)}</loc></url>`).join("\n")}\n</urlset>\n`;
      return new Response(body, { headers: { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=300" } });
    }

    if (url.pathname === "/runtime-config.js") {
      const enabled = analyticsOn(env);
      const apiBase = enabled ? `${url.origin}/__axiom/backend` : (env.API_BASE || "").replace(/\/+$/, "");
      const body = `window.AXIOM_RUNTIME_CONFIG = Object.freeze({ apiBase: ${JSON.stringify(apiBase)}, analyticsEnabled: ${enabled}, analyticsEndpoint: "/__axiom/events" });`;

      return new Response(body, {
        headers: {
          "Content-Type": "application/javascript; charset=utf-8",
          "Cache-Control": "no-store"
        }
      });
    }

    const response = await env.ASSETS.fetch(request);
    const pagePath = url.pathname.endsWith(".html") ? url.pathname : `${url.pathname.replace(/\/$/, "")}.html`;
    if (!noindexPaths.has(pagePath)) return response;
    const headers = new Headers(response.headers);
    headers.set("X-Robots-Tag", "noindex, nofollow");
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  }
};

export default worker;
