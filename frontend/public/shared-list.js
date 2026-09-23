async function loadSharedList() {
  const params = new URLSearchParams(window.location.search);
  const userId = params.get("user");
  const listId = params.get("id");

  const titleEl = document.querySelector("[data-list-title]");
  const summaryEl = document.querySelector("[data-list-summary]");
  const ownerEl = document.querySelector("[data-list-owner]");
  const backLink = document.querySelector("[data-back-link]");
  const grid = document.querySelector("[data-list-novels]");

  if (userId && backLink) backLink.href = `/user.html?id=${encodeURIComponent(userId)}`;

  const showUnavailable = () => {
    titleEl.textContent = "Reading list unavailable";
    summaryEl.textContent = "";
    grid.innerHTML = '<p class="search-empty">This reading list is private or no longer exists.</p>';
  };

  if (!userId || !listId) {
    showUnavailable();
    return;
  }

  try {
    const response = await authFetch(
      `${API_BASE}/api/users/${encodeURIComponent(userId)}/reading-lists/${encodeURIComponent(listId)}`
    );
    if (response.status === 404) {
      showUnavailable();
      return;
    }
    if (!response.ok) throw new Error("Failed to load reading list");

    const list = await response.json();
    const username = list.owner?.username || "this reader";
    document.title = `${list.name} | Axiom`;
    titleEl.textContent = list.name;
    ownerEl.textContent = `Reading list by ${username}`;
    if (backLink) backLink.textContent = `← Back to ${username}'s profile`;

    const likeSlot = document.querySelector("[data-list-like]");
    if (likeSlot) {
      likeSlot.innerHTML = "";
      likeSlot.appendChild(createListLikeControl(list, { isOwner: Boolean(list.is_owner), large: true }));
    }

    const novels = list.novels || [];
    summaryEl.textContent = `${novels.length} ${novels.length === 1 ? "novel" : "novels"} in this list.`;
    initListReviews(listId);
    grid.innerHTML = "";
    if (!novels.length) {
      grid.innerHTML = '<p class="search-empty">No novels in this list yet.</p>';
      return;
    }
    novels.forEach((novel, index) => grid.appendChild(createNovelCard(novel, index)));
  } catch (error) {
    titleEl.textContent = "Couldn't load this list";
    grid.innerHTML = '<p class="search-empty">Make sure the backend is running on port 8000.</p>';
  }
}

loadSharedList();