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

const VISIBILITY_OPTIONS = [
  ["private", "Private"],
  ["friends", "Visible to Friends"],
  ["public", "Public"],
];

function createVisibilityControl(list) {
  const wrapper = document.createElement("div");
  wrapper.className = "reading-list-visibility";

  const head = document.createElement("div");
  head.className = "reading-list-visibility-head";

  const selectId = `list-visibility-${list.id}`;
  const label = document.createElement("label");
  label.setAttribute("for", selectId);
  label.textContent = "Who can see this";

  const status = document.createElement("span");
  status.className = "reading-list-visibility-status";
  status.setAttribute("aria-live", "polite");
  head.append(label, status);

  const select = document.createElement("select");
  select.id = selectId;
  select.className = "reading-list-visibility-select";
  VISIBILITY_OPTIONS.forEach(([value, text]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    select.appendChild(option);
  });
  select.value = list.visibility || "private";

  select.addEventListener("change", async () => {
    const next = select.value;
    const previous = list.visibility || "private";
    select.disabled = true;
    status.textContent = "Saving…";
    try {
      const response = await authFetch(`${API_BASE}/api/reading-lists/${list.id}/visibility`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visibility: next }),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(typeof result.detail === "string" ? result.detail : "Update failed");
      }
      list.visibility = next;
      status.textContent = "Saved";
      setTimeout(() => { status.textContent = ""; }, 1500);
    } catch (error) {
      select.value = previous;
      status.textContent = "";
      alert(error.message || "Couldn't update this list's visibility. Please try again.");
    } finally {
      select.disabled = false;
    }
  });

  wrapper.append(head, select);
  return wrapper;
}

function createListCard(list) {
  const card = document.createElement("article");
  card.className = "reading-list-card";

  const link = document.createElement("a");
  link.className = "reading-list-card-link";
  link.href = `/list.html?id=${list.id}`;

  const bookcase = createListBookcase(list.preview_novels || []);

  const title = document.createElement("h3");
  title.textContent = list.name;

  const count = document.createElement("p");
  const novelWord = list.novel_count === 1 ? "novel" : "novels";
  count.textContent = `${list.novel_count} ${novelWord}`;

  link.appendChild(bookcase);
  link.appendChild(title);
  link.appendChild(count);
  link.appendChild(createListRatingLine(list));

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
  card.appendChild(createVisibilityControl(list));
  card.appendChild(actions);

  return card;
}

function createGhostListCard() {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "reading-list-card create-list-card";
  button.setAttribute("aria-label", "Create a new reading list");
  button.innerHTML = `
    <span class="create-list-preview" aria-hidden="true">
      <span class="create-list-ghost-books">
        <span class="create-list-ghost-book"></span>
        <span class="create-list-ghost-book"></span>
        <span class="create-list-ghost-book"></span>
      </span>
      <span class="create-list-plus">+</span>
    </span>
    <strong>Create a new list</strong>
    <small>Start another collection</small>`;
  button.addEventListener("click", openCreateListModal);
  return button;
}

function openCreateListModal() {
  const modal = document.querySelector("[data-create-list-modal]");
  if (!modal) return;
  modal.classList.remove("is-hidden");
  document.body.classList.add("modal-open");
  requestAnimationFrame(() => document.getElementById("new-list-name")?.focus());
}

function closeCreateListModal() {
  const modal = document.querySelector("[data-create-list-modal]");
  if (!modal) return;
  modal.classList.add("is-hidden");
  document.body.classList.remove("modal-open");
  document.querySelector(".create-list-card")?.focus();
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
    await Promise.all(lists.map(async (list) => {
      if (!list.novel_count || list.preview_novels?.length) return;
      try {
        const detailResponse = await authFetch(`${API_BASE}/api/reading-lists/${list.id}`);
        if (!detailResponse.ok) return;
        const detail = await detailResponse.json();
        list.preview_novels = (detail.novels || []).slice(0, 3);
      } catch {
        list.preview_novels = [];
      }
    }));
    grid.innerHTML = "";

    if (summary) {
      const listWord = lists.length === 1 ? "list" : "lists";
      summary.textContent = `You have ${lists.length} reading ${listWord}.`;
    }

    lists.forEach((list) => grid.appendChild(createListCard(list)));
    grid.appendChild(createGhostListCard());
  } catch (error) {
    grid.innerHTML = "<p class=\"search-empty\">Couldn't load your reading lists. Make sure the backend is running on port 8000.</p>";
  }
}

function setupNewListForm() {
  const form = document.querySelector("[data-new-list-form]");
  if (!form) return;

  const modal = document.querySelector("[data-create-list-modal]");
  document.querySelector("[data-create-list-close]")?.addEventListener("click", closeCreateListModal);
  document.querySelector("[data-create-list-cancel]")?.addEventListener("click", closeCreateListModal);
  modal?.addEventListener("click", (event) => {
    if (event.target === modal) closeCreateListModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal?.classList.contains("is-hidden")) closeCreateListModal();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("new-list-name");
    const name = input.value.trim();
    if (!name) return;

    const button = form.querySelector('button[type="submit"]');
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
      closeCreateListModal();
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
