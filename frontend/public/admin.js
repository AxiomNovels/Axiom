const adminStatus = document.getElementById("admin-status");
const adminContent = document.getElementById("admin-content");
let adminId;
let dirty = false;
let editorVersion = 0;
let rebuildPoll;
const state = { users: { page: 1, query: "", version: 0 }, novels: { page: 1, query: "", version: 0 } };

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function status(message, error = false) {
  adminStatus.textContent = message;
  adminStatus.classList.toggle("error", error);
}
async function request(path, options = {}) {
  const response = await authFetch(`${API_BASE}/api/admin${path}`, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) adminContent.hidden = true;
    throw new Error(data.detail || "Request failed. Please try again.");
  }
  return data;
}
function action(text, handler) {
  const button = element("button", text);
  button.type = "button";
  button.addEventListener("click", async () => {
    button.disabled = true;
    try { await handler(); } catch (error) { status(error.message, true); }
    finally { button.disabled = false; }
  });
  return button;
}
function rebuildStatus(text, error = false) {
  const target = document.getElementById("profile-rebuild-status");
  target.textContent = text;
  target.classList.toggle("error", error);
}
function rebuildItemCopy(item) {
  if (item.status === "completed") return "Profile rebuilt";
  if (item.status === "failed") return item.error || "Profile generation failed";
  if (item.status === "not_needed") return "Already complete; no rebuild needed";
  if (item.status === "running") return "Rebuilding now";
  return "Queued to rebuild";
}
function rebuildItemLabel(item) {
  return ({ completed: "Built", failed: "Not built", not_needed: "Not needed", running: "Building", queued: "Queued" })[item.status] || item.status;
}
function renderRebuildItems(items, host) {
  host.replaceChildren();
  const list = element("div", undefined, "profile-rebuild-results-list");
  const ordered = [...items].sort((left, right) => left.status.localeCompare(right.status) || (left.novels?.title || "").localeCompare(right.novels?.title || ""));
  ordered.forEach((item) => {
    const row = element("div", undefined, `profile-rebuild-result is-${item.status}`);
    const novel = item.novels?.title || `Novel #${item.novel_id}`;
    const copy = element("div");
    copy.append(element("strong", novel), element("small", rebuildItemCopy(item)));
    row.append(element("span", rebuildItemLabel(item), "admin-badge"), copy);
    list.append(row);
  });
  host.append(list);
}
function jobSummary(job) {
  return `${job.processed}/${job.total} processed · ${job.succeeded} built · ${job.failed} not built`;
}
function displayBuildTime(value) {
  return value ? new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "Just now";
}
async function loadRebuildHistory(activeJobId) {
  const host = document.getElementById("profile-rebuild-history");
  const data = await request("/protagonist-rebuilds");
  host.replaceChildren();
  if (!data.jobs.length) { host.append(element("p", "No rebuilds have been run yet.")); return; }
  data.jobs.forEach((job) => {
    const details = document.createElement("details");
    details.className = "profile-history-job";
    details.open = job.id === activeJobId || job.status === "running" || job.status === "queued";
    const summary = document.createElement("summary");
    const copy = element("div");
    copy.append(element("strong", `${job.mode === "all" ? "Every profile" : "Outdated profiles"} rebuild`), element("small", `${displayBuildTime(job.created_at)} · ${jobSummary(job)}`));
    summary.append(element("span", job.status === "completed" ? "Complete" : job.status === "running" ? "Running" : "Queued", "admin-badge"), copy);
    details.append(summary);
    const body = element("div", undefined, "profile-history-job-body");
    const items = element("div");
    const loadItems = async () => {
      if (items.childElementCount) return;
      items.append(element("p", "Loading this run…"));
      try {
        const response = await request(`/protagonist-rebuilds/${job.id}/items`);
        renderRebuildItems(response.items || [], items);
      } catch (error) { items.replaceChildren(element("p", error.message, "error")); }
    };
    details.addEventListener("toggle", () => { if (details.open) loadItems(); });
    if (details.open) loadItems();
    body.append(items);
    if (job.status === "completed") {
      const remove = action("Delete this history entry", async () => {
        if (!confirm("Delete this rebuild and its per-novel history? This cannot be undone.")) return;
        await request(`/protagonist-rebuilds/${job.id}`, { method: "DELETE" });
        await loadRebuildHistory();
      });
      remove.className = "admin-danger";
      body.append(remove);
    }
    details.append(body); host.append(details);
  });
}
async function watchRebuild(jobId) {
  clearInterval(rebuildPoll);
  const refresh = async () => {
    try {
      const job = await request(`/protagonist-rebuilds/${jobId}`);
      rebuildStatus(`${job.status === "completed" ? "Finished" : "Running"}: ${jobSummary(job)}.`);
      await loadRebuildHistory(jobId);
      if (job.status === "completed") clearInterval(rebuildPoll);
    } catch (error) { clearInterval(rebuildPoll); rebuildStatus(error.message, true); }
  };
  await refresh();
  rebuildPoll = setInterval(refresh, 4000);
}
async function startRebuild(includeComplete) {
  const label = includeComplete ? "every protagonist profile" : "only incomplete or outdated protagonist profiles";
  if (!confirm(`Rebuild ${label}? This uses Gemini for each selected novel and can take a while.`)) return;
  const job = await request("/protagonist-rebuilds", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_complete: includeComplete }),
  });
  rebuildStatus(`Queued ${job.total} profiles…`);
  await loadRebuildHistory(job.id);
  await watchRebuild(job.id);
}
async function loadList(kind) {
  const current = state[kind];
  const version = ++current.version;
  status("Loading...");
  const data = await request(`/${kind}?q=${encodeURIComponent(current.query)}&page=${current.page}`);
  if (version !== current.version) return;
  const results = document.getElementById(`${kind}-results`);
  results.replaceChildren();
  const columns = element("div", undefined, "admin-list-columns");
  columns.append(element("span", kind === "users" ? "ACCOUNT" : "NOVEL"), element("span", kind === "users" ? "STATUS" : "CATALOGUE"), element("span", "ACTIONS"));
  results.append(columns);
  for (const item of data[kind]) {
    const row = element("div", undefined, "admin-row admin-catalog-row");
    const identity = element("div", undefined, "admin-identity");
    const name = kind === "users" ? item.username : item.title;
    const avatar = element("span", name.slice(0, 1).toUpperCase(), "admin-avatar");
    avatar.setAttribute("aria-hidden", "true");
    const description = element("div", undefined, "admin-description");
    description.append(element("strong", name));
    description.append(element("small", kind === "users" ? (item.special ? "Special account" : "Reader") : (item.author || "Unknown author")));
    identity.append(avatar, description);
    const badge = element("span", kind === "users" ? (item.banned ? "Banned" : "Active") : "Novel", `admin-badge ${item.banned ? "is-banned" : kind === "users" ? "is-active" : ""}`);
    const actions = element("div", undefined, "admin-row-actions");
    row.append(identity, badge, actions);
    if (kind === "users") {
      actions.append(action("View votes", () => openVotes("users", item.id, item.username)));
      const menu = element("details", undefined, "admin-action-menu");
      const toggle = element("summary", "More", "admin-more");
      toggle.setAttribute("aria-label", `More actions for ${item.username}`);
      const options = element("div", undefined, "admin-menu-options");
      const remove = action("Delete all votes", async () => { menu.open = false; await deleteAllUserVotes(item.id, item.username); });
      remove.className = "admin-danger";
      options.append(remove);
      if (!item.special && item.id !== adminId) {
        const ban = action(item.banned ? "Unban account" : "Ban account", async () => {
          menu.open = false;
          if (!confirm(`${item.banned ? "Unban" : "Ban"} ${item.username}?`)) return;
          await request(`/users/${item.id}/ban`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ banned: !item.banned }) });
          await loadList(kind);
          status(`${item.username} ${item.banned ? "unbanned" : "banned"}.`);
        });
        ban.className = "admin-danger";
        options.append(ban);
      }
      menu.append(toggle, options);
      menu.addEventListener("toggle", () => {
        if (menu.open) document.querySelectorAll(".admin-action-menu[open]").forEach(other => { if (other !== menu) other.open = false; });
      });
      actions.append(menu);
    } else {
      actions.append(action("Edit profiles", () => openEditor(item.id)));
      actions.append(action("Vote distribution", () => openVotes("novels", item.id, item.title)));
    }
    results.append(row);
  }
  if (!data[kind].length) results.append(element("p", "No matches found."));
  const pages = document.getElementById(`${kind}-pages`);
  const previous = action("Previous", async () => { current.page--; await loadList(kind); });
  previous.disabled = current.page === 1;
  const next = action("Next", async () => { current.page++; await loadList(kind); });
  next.disabled = current.page * 25 >= data.total;
  pages.replaceChildren(previous, element("span", `Page ${current.page} / ${data.total} results`), next);
  status("");
}
async function openEditor(id) {
  if (dirty && !confirm("Discard unsaved profile changes?")) return;
  const version = ++editorVersion;
  const data = await request(`/novels/${id}/profiles`);
  if (version !== editorVersion) return;
  dirty = false;
  const editor = document.getElementById("profile-editor");
  const heading = element("div", undefined, "editor-heading");
  const title = element("div");
  title.append(element("p", "PROFILE WORKSPACE", "eyebrow"), element("h2", data.novel.title), element("p", "Saved scores are loaded below. Drag a slider or use the arrow keys to adjust it."));
  const novelLink = element("a", "View novel ↗", "admin-novel-link");
  novelLink.href = `/novel.html?id=${id}`;
  heading.append(title, novelLink);
  editor.replaceChildren(heading);
  const descriptions = {
    protagonist: "All ten scores must be filled in to enable voting, including zeros. Saved edits become the new defaults. Use Vote distribution → Lock scores to keep all protagonist scores fixed while votes continue to be collected.",
  };
  for (const [kind, profile] of Object.entries(data.profiles)) {
    const form = element("form", undefined, "admin-profile");
    const header = element("div", undefined, "profile-heading");
    const headingText = element("div");
    headingText.append(element("h3", `${kind[0].toUpperCase() + kind.slice(1)} profile`), element("p", descriptions[kind]));
    header.append(headingText);
    form.append(header);
    const fields = element("div", undefined, "admin-fields");
    const inputs = {};
    const saved = { ...profile.scores };
    let savedName = profile.protagonist_name || "";
    let saving = false;
    const feedback = element("p", "No unsaved changes.");
    feedback.setAttribute("role", "status");
    const save = element("button", "Save changes", "admin-primary");
    const reset = element("button", "Reset changes", "admin-secondary");
    const generate = element("button", "Generate with Gemini", "admin-secondary");
    generate.type = "button";
    reset.type = "button";
    function updateDirty() {
      const changed = Object.keys(saved).some(key => inputs[key].dataset.unset !== String(saved[key] == null) ||
        (inputs[key].dataset.unset !== "true" && Number(inputs[key].value) !== saved[key])) ||
        (inputs.protagonist_name && inputs.protagonist_name.value !== savedName);
      form.dataset.dirty = String(Boolean(changed));
      dirty = Boolean(editor.querySelector('[data-dirty="true"]'));
      save.disabled = saving || !changed;
      reset.disabled = saving || !changed;
      feedback.classList.remove("error");
      feedback.textContent = changed ? "Unsaved changes" : "No unsaved changes.";
    }
    function labelFor(key) {
      // VOTE_LABELS (admin-votes.js, loaded first) is the single trait-label table for this page.
      return VOTE_LABELS[key] || key.replaceAll("_", " ").replace(/^./, ch => ch.toUpperCase());
    }
    if (kind === "protagonist") {
      const label = element("label", "Protagonist name", "admin-name-field");
      const input = document.createElement("input");
      input.type = "text"; input.required = true; input.maxLength = 200;
      input.value = savedName; input.addEventListener("input", updateDirty);
      inputs.protagonist_name = input; label.append(input); form.append(label);
    }
    const renderers = {};
    for (const [key, value] of Object.entries(profile.scores)) {
      const label = element("label", undefined, "score-field");
      const top = element("span", undefined, "score-heading");
      const output = element("output");
      top.append(element("span", labelFor(key)), output);
      const input = document.createElement("input");
      input.type = "range"; input.min = 0; input.max = 100; input.step = 1;
      input.id = `score-${kind}-${key}`; input.setAttribute("aria-label", labelFor(key));
      output.htmlFor = input.id;
      input.value = value ?? 50; input.dataset.unset = String(value == null);
      const bottom = element("span", undefined, "score-scale");
      const baseline = element("span");
      bottom.append(element("span", "0"), baseline, element("span", "100"));
      function render() {
        const unset = input.dataset.unset === "true";
        output.textContent = unset ? "Not scored" : input.value;
        input.setAttribute("aria-valuetext", unset ? "Not scored; adjust to set a value" : `${input.value} out of 100`);
        input.style.setProperty("--score", `${input.value}%`);
        label.classList.toggle("is-unscored", unset);
        baseline.textContent = saved[key] == null ? "No saved score" : `Saved: ${saved[key]}`;
      }
      input.addEventListener("input", () => { input.dataset.unset = "false"; render(); updateDirty(); });
      // Clicking the midpoint also deliberately sets a previously missing score.
      input.addEventListener("change", () => { input.dataset.unset = "false"; render(); updateDirty(); });
      inputs[key] = input; renderers[key] = render; render();
      label.append(top, input, bottom); fields.append(label);
    }
    reset.addEventListener("click", () => {
      for (const key of Object.keys(saved)) {
        inputs[key].value = saved[key] ?? 50;
        inputs[key].dataset.unset = String(saved[key] == null); renderers[key]();
      }
      if (inputs.protagonist_name) inputs.protagonist_name.value = savedName;
      updateDirty();
    });
    const footer = element("div", undefined, "profile-footer");
    const buttons = element("div", undefined, "profile-actions");
    generate.addEventListener("click", async () => {
      if (saving) return;
      if (form.dataset.dirty === "true" && !confirm("Replace your unsaved edits with Gemini scores?")) return;
      saving = true;
      generate.disabled = save.disabled = reset.disabled = true;
      Object.values(inputs).forEach(input => { input.disabled = true; });
      generate.textContent = "Generating…";
      feedback.classList.remove("error");
      feedback.textContent = "Gemini is identifying the protagonist and scoring traits. This may take a minute.";
      form.setAttribute("aria-busy", "true");
      try {
        const draft = await request(`/novels/${id}/profiles/protagonist/generate`, { method: "POST" });
        if (version !== editorVersion) return;
        if (!draft.protagonist_name || Object.keys(saved).some(key => !Number.isInteger(draft.scores?.[key]) || draft.scores[key] < 0 || draft.scores[key] > 100)) {
          throw new Error("Gemini returned an incomplete profile. Existing scores were kept.");
        }
        for (const key of Object.keys(saved)) {
          inputs[key].value = draft.scores[key];
          inputs[key].dataset.unset = "false";
          renderers[key]();
        }
        inputs.protagonist_name.value = draft.protagonist_name;
        updateDirty();
        feedback.textContent = "Gemini draft ready. Review the scores, then save changes." + (draft.evidence_summary ? ` ${draft.evidence_summary}` : "");
      } catch (error) {
        feedback.textContent = error.message;
        feedback.classList.add("error");
      } finally {
        saving = false;
        form.removeAttribute("aria-busy");
        generate.disabled = false;
        generate.textContent = "Generate with Gemini";
        Object.values(inputs).forEach(input => { input.disabled = false; });
        save.disabled = form.dataset.dirty !== "true";
        reset.disabled = save.disabled;
      }
    });
    buttons.append(generate, reset, save); footer.append(feedback, buttons);
    form.append(fields, footer);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (saving || save.disabled) return;
      const missing = Object.keys(saved).find(key => inputs[key].dataset.unset === "true");
      if (missing) {
        feedback.textContent = `Set a score for ${labelFor(missing)} before saving this profile.`;
        feedback.classList.add("error"); inputs[missing].focus(); return;
      }
      saving = true; save.disabled = true; reset.disabled = true; generate.disabled = true;
      Object.values(inputs).forEach(input => { input.disabled = true; });
      feedback.textContent = "Saving changes...";
      const payload = { scores: Object.fromEntries(Object.keys(saved).map(key => [key, Number(inputs[key].value)])) };
      if (kind === "protagonist") payload.protagonist_name = inputs.protagonist_name.value.trim();
      try {
        await request(`/novels/${id}/profiles/${kind}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        Object.assign(saved, payload.scores);
        if (inputs.protagonist_name) { savedName = payload.protagonist_name; inputs.protagonist_name.value = savedName; }
        Object.values(renderers).forEach(render => render());
        updateDirty(); feedback.textContent = "Changes saved.";
      } catch (error) { feedback.textContent = error.message; feedback.classList.add("error"); }
      finally {
        saving = false;
        generate.disabled = false;
        Object.values(inputs).forEach(input => { input.disabled = false; });
        save.disabled = form.dataset.dirty !== "true"; reset.disabled = save.disabled;
      }
    });
    editor.append(form); updateDirty();
  }
  editor.scrollIntoView({ behavior: "smooth", block: "start" });
}

let selectedHomeNovel = null;

function renderHomeFeatureSelection(novel) {
  selectedHomeNovel = novel;
  document.getElementById("home-feature-novel-id").value = novel?.id || "";
  document.getElementById("home-feature-selection").textContent = novel
    ? `Featured novel: ${novel.title}${novel.author ? ` by ${novel.author}` : ""}`
    : "Choose a novel to begin.";
}

async function loadHomeFeature() {
  const data = await request("/home-feature");
  const feature = data.feature;
  if (!feature) return;
  renderHomeFeatureSelection(feature.novel);
  document.getElementById("home-feature-inquiry").value = feature.inquiry;
  document.getElementById("home-feature-description").value = feature.description;
  document.getElementById("home-feature-tags").value = (feature.tags || []).join(", ");
  document.getElementById("home-feature-status").textContent = "Current published feature loaded.";
}

async function searchHomeFeatureNovels() {
  const query = document.getElementById("home-feature-query").value.trim();
  const data = await request(`/novels?q=${encodeURIComponent(query)}&page=1`);
  const results = document.getElementById("home-feature-results");
  results.replaceChildren();
  if (!data.novels.length) {
    results.append(element("p", "No catalogue novels match that search."));
    return;
  }
  data.novels.forEach((novel) => {
    const row = element("div", undefined, "home-feature-result");
    const copy = element("div");
    copy.append(element("strong", novel.title), element("small", novel.author || "Unknown author"));
    const choose = action(selectedHomeNovel?.id === novel.id ? "Selected" : "Choose", async () => {
      renderHomeFeatureSelection(novel);
      document.getElementById("home-feature-status").textContent = "Novel selected. Add the editorial copy, then publish.";
      results.querySelectorAll("button").forEach((button) => { button.textContent = "Choose"; });
      choose.textContent = "Selected";
    });
    choose.disabled = selectedHomeNovel?.id === novel.id;
    row.append(copy, choose);
    results.append(row);
  });
}

document.getElementById("home-tab").addEventListener("click", () => {
  ["users", "novels", "home"].forEach((section) => {
    document.getElementById(`${section}-panel`).hidden = section !== "home";
    document.getElementById(`${section}-tab`).setAttribute("aria-pressed", String(section === "home"));
  });
  loadHomeFeature().catch((error) => status(error.message, true));
});
document.getElementById("home-feature-search").addEventListener("submit", (event) => {
  event.preventDefault();
  searchHomeFeatureNovels().catch((error) => status(error.message, true));
});
document.getElementById("home-feature-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const statusEl = document.getElementById("home-feature-status");
  const novelId = Number(document.getElementById("home-feature-novel-id").value);
  if (!novelId) { statusEl.textContent = "Choose a catalogue novel first."; return; }
  const submit = event.currentTarget.querySelector("button[type='submit']");
  submit.disabled = true;
  statusEl.textContent = "Publishing…";
  try {
    await request("/home-feature", {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        novel_id: novelId,
        inquiry: document.getElementById("home-feature-inquiry").value,
        description: document.getElementById("home-feature-description").value,
        tags: document.getElementById("home-feature-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
      }),
    });
    statusEl.textContent = "Published. The Home page will now show this feature.";
  } catch (error) { statusEl.textContent = error.message; statusEl.classList.add("error"); }
  finally { submit.disabled = false; }
});
document.getElementById("rebuild-outdated").addEventListener("click", () => startRebuild(false).catch(error => rebuildStatus(error.message, true)));
document.getElementById("rebuild-all").addEventListener("click", () => startRebuild(true).catch(error => rebuildStatus(error.message, true)));
document.getElementById("refresh-rebuild-history").addEventListener("click", () => loadRebuildHistory().catch(error => rebuildStatus(error.message, true)));

for (const kind of ["users", "novels"]) {
  document.getElementById(`${kind}-tab`).addEventListener("click", () => {
    for (const section of ["users", "novels", "home"]) {
      document.getElementById(`${section}-panel`).hidden = section !== kind;
      document.getElementById(`${section}-tab`).setAttribute("aria-pressed", String(section === kind));
    }
    if (kind === "novels") loadRebuildHistory().catch(error => rebuildStatus(error.message, true));
    loadList(kind).catch(error => status(error.message, true));
  });
  document.getElementById(`${kind}-search`).addEventListener("submit", event => {
    event.preventDefault();
    state[kind].query = document.getElementById(`${kind}-query`).value.trim(); state[kind].page = 1;
    loadList(kind).catch(error => status(error.message, true));
  });
}
window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
(async () => {
  try { const me = await request("/me"); adminId = me.id; adminContent.hidden = false; await loadList("users"); }
  catch (error) { status(error.message, true); }
})();

// Native details menus support keyboard activation; close on Escape or outside click.
document.addEventListener("click", event => {
  document.querySelectorAll(".admin-action-menu[open]").forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") document.querySelectorAll(".admin-action-menu[open]").forEach(menu => { menu.open = false; menu.querySelector("summary").focus(); });
});
