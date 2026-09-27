const DIRECTORY_API_BASE = "http://localhost:8000";

const searchForm = document.querySelector("[data-reader-search]");
const searchInput = document.querySelector("#reader-query");
const statusEl = document.querySelector("[data-reader-status]");
const resultsEl = document.querySelector("[data-reader-results]");
const sortSelect = document.querySelector("[data-reader-sort]");

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = value || "";
  return element.innerHTML;
}

function initialFor(user) {
  return (user.username || "?").trim().charAt(0).toUpperCase() || "?";
}

function avatarMarkup(user) {
  if (user.avatar_url) {
    return `<img src="${escapeHtml(user.avatar_url)}" alt="" loading="lazy">`;
  }
  return `<span>${escapeHtml(initialFor(user))}</span>`;
}

function renderUsers(users, query) {
  if (!users.length) {
    const message = query
      ? `No readers match “${escapeHtml(query)}”.`
      : "No reader profiles are available yet.";
    resultsEl.innerHTML = `<p class="reader-directory-empty">${message}</p>`;
    return;
  }

  resultsEl.innerHTML = users.map((user) => {
    const tags = Array.isArray(user.tag_preferences) ? user.tag_preferences.slice(0, 3) : [];
    const tagMarkup = tags.length
      ? `<div class="reader-directory-tags">${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>`
      : "";
    const location = user.country ? `<p class="reader-directory-location">${escapeHtml(user.country)}</p>` : "";
    const about = user.about_me
      ? `<p class="reader-directory-about">${escapeHtml(user.about_me)}</p>`
      : `<p class="reader-directory-about is-empty">A fellow Axiom reader.</p>`;

    return `<a class="reader-directory-card" href="/user.html?id=${encodeURIComponent(user.id)}">
      <span class="reader-directory-avatar">${avatarMarkup(user)}</span>
      <span class="reader-directory-body">
        <span class="reader-directory-name"><strong>${escapeHtml(user.username || "Reader")}</strong>${user.special ? '<span class="account-special-badge">Admin</span>' : ""}</span>
        ${location}
        ${about}
        ${tagMarkup}
      </span>
      <span class="reader-directory-arrow" aria-hidden="true">→</span>
    </a>`;
  }).join("");
}

async function loadReaders(query = "", sort = sortSelect.value) {
  statusEl.textContent = "Loading readers…";
  resultsEl.innerHTML = "";
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  params.set("sort", sort);

  try {
    const response = await fetch(`${DIRECTORY_API_BASE}/api/users?${params}`);
    if (!response.ok) throw new Error("Directory request failed");
    const payload = await response.json();
    const users = payload.users || [];
    statusEl.textContent = users.length
      ? `${users.length} reader${users.length === 1 ? "" : "s"}${query ? ` matching “${query}”` : ""}`
      : "";
    renderUsers(users, query);
  } catch {
    statusEl.textContent = "";
    resultsEl.innerHTML = "<p class=\"reader-directory-empty\">We couldn't load the reader directory. Please try again.</p>";
  }
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  loadReaders(searchInput.value.trim());
});

sortSelect.addEventListener("change", () => {
  loadReaders(searchInput.value.trim(), sortSelect.value);
});

loadReaders();
