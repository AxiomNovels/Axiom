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

function renderActivityStars(container, rating) {
  const value = Number(rating) || 0;
  container.innerHTML = "";
  for (let index = 1; index <= 5; index += 1) {
    const star = document.createElement("span");
    star.textContent = "★";
    star.dataset.fill = value >= index ? "full" : value >= index - 0.5 ? "half" : "empty";
    container.appendChild(star);
  }
}

function renderUserActivity(payload) {
  const feed = document.querySelector("[data-user-activity-feed]");
  const stats = document.querySelector("[data-user-activity-stats]");
  if (!feed || !stats) return;

  const count = Number(payload.review_count) || 0;
  stats.textContent = count
    ? `${count} ${count === 1 ? "review" : "reviews"} · ${Number(payload.average_rating).toFixed(1)} average`
    : "No reviews yet";
  feed.innerHTML = "";

  if (!payload.activity?.length) {
    feed.innerHTML = '<div class="user-activity-empty"><strong>No activity yet</strong><p>This reader has not rated or reviewed a novel.</p></div>';
    return;
  }

  payload.activity.forEach((activity) => {
    const novel = activity.novel || {};
    const card = document.createElement("article");
    card.className = "user-activity-card";

    const coverLink = document.createElement("a");
    coverLink.className = "user-activity-cover";
    coverLink.href = `/novel.html?id=${encodeURIComponent(activity.novel_id)}`;
    if (novel.cover_image_url) {
      const image = document.createElement("img");
      image.referrerPolicy = "no-referrer";
      image.src = novel.cover_image_url;
      image.alt = `Cover of ${novel.title || "novel"}`;
      image.addEventListener("error", () => {
        image.remove();
        coverLink.classList.add("has-fallback");
        coverLink.textContent = novel.title || "Axiom";
      }, { once: true });
      coverLink.appendChild(image);
    } else {
      coverLink.classList.add("has-fallback");
      coverLink.textContent = novel.title || "Axiom";
    }

    const body = document.createElement("div");
    body.className = "user-activity-body";
    const context = document.createElement("p");
    context.className = "user-activity-context";
    context.textContent = activity.comment ? "Reviewed" : "Rated";
    const title = document.createElement("a");
    title.className = "user-activity-title";
    title.href = coverLink.href;
    title.textContent = novel.title || "Unknown novel";
    const author = document.createElement("span");
    author.className = "user-activity-author";
    author.textContent = novel.author ? `by ${novel.author}` : "";
    const meta = document.createElement("div");
    meta.className = "user-activity-meta";
    const stars = document.createElement("span");
    stars.className = "review-card-stars";
    stars.setAttribute("aria-label", `${activity.rating} out of 5 stars`);
    renderActivityStars(stars, activity.rating);
    const date = document.createElement("time");
    date.dateTime = activity.updated_at;
    date.textContent = new Date(activity.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    meta.append(stars, date);
    body.append(context, title, author, meta);
    if (activity.comment) {
      const comment = document.createElement("p");
      comment.className = "user-activity-comment";
      comment.textContent = activity.comment;
      body.appendChild(comment);
    }
    card.append(coverLink, body);
    feed.appendChild(card);
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

  const activityLink = document.querySelector("[data-user-activity-link]");
  if (activityLink) activityLink.href = `/activity.html?id=${encodeURIComponent(userId)}`;

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
