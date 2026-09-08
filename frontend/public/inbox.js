function requireSession() {
  if (!getAccessToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

function formatNotificationDate(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  const day = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  const time = date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${day} · ${time}`;
}

async function setNotificationRead(id, isRead) {
  const response = await authFetch(`${API_BASE}/api/inbox/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_read: isRead }),
  });
  if (response.status === 401) {
    window.location.href = "/login.html";
    return null;
  }
  if (!response.ok) throw new Error("Couldn't update this message.");
  return response.json();
}

// Renders the friend_request-specific part of a message body: a link to
// the sender's profile, and either the live Accept/Reject controls (while
// data.friendship_status is "pending") or a short resolved message.
// Called again after a response is submitted so the UI reflects the
// backend's answer rather than assuming the click succeeded as intended.
function renderFriendRequestExtras(extrasContainer, notification) {
  extrasContainer.innerHTML = "";
  const data = notification.data || {};

  if (data.sender_id) {
    const profileLine = document.createElement("p");
    profileLine.className = "inbox-friend-request-link";
    profileLine.append("From ");
    const link = document.createElement("a");
    link.href = `/user.html?id=${encodeURIComponent(data.sender_id)}`;
    link.textContent = data.sender_username || "this reader";
    profileLine.appendChild(link);
    extrasContainer.appendChild(profileLine);
  }

  const status = data.friendship_status;

  if (status !== "pending") {
    const resolved = document.createElement("p");
    resolved.className = "inbox-friend-request-resolved";
    if (status === "accepted") resolved.textContent = "You accepted this request. You're now friends.";
    else if (status === "rejected") resolved.textContent = "You declined this request.";
    else resolved.textContent = "This request is no longer available.";
    extrasContainer.appendChild(resolved);
    return;
  }

  const actionsRow = document.createElement("div");
  actionsRow.className = "inbox-friend-request-actions";

  const acceptButton = document.createElement("button");
  acceptButton.type = "button";
  acceptButton.className = "inbox-friend-accept";
  acceptButton.textContent = "Accept";

  const rejectButton = document.createElement("button");
  rejectButton.type = "button";
  rejectButton.className = "ghost-link inbox-friend-reject";
  rejectButton.textContent = "Reject";

  async function respond(action) {
    acceptButton.disabled = true;
    rejectButton.disabled = true;
    try {
      const response = await authFetch(`${API_BASE}/api/friendships/${data.friendship_id}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't update this request.");
      }
      notification.data = { ...data, friendship_status: result.status };
      renderFriendRequestExtras(extrasContainer, notification);
      window.refreshFriendRequestBadges?.();
    } catch (error) {
      alert(error.message || "Couldn't update this request. Please try again.");
      acceptButton.disabled = false;
      rejectButton.disabled = false;
    }
  }

  acceptButton.addEventListener("click", () => respond("accept"));
  rejectButton.addEventListener("click", () => respond("reject"));
  actionsRow.append(acceptButton, rejectButton);
  extrasContainer.appendChild(actionsRow);
}

// Each message is a <details>/<summary> disclosure, matching the pattern
// already used elsewhere on the site (trait guides, profile disclosures).
// Opening it is what marks a message read; the button lets a reader
// manually flip read/unread state either way afterward.
function createNotificationCard(notification) {
  const details = document.createElement("details");
  details.className = "inbox-message";
  details.dataset.id = notification.id;

  const summary = document.createElement("summary");
  summary.className = "inbox-message-summary";

  const dot = document.createElement("span");
  dot.className = "inbox-unread-dot";
  dot.setAttribute("aria-hidden", "true");

  const subject = document.createElement("strong");
  subject.className = "inbox-message-subject";
  subject.textContent = notification.subject;

  const date = document.createElement("time");
  date.className = "inbox-message-date";
  date.dateTime = notification.created_at;
  date.textContent = formatNotificationDate(notification.created_at);

  summary.append(dot, subject, date);

  const body = document.createElement("div");
  body.className = "inbox-message-body";

  const bodyText = document.createElement("p");
  bodyText.textContent = notification.body;
  body.appendChild(bodyText);

  if (notification.type === "friend_request") {
    const extras = document.createElement("div");
    extras.className = "inbox-friend-request-extras";
    renderFriendRequestExtras(extras, notification);
    body.appendChild(extras);
  }

  const actions = document.createElement("div");
  actions.className = "inbox-message-actions";

  const readToggleButton = document.createElement("button");
  readToggleButton.type = "button";
  readToggleButton.className = "ghost-link inbox-read-toggle";

  function applyReadState(isRead) {
    notification.is_read = isRead;
    details.classList.toggle("is-unread", !isRead);
    readToggleButton.textContent = isRead ? "Mark as unread" : "Mark as read";
    window.refreshInboxBadge?.();
  }

  readToggleButton.addEventListener("click", async () => {
    readToggleButton.disabled = true;
    try {
      const updated = await setNotificationRead(notification.id, !notification.is_read);
      if (updated) applyReadState(updated.is_read);
    } catch (error) {
      alert(error.message || "Couldn't update this message. Please try again.");
    } finally {
      readToggleButton.disabled = false;
    }
  });

  actions.appendChild(readToggleButton);
  body.appendChild(actions);
  details.append(summary, body);

  applyReadState(notification.is_read);

  details.addEventListener("toggle", async () => {
    if (!details.open || notification.is_read) return;
    try {
      const updated = await setNotificationRead(notification.id, true);
      if (updated) applyReadState(updated.is_read);
    } catch {
      // The message still opens even if the read receipt fails to save;
      // the reader can always use the manual toggle afterward.
    }
  });

  return details;
}

function updateInboxSummary(notifications) {
  const summary = document.querySelector("[data-inbox-summary]");
  if (!summary) return;

  if (!notifications.length) {
    summary.textContent = "Your inbox is empty.";
    return;
  }

  const unread = notifications.filter((notification) => !notification.is_read).length;
  const messageWord = notifications.length === 1 ? "message" : "messages";
  summary.textContent = unread
    ? `${notifications.length} ${messageWord}, ${unread} unread.`
    : `${notifications.length} ${messageWord}.`;
}

async function loadInbox() {
  const list = document.querySelector("[data-inbox-list]");
  if (!list) return;

  try {
    const response = await authFetch(`${API_BASE}/api/inbox`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) throw new Error("Failed to load inbox");

    const notifications = await response.json();
    updateInboxSummary(notifications);
    list.innerHTML = "";

    if (!notifications.length) {
      list.innerHTML = '<p class="search-empty">Your inbox is empty. System notifications will appear here.</p>';
      return;
    }

    notifications.forEach((notification) => list.appendChild(createNotificationCard(notification)));
  } catch (error) {
    const summary = document.querySelector("[data-inbox-summary]");
    if (summary) summary.textContent = "Inbox is temporarily unavailable.";
    list.innerHTML = "<p class=\"search-empty\">Couldn't load your inbox. Make sure the backend is running on port 8000.</p>";
  }
}

if (requireSession()) {
  loadInbox();
}