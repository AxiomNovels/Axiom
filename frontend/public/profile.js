function requireSession() {
  if (!getAccessToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

const preferredTags = new Set();
let allTags = [];

function renderPreferredTags() {
  const container = document.querySelector("[data-selected-tags]");
  container.innerHTML = "";
  if (!preferredTags.size) {
    container.innerHTML = "<p>No tag preferences added yet.</p>";
    return;
  }
  preferredTags.forEach((tag) => {
    const chip = document.createElement("div");
    chip.className = "selected-tag";
    const name = document.createElement("span");
    name.textContent = tag;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "tag-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${tag}`);
    remove.addEventListener("click", () => {
      preferredTags.delete(tag);
      renderPreferredTags();
      renderSuggestions();
    });
    chip.append(name, remove);
    container.appendChild(chip);
  });
}

function addTag(tag) {
  preferredTags.add(tag);
  const input = document.getElementById("tag-search");
  input.value = "";
  input.focus();
  renderPreferredTags();
  renderSuggestions();
}

function renderSuggestions() {
  const input = document.getElementById("tag-search");
  const list = document.querySelector("[data-tag-suggestions]");
  const query = input.value.trim().toLowerCase();
  if (!query) {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    return;
  }
  const matches = allTags
    .filter((tag) => tag.toLowerCase().includes(query) && !preferredTags.has(tag))
    .slice(0, 8);
  list.innerHTML = "";
  matches.forEach((tag) => {
    const option = document.createElement("button");
    option.type = "button";
    option.role = "option";
    option.textContent = tag;
    option.addEventListener("click", () => addTag(tag));
    list.appendChild(option);
  });
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.textContent = "No matching tags";
    list.appendChild(empty);
  }
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

async function loadTagOptions() {
  const tagInput = document.getElementById("tag-search");
  try {
    const response = await fetch(`${API_BASE}/api/search/options`);
    if (!response.ok) throw new Error("Options request failed");
    const options = await response.json();
    allTags = options.tags || [];
    tagInput.disabled = !allTags.length;
    tagInput.placeholder = allTags.length ? "Start typing a tag..." : "No tags are available yet";
  } catch {
    tagInput.disabled = true;
    tagInput.placeholder = "Couldn't load tags";
  }
}

function setupTagCombobox() {
  const tagInput = document.getElementById("tag-search");
  tagInput.addEventListener("input", renderSuggestions);
  tagInput.addEventListener("focus", renderSuggestions);
  tagInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const first = document.querySelector("[data-tag-suggestions] button");
      if (first) first.click();
    }
    if (event.key === "Escape") {
      document.querySelector("[data-tag-suggestions]").hidden = true;
      tagInput.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".tag-combobox")) {
      document.querySelector("[data-tag-suggestions]").hidden = true;
      tagInput.setAttribute("aria-expanded", "false");
    }
  });
}

function setupAboutMeCounter() {
  const textarea = document.getElementById("about-me");
  const counter = document.querySelector("[data-about-me-counter]");
  const updateCounter = () => {
    counter.textContent = `${textarea.value.length}/500 characters`;
  };
  textarea.addEventListener("input", updateCounter);
  updateCounter();
}

function formatJoinDate(isoString) {
  if (!isoString) return "Unknown";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function showProfileMessage(message, isError = false) {
  const el = document.querySelector("[data-profile-message]");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("is-hidden");
  el.classList.toggle("profile-message-error", isError);
}

function clearProfileMessage() {
  const el = document.querySelector("[data-profile-message]");
  if (!el) return;
  el.textContent = "";
  el.classList.add("is-hidden");
  el.classList.remove("profile-message-error");
}

async function loadProfile() {
  const usernameEl = document.querySelector("[data-profile-username]");
  const joinDateEl = document.querySelector("[data-profile-join-date]");
  const form = document.querySelector("[data-profile-form]");
  const aboutMeEl = document.getElementById("about-me");
  const counterEl = document.querySelector("[data-about-me-counter]");

  try {
    const response = await authFetch(`${API_BASE}/api/profile`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) throw new Error("Failed to load profile");

    const profile = await response.json();

    if (usernameEl) usernameEl.textContent = profile.username || "";
    if (joinDateEl) joinDateEl.textContent = formatJoinDate(profile.created_at);
    document.title = `${profile.username || "Profile"} | Axiom`;

    form.gender.value = profile.gender || "Prefer not to say";
    form.city.value = profile.city || "";
    form.country.value = profile.country || "";
    aboutMeEl.value = profile.about_me || "";
    counterEl.textContent = `${(profile.about_me || "").length}/500 characters`;

    (profile.tag_preferences || []).forEach((tag) => preferredTags.add(tag));
    renderPreferredTags();
  } catch (error) {
    if (usernameEl) usernameEl.textContent = "Couldn't load";
    if (joinDateEl) joinDateEl.textContent = "Couldn't load";
    console.error("[profile.js] failed to load profile:", error);
    showProfileMessage("Couldn't load your profile. Make sure the backend is running on port 8000.", true);
  }
}

function setupProfileForm() {
  const form = document.querySelector("[data-profile-form]");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearProfileMessage();

    const button = form.querySelector('button[type="submit"]');
    const originalText = button.textContent;
    button.textContent = "Saving...";
    button.disabled = true;

    const payload = {
      gender: form.gender.value,
      city: form.city.value.trim(),
      country: form.country.value.trim(),
      about_me: document.getElementById("about-me").value.trim(),
      tag_preferences: [...preferredTags],
    };

    try {
      const response = await authFetch(`${API_BASE}/api/profile`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message =
          (typeof result.detail === "string" && result.detail) ||
          (Array.isArray(result.detail) && result.detail[0]?.msg) ||
          "Couldn't save your profile. Please try again.";
        showProfileMessage(message, true);
        return;
      }
      showProfileMessage("Profile saved.");
    } catch (error) {
      showProfileMessage("Couldn't reach the backend. Make sure it is running on port 8000.", true);
    } finally {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
}

if (requireSession()) {
  setupTagCombobox();
  setupAboutMeCounter();
  loadTagOptions();
  loadProfile();
  setupProfileForm();
}