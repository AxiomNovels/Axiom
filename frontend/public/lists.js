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

// Icon + one-line description shown for each visibility level, used both
// by the chip's compact label and by the popover's option rows.
const VISIBILITY_CONFIG = {
  private: { emoji: "🔒", label: "Private", description: "Only you can see this list." },
  friends: { emoji: "👥", label: "Friends", description: "People you're friends with can see it." },
  public: { emoji: "🌍", label: "Public", description: "Anyone with the link can see it." },
};

// A small emoji "chip" (built on the same <details>/<summary> disclosure
// pattern as the reading-list picker on novel.js and the account menu in
// script.js) that opens a popover of visibility options.
function createVisibilityControl(list) {
  const picker = document.createElement("details");
  picker.className = "list-visibility-picker";

  const summary = document.createElement("summary");
  summary.className = "list-visibility-chip";

  const icon = document.createElement("span");
  icon.className = "list-visibility-icon";
  icon.setAttribute("aria-hidden", "true");

  const label = document.createElement("span");
  label.className = "list-visibility-label";

  const status = document.createElement("span");
  status.className = "list-visibility-status";
  status.setAttribute("aria-live", "polite");

  summary.append(icon, label, status);

  const menu = document.createElement("div");
  menu.className = "list-visibility-menu";
  const heading = document.createElement("strong");
  heading.textContent = "Who can see this";
  menu.appendChild(heading);

  const optionButtons = {};

  function applyVisibility(value) {
    const entry = VISIBILITY_CONFIG[value] || VISIBILITY_CONFIG.private;
    icon.textContent = entry.emoji;
    label.textContent = entry.label;
    Object.entries(optionButtons).forEach(([optionValue, button]) => {
      button.classList.toggle("is-selected", optionValue === value);
    });
  }

  function setBusy(busy) {
    Object.values(optionButtons).forEach((button) => { button.disabled = busy; });
  }

  Object.entries(VISIBILITY_CONFIG).forEach(([value, entry]) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "list-visibility-option";

    const optionIcon = document.createElement("span");
    optionIcon.className = "list-visibility-option-icon";
    optionIcon.setAttribute("aria-hidden", "true");
    optionIcon.textContent = entry.emoji;

    const copy = document.createElement("span");
    copy.className = "list-visibility-option-copy";
    const title = document.createElement("strong");
    title.textContent = entry.label;
    const description = document.createElement("small");
    description.textContent = entry.description;
    copy.append(title, description);

    const check = document.createElement("span");
    check.className = "list-visibility-option-check";
    check.setAttribute("aria-hidden", "true");
    check.textContent = "✓";

    option.append(optionIcon, copy, check);

    option.addEventListener("click", async () => {
      const previous = list.visibility || "private";
      if (value === previous) {
        picker.removeAttribute("open");
        return;
      }

      setBusy(true);
      status.textContent = "Saving…";
      try {
        const response = await authFetch(`${API_BASE}/api/reading-lists/${list.id}/visibility`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ visibility: value }),
        });
        if (response.status === 401) {
          window.location.href = "/login.html";
          return;
        }
        if (!response.ok) {
          const result = await response.json().catch(() => ({}));
          throw new Error(typeof result.detail === "string" ? result.detail : "Update failed");
        }
        list.visibility = value;
        applyVisibility(value);
        status.textContent = "Saved";
        setTimeout(() => { status.textContent = ""; }, 1500);
        picker.removeAttribute("open");
      } catch (error) {
        status.textContent = "";
        alert(error.message || "Couldn't update this list's visibility. Please try again.");
      } finally {
        setBusy(false);
      }
    });

    optionButtons[value] = option;
    menu.appendChild(option);
  });

  applyVisibility(list.visibility || "private");
  picker.append(summary, menu);
  return picker;
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

  link.append(bookcase, title, count, createListRatingLine(list));

  // Footer: who can see the list on the left, its heart on the right. The
  // heart is the same control used on the list's own page and on profiles.
  const metaRow = document.createElement("div");
  metaRow.className = "reading-list-card-meta-row";
  metaRow.append(createVisibilityControl(list), createListLikeControl(list, { isOwner: true }));

  const actions = document.createElement("div");
  actions.className = "reading-list-card-actions";

  const renameButton = document.createElement("button");
  renameButton.type = "button";
  renameButton.className = "ghost-link reading-list-action";
  renameButton.textContent = "Rename";
  renameButton.setAttribute("aria-label", `Rename ${list.name}`);
  renameButton.addEventListener("click", () => openListModal(list));

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.className = "ghost-link reading-list-action";
  deleteButton.textContent = "Delete";
  deleteButton.setAttribute("aria-label", `Delete ${list.name}`);
  deleteButton.addEventListener("click", () => deleteList(list));

  actions.append(renameButton, deleteButton);
  card.append(link, metaRow, actions);
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
    <strong>Start a new list</strong>
    <small>Give another set of stories its own shelf</small>`;
  // Wrapped on purpose: passing openListModal directly would hand it the
  // click event as its `list` argument and put the dialog in rename mode.
  button.addEventListener("click", () => openListModal());
  return button;
}

// ---------------------------------------------------------------------
// Create / rename dialog (one dialog, two modes)
// ---------------------------------------------------------------------

let editingList = null; // null = creating a new list; otherwise the list being renamed
let modalReturnFocus = null;

function getListModal() {
  return document.querySelector("[data-create-list-modal]");
}

// The inline error line is created on first use so lists.html needs no changes.
function getModalError(modal) {
  let error = modal.querySelector(".create-list-error");
  if (!error) {
    error = document.createElement("p");
    error.className = "create-list-error";
    error.setAttribute("role", "alert");
    modal.querySelector(".modal-actions").before(error);
  }
  return error;
}

function openListModal(list = null) {
  const modal = getListModal();
  if (!modal) return;

  editingList = list;
  modalReturnFocus = document.activeElement;
  const renaming = Boolean(list);

  modal.querySelector(".eyebrow").textContent = renaming ? "Rename collection" : "New collection";
  modal.querySelector("#new-list-heading").textContent = renaming ? "Rename your reading list" : "Create a reading list";
  modal.querySelector('button[type="submit"]').textContent = renaming ? "Save name" : "Create list";
  getModalError(modal).textContent = "";

  const input = document.getElementById("new-list-name");
  input.value = renaming ? list.name : "";

  modal.classList.remove("is-hidden");
  document.body.classList.add("modal-open");
  requestAnimationFrame(() => {
    input.focus();
    input.select();
  });
}

function closeListModal() {
  const modal = getListModal();
  if (!modal) return;
  modal.classList.add("is-hidden");
  document.body.classList.remove("modal-open");
  editingList = null;
  if (modalReturnFocus && modalReturnFocus.isConnected) modalReturnFocus.focus();
  modalReturnFocus = null;
}

async function deleteList(list) {
  const confirmed = await showConfirmModal(
    `Delete “${list.name}”? The list and everything on it will be removed. This can't be undone.`
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
      summary.textContent = lists.length
        ? `You have ${lists.length} reading ${listWord}.`
        : "Your shelves are empty. Start your first list below.";
    }

    lists.forEach((list) => grid.appendChild(createListCard(list)));
    grid.appendChild(createGhostListCard());
  } catch (error) {
    grid.innerHTML = "<p class=\"search-empty\">Couldn't load your reading lists. Make sure the backend is running on port 8000.</p>";
  }
}

function setupListModal() {
  const form = document.querySelector("[data-new-list-form]");
  const modal = getListModal();
  if (!form || !modal) return;

  document.querySelector("[data-create-list-close]")?.addEventListener("click", closeListModal);
  document.querySelector("[data-create-list-cancel]")?.addEventListener("click", closeListModal);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeListModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("is-hidden")) closeListModal();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.getElementById("new-list-name");
    const errorEl = getModalError(modal);
    const name = input.value.trim();

    if (!name) {
      errorEl.textContent = "Give your list a name.";
      input.focus();
      return;
    }

    const renaming = Boolean(editingList);
    if (renaming && name === editingList.name) {
      closeListModal();
      return;
    }

    const submit = form.querySelector('button[type="submit"]');
    const idleLabel = submit.textContent;
    submit.textContent = renaming ? "Saving..." : "Creating...";
    submit.disabled = true;
    errorEl.textContent = "";

    try {
      const url = renaming
        ? `${API_BASE}/api/reading-lists/${editingList.id}`
        : `${API_BASE}/api/reading-lists`;
      const response = await authFetch(url, {
        method: renaming ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : `Couldn't ${renaming ? "rename" : "create"} this list. Please try again.`
        );
      }
      closeListModal();
      await loadReadingLists();
    } catch (error) {
      errorEl.textContent = error.message || "Something went wrong. Please try again.";
    } finally {
      submit.textContent = idleLabel;
      submit.disabled = false;
    }
  });
}

// Close an open visibility popover when clicking anywhere outside it (or on
// Escape), matching the reading-list picker on novel.js and the account menu
// in script.js.
document.addEventListener("click", (event) => {
  document.querySelectorAll(".list-visibility-picker[open]").forEach((picker) => {
    if (!picker.contains(event.target)) picker.removeAttribute("open");
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  document.querySelectorAll(".list-visibility-picker[open]").forEach((picker) => picker.removeAttribute("open"));
});

if (requireSession()) {
  setupListModal();
  loadReadingLists();
}