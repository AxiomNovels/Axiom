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
  body.append(bodyText, actions);
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