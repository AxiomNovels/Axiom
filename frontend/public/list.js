function getListIdFromUrl() {
  return new URLSearchParams(window.location.search).get("id");
}

function createListNovelCard(novel, index, listId) {
  const wrapper = document.createElement("div");
  wrapper.className = "list-novel-item";

  const link = createNovelCard(novel, index);

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
}