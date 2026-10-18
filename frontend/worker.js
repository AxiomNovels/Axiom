// Cloudflare serves matching static files directly. This Worker only handles
// the small runtime configuration endpoint and any unmatched asset requests.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const siteOrigin = "https://axiomnovels.com";
    const sitemapPaths = ["/", "/finder.html", "/readers.html"];
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
        const catalogue = await fetch(`${apiBase}/api/novels`);
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
      const apiBase = (env.API_BASE || "").replace(/\/+$/, "");
      const body = `window.AXIOM_RUNTIME_CONFIG = Object.freeze({ apiBase: ${JSON.stringify(apiBase)} });`;

      return new Response(body, {
        headers: {
          "Content-Type": "application/javascript; charset=utf-8",
          "Cache-Control": "no-store"
        }
      });
    }

    const response = await env.ASSETS.fetch(request);
    if (!noindexPaths.has(url.pathname)) return response;
    const headers = new Headers(response.headers);
    headers.set("X-Robots-Tag", "noindex, nofollow");
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  }
};
