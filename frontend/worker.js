// Cloudflare serves matching static files directly. This Worker only handles
// the small runtime configuration endpoint and any unmatched asset requests.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

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

    return env.ASSETS.fetch(request);
  }
};
