let lastSearch = null;
let myUploadsLoaded = false;

function getUploadElements() {
  return {
    form: document.querySelector("[data-upload-form]"),
    errorEl: document.querySelector("[data-upload-error]"),
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

  clearMessage(elements.successEl);
  elements.addButton.disabled = false;
  elements.addButton.textContent = "Add to Axiom";

  elements.form.classList.add("is-hidden");
  elements.preview.classList.remove("is-hidden");
}

function resetToForm(elements) {
  elements.form.reset();
  elements.form.classList.remove("is-hidden");
  elements.preview.classList.add("is-hidden");
  clearMessage(elements.errorEl);
  clearMessage(elements.successEl);
  elements.addButton.disabled = false;
  elements.addButton.textContent = "Add to Axiom";
  lastSearch = null;
}

async function handleSearch(event, elements) {
  event.preventDefault();

  const url = elements.form.url.value.trim();
  const source = elements.form.source.value;
  clearMessage(elements.errorEl);

  if (!url || !source) {
    showError(elements.errorEl, "Enter a novel URL and choose a source.");
    return;
  }

  elements.searchButton.disabled = true;
  elements.searchButton.textContent = "Searching...";

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

    lastSearch = { url, source };
    renderPreview(elements, result);
  } catch (error) {
    showError(elements.errorEl, "Couldn't reach the backend. Make sure it is running on port 8000.");
  } finally {
    elements.searchButton.disabled = false;
    elements.searchButton.textContent = "Search";
  }
}

async function handleAdd(elements) {
  if (!lastSearch) return;

  clearMessage(elements.successEl);
  elements.addButton.disabled = true;
  elements.addButton.textContent = "Adding...";
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
      elements.successEl.textContent = "";
      elements.successEl.append("Novel already exists: ");
      const link = document.createElement("a");
      link.href = `/novel.html?id=${detail.novel_id}`;
      link.textContent = detail.title || "View novel";
      elements.successEl.appendChild(link);
      elements.successEl.classList.remove("is-hidden");
      return;
    }

    if (!response.ok) {
      elements.successEl.textContent =
        typeof result.detail === "string" ? result.detail : "URL is invalid or source is incorrect.";
      elements.successEl.classList.remove("is-hidden");
      return;
    }

    elements.successEl.textContent = "";
    elements.successEl.append("Added to Axiom: ");
    const link = document.createElement("a");
    link.href = `/novel.html?id=${result.id}`;
    link.textContent = result.title || "View novel";
    elements.successEl.appendChild(link);
    elements.successEl.classList.remove("is-hidden");
    added = true;

    // The new novel now belongs in "Your uploaded novels" -- refresh it
    // so it's up to date next time the user expands the list.
    myUploadsLoaded = false;
    if (elements.mineToggle.getAttribute("aria-expanded") === "true") {
      loadMyUploads(elements);
    }
  } catch (error) {
    elements.successEl.textContent = "Couldn't reach the backend. Make sure it is running on port 8000.";
    elements.successEl.classList.remove("is-hidden");
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

function initUploadForm() {
  const elements = getUploadElements();
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
