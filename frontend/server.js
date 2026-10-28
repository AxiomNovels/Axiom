const http = require("http");
const fs = require("fs/promises");
const path = require("path");

const PORT = process.env.PORT || 3000;
const PUBLIC_DIR = path.join(__dirname, "public");
const SITE_ORIGIN = "https://axiomnovels.com";
const API_BASE = (process.env.API_BASE || "http://localhost:8000").replace(/\/+$/, "");
const SITEMAP_PATHS = ["/", "/finder.html", "/readers.html", "/quiz/"];
const NOINDEX_PATHS = new Set([
  "/activity.html", "/admin.html", "/friends.html", "/inbox.html", "/list.html",
  "/lists.html", "/login.html", "/profile.html", "/search.html", "/shared-list.html",
  "/signup.html", "/under-construction.html", "/upload.html", "/user.html", "/vote.html",
  "/mission.html", "/team.html", "/protagonist-profile-info.html",
]);

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon"
};

function xmlEscape(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;",
  })[character]);
}

async function sitemapXml() {
  const paths = new Set(SITEMAP_PATHS);
  try {
    const response = await fetch(`${API_BASE}/api/novels`, { signal: AbortSignal.timeout(4000) });
    if (response.ok) {
      const novels = await response.json();
      for (const novel of Array.isArray(novels) ? novels : []) {
        if (Number.isInteger(Number(novel.id))) paths.add(`/novel.html?id=${encodeURIComponent(novel.id)}`);
      }
    }
  } catch {
    // The static public pages remain valid if the sleeping/unavailable API cannot be reached.
  }
  const urls = [...paths].map((pathname) => `  <url><loc>${xmlEscape(`${SITE_ORIGIN}${pathname}`)}</loc></url>`).join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`;
}

function safePublicPath(requestUrl) {
  try {
  const url = new URL(requestUrl, `http://localhost:${PORT}`);
  const pathname = url.pathname === "/" ? "/index.html"
    : ["/quiz", "/quiz/"].includes(url.pathname) ? "/quiz/index.html" : url.pathname;
  const decodedPath = decodeURIComponent(pathname);
  const filePath = path.normalize(path.join(PUBLIC_DIR, decodedPath));

  const relative = path.relative(PUBLIC_DIR, filePath);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative) || decodedPath.includes("\0")) {
    return null;
  }

  return filePath;
  } catch {
    return null;
  }
}

async function analyticsEnabled() {
  // An explicit frontend override is useful for tests. Ordinary local startup
  // follows the backend, which already loads its private .env file.
  if (process.env.ANALYTICS_ENABLED !== undefined) {
    return process.env.ANALYTICS_ENABLED.toLowerCase() === "true";
  }
  try {
    const response = await fetch(`${API_BASE}/api/analytics/config`, { signal: AbortSignal.timeout(1500) });
    return response.ok && (await response.json()).enabled === true;
  } catch {
    // A stopped/older backend must not stop the frontend from serving pages.
    return false;
  }
}

async function handleRequest(request, response) {
  const filePath = safePublicPath(request.url);
  if (!filePath) {
    response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Bad request");
    return;
  }
  const requestPath = new URL(request.url, `http://localhost:${PORT}`).pathname;
  if (requestPath === "/sitemap.xml") {
    response.writeHead(200, { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=300" });
    response.end(await sitemapXml());
    return;
  }
  if (requestPath === "/runtime-config.js") {
    const apiBase = (process.env.API_BASE || "http://localhost:8000").replace(/\/+$/, "");
    const enabled = await analyticsEnabled();
    const body = `window.AXIOM_RUNTIME_CONFIG = Object.freeze({ apiBase: ${JSON.stringify(apiBase)}, analyticsEnabled: ${enabled}, analyticsEndpoint: ${JSON.stringify(`${apiBase}/api/analytics/events`)} });`;
    response.writeHead(200, {
      "Content-Type": "text/javascript; charset=utf-8",
      "Cache-Control": "no-store"
    });
    response.end(body);
    return;
  }

  try {
    const data = await fs.readFile(filePath);
    const extension = path.extname(filePath);
    const headers = { "Content-Type": contentTypes[extension] || "application/octet-stream" };
    if (NOINDEX_PATHS.has(requestPath)) headers["X-Robots-Tag"] = "noindex, nofollow";
    response.writeHead(200, headers);
    response.end(data);
  } catch (error) {
    if (error.code === "ENOENT") {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Page not found");
      return;
    }

    response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Something went wrong");
  }
}

http.createServer(handleRequest).listen(PORT, () => {
  console.log(`Axiom frontend running at http://localhost:${PORT}`);
});
