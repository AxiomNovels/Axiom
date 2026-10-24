/* First-party, opt-in reader analytics. No token or IP is stored by this script. */
(() => {
  const config = window.AXIOM_RUNTIME_CONFIG || {};
  const preferenceKey = "axiomAnalyticsConsent";
  const sessionKey = "axiomAnalyticsVisit";
  let enabled = false;
  let activeSeconds = 0;
  let lastTick = performance.now();
  let lastInteraction = Date.now();
  let started = false;
  const preference = () => { try { return localStorage.getItem(preferenceKey); } catch { return "declined"; } };
  const privacySignal = () => navigator.globalPrivacyControl || navigator.doNotTrack === "1";

  function visit() {
    const now = Date.now();
    let stored;
    try { stored = JSON.parse(localStorage.getItem(sessionKey)); } catch { /* Start a new visit. */ }
    if (!stored || now-stored.lastActive > 30*60*1000 || !stored.id) stored = { id: crypto.randomUUID() };
    stored.lastActive = now;
    try { localStorage.setItem(sessionKey, JSON.stringify(stored)); } catch { return null; }
    return stored.id;
  }

  async function send(event, seconds = 0) {
    if (!enabled || privacySignal()) return;
    const session = visit();
    if (!session) return;
    const path = location.pathname;
    if (!/^\/(?:[a-zA-Z0-9_-]+(?:\.html)?\/?)?$/.test(path)) return;
    try {
      await authFetch(config.analyticsEndpoint || `${API_BASE}/api/analytics/events`, {
        method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
        skipSessionRefresh: true,
        body: JSON.stringify({ id: crypto.randomUUID(), session_id: session, event, path, active_seconds: Math.min(30, seconds) }),
      });
    } catch { /* Analytics never interrupts browsing; do not queue private activity offline. */ }
  }

  function tick() {
    const now = performance.now();
    const elapsed = Math.min(5, Math.max(0, (now-lastTick)/1000));
    lastTick = now;
    if (enabled && document.visibilityState === "visible" && Date.now()-lastInteraction < 60000) activeSeconds += elapsed;
  }

  function flush() {
    tick();
    const seconds = Math.floor(activeSeconds);
    activeSeconds = 0;
    if (seconds > 0) void send("heartbeat", seconds);
  }

  function applyPreference() {
    const before = enabled;
    enabled = config.analyticsEnabled === true && preference() === "accepted" && !privacySignal();
    if (enabled && !before) { lastInteraction = Date.now(); lastTick = performance.now(); void send("page_view"); }
    if (!enabled) { activeSeconds = 0; try { localStorage.removeItem(sessionKey); } catch {} }
    if (enabled && !started) {
      started = true;
      setInterval(tick, 5000);
      setInterval(flush, 30000);
    }
  }

  function showPreferences() {
    document.getElementById("analytics-consent")?.remove();
    const box = document.createElement("section");
    box.id = "analytics-consent";
    box.className = "analytics-consent";
    box.setAttribute("aria-label", "Analytics preferences");
    const text = document.createElement("p");
    text.textContent = "Help improve Axiom? Optional analytics measure page visits, country, and active time. When signed in, activity can be linked to your account. Request counts are collected separately.";
    const link = document.createElement("a");
    link.href = "/analytics-privacy.html"; link.textContent = "How analytics works";
    box.append(text, link);
    for (const [label, value] of [["Allow analytics", "accepted"], ["Decline analytics", "declined"]]) {
      const button = document.createElement("button");
      button.type = "button"; button.textContent = label;
      button.addEventListener("click", () => {
        try { localStorage.setItem(preferenceKey, value); } catch {}
        box.remove(); applyPreference();
      });
      box.append(button);
    }
    if (privacySignal()) { text.textContent += " Your browser privacy signal is enabled, so optional tracking will remain off."; }
    document.body.append(box);
  }

  document.querySelectorAll("[data-analytics-preferences]").forEach(button => {
    button.hidden = !config.analyticsEnabled;
    button.addEventListener("click", showPreferences);
  });
  for (const name of ["pointerdown", "keydown", "scroll", "touchstart"]) {
    window.addEventListener(name, () => { lastInteraction = Date.now(); }, { passive: true });
  }
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
    else { lastTick = performance.now(); lastInteraction = Date.now(); }
  });
  window.addEventListener("pagehide", flush);
  window.addEventListener("pageshow", event => { if (event.persisted) { lastTick = performance.now(); lastInteraction = Date.now(); void send("page_view"); } });
  window.addEventListener("storage", event => { if (event.key === preferenceKey) applyPreference(); });
  applyPreference();
  if (config.analyticsEnabled && !preference() && !privacySignal()) showPreferences();
})();
