function getUserIdFromUrl() {
  return new URLSearchParams(window.location.search).get("id");
}

function formatOrFallback(value, fallback) {
  return value && String(value).trim() ? value : fallback;
}

function renderUserAvatar(profile) {
  const avatarEl = document.querySelector("[data-user-avatar]");
  if (!avatarEl) return;
  avatarEl.innerHTML = "";
  if (profile.avatar_url) {
    const img = document.createElement("img");
    img.src = profile.avatar_url;
    img.alt = `${profile.username || "User"}'s avatar`;
    avatarEl.appendChild(img);
  } else {
    const initial = document.createElement("span");
    initial.textContent = (profile.username || "?").charAt(0).toUpperCase();
    avatarEl.appendChild(initial);
  }
}

function renderUserTags(tags) {
  const container = document.querySelector("[data-user-tags]");
  if (!container) return;
  container.innerHTML = "";
  if (!tags || !tags.length) {
    container.innerHTML = "<p class=\"user-profile-empty\">None</p>";
    return;
  }
  tags.forEach((tag) => {
    const chip = document.createElement("span");
    chip.className = "genre-tag";
    chip.textContent = tag;
    container.appendChild(chip);
  });
}

async function loadPublicProfile() {
  const userId = getUserIdFromUrl();
  const usernameEl = document.querySelector("[data-user-username]");
  const genderEl = document.querySelector("[data-user-gender]");
  const countryEl = document.querySelector("[data-user-country]");
  const cityEl = document.querySelector("[data-user-city]");
  const aboutEl = document.querySelector("[data-user-about]");

  if (!userId) {
    if (usernameEl) usernameEl.textContent = "User not found";
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/users/${userId}`);
    if (response.status === 404) {
      if (usernameEl) usernameEl.textContent = "User not found";
      return;
    }
    if (!response.ok) throw new Error("Failed to load user profile");

    const profile = await response.json();
    document.title = `${profile.username || "User"} | Axiom`;

    if (usernameEl) usernameEl.textContent = profile.username || "Unknown reader";
    renderUserAvatar(profile);

    if (genderEl) genderEl.textContent = formatOrFallback(profile.gender, "Prefer not to say");
    if (countryEl) countryEl.textContent = formatOrFallback(profile.country, "Not specified");
    if (cityEl) cityEl.textContent = formatOrFallback(profile.city, "Not specified");

    renderUserTags(profile.tag_preferences);

    if (aboutEl) {
      aboutEl.textContent = formatOrFallback(
        profile.about_me,
        "This reader hasn't shared an About Me yet."
      );
    }
  } catch (error) {
    console.error("[user.js] failed to load public profile:", error);
    if (usernameEl) usernameEl.textContent = "Couldn't load this profile";
  }
}

loadPublicProfile();