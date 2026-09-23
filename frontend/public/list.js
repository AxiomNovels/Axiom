function getListIdFromUrl() {
  return new URLSearchParams(window.location.search).get("id");
}

// A small "Chapter N" control shown on each novel in a reading list.
// Saves via PUT /api/reading-progress/{novel_id} on blur/Enter, and keeps
// the in-memory novel.current_chapter in sync so repeated edits diff
// correctly without needing a full list reload.
function createChapterControl(novel) {
  const wrapper = document.createElement("div");
  wrapper.className = "list-novel-chapter";

  const label = document.createElement("label");
  label.className = "list-novel-chapter-label";
  label.textContent = "Chapter";
  label.setAttribute("for", `chapter-input-${novel.id}`);

  const input = document.createElement("input");
  input.type = "number";
  input.min = "1";
  input.step = "1";
  input.inputMode = "numeric";
  input.id = `chapter-input-${novel.id}`;
  input.className = "list-novel-chapter-input";
  input.value = novel.current_chapter || 1;
  input.setAttribute("aria-label", `Current chapter for ${novel.title}`);

  const status = document.createElement("span");
  status.className = "list-novel-chapter-status";
  status.setAttribute("aria-live", "polite");

  const saveChapter = async () => {
    const parsed = Math.max(1, Math.floor(Number(input.value)) || 1);
    input.value = parsed;
    if (parsed === novel.current_chapter) return;

    status.textContent = "Saving…";
    try {
      const response = await authFetch(`${API_BASE}/api/reading-progress/${novel.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_chapter: parsed }),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      if (!response.ok) throw new Error("Update failed");
      novel.current_chapter = parsed;
      status.textContent = "Saved";
      setTimeout(() => { status.textContent = ""; }, 1500);
    } catch (error) {
      status.textContent = "";
      alert("Couldn't save your chapter progress. Please try again.");
      input.value = novel.current_chapter || 1;
    }
  };

  input.addEventListener("change", saveChapter);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      input.blur();
    }
  });

  wrapper.append(label, input, status);
  return wrapper;
}

function createListNovelCard(novel, index, listId) {
  const wrapper = document.createElement("div");
  wrapper.className = "list-novel-item";

  const link = createNovelCard(novel, index);
  const chapterControl = createChapterControl(novel);

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "ghost-link list-novel-remove";
  removeButton.textContent = "Remove";
  removeButton.addEventListener("click", async () => {
    removeButton.disabled = true;
    try {
      const response = await authFetch(
        `${API_BASE}/api/reading-lists/${listId}/novels/${novel.id}`,
        { method: "DELETE" }
      );
      if (!response.ok) throw new Error("Remove failed");
      await loadReadingList();
    } catch (error) {
      alert("Couldn't remove this novel. Please try again.");
      removeButton.disabled = false;
    }
  });

  wrapper.appendChild(link);
  wrapper.appendChild(chapterControl);
  wrapper.appendChild(removeButton);
  return wrapper;
}

async function loadReadingList() {
  const listId = getListIdFromUrl();
  const titleEl = document.querySelector("[data-list-title]");
  const summaryEl = document.querySelector("[data-list-summary]");
  const grid = document.querySelector("[data-list-novels]");

  if (!listId) {
    if (titleEl) titleEl.textContent = "Reading list not found";
    return;
  }

  try {
    const response = await authFetch(`${API_BASE}/api/reading-lists/${listId}`);
    if (response.status === 401) {
      window.location.href = "/login.html";
      return;
    }
    if (response.status === 404) {
      if (titleEl) titleEl.textContent = "Reading list not found";
      if (grid) grid.innerHTML = "";
      return;
    }
    if (!response.ok) throw new Error("Failed to load reading list");

    const list = await response.json();
    document.title = `${list.name} | Axiom`;
    if (titleEl) titleEl.textContent = list.name;

    const likeSlot = document.querySelector("[data-list-like]");
    if (likeSlot) {
      likeSlot.innerHTML = "";
      likeSlot.appendChild(createListLikeControl(list, { isOwner: true, large: true }));
    }

    const novels = list.novels || [];
    if (summaryEl) {
      const novelWord = novels.length === 1 ? "novel" : "novels";
      summaryEl.textContent = `${novels.length} ${novelWord} in this list.`;
    }

    if (!grid) return;
    grid.innerHTML = "";

    if (!novels.length) {
      grid.innerHTML = "<p class=\"search-empty\">No novels in this list yet. Add some from any novel's page.</p>";
      return;
    }

    novels.forEach((novel, index) => grid.appendChild(createListNovelCard(novel, index, listId)));
  } catch (error) {
    if (titleEl) titleEl.textContent = "Couldn't load this list";
    if (grid) grid.innerHTML = "<p class=\"search-empty\">Make sure the backend is running on port 8000.</p>";
  }
}

if (!getAccessToken()) {
  window.location.href = "/login.html";
} else {
  loadReadingList();
  initListReviews(getListIdFromUrl());
}