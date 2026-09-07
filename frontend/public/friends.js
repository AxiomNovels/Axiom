function requireSession() {
  if (!getAccessToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

function createFriendListItem(profile) {
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

function createPendingListItem(entry) {
  const item = createFriendListItem(entry.user);
  item.classList.add("is-pending");

  const badge = document.createElement("span");
  badge.className = "friend-list-direction";
  badge.textContent = entry.direction === "outgoing" ? "Request sent" : "Awaiting your response";
  item.appendChild(badge);

  return item;
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
      friends.forEach((profile) => allList.appendChild(createFriendListItem(profile)));
    }

    pendingList.innerHTML = "";
    if (!pending.length) {
      renderEmptyState(pendingList, "No pending friend requests.");
    } else {
      pending.forEach((entry) => pendingList.appendChild(createPendingListItem(entry)));
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