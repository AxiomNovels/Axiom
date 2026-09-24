let lastSearch = null;
let myUploadsLoaded = false;

function getUploadElements() {
  return {
    form: document.querySelector("[data-upload-form]"),
    errorEl: document.querySelector("[data-upload-error]"),
    progressEl: document.querySelector("[data-upload-progress]"),
    searchButton: document.querySelector("[data-upload-search-button]"),
    preview: document.querySelector("[data-upload-preview]"),
    coverEl: document.querySelector("[data-upload-cover]"),
    titleEl: document.querySelector("[data-upload-title]"),
    authorEl: document.querySelector("[data-upload-author]"),
    statusEl: document.querySelector("[data-upload-status]"),
    chaptersEl: document.querySelector("[data-upload-chapters]"),
    genresEl: document.querySelector("[data-upload-genres]"),
    tagsEl: document.querySelector("[data-upload-tags]"),
    synopsisEl: document.querySelector("[data-upload-synopsis]"),
    profilesEl: document.querySelector("[data-upload-profiles]"),
    successEl: document.querySelector("[data-upload-success]"),
    addButton: document.querySelector("[data-upload-add-button]"),
    editButton: document.querySelector("[data-upload-edit]"),
    closeButton: document.querySelector("[data-upload-close]"),
    mineToggle: document.querySelector("[data-upload-mine-toggle]"),
    mineToggleLabel: document.querySelector("[data-upload-mine-toggle-label]"),
    mineList: document.querySelector("[data-upload-mine-list]"),
  };
}

function showError(errorEl, message) {
  errorEl.textContent = message;
  errorEl.classList.remove("is-hidden");
}

function clearMessage(el) {
  el.textContent = "";
  el.classList.add("is-hidden");
}

function showMessage(el, message) {
  el.textContent = message;
  el.classList.remove("is-hidden");
}

// "<prefix> <link to the novel>" -- used for both "Added to Axiom" and
// "Novel already exists".
function showNovelLink(el, prefix, novelId, title) {
  el.textContent = "";
  el.append(`${prefix}: `);
  const link = document.createElement("a");
  link.href = `/novel.html?id=${encodeURIComponent(novelId)}`;
  link.textContent = title || "View novel";
  el.appendChild(link);
  el.classList.remove("is-hidden");
}

// Chapter counts are optional -- a source page may not expose one,
// or scraping it may fail -- so this falls back to "Unknown" the same
// way author/status already do, rather than showing a misleading 0.
// When a count is available it's shown compactly (e.g. "123.4K") with
// the exact figure available on hover/focus via the title attribute.
function describeCount(el, value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) {
    el.textContent = "Unknown";
    el.removeAttribute("title");
    return;
  }
  el.textContent = formatCompactNumber(number);
  el.title = number.toLocaleString();
}

// ---------------------------------------------------------------------
// Profiles
//
// Everything below renders whatever the API sends. It knows nothing about
// individual traits, how many profiles there are, or how many traits each
// has: the backend supplies titles and display labels. Changing the
// profiler's traits or prompts therefore needs no change on this page.
//
// A profile looks like:
//   { kind, title, description, status, message, protagonist_name,
//     confidence, evidence_summary, scores: [{ key, label, score }] }
// where status is "ready" (previewed), "saved", "skipped" or "failed".
// ---------------------------------------------------------------------

const PROFILE_BADGES = {
  saved: { text: "Saved", className: "is-saved" },
  failed: { text: "Unavailable", className: "is-failed" },
  skipped: { text: "Skipped", className: "" },
};

function createScoreRow(item) {
  const score = Math.max(0, Math.min(100, Number(item.score) || 0));

  const row = document.createElement("div");
  row.className = "trait-row";

  const label = document.createElement("div");
  label.className = "trait-label";
  label.textContent = item.label || item.key || "";

  const track = document.createElement("div");
  track.className = "trait-bar-track";
  const fill = document.createElement("div");
  fill.className = "trait-bar-fill";
  fill.style.width = `${score}%`;
  track.appendChild(fill);

  const value = document.createElement("div");
  value.className = "trait-score";
  value.textContent = String(score);

  row.append(label, track, value);
  return row;
}

function createProfileCard(profile) {
  const card = document.createElement("section");
  card.className = "profile-section upload-profile";

  const header = document.createElement("div");
  header.className = "upload-profile-header";
  const heading = document.createElement("div");
  const title = document.createElement("h3");
  title.className = "upload-profile-title";
  title.textContent = profile.title || profile.kind || "Profile";
  heading.appendChild(title);
  if (profile.description) {
    const description = document.createElement("p");
    description.className = "upload-profile-description";
    description.textContent = profile.description;
    heading.appendChild(description);
  }
  header.appendChild(heading);

  const badgeConfig = PROFILE_BADGES[profile.status];
  if (badgeConfig) {
    const badge = document.createElement("span");
    badge.className = `upload-profile-badge ${badgeConfig.className}`.trim();
    badge.textContent = badgeConfig.text;
    header.appendChild(badge);
  }
  card.appendChild(header);

  const scores = Array.isArray(profile.scores) ? profile.scores : [];
  if (!scores.length) {
    const note = document.createElement("p");
    note.className = `upload-profile-note${profile.status === "failed" ? " is-failed" : ""}`;
    note.textContent = profile.message || "This profile isn't available.";
    card.appendChild(note);
    return card;
  }

  if (profile.protagonist_name) {
    const subject = document.createElement("p");
    subject.className = "upload-profile-subject";
    subject.append("Protagonist: ");
    const name = document.createElement("strong");
    name.textContent = profile.protagonist_name;
    subject.appendChild(name);
    card.appendChild(subject);
  }

  scores.forEach((item) => card.appendChild(createScoreRow(item)));

  const metaLines = [];
  if (typeof profile.confidence === "number") {
    metaLines.push(`Confidence: ${profile.confidence} out of 100`);
  }
  if (profile.evidence_summary) metaLines.push(profile.evidence_summary);
  if (metaLines.length) {
    const meta = document.createElement("p");
    meta.className = "upload-profile-meta";
    metaLines.forEach((text) => {
      const line = document.createElement("span");
      line.textContent = text;
      meta.appendChild(line);
    });
    card.appendChild(meta);
  }

  return card;
}

function renderProfiles(elements, profiling, { saved = false } = {}) {
  const container = elements.profilesEl;
  if (!container) return;
  container.replaceChildren();

  const profiles = Array.isArray(profiling?.profiles) ? profiling.profiles : [];
  const notice = typeof profiling?.notice === "string" ? profiling.notice : "";
  if (!profiles.length && !notice) {
    container.classList.add("is-hidden");
    return;
  }

  if (profiles.length) {
    const heading = document.createElement("h3");
    heading.className = "upload-profiles-heading";
    heading.textContent = "Profiles";
    const intro = document.createElement("p");
    intro.className = "upload-profiles-intro";
    intro.textContent = saved
      ? "Here is what was saved with the novel."
      : "Generated automatically from the synopsis, tags, and public reader comments. These are saved with the novel when you add it.";
    container.append(heading, intro);
    profiles.forEach((profile) => container.appendChild(createProfileCard(profile)));
  }

  if (notice) {
    const noticeEl = document.createElement("p");
    noticeEl.className = "upload-profiles-notice";
    noticeEl.textContent = notice;
    container.appendChild(noticeEl);
  }

  container.classList.remove("is-hidden");
}

// ---------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------

function renderPreview(elements, novel) {
  elements.titleEl.textContent = novel.title || "Untitled";
  elements.authorEl.textContent = novel.author || "Unknown";
  elements.statusEl.textContent = novel.status || "Unknown";
  describeCount(elements.chaptersEl, novel.chapter_count);
  elements.genresEl.textContent = (novel.genres || []).join(", ") || "None";
  elements.tagsEl.textContent = (novel.tags || []).join(", ") || "None";
  elements.synopsisEl.textContent = novel.synopsis || "No synopsis available.";

  elements.coverEl.innerHTML = "";
  if (novel.cover_image_url) {
    const image = document.createElement("img");
    image.className = "upload-preview-cover-image";
    image.referrerPolicy = "no-referrer";
    image.src = novel.cover_image_url;
    image.alt = "";
    image.addEventListener("error", () => image.remove(), { once: true });
    elements.coverEl.appendChild(image);
  }

  renderProfiles(elements, novel.profiling);

  clearMessage(elements.successEl);
  elements.addButton.disabled = false;
  elements.addButton.textContent = "Add to Axiom";

  // The server already knows this novel is in the catalogue, so say so now
  // instead of waiting for the add attempt to be rejected.
  if (novel.existing_novel) {
    showNovelLink(elements.successEl, "Novel already exists", novel.existing_novel.id, novel.existing_novel.title);
    elements.addButton.disabled = true;
  }

  elements.form.classList.add("is-hidden");
  elements.preview.classList.remove("is-hidden");
}

function resetToForm(elements) {
  elements.form.reset();
  elements.form.classList.remove("is-hidden");
  elements.preview.classList.add("is-hidden");
  clearMessage(elements.errorEl);
  clearMessage(elements.progressEl);
  clearMessage(elements.successEl);
  renderProfiles(elements, null);
  elements.addButton.disabled = false;
  elements.addButton.textContent = "Add to Axiom";
  lastSearch = null;
}

async function handleSearch(event, elements) {
  event.preventDefault();
  if (elements.searchButton.disabled) return;

  const url = elements.form.url.value.trim();
  const source = elements.form.source.value;
  clearMessage(elements.errorEl);

  if (!url || !source) {
    showError(elements.errorEl, "Enter a novel URL and choose a source.");
    return;
  }

  elements.searchButton.disabled = true;
  elements.searchButton.textContent = "Searching...";
  showMessage(
    elements.progressEl,
    "Reading the novel page and generating its profiles. This can take up to a minute."
  );

  try {
    const response = await authFetch(`${API_BASE}/api/novels/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, source }),
    });

    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }

    const result = await response.json().catch(() => ({}));

    if (!response.ok) {
      showError(
        elements.errorEl,
        typeof result.detail === "string" ? result.detail : "URL is invalid or source is incorrect."
      );
      return;
    }

    // profile_token lets the server save exactly the profiles shown below
    // instead of generating new ones when the novel is added.
    lastSearch = { url, source, profile_token: result.profiling?.token || null };
    renderPreview(elements, result);
  } catch (error) {
    showError(elements.errorEl, "Couldn't reach the backend. Make sure it is running on port 8000.");
  } finally {
    clearMessage(elements.progressEl);
    elements.searchButton.disabled = false;
    elements.searchButton.textContent = "Search";
  }
}

async function handleAdd(elements) {
  if (!lastSearch) return;

  elements.addButton.disabled = true;
  elements.addButton.textContent = "Adding...";
  showMessage(elements.successEl, "Saving the novel and its profiles...");
  let added = false;

  try {
    const response = await authFetch(`${API_BASE}/api/novels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(lastSearch),
    });

    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }

    const result = await response.json().catch(() => ({}));

    if (response.status === 409) {
      const detail = result.detail || {};
      showNovelLink(elements.successEl, "Novel already exists", detail.novel_id, detail.title);
      return;
    }

    if (!response.ok) {
      showMessage(
        elements.successEl,
        typeof result.detail === "string" ? result.detail : "URL is invalid or source is incorrect."
      );
      return;
    }

    showNovelLink(elements.successEl, "Added to Axiom", result.id, result.title);
    added = true;

    // Show what was actually stored, which is what the user previewed
    // unless a profile couldn't be saved.
    if (result.profiling) renderProfiles(elements, result.profiling, { saved: true });

    // The new novel now belongs in "Your uploaded novels" -- refresh it
    // so it's up to date next time the user expands the list.
    myUploadsLoaded = false;
    if (elements.mineToggle.getAttribute("aria-expanded") === "true") {
      loadMyUploads(elements);
    }
  } catch (error) {
    showMessage(elements.successEl, "Couldn't reach the backend. Make sure it is running on port 8000.");
  } finally {
    elements.addButton.textContent = "Add to Axiom";
    elements.addButton.disabled = added;
  }
}

function closeUploadForm() {
  if (window.history.length > 1) {
    window.history.back();
  } else {
    window.location.href = "/";
  }
}

async function loadMyUploads(elements) {
  const list = elements.mineList;
  list.innerHTML = "<p>Loading&hellip;</p>";

  try {
    const response = await authFetch(`${API_BASE}/api/novels/mine`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) throw new Error("Failed to load your novels");

    const novels = await response.json();
    myUploadsLoaded = true;

    elements.mineToggleLabel.textContent = `Your uploaded novels (${novels.length})`;

    list.innerHTML = "";
    if (!novels.length) {
      list.innerHTML = "<p class=\"upload-mine-empty\">You haven't uploaded any novels yet.</p>";
      return;
    }

    const ul = document.createElement("ul");
    novels.forEach((novel) => {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.href = `/novel.html?id=${novel.id}`;
      link.textContent = novel.title;
      li.appendChild(link);
      ul.appendChild(li);
    });
    list.appendChild(ul);
  } catch (error) {
    list.innerHTML = "<p class=\"upload-mine-empty\">Couldn't load your uploaded novels.</p>";
  }
}

function setupMyUploads(elements) {
  elements.mineToggle.addEventListener("click", () => {
    const expanded = elements.mineToggle.getAttribute("aria-expanded") === "true";
    elements.mineToggle.setAttribute("aria-expanded", String(!expanded));
    elements.mineList.classList.toggle("is-hidden", expanded);

    if (!expanded && !myUploadsLoaded) {
      loadMyUploads(elements);
    }
  });
}

function setupSourceAutodetect(elements) {
  const urlInput = elements.form.url;
  const sourceSelect = elements.form.source;

  urlInput.addEventListener("input", () => {
    const value = urlInput.value.trim().toLowerCase();

    if (!value) {
      sourceSelect.value = "";
      return;
    }

    // Allow URLs with or without https://
    let hostname = "";
    try {
      const normalized = /^https?:\/\//i.test(value) ? value : `https://${value}`;
      hostname = new URL(normalized).hostname.toLowerCase();
    } catch {
      // URL isn't complete/valid yet; leave the current selection alone.
      return;
    }

    if (hostname === "webnovel.com" || hostname.endsWith(".webnovel.com")) {
      sourceSelect.value = "WebNovel";
    } else if (hostname === "wattpad.com" || hostname.endsWith(".wattpad.com")) {
      sourceSelect.value = "Wattpad";
    } else if (hostname === "royalroad.com" || hostname.endsWith(".royalroad.com")) {
      sourceSelect.value = "Royal Road";
    }
  });
}

function initUploadForm() {
  const elements = getUploadElements();
  setupSourceAutodetect(elements);
  elements.form.addEventListener("submit", (event) => handleSearch(event, elements));
  elements.addButton.addEventListener("click", () => handleAdd(elements));
  elements.editButton.addEventListener("click", () => resetToForm(elements));
  elements.closeButton.addEventListener("click", closeUploadForm);
  setupMyUploads(elements);
}

if (!getAccessToken()) {
  window.location.href = "/login.html";
} else {
  initUploadForm();
}
