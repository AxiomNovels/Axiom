const deletionState = { page: 1, query: "", version: 0 };

async function loadDeletionNovels() {
  const version = ++deletionState.version;
  const host = document.getElementById("deletion-results");
  status("Searching novels...");
  const data = await request(`/novels?q=${encodeURIComponent(deletionState.query)}&page=${deletionState.page}`);
  if (version !== deletionState.version) return;
  if (!data.novels.length && deletionState.page > 1) {
    deletionState.page--;
    return loadDeletionNovels();
  }
  host.replaceChildren();
  for (const novel of data.novels) {
    const row = element("div", undefined, "home-feature-result");
    const copy = element("div");
    const link = element("a", novel.title);
    link.href = `/novel.html?id=${encodeURIComponent(novel.id)}`;
    copy.append(link, element("small", novel.author || "Unknown author"));
    const remove = action("Delete novel", async () => {
      if (!await confirmNovelDeletion(novel)) return;
      // Discard only the deleted novel's editor. Other drafts stay intact.
      const editor = document.getElementById("profile-editor");
      if (editor.dataset.novelId === String(novel.id)) {
        ++editorVersion; editor.replaceChildren(); dirty = false;
      }
      ++voteViewVersion; voteView = null;
      document.getElementById("vote-workspace").hidden = true;
      ++state.novels.version;
      document.getElementById("novels-results").replaceChildren();
      document.getElementById("home-feature-results").replaceChildren();
      if (selectedHomeNovel?.id === novel.id) renderHomeFeatureSelection(null);
      row.remove();
      try { await loadDeletionNovels(); }
      catch { status("Novel deleted and affected readers notified. Search again to refresh the catalogue."); return; }
      status("Novel deleted. Affected readers have been notified in their Inbox.");
    });
    remove.className = "admin-danger";
    remove.setAttribute("aria-label", `Delete novel: ${novel.title}`);
    row.append(copy, remove); host.append(row);
  }
  if (!data.novels.length) host.append(element("p", "No matches found."));
  const previous = action("Previous", async () => { deletionState.page--; await loadDeletionNovels(); });
  previous.disabled = deletionState.page === 1;
  const next = action("Next", async () => { deletionState.page++; await loadDeletionNovels(); });
  next.disabled = deletionState.page * 25 >= data.total;
  document.getElementById("deletion-pages").replaceChildren(previous, element("span", `Page ${deletionState.page} / ${data.total} results`), next);
  status("");
}

document.getElementById("deletion-tab").addEventListener("click", () => {
  for (const section of ["users", "novels", "home", "definition", "deletion"]) {
    document.getElementById(`${section}-panel`).hidden = section !== "deletion";
    document.getElementById(`${section}-tab`).setAttribute("aria-pressed", String(section === "deletion"));
  }
  document.getElementById("vote-workspace").hidden = true;
  loadDeletionNovels().catch(error => status(error.message, true));
});
document.getElementById("deletion-search").addEventListener("submit", event => {
  event.preventDefault();
  deletionState.query = document.getElementById("deletion-query").value.trim();
  deletionState.page = 1;
  loadDeletionNovels().catch(error => status(error.message, true));
});
