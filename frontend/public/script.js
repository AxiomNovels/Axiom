const API_BASE = "http://localhost:8000";
const COVER_CLASSES = ["cover-one", "cover-two", "cover-three", "cover-four", "cover-five"];

// Shared by the novel page, upload preview, and search results to show
// chapter counts compactly (e.g. 123456 -> "123.4K").
// Values are truncated rather than rounded up at one decimal place, so
// 123456 reads as "123.4K" and not "123.5K" -- matching how most sites
// display counts (never rounding a count up past what it
// actually is). Numbers under 1,000 are shown in full with no decimal.
const COMPACT_NUMBER_UNITS = [
  { threshold: 1_000_000_000, suffix: "B" },
  { threshold: 1_000_000, suffix: "M" },
  { threshold: 1_000, suffix: "K" },
];

function formatCompactNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) return null;

  for (const { threshold, suffix } of COMPACT_NUMBER_UNITS) {
    if (number >= threshold) {
      const truncated = Math.floor((number / threshold) * 10) / 10;
      return `${truncated}${suffix}`;
    }
  }

  return String(Math.trunc(number));
}

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("axiomUser"));
  } catch {
    return null;
  }
}

function getStoredSession() {
  try {
    return JSON.parse(localStorage.getItem("axiomSession"));
  } catch {
    return null;
  }
}

function getAccessToken() {
  return getStoredSession()?.access_token || null;
}

async function authFetch(url, options = {}) {
  const token = getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(url, { ...options, headers });
}

function getUserName(user) {
  if (!user) {
    return "";
  }

  return user.user_metadata?.username || user.email || "reader";
}

function applyAccountAvatar(avatarUrl) {
  const user = getStoredUser();
  const initial = getUserName(user).charAt(0).toUpperCase();

  // Targets the inner content span rather than .account-trigger itself,
  // since the trigger also holds a sibling friend-request badge (see
  // updateAccountNav) that must survive this update untouched.
  const triggerContent = document.querySelector("[data-account-trigger-content]");
  if (triggerContent) {
    if (avatarUrl) {
      triggerContent.innerHTML = "";
      const img = document.createElement("img");
      img.src = avatarUrl;
      img.alt = "";
      img.className = "account-avatar-image";
      triggerContent.appendChild(img);
    } else {
      triggerContent.textContent = initial;
    }
  }

  // The larger avatar shown next to the username inside the dropdown,
  // kept in sync with the small header icon above.
  const popoverAvatar = document.querySelector("[data-popover-avatar]");
  if (popoverAvatar) {
    if (avatarUrl) {
      popoverAvatar.innerHTML = "";
      const img = document.createElement("img");
      img.src = avatarUrl;
      img.alt = "";
      img.className = "account-popover-avatar-image";
      popoverAvatar.appendChild(img);
    } else {
      popoverAvatar.textContent = initial;
    }
  }
}

// Exposed globally so profile.js can refresh the header avatar immediately
// after a new one is saved, without needing a full page reload.
async function refreshAccountAvatar() {
  if (!getAccessToken()) return;
  try {
    const response = await authFetch(`${API_BASE}/api/profile`);
    if (!response.ok) return;
    const profile = await response.json();
    applyAccountAvatar(profile.avatar_url || null);
  } catch {
    // The initial-letter fallback stays in place if this fails; not
    // worth surfacing an error just for the header icon.
  }
}
window.refreshAccountAvatar = refreshAccountAvatar;

// Exposed globally so inbox.js can refresh the header badge immediately
// after a message is opened or its read state is toggled, without a
// full page reload.
async function refreshInboxBadge() {
  const badge = document.querySelector("[data-inbox-badge]");
  if (!badge) return;

  if (!getAccessToken()) {
    badge.classList.add("is-hidden");
    badge.textContent = "";
    return;
  }

  try {
    const response = await authFetch(`${API_BASE}/api/inbox/unread-count`);
    if (!response.ok) return;
    const result = await response.json();
    const count = Number(result.unread_count) || 0;

    if (count > 0) {
      badge.textContent = count > 9 ? "9+" : String(count);
      badge.classList.remove("is-hidden");
    } else {
      badge.textContent = "";
      badge.classList.add("is-hidden");
    }
  } catch {
    // Leave whatever badge state was already showing; not worth
    // surfacing an error just for the header icon.
  }
}
window.refreshInboxBadge = refreshInboxBadge;

// Exposed globally so friends.js and inbox.js can refresh these badges
// immediately after an incoming request is accepted or rejected from
// either of those pages, without a full page reload.
async function refreshFriendRequestBadges() {
  const avatarBadge = document.querySelector("[data-friends-request-avatar-badge]");
  const linkBadge = document.querySelector("[data-friends-request-badge]");
  if (!avatarBadge && !linkBadge) return;

  const badges = [avatarBadge, linkBadge].filter(Boolean);

  if (!getAccessToken()) {
    badges.forEach((badge) => {
      badge.classList.add("is-hidden");
      badge.textContent = "";
    });
    return;
  }

  try {
    const response = await authFetch(`${API_BASE}/api/friendships/incoming-count`);
    if (!response.ok) return;
    const result = await response.json();
    const count = Number(result.incoming_count) || 0;

    badges.forEach((badge) => {
      if (count > 0) {
        badge.textContent = count > 9 ? "9+" : String(count);
        badge.classList.remove("is-hidden");
      } else {
        badge.textContent = "";
        badge.classList.add("is-hidden");
      }
    });
  } catch {
    // Leave whatever badge state was already showing; not worth
    // surfacing an error just for a header badge.
  }
}
window.refreshFriendRequestBadges = refreshFriendRequestBadges;

function updateAccountNav() {
  const guestActions = document.querySelector("[data-guest-actions]");
  const userActions = document.querySelector("[data-user-actions]");
  const userGreeting = document.querySelector("[data-user-greeting]");
  const logoutButton = document.querySelector("[data-logout-button]");

  if (!guestActions || !userActions || !userGreeting || !logoutButton) {
    return;
  }

  const user = getStoredUser();

  if (user) {
    guestActions.classList.add("is-hidden");
    userActions.classList.remove("is-hidden");
    userGreeting.textContent = `Hi ${getUserName(user)}`;

    if (!userActions.querySelector("[data-my-lists-link]")) {
      const myListsLink = document.createElement("a");
      myListsLink.href = "/lists.html";
      myListsLink.className = "my-lists-link";
      myListsLink.innerHTML = `
        <svg class="my-lists-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.5 6.5h5v13h-5z" />
          <path d="M9.5 3.5h5.5v16H9.5z" />
          <path d="m16 6.2 4.4-1 2.5 13.6-4.4.8z" />
          <path class="book-detail" d="M5 9h2M11 7h2.5m-2.5 9h2.5m5.9-7.7 1.3-.2M2 21h21" />
        </svg>
        <span>My Lists</span>`;
      myListsLink.setAttribute("data-my-lists-link", "");
      userActions.insertBefore(myListsLink, userGreeting);
    }

    // Inbox link + unread badge, placed right next to My Lists.
    if (!userActions.querySelector("[data-inbox-link]")) {
      const inboxLink = document.createElement("a");
      inboxLink.href = "/inbox.html";
      inboxLink.className = "inbox-link";
      inboxLink.setAttribute("data-inbox-link", "");
      inboxLink.setAttribute("aria-label", "Inbox");
      inboxLink.innerHTML = `
        <span class="inbox-icon-wrap">
          <svg class="inbox-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M3.5 6.5h17v11h-17z" />
            <path d="m3.5 6.5 8.5 6 8.5-6" />
          </svg>
          <span class="inbox-badge is-hidden" data-inbox-badge aria-hidden="true"></span>
        </span>
        <span>Inbox</span>`;

      const myListsLink = userActions.querySelector("[data-my-lists-link]");
      userActions.insertBefore(inboxLink, myListsLink ? myListsLink.nextSibling : userGreeting);
    }

    if (!userActions.querySelector("[data-account-menu]")) {
      const accountMenu = document.createElement("details");
      accountMenu.className = "account-menu";
      accountMenu.setAttribute("data-account-menu", "");

            const accountTrigger = document.createElement("summary");
      accountTrigger.className = "account-trigger";
      accountTrigger.setAttribute("aria-label", "Open account menu");

      const accountTriggerContent = document.createElement("span");
      accountTriggerContent.className = "account-trigger-content";
      accountTriggerContent.setAttribute("data-account-trigger-content", "");
      accountTriggerContent.textContent = getUserName(user).charAt(0).toUpperCase();

      const accountTriggerBadge = document.createElement("span");
      accountTriggerBadge.className = "account-trigger-badge is-hidden";
      accountTriggerBadge.setAttribute("data-friends-request-avatar-badge", "");
      accountTriggerBadge.setAttribute("aria-hidden", "true");

      accountTrigger.append(accountTriggerContent, accountTriggerBadge);

      const popover = document.createElement("div");
      popover.className = "account-popover";

      const popoverHeader = document.createElement("div");
      popoverHeader.className = "account-popover-header";

      const popoverAvatar = document.createElement("div");
      popoverAvatar.className = "account-popover-avatar";
      popoverAvatar.setAttribute("data-popover-avatar", "");
      popoverAvatar.setAttribute("aria-hidden", "true");
      popoverAvatar.textContent = getUserName(user).charAt(0).toUpperCase();

      userGreeting.textContent = getUserName(user);
      userGreeting.classList.add("account-popover-username");

      popoverHeader.append(popoverAvatar, userGreeting);

      const manageProfileLink = document.createElement("a");
      manageProfileLink.href = "/profile.html";
      manageProfileLink.className = "account-popover-link";
      manageProfileLink.setAttribute("data-manage-profile-link", "");
      manageProfileLink.textContent = "Manage profile";

      const activityLink = document.createElement("a");
      activityLink.href = "/activity.html";
      activityLink.className = "account-popover-link";
      activityLink.setAttribute("data-activity-link", "");
      activityLink.textContent = "Your activity";

      const friendsLink = document.createElement("a");
      friendsLink.href = "/friends.html";
      friendsLink.className = "account-popover-link account-popover-link-friends";
      friendsLink.setAttribute("data-friends-page-link", "");

      const friendsLabel = document.createElement("span");
      friendsLabel.textContent = "Friends";

      const friendsBadge = document.createElement("span");
      friendsBadge.className = "account-popover-badge is-hidden";
      friendsBadge.setAttribute("data-friends-request-badge", "");
      friendsBadge.setAttribute("aria-hidden", "true");

      friendsLink.append(friendsLabel, friendsBadge);

      const uploadNovelLink = document.createElement("a");
      uploadNovelLink.href = "/upload.html";
      uploadNovelLink.className = "account-popover-link";
      uploadNovelLink.setAttribute("data-upload-novel-link", "");
      uploadNovelLink.textContent = "Upload a novel";

      popover.append(popoverHeader, manageProfileLink, activityLink, friendsLink, uploadNovelLink, logoutButton);
      accountMenu.append(accountTrigger, popover);
      userActions.appendChild(accountMenu);
    }

    refreshAccountAvatar();
    refreshInboxBadge();
    refreshFriendRequestBadges();
  } else {
    guestActions.classList.remove("is-hidden");
    userActions.classList.add("is-hidden");
    userGreeting.textContent = "";
  }

  logoutButton.addEventListener("click", () => {
    localStorage.removeItem("axiomUser");
    localStorage.removeItem("axiomSession");
    window.location.href = "/";
  });
}

updateAccountNav();

document.addEventListener("click", (event) => {
  const accountMenu = document.querySelector("[data-account-menu]");

  if (!accountMenu) return;

  // If the click happened outside the account dropdown, close it.
  if (!accountMenu.contains(event.target)) {
    accountMenu.removeAttribute("open");
  }
});

function showAuthError(form, message) {
  const errorEl = form.querySelector("[data-auth-error]");
  if (!errorEl) {
    alert(message);
    return;
  }
  errorEl.textContent = message;
  errorEl.classList.remove("is-hidden");
}

function clearAuthError(form) {
  const errorEl = form.querySelector("[data-auth-error]");
  if (!errorEl) return;
  errorEl.textContent = "";
  errorEl.classList.add("is-hidden");
}

document.querySelectorAll(".auth-form").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAuthError(form);

    const password = form.querySelector("#password");
    const confirmPassword = form.querySelector("#confirm-password");

    if (password && confirmPassword && password.value !== confirmPassword.value) {
      showAuthError(form, "Those passwords don't match. Please re-enter them.");
      confirmPassword.focus();
      return;
    }

    const button = form.querySelector("button");
    const originalText = button.textContent;
    const isSignup = window.location.pathname.includes("signup");
    const endpoint = isSignup ? "/api/signup" : "/api/login";

    const payload = isSignup
      ? {
          email: form.querySelector("#email").value.trim(),
          username: form.querySelector("#username").value.trim(),
          password: password.value
        }
      : {
          identifier: form.querySelector("#identifier").value.trim(),
          password: password.value
        };

    button.textContent = "Working...";
    button.disabled = true;

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const message =
          (typeof result.detail === "string" && result.detail) ||
          (Array.isArray(result.detail) && result.detail[0]?.msg) ||
          result.error ||
          "Something went wrong. Please try again.";
        showAuthError(form, message);
        return;
      }

      localStorage.setItem("axiomUser", JSON.stringify(result.user));
      localStorage.setItem("axiomSession", JSON.stringify(result.session));

      // New accounts land on their profile page first so they can fill in
      // preferences right away; logging back in later goes straight to
      // reading lists as before.
      let destination = "/login.html";
      if (result.session) {
        destination = isSignup ? "/profile.html" : "/lists.html";
      }
      window.location.href = destination;
    } catch (error) {
      showAuthError(form, "Couldn't reach the backend. Make sure it is running on port 8000.");
    } finally {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
});

document.querySelectorAll(".search-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const input = form.querySelector("input[type='search']");
    const query = input.value.trim();
    if (!query) {
      event.preventDefault();
      input.focus();
    }
  });
});

function createNovelCard(novel, index) {
  const link = document.createElement("a");
  link.href = `/novel.html?id=${novel.id}`;
  link.className = "book-card-link";

  const article = document.createElement("article");
  article.className = "book-card";

  const cover = document.createElement("div");
  cover.className = `book-cover ${COVER_CLASSES[index % COVER_CLASSES.length]}`;
  if (novel.cover_image_url) {
    const coverImage = document.createElement("img");
    coverImage.className = "book-cover-image";
    coverImage.referrerPolicy = "no-referrer";
    coverImage.src = novel.cover_image_url;
    coverImage.alt = `${novel.title} cover`;
    coverImage.addEventListener("error", () => {
      coverImage.remove();
      const coverSpan = document.createElement("span");
      coverSpan.textContent = novel.title;
      cover.appendChild(coverSpan);
    }, { once: true });
    cover.appendChild(coverImage);
  } else {
    const coverSpan = document.createElement("span");
    coverSpan.textContent = novel.title;
    cover.appendChild(coverSpan);
  }

  const title = document.createElement("h3");
  title.textContent = novel.title;

  const blurb = document.createElement("p");
  const synopsis = novel.synopsis || "";
  blurb.textContent = synopsis.length > 90 ? `${synopsis.slice(0, 90)}...` : synopsis;

  article.appendChild(cover);
  article.appendChild(title);
  article.appendChild(blurb);
  link.appendChild(article);

  return link;
}

async function loadFeaturedNovels() {
  const grid = document.querySelector("[data-novel-grid]");
  if (!grid) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/novels/featured`);
    if (!response.ok) {
      throw new Error("Failed to load featured novels");
    }
    const novels = await response.json();

    grid.innerHTML = "";
    novels.forEach((novel, index) => {
      grid.appendChild(createNovelCard(novel, index));
    });
  } catch (error) {
    grid.innerHTML = "<p>Couldn't load novels. Make sure the backend is running on port 8000.</p>";
  }
}

loadFeaturedNovels();
