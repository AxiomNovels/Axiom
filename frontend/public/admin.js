const adminStatus = document.getElementById("admin-status");
const adminContent = document.getElementById("admin-content");
let adminId;
let dirty = false;
let editorVersion = 0;
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
async function loadList(kind) {
  const current = state[kind];
  const version = ++current.version;
  status("Loadingâ€¦");
  const data = await request(`/${kind}?q=${encodeURIComponent(current.query)}&page=${current.page}`);
  if (version !== current.version) return;
  const results = document.getElementById(`${kind}-results`);
  results.replaceChildren();
  for (const item of data[kind]) {
    const row = element("div", undefined, "admin-row");
    const description = element("div", kind === "users" ? item.username : item.title);
    description.append(element("small", kind === "users"
      ? `${item.special ? "SPECIAL Â· " : ""}${item.banned ? "Banned" : "Active"}`
      : (item.author || "Unknown author")));
    row.append(description);
    if (kind === "users") {
      if (!item.special && item.id !== adminId) row.append(action(item.banned ? "Unban" : "Ban account", async () => {
        if (!confirm(`${item.banned ? "Unban" : "Ban"} ${item.username}?`)) return;
        await request(`/users/${item.id}/ban`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ banned: !item.banned }) });
        await loadList(kind);
        status(`${item.username} ${item.banned ? "unbanned" : "banned"}.`);
      }));
    } else row.append(action("Edit profiles", () => openEditor(item.id)));
    results.append(row);
  }
  if (!data[kind].length) results.append(element("p", "No matches found."));
  const pages = document.getElementById(`${kind}-pages`);
  const previous = action("Previous", async () => { current.page--; await loadList(kind); });
  previous.disabled = current.page === 1;
  const next = action("Next", async () => { current.page++; await loadList(kind); });
  next.disabled = current.page * 25 >= data.total;
  pages.replaceChildren(previous, element("span", `Page ${current.page} Â· ${data.total} results`), next);
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
    protagonist: "The character behind the story: motivations, attachments, and temperament.",
    philosophy: "The ideas and philosophical themes that shape the novel.",
    storytelling: "How the story unfolds: its focus, structure, and style."
  };
  let profileIndex = 0;
  for (const [kind, profile] of Object.entries(data.profiles)) {
    const form = element("form", undefined, "admin-profile");
    const header = element("div", undefined, "profile-heading");
    header.append(element("span", String(++profileIndex).padStart(2, "0"), "profile-index"));
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
      return ({arrogance_pride: "Ego", kinship_friendship: "Kinship & friendship", sexual_desire: "Lust"})[key] || key.replaceAll("_", " ").replace(/^./, ch => ch.toUpperCase());
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
    buttons.append(reset, save); footer.append(feedback, buttons);
    form.append(fields, footer);
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (saving || save.disabled) return;
      const missing = Object.keys(saved).find(key => inputs[key].dataset.unset === "true");
      if (missing) {
        feedback.textContent = `Set a score for ${labelFor(missing)} before saving this profile.`;
        feedback.classList.add("error"); inputs[missing].focus(); return;
      }
      saving = true; save.disabled = true; reset.disabled = true;
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
        Object.values(inputs).forEach(input => { input.disabled = false; });
        save.disabled = form.dataset.dirty !== "true"; reset.disabled = save.disabled;
      }
    });
    editor.append(form); updateDirty();
  }
  editor.scrollIntoView({ behavior: "smooth", block: "start" });
}
for (const kind of ["users", "novels"]) {
  document.getElementById(`${kind}-tab`).addEventListener("click", () => {
    for (const section of ["users", "novels"]) {
      document.getElementById(`${section}-panel`).hidden = section !== kind;
      document.getElementById(`${section}-tab`).setAttribute("aria-pressed", String(section === kind));
    }
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
