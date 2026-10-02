const LOCAL_API_BASE = "http://localhost:8000";
// Cloudflare provides this at request time; local development falls back to
// the local backend without requiring any environment setup.
const API_BASE = window.AXIOM_RUNTIME_CONFIG?.apiBase || LOCAL_API_BASE;
const COVER_CLASSES = ["cover-one", "cover-two", "cover-three", "cover-four", "cover-five"];
let sessionRefreshPromise = null;
let sessionRefreshTimer = null;
const AUTH_MODE_KEY = "axiomAuthMode";
const NORMAL_SESSION_COOKIE = "axiomNormalSession";

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

function hasNormalSessionCookie() {
  return document.cookie
    .split(";")
    .some((cookie) => cookie.trim() === `${NORMAL_SESSION_COOKIE}=1`);
}

function setNormalSessionCookie() {
  // No Max-Age or Expires makes this a browser-session cookie: it is shared
  // by all tabs, but removed when the browser session ends.
  document.cookie = `${NORMAL_SESSION_COOKIE}=1; Path=/; SameSite=Lax`;
}

function clearNormalSessionCookie() {
  document.cookie = `${NORMAL_SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

function hasUsableLocalAuthState() {
  // Older local-storage sessions predate the mode flag and were remembered
  // sessions, so retain them during the rollout.
  return localStorage.getItem(AUTH_MODE_KEY) !== "normal" || hasNormalSessionCookie();
}

function getStoredValue(key) {
  // Both login modes use localStorage so another tab can authenticate. A
  // normal login is gated by a session cookie, which is shared by tabs but
  // disappears after the browser is closed; a remembered login has no gate.
  try {
    if (hasUsableLocalAuthState()) {
      const value = localStorage.getItem(key);
      if (value) return JSON.parse(value);
    }
  } catch {
    // Invalid or unavailable browser storage is treated as signed out.
  }

  // Retain an in-progress login from the prior implementation until its tab
  // closes. New logins are always stored in localStorage as described above.
  for (const storage of [sessionStorage]) {
    try {
      const value = storage.getItem(key);
      if (value) return JSON.parse(value);
    } catch {
      // Invalid or unavailable browser storage is treated as signed out.
    }
  }
  return null;
}

function getStoredUser() {
  return getStoredValue("axiomUser");
}

function getStoredSession() {
  return getStoredValue("axiomSession");
}

function storeAuthState(user, session, remember) {
  // localStorage is shared by tabs. For an unchecked login, a session cookie
  // provides the browser-session lifetime without isolating each tab.
  sessionStorage.removeItem("axiomUser");
  sessionStorage.removeItem("axiomSession");
  localStorage.setItem("axiomUser", JSON.stringify(user));
  localStorage.setItem("axiomSession", JSON.stringify(session));
  localStorage.setItem(AUTH_MODE_KEY, remember ? "remembered" : "normal");
  if (remember) {
    clearNormalSessionCookie();
  } else {
    setNormalSessionCookie();
  }
  scheduleSessionRefresh();
}

function clearAuthState() {
  if (sessionRefreshTimer) {
    window.clearTimeout(sessionRefreshTimer);
    sessionRefreshTimer = null;
  }
  for (const storage of [localStorage, sessionStorage]) {
    storage.removeItem("axiomUser");
    storage.removeItem("axiomSession");
  }
  localStorage.removeItem(AUTH_MODE_KEY);
  clearNormalSessionCookie();
}

function getAccessToken() {
  return getStoredSession()?.access_token || null;
}

function sessionIsRemembered() {
  try {
    const mode = localStorage.getItem(AUTH_MODE_KEY);
    if (mode) return mode === "remembered";

    // Before the mode flag existed, only remembered sessions were stored in
    // localStorage; normal sessions were in this tab's sessionStorage.
    return Boolean(localStorage.getItem("axiomSession"));
  } catch {
    return false;
  }
}

async function refreshAuthSession() {
  if (sessionRefreshPromise) return sessionRefreshPromise;

  const currentSession = getStoredSession();
  if (!currentSession?.refresh_token) return false;

  sessionRefreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/session/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: currentSession.refresh_token })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.session?.access_token) {
        clearAuthState();
        return false;
      }
      storeAuthState(result.user || getStoredUser(), result.session, sessionIsRemembered());
      return true;
    } catch {
      // A temporary network failure should not discard a still-valid session.
      // The next authenticated request will attempt a refresh again.
      return false;
    } finally {
      sessionRefreshPromise = null;
    }
  })();

  return sessionRefreshPromise;
}

function scheduleSessionRefresh() {
  if (sessionRefreshTimer) window.clearTimeout(sessionRefreshTimer);

  const expiresAt = Number(getStoredSession()?.expires_at);
  if (!Number.isFinite(expiresAt) || expiresAt <= 0) return;

  // Refresh one minute before expiry. This is scheduled only while a page is
  // open; returning to the app is also covered by authFetch's 401 retry.
  const delay = Math.max(0, expiresAt * 1000 - Date.now() - 60_000);
  sessionRefreshTimer = window.setTimeout(() => {
    refreshAuthSession().then((refreshed) => {
      if (!refreshed && getAccessToken()) scheduleSessionRefresh();
    });
  }, delay);
}

async function sendAuthenticatedRequest(url, options) {
  const token = getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(url, { ...options, headers });
}

async function authFetch(url, options = {}) {
  const response = await sendAuthenticatedRequest(url, options);
  if (response.status !== 401 || options.skipSessionRefresh) return response;

  if (!await refreshAuthSession()) return response;
  return sendAuthenticatedRequest(url, options);
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

let presenceHeartbeatTimer = null;

async function sendPresenceHeartbeat() {
  if (!getAccessToken() || document.visibilityState !== "visible") return;
  try {
    await authFetch(`${API_BASE}/api/presence/heartbeat`, {
      method: "POST",
      skipSessionRefresh: true,
    });
  } catch {
    // Presence is intentionally best-effort. A missed check-in simply lets
    // the short online window expire rather than affecting the reader's use.
  }
}

function startPresenceTracking() {
  if (!getAccessToken()) return;
  sendPresenceHeartbeat();
  presenceHeartbeatTimer = window.setInterval(sendPresenceHeartbeat, 60_000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") sendPresenceHeartbeat();
  });
}

startPresenceTracking();

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

      // The account name is a direct route to the reader's public profile;
      // profile management remains available as its own explicit menu item.
      const profileNameLink = document.createElement("a");
      profileNameLink.href = `/user.html?id=${encodeURIComponent(user.id)}`;
      profileNameLink.className = "user-greeting account-popover-username";
      profileNameLink.textContent = getUserName(user);
      userGreeting.remove();

      popoverHeader.append(popoverAvatar, profileNameLink);

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

    authFetch(`${API_BASE}/api/admin/me`).then((response) => {
      if (!response.ok || document.querySelector("[data-admin-link]")) return;
      const link = document.createElement("a");
      link.href = "/admin.html";
      link.className = "account-popover-link";
      link.dataset.adminLink = "";
      link.textContent = "Admin hub";
      document.querySelector(".account-popover")?.insertBefore(link, logoutButton);
    }).catch(() => {});
    refreshAccountAvatar();
    refreshInboxBadge();
    refreshFriendRequestBadges();
  } else {
    guestActions.classList.remove("is-hidden");
    userActions.classList.add("is-hidden");
    userGreeting.textContent = "";
  }

  logoutButton.addEventListener("click", () => {
    clearAuthState();
    window.location.href = "/";
  });
}

scheduleSessionRefresh();
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

      const rememberCheckbox = form.querySelector("input[name='remember']");
      // Sign-up has no checkbox and keeps the app's prior persistent-session
      // behavior. On the login form, the reader explicitly chooses whether
      // the session should survive closing the browser.
      const remember = isSignup || Boolean(rememberCheckbox?.checked);
      storeAuthState(result.user, result.session, remember);

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

function createListRatingLine(list) {
  const line = document.createElement("p");
  line.className = "reading-list-rating";
  const count = Number(list.review_count) || 0;

  if (!count || list.average_rating == null) {
    line.classList.add("is-unrated");
    line.textContent = "Not yet rated";
    return line;
  }

  const star = document.createElement("span");
  star.setAttribute("aria-hidden", "true");
  star.textContent = "★";

  const value = document.createElement("strong");
  value.textContent = `${Number(list.average_rating).toFixed(1)}/5`;

  const total = document.createElement("span");
  total.className = "reading-list-rating-count";
  total.textContent = ` · ${count} ${count === 1 ? "review" : "reviews"}`;

  line.append(star, " ", value, total);
  return line;
}

function createListLikeHeartIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "list-like-icon");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute(
    "d",
    "M12 21s-6.72-4.35-9.3-8.14C.86 10.27 1.32 6.9 4 5.1c2.2-1.47 4.94-.98 6.6.9L12 7.4l1.4-1.4c1.66-1.88 4.4-2.37 6.6-.9 2.68 1.8 3.14 5.17 1.3 7.76C18.72 16.65 12 21 12 21Z"
  );
  svg.appendChild(path);
  return svg;
}

// The ONE like control for a whole reading list. lists.js (the cards),
// list.js, shared-list.js and user.js all call it, so a list's heart looks
// and behaves the same everywhere. Likes on individual *reviews* are a
// separate thumbs-up that lives in list-reviews.js
// (createListReviewLikeControl) -- keep the two names distinct, because every
// page loads these scripts into one shared global scope.
//
// `list` is mutated in place (like_count / viewer_has_liked) so any other
// control built from the same object stays in sync. Owners see a read-only
// count, since you can't like your own list.
function createListLikeControl(list, { isOwner = false, large = false } = {}) {
  const wrapper = document.createElement("div");
  wrapper.className = large ? "list-like large" : "list-like";

  // Owners get a non-interactive <span>: a permanently disabled <button>
  // just reads as broken.
  const control = document.createElement(isOwner ? "span" : "button");
  control.className = "list-like-button";
  if (isOwner) {
    control.classList.add("is-own");
    control.setAttribute("role", "img");
    control.title = "Readers who can see this list can like it. You can't like your own list.";
  } else {
    control.type = "button";
  }

  const count = document.createElement("span");
  count.className = "list-like-count";
  control.append(createListLikeHeartIcon(), count);
  wrapper.appendChild(control);

  const likesText = (total) => `${total} ${total === 1 ? "like" : "likes"}`;

  function render() {
    const total = Math.max(0, Number(list.like_count) || 0);
    const liked = Boolean(list.viewer_has_liked);
    count.textContent = String(total);
    control.classList.toggle("has-likes", total > 0);

    if (isOwner) {
      control.setAttribute("aria-label", `${likesText(total)} on your reading list`);
      return;
    }
    control.classList.toggle("is-liked", liked);
    control.setAttribute("aria-pressed", String(liked));
    control.setAttribute("aria-label", `${liked ? "Unlike" : "Like"} this reading list (${likesText(total)})`);
    control.title = liked ? "Unlike this list" : "Like this list";
  }
  render();

  if (isOwner) return wrapper;

  control.addEventListener("animationend", () => control.classList.remove("is-popping"));

  let pending = false;
  control.addEventListener("click", async () => {
    if (!getAccessToken()) {
      window.location.href = "/login.html";
      return;
    }
    if (pending) return;
    pending = true;

    // Optimistic update so the heart responds instantly; the server's answer
    // replaces it, and any failure rolls it back.
    const wasLiked = Boolean(list.viewer_has_liked);
    const previousCount = Number(list.like_count) || 0;
    list.viewer_has_liked = !wasLiked;
    list.like_count = Math.max(0, previousCount + (wasLiked ? -1 : 1));
    render();
    if (!wasLiked) {
      control.classList.remove("is-popping");
      void control.offsetWidth; // restart the animation on rapid like/unlike
      control.classList.add("is-popping");
    }
    const rollBack = () => {
      list.viewer_has_liked = wasLiked;
      list.like_count = previousCount;
      render();
    };

    try {
      const response = await authFetch(
        `${API_BASE}/api/reading-lists/${encodeURIComponent(list.id)}/like`,
        { method: wasLiked ? "DELETE" : "POST" }
      );
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (response.status === 404) {
        rollBack();
        alert("This reading list is no longer available to you.");
        return;
      }
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't update your like.");
      }
      list.like_count = result.like_count;
      list.viewer_has_liked = result.liked;
      render();
    } catch (error) {
      rollBack();
      alert(error.message || "Couldn't update your like. Please try again.");
    } finally {
      pending = false;
    }
  });

  return wrapper;
}

function createListBookcase(previews = []) {
  const bookcase = document.createElement("div");
  bookcase.className = "list-bookcase";
  bookcase.setAttribute("aria-hidden", "true");
  for (let index = 0; index < 3; index += 1) {
    const novel = previews[index];
    const book = document.createElement("div");
    book.className = novel ? "list-preview-book" : "list-preview-book is-empty";
    if (novel?.cover_image_url) {
      const image = document.createElement("img");
      image.referrerPolicy = "no-referrer";
      image.src = novel.cover_image_url;
      image.alt = "";
      image.addEventListener("error", () => {
        image.remove();
        book.classList.add("has-fallback");
        book.textContent = novel.title || "Axiom";
      }, { once: true });
      book.appendChild(image);
    } else if (novel) {
      book.classList.add("has-fallback");
      book.textContent = novel.title || "Axiom";
    } else {
      const mark = document.createElement("span");
      mark.textContent = "A";
      book.appendChild(mark);
    }
    bookcase.appendChild(book);
  }
  return bookcase;
}

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

async function loadHomeFeature() {
  const featureCard = document.querySelector("[data-home-feature]");
  if (!featureCard) return;
  try {
    const response = await fetch(`${API_BASE}/api/home-feature`);
    const feature = await response.json().catch(() => null);
    if (!response.ok || !feature?.novel) return;
    const inquiry = featureCard.querySelector("[data-home-feature-inquiry]");
    const description = featureCard.querySelector("[data-home-feature-description]");
    const tags = featureCard.querySelector("[data-home-feature-tags]");
    const cover = featureCard.querySelector("[data-home-feature-cover]");
    const link = featureCard.querySelector("[data-home-feature-link]");
    inquiry.textContent = feature.inquiry;
    description.textContent = feature.description;
    tags.replaceChildren();
    (feature.tags || []).forEach((tag) => {
      const chip = document.createElement("span");
      chip.textContent = tag;
      tags.appendChild(chip);
    });
    cover.replaceChildren();
    if (feature.novel.cover_image_url) {
      const image = document.createElement("img");
      image.className = "book-cover-image";
      image.src = feature.novel.cover_image_url;
      image.alt = `${feature.novel.title} cover`;
      image.referrerPolicy = "no-referrer";
      cover.appendChild(image);
    } else {
      const title = document.createElement("span");
      title.textContent = feature.novel.title;
      cover.appendChild(title);
    }
    link.href = `/novel.html?id=${encodeURIComponent(feature.novel.id)}`;
    link.hidden = false;
  } catch {
    // The static feature remains visible when no feature has been published.
  }
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
loadHomeFeature();
