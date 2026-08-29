let lastSearch = null;

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
    tagsEl: document.querySelector("[data-upload-tags]"),
    synopsisEl: document.querySelector("[data-upload-synopsis]"),
    successEl: document.querySelector("[data-upload-success]"),
    addButton: document.querySelector("[data-upload-add-button]"),
    editButton: document.querySelector("[data-upload-edit]"),
    closeButton: document.querySelector("[data-upload-close]"),
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

function renderPreview(elements, novel) {
  elements.titleEl.textContent = novel.title || "Untitled";
  elements.authorEl.textContent = novel.author || "Unknown";
  elements.statusEl.textContent = novel.status || "Unknown";
  elements.tagsEl.textContent = (novel.genres || []).join(", ") || "None";
  elements.synopsisEl.textContent = novel.synopsis || "No synopsis available.";

  elements.coverEl.innerHTML = "";
  if (novel.cover_image_url) {
    const image = document.createElement("img");
    image.className = "upload-preview-cover-image";
    image.src = novel.cover_image_url;
    image.alt = "";
    image.referrerPolicy = "no-referrer";
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

function initUploadForm() {
  const elements = getUploadElements();
  elements.form.addEventListener("submit", (event) => handleSearch(event, elements));
  elements.addButton.addEventListener("click", () => handleAdd(elements));
  elements.editButton.addEventListener("click", () => resetToForm(elements));
  elements.closeButton.addEventListener("click", closeUploadForm);
}

if (!getAccessToken()) {
  window.location.href = "/login.html";
} else {
  initUploadForm();
}