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

const SOCIAL_PLATFORM_LABELS = {
  discord: "Discord",
  instagram: "Instagram",
  reddit: "Reddit",
  tiktok: "TikTok",
};

const SOCIAL_PLATFORM_ICONS = {
  discord: `
    <svg class="social-platform-icon discord-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M19.54 5.07A16.8 16.8 0 0 0 15.3 3.75l-.52 1.06a15.6 15.6 0 0 0-5.56 0L8.7 3.75a16.8 16.8 0 0 0-4.24 1.32C1.78 9.29 1.05 13.4 1.42 17.45a16.9 16.9 0 0 0 5.2 2.63l1.27-1.73a10.5 10.5 0 0 1-1.99-.96l.49-.38a12 12 0 0 0 10.22 0l.5.38c-.64.38-1.31.7-2 .96l1.27 1.73a16.9 16.9 0 0 0 5.2-2.63c.43-4.7-.74-8.77-2.04-12.38ZM8.68 15.1c-.99 0-1.8-.91-1.8-2.03s.79-2.04 1.8-2.04c1 0 1.81.92 1.8 2.04 0 1.12-.8 2.03-1.8 2.03Zm6.64 0c-.99 0-1.8-.91-1.8-2.03s.79-2.04 1.8-2.04c1 0 1.81.92 1.8 2.04 0 1.12-.8 2.03-1.8 2.03Z"
      />
    </svg>
  `,

  instagram: `
    <svg class="social-platform-icon instagram-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M7.8 2h8.4A5.8 5.8 0 0 1 22 7.8v8.4a5.8 5.8 0 0 1-5.8 5.8H7.8A5.8 5.8 0 0 1 2 16.2V7.8A5.8 5.8 0 0 1 7.8 2Zm-.2 2A3.6 3.6 0 0 0 4 7.6v8.8A3.6 3.6 0 0 0 7.6 20h8.8a3.6 3.6 0 0 0 3.6-3.6V7.6A3.6 3.6 0 0 0 16.4 4H7.6Zm8.9 1.5a1.35 1.35 0 1 1 0 2.7 1.35 1.35 0 0 1 0-2.7ZM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10Zm0 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z"
      />
    </svg>
  `,

  reddit: `
    <svg class="social-platform-icon reddit-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M22 12.1c0-1.55-1.26-2.8-2.81-2.8-.76 0-1.45.3-1.96.8-1.29-.9-2.93-1.47-4.74-1.6l1.01-4.73 3.28.7a1.8 1.8 0 1 0 .27-1.28l-3.65-.78a.65.65 0 0 0-.76.5l-1.12 5.27c-1.87.1-3.56.67-4.89 1.57a2.8 2.8 0 1 0-1.99 4.77c0 .14-.01.28-.01.42 0 3.44 3.86 6.24 8.62 6.24s8.62-2.8 8.62-6.24c0-.14 0-.28-.01-.42A2.8 2.8 0 0 0 22 12.1ZM7.4 13.25a1.45 1.45 0 1 1 0-2.9 1.45 1.45 0 0 1 0 2.9Zm9.58 3.36c-1.27 1.27-4.3 1.37-4.98 1.37s-3.71-.1-4.98-1.37a.65.65 0 0 1 .92-.92c.77.77 2.79.99 4.06.99s3.29-.22 4.06-.99a.65.65 0 1 1 .92.92Zm-.38-3.36a1.45 1.45 0 1 1 0-2.9 1.45 1.45 0 0 1 0 2.9Z"
      />
    </svg>
  `,

  tiktok: `
    <svg class="social-platform-icon tiktok-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M16.6 3c.35 1.82 1.38 3.27 3.4 3.8v2.34c-1.14-.03-2.3-.3-3.4-.86v5.78c0 4.18-2.86 6.94-6.72 6.94A6.2 6.2 0 0 1 3.5 14.8c0-3.66 2.8-6.45 6.5-6.45.4 0 .8.04 1.18.11v2.54a3.85 3.85 0 0 0-1.18-.18c-1.7 0-3.1 1.34-3.1 3.98 0 1.73 1.1 3.72 3.04 3.72 1.84 0 2.99-1.36 2.99-3.53V3h3.67Z"
      />
    </svg>
  `,
};

function renderSocialLinks(socialLinks) {
  const container = document.querySelector("[data-user-social-list]");
  if (!container) return;

  container.innerHTML = "";

  Object.entries(SOCIAL_PLATFORM_LABELS).forEach(([platform, label]) => {
    const entry = (socialLinks || {})[platform] || { state: "unset" };

    const row = document.createElement("div");
    row.className = "user-social-row";

    const name = document.createElement("span");
    name.className = "user-social-platform";

    // Add the same icon used on the Manage Profile page.
    name.innerHTML = SOCIAL_PLATFORM_ICONS[platform] || "";

    const nameText = document.createElement("span");
    nameText.textContent = label;
    name.appendChild(nameText);

    const value = document.createElement("span");
    value.className = "user-social-value";

    if (entry.state === "visible") {
      value.textContent = entry.username;
      value.classList.add("has-value");
    } else if (entry.state === "hidden") {
      value.textContent = `This reader's ${label} account is visible to friends only.`;
      value.classList.add("is-restricted");
    } else {
      value.textContent = `This reader has not shared a ${label} profile yet.`;
      value.classList.add("is-empty");
    }

    row.append(name, value);
    container.appendChild(row);
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

// ---------------------------------------------------------------------
// Friend action (Add friend / Request sent / Friends) on a profile page
// ---------------------------------------------------------------------

const FRIEND_STATUS_ICONS = {
  add: "\uD83D\uDC64+",     // 👤+
  pending: "\uD83D\uDC64\u2713", // 👤✓
  friends: "\uD83D\uDC65\u2713", // 👥✓
};

function renderFriendActionStatic(container, status) {
  const span = document.createElement("span");
  span.className = `friend-action-static is-${status}`;
  span.textContent =
    status === "friends"
      ? `${FRIEND_STATUS_ICONS.friends} Friends`
      : `${FRIEND_STATUS_ICONS.pending} Request sent`;
  container.replaceChildren(span);
}

function renderFriendActionButton(container, targetUserId) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "friend-action-button";
  button.textContent = `${FRIEND_STATUS_ICONS.add} Add friend`;

  button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = "Sending\u2026";
    try {
      const response = await authFetch(`${API_BASE}/api/friendships/${targetUserId}`, {
        method: "POST",
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof result.detail === "string" ? result.detail : "Couldn't send that friend request."
        );
      }
      // The backend is the source of truth for the resulting state --
      // this also covers the mutual-request case, where sending a
      // request to someone who already requested *you* immediately
      // makes you friends instead of leaving a pending request.
      if (result.status === "friends") {
        renderFriendActionStatic(container, "friends");
      } else {
        renderFriendActionStatic(container, "pending");
      }
    } catch (error) {
      alert(error.message || "Couldn't send that friend request. Please try again.");
      button.disabled = false;
      button.textContent = `${FRIEND_STATUS_ICONS.add} Add friend`;
    }
  });

  container.replaceChildren(button);
}

function renderFriendAction(container, targetUserId, status) {
  if (status === "friends") renderFriendActionStatic(container, "friends");
  else if (status === "pending") renderFriendActionStatic(container, "pending");
  else renderFriendActionButton(container, targetUserId);
}

async function loadFriendAction(targetUserId) {
  const container = document.querySelector("[data-friend-action]");
  if (!container || !targetUserId) return;

  // Friending requires an account, and a user can never friend
  // themselves -- both cases simply show nothing, matching a normal
  // profile page's "no action available" state.
  const viewer = getStoredUser();
  if (!getAccessToken() || !viewer || viewer.id === targetUserId) {
    container.innerHTML = "";
    return;
  }

  try {
    const response = await authFetch(`${API_BASE}/api/friendships/status/${targetUserId}`);
    if (response.status === 401) {
      container.innerHTML = "";
      return;
    }
    if (!response.ok) throw new Error("Failed to load friend status");
    const result = await response.json();
    if (result.status === "self") {
      container.innerHTML = "";
      return;
    }
    renderFriendAction(container, targetUserId, result.status);
  } catch (error) {
    console.error("[user.js] failed to load friend status:", error);
    container.innerHTML = "";
  }
}

const LIST_VISIBILITY_LABELS = {
  private: "Private",
  friends: "Friends only",
  public: "Public",
};

function createProfileListCard(list, ownerId, isOwner) {
  const card = document.createElement("article");
  card.className = "reading-list-card";

  const link = document.createElement("a");
  link.className = "reading-list-card-link";
  link.href = isOwner
    ? `/list.html?id=${encodeURIComponent(list.id)}`
    : `/shared-list.html?user=${encodeURIComponent(ownerId)}&id=${encodeURIComponent(list.id)}`;

  const title = document.createElement("h3");
  title.textContent = list.name;

  const count = document.createElement("p");
  count.textContent = `${list.novel_count} ${list.novel_count === 1 ? "novel" : "novels"}`;

   link.append(createListBookcase(list.preview_novels || []), title, count, createListRatingLine(list));

  // Only the owner sees which level each list is set to.
  if (isOwner) {
    const badge = document.createElement("span");
    badge.className = "reading-list-visibility-badge";
    badge.textContent = LIST_VISIBILITY_LABELS[list.visibility] || "Private";
    link.appendChild(badge);
  }

  card.appendChild(link);
  return card;
}

async function loadUserReadingLists(userId, username) {
  const container = document.querySelector("[data-user-reading-lists]");
  if (!container) return;

  try {
    // authFetch so the backend can tell whether the viewer is the owner or a friend.
    const response = await authFetch(`${API_BASE}/api/users/${encodeURIComponent(userId)}/reading-lists`);
    if (!response.ok) throw new Error("Failed to load reading lists");
    const payload = await response.json();
    const lists = payload.lists || [];

    container.innerHTML = "";
    if (!lists.length) {
      const empty = document.createElement("p");
      empty.className = "user-profile-empty";

      if (payload.is_owner) {
        empty.textContent = "You don't have any reading lists yet.";
      } else {
        const message = document.createElement("em");
        message.textContent = `${username || payload.username || "This reader"} does not have any public reading lists.`;
        empty.appendChild(message);
      }

      container.appendChild(empty);
      return;
    }

    lists.forEach((list) => container.appendChild(createProfileListCard(list, userId, payload.is_owner)));
  } catch (error) {
    console.error("[user.js] failed to load reading lists:", error);
    container.innerHTML = '<p class="user-profile-empty">Reading lists are temporarily unavailable.</p>';
  }
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
    // authFetch (not plain fetch) so a logged-in viewer's identity is
    // sent along -- the backend uses it to decide whether this viewer
    // can see the profile owner's friends-only social accounts. It works
    // fine for a logged-out viewer too; authFetch just omits the header.
    const response = await authFetch(`${API_BASE}/api/users/${userId}`);
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
    renderSocialLinks(profile.social_links);
    loadUserReadingLists(userId, profile.username);
    loadFriendAction(userId);

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
