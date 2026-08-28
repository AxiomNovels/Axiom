function requireSession() {
  if (!getAccessToken()) {
    window.location.href = "/login.html";
    return false;
  }
  return true;
}

// Shows the shared Yes/No modal and resolves true/false with the user's
// choice. Falls back to the native confirm() if the modal markup is
// missing from the page for some reason.
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

function createListCard(list) {
  const card = document.createElement("article");
  card.className = "reading-list-card";

  const link = document.createElement("a");
  link.className = "reading-list-card-link";
  link.href = `/list.html?id=${list.id}`;

  const title = document.createElement("h3");
  title.textContent = list.name;

  const count = document.createElement("p");
  const novelWord = list.novel_count === 1 ? "novel" : "novels";
  count.textContent = `${list.novel_count} ${novelWord}`;

  link.appendChild(title);
  link.appendChild(count);

  const actions = document.createElement("div");
  actions.className = "reading-list-card-actions";

  const renameButton = document.createElement("button");
  renameButton.type = "button";
  renameButton.className = "ghost-link reading-list-action";
  renameButton.textContent = "Rename";
  renameButton.addEventListener("click", () => renameList(list));

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "ghost-link reading-list-action";
  deleteButton.textContent = "Delete";
  deleteButton.addEventListener("click", () => deleteList(list));

  actions.appendChild(renameButton);
  actions.appendChild(deleteButton);

  card.appendChild(link);
  card.appendChild(actions);
  return card;
}

async function renameList(list) {
  const nextName = window.prompt("Rename list", list.name);
  if (nextName === null) return;

  const trimmed = nextName.trim();
  if (!trimmed || trimmed === list.name) return;

  try {
    const response = await authFetch(`${API_BASE}/api/reading-lists/${list.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: trimmed }),
    });
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.detail || "Rename failed");
    }
    await loadReadingLists();
  } catch (error) {
    alert(error.message || "Couldn't rename this list. Please try again.");
  }
}

async function deleteList(list) {
  const confirmed = await showConfirmModal(
    "All novels in this list will be lost forever. Do you wish to proceed?"
  );
  if (!confirmed) return;

  try {
    const response = await authFetch(`${API_BASE}/api/reading-lists/${list.id}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error("Delete failed");
    await loadReadingLists();
  } catch (error) {
    alert("Couldn't delete this list. Please try again.");
  }
}

async function loadReadingLists() {
  const grid = document.querySelector("[data-lists-grid]");
  const summary = document.querySelector("[data-lists-summary]");
  if (!grid) return;

  try {
    const response = await authFetch(`${API_BASE}/api/reading-lists`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (!response.ok) throw new Error("Failed to load reading lists");

    const lists = await response.json();
    grid.innerHTML = "";

    if (summary) {
      const listWord = lists.length === 1 ? "list" : "lists";
      summary.textContent = `You have ${lists.length} reading ${listWord}.`;
    }

    if (!lists.length) {
      grid.innerHTML = "<p class=\"search-empty\">You don't have any reading lists yet. Create one above.</p>";
      return;
    }

    lists.forEach((list) => grid.appendChild(createListCard(list)));
  } catch (error) {
    grid.innerHTML = "<p class=\"search-empty\">Couldn't load your reading lists. Make sure the backend is running on port 8000.</p>";
  }
}

function setupNewListForm() {
  const form = document.querySelector("[data-new-list-form]");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("new-list-name");
    const name = input.value.trim();
    if (!name) return;

    const button = form.querySelector("button");
    const originalText = button.textContent;
    button.textContent = "Creating...";
    button.disabled = true;

    try {
      const response = await authFetch(`${API_BASE}/api/reading-lists`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail || "Create failed");
      }
      input.value = "";
      await loadReadingLists();
    } catch (error) {
      alert(error.message || "Couldn't create this list. Please try again.");
    } finally {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
}

if (requireSession()) {
  setupNewListForm();
  loadReadingLists();
}