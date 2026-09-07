function requireSession() {
  if (!getAccessToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

// Shows the shared Yes/No modal and resolves true/false with the user's
// choice. Falls back to the native confirm() if the modal markup is
// missing from the page for some reason. Matches the implementation in
// lists.js so the confirmation experience feels the same across pages.
function showConfirmModal(message) {
  return new Promise((resolve) => {
    const overlay = document.querySelector("[data-modal-overlay]");
    const messageEl = document.querySelector("[data-modal-message]");
    const confirmButton = document.querySelector("[data-modal-confirm]");
    const cancelButton = document.querySelector("[data-modal-cancel]");

    if (!overlay || !messageEl || !confirmButton || !cancelButton) {
      resolve(window.confirm(message));
      return;
    }

    messageEl.textContent = message;
    overlay.classList.remove("is-hidden");

    const cleanup = (result) => {
      overlay.classList.add("is-hidden");
      confirmButton.removeEventListener("click", onConfirm);
      cancelButton.removeEventListener("click", onCancel);
      resolve(result);
    };
    const onConfirm = () => cleanup(true);
    const onCancel = () => cleanup(false);

    confirmButton.addEventListener("click", onConfirm);
    cancelButton.addEventListener("click", onCancel);
  });
}

function createFriendProfileLink(profile) {
  const link = document.createElement("a");
  link.className = "friend-list-item";
  link.href = `/user.html?id=${encodeURIComponent(profile.id)}`;

  const avatar = document.createElement("span");
  avatar.className = "friend-list-avatar";
  if (profile.avatar_url) {
    const image = document.createElement("img");
    image.referrerPolicy = "no-referrer";
    image.src = profile.avatar_url;
    image.alt = "";
    image.addEventListener("error", () => {
      image.remove();
      avatar.classList.add("has-fallback");
      avatar.textContent = (profile.username || "?").charAt(0).toUpperCase();
    }, { once: true });
    avatar.appendChild(image);
  } else {
    avatar.classList.add("has-fallback");
    avatar.textContent = (profile.username || "?").charAt(0).toUpperCase();
  }

  const name = document.createElement("span");
  name.className = "friend-list-name";
  name.textContent = profile.username || "Axiom reader";

  link.append(avatar, name);
  return link;
}

// "All" tab: profile link + a Remove button. Removing calls onRemoved
// (a full reload of the friends page) once the backend confirms it, so
// the list always reflects the database rather than an optimistic guess.
function createFriendRow(entry, onRemoved) {
  const row = document.createElement("div");
  row.className = "friend-list-row";
  row.appendChild(createFriendProfileLink(entry.user));

  const actions = document.createElement("div");
  actions.className = "friend-list-row-actions";

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "ghost-link friend-list-remove";
  removeButton.textContent = "Remove";
  removeButton.addEventListener("click", async () => {
    const name = entry.user.username || "this reader";
    const confirmed = await showConfirmModal(`Remove ${name} as a friend?`);
    if (!confirmed) return;

    removeButton.disabled = true;
    removeButton.textContent = "Removing\u2026";
    try {
      const response = await authFetch(`${API_BASE}/api/friendships/${entry.friendship_id}`, {
        method: "DELETE",
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't remove this friend.");
      }
      onRemoved();
    } catch (error) {
      alert(error.message || "Couldn't remove this friend. Please try again.");
      removeButton.disabled = false;
      removeButton.textContent = "Remove";
    }
  });

  actions.appendChild(removeButton);
  row.appendChild(actions);
  return row;
}

// "Pending" tab: profile link + a direction badge. Purely informational
// -- accepting/rejecting still happens from the Inbox notification.
function createPendingRow(entry) {
  const row = document.createElement("div");
  row.className = "friend-list-row is-pending";
  row.appendChild(createFriendProfileLink(entry.user));

  const badge = document.createElement("span");
  badge.className = "friend-list-direction";
  badge.textContent = entry.direction === "outgoing" ? "Request sent" : "Awaiting your response";
  row.appendChild(badge);

  return row;
}

function renderEmptyState(container, message) {
  container.innerHTML = "";
  const empty = document.createElement("p");
  empty.className = "search-empty";
  empty.textContent = message;
  container.appendChild(empty);
}

function setupFriendsTabs() {
  const tabs = [...document.querySelectorAll("[data-friends-tab]")];
  const panels = [...document.querySelectorAll("[data-friends-panel]")];

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.friendsTab;

      tabs.forEach((otherTab) => {
        const isActive = otherTab === tab;
        otherTab.setAttribute("aria-selected", String(isActive));
        otherTab.tabIndex = isActive ? 0 : -1;
      });

      panels.forEach((panel) => {
        panel.hidden = panel.dataset.friendsPanel !== target;
      });
    });
  });
}

async function loadFriends() {
  const summary = document.querySelector("[data-friends-summary]");
  const allList = document.querySelector('[data-friends-list="all"]');
  const pendingList = document.querySelector('[data-friends-list="pending"]');
  if (!allList || !pendingList) return;

  try {
    const response = await authFetch(`${API_BASE}/api/friendships`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) throw new Error("Failed to load friends");

    const payload = await response.json();
    const friends = payload.friends || [];
    const pending = payload.pending || [];

    if (summary) {
      const friendWord = friends.length === 1 ? "friend" : "friends";
      const pendingSuffix = pending.length
        ? ` \u00b7 ${pending.length} pending ${pending.length === 1 ? "request" : "requests"}`
        : "";
      summary.textContent = `${friends.length} ${friendWord}${pendingSuffix}.`;
    }

    allList.innerHTML = "";
    if (!friends.length) {
      renderEmptyState(allList, "You haven't connected with any readers yet.");
    } else {
      // The backend already returns these sorted alphabetically by
      // username, so no client-side sort is needed here.
      friends.forEach((entry) => allList.appendChild(createFriendRow(entry, loadFriends)));
    }

    pendingList.innerHTML = "";
    if (!pending.length) {
      renderEmptyState(pendingList, "No pending friend requests.");
    } else {
      pending.forEach((entry) => pendingList.appendChild(createPendingRow(entry)));
    }
  } catch (error) {
    if (summary) summary.textContent = "Friends are temporarily unavailable.";
    renderEmptyState(allList, "Couldn't load your friends. Make sure the backend is running on port 8000.");
    renderEmptyState(pendingList, "Couldn't load your friends. Make sure the backend is running on port 8000.");
  }
}

if (requireSession()) {
  setupFriendsTabs();
  loadFriends();
}