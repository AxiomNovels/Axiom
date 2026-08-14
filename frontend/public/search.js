function getSearchQuery() {
  return new URLSearchParams(window.location.search).get("q")?.trim() || "";
}

async function loadSearchResults() {
  const query = getSearchQuery();
  const input = document.getElementById("novel-search");
  const summary = document.querySelector("[data-results-summary]");
  const results = document.querySelector("[data-search-results]");

  if (input) input.value = query;

  if (!query) {
    summary.textContent = "Enter a title, author, genre, theme, or mood to begin.";
    results.innerHTML = "<p class=\"search-empty\">No search entered yet.</p>";
    return;
  }

  document.title = `${query} | Search | Axiom`;

  try {
    const response = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error("Search request failed");

    const novels = await response.json();
    const resultWord = novels.length === 1 ? "result" : "results";
    summary.textContent = `${novels.length} ${resultWord} for “${query}”, ordered by relevance.`;
    results.innerHTML = "";

    if (!novels.length) {
      results.innerHTML = "<p class=\"search-empty\">No matching novels found. Try a title, author, genre, or a broader theme.</p>";
      return;
    }

    novels.forEach((novel, index) => {
      results.appendChild(createNovelCard(novel, index));
    });
  } catch (error) {
    summary.textContent = "Search is temporarily unavailable.";
    results.innerHTML = "<p class=\"search-empty\">Couldn't load results. Make sure the backend is running on port 8000.</p>";
  }
}

loadSearchResults();
