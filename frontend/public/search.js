const PROFILE_LABELS = {
  impulsivity:"Impulsivity", arrogance_pride:"Ego", kinship_friendship:"Kinship & friendship",
  romantic_attachment:"Romantic attachment", sexual_desire:"Lust", selflessness:"Selflessness",
  freedom:"Freedom", survival:"Survival", existentialism:"Existentialism", moral_ambiguity:"Moral ambiguity",
  self_improvement:"Self-improvement", determinism:"Determinism", revenge:"Revenge", romance:"Romance",
  political_intrigue:"Political intrigue", psychological_warfare:"Psychological warfare",
  kingdom_building:"Kingdom building", action:"Action", slice_of_life:"Slice of life", mystery:"Mystery", worldbuilding:"Worldbuilding"
};

function showActiveFilters(params) {
  const container = document.querySelector("[data-filter-chips]");
  const sidebar = document.querySelector("[data-active-filters]");
  const chips = [];
  const query = params.get("q")?.trim();
  if (query) chips.push(`Keywords: ${query}`);
  (params.get("include_tags") || "").split(",").filter(Boolean).forEach((tag) => chips.push(`+ ${tag}`));
  (params.get("exclude_tags") || "").split(",").filter(Boolean).forEach((tag) => chips.push(`− ${tag}`));
  if (params.get("status")) chips.push(`Status: ${params.get("status")}`);
  if (params.get("min_rating")) chips.push(`Rating: ${params.get("min_rating")} stars & up`);
  if (params.get("include_tags")) chips.push(`Tag match: ${(params.get("tag_mode") || "and").toUpperCase()}`);
  Object.entries(PROFILE_LABELS).forEach(([key, label]) => {
    const min = params.get(`${key}_min`); const max = params.get(`${key}_max`);
    if (min && max) chips.push(`${label}: ${min}–${max}`);
    else if (min) chips.push(`${label}: ≥ ${min}`);
    else if (max) chips.push(`${label}: ≤ ${max}`);
  });
  if (!chips.length) { sidebar.hidden = true; return; }
  chips.forEach((text) => { const chip = document.createElement("span"); chip.textContent = text; container.appendChild(chip); });
}

function resultCard(novel, index) {
  const link = document.createElement("a"); link.href = `/novel.html?id=${novel.id}`; link.className = "series-result book-card-link";
  const cover = document.createElement("div"); cover.className = `result-cover ${COVER_CLASSES[index % COVER_CLASSES.length]}`;
  if (novel.cover_image_url) { const image = document.createElement("img"); image.referrerPolicy = "no-referrer"; image.src = novel.cover_image_url; image.alt = `${novel.title} cover`; image.addEventListener("error", () => { image.remove(); cover.textContent = novel.title || "Axiom"; }, { once: true }); cover.appendChild(image); }
  else cover.textContent = novel.title;
  const copy = document.createElement("div");
  const genres = novel.genres || [];
  const tags = genres.slice(0, 6).map((tag) => `<span>${tag}</span>`).join("");
  const remainingTags = genres.length > 6 ? `<span class="more-tags">+${genres.length - 6}</span>` : "";
  copy.innerHTML = `<div class="result-title-row"><div><h3></h3><p class="result-author"></p></div><span class="result-status"></span></div><div class="result-rating"></div><div class="result-stats"></div><p class="result-synopsis"></p><div class="result-tags">${tags}${remainingTags}</div>`;
  copy.querySelector("h3").textContent = novel.title; copy.querySelector(".result-author").textContent = `by ${novel.author || "Unknown"}`;
  copy.querySelector(".result-status").textContent = novel.status || "Unknown"; copy.querySelector(".result-synopsis").textContent = novel.synopsis || "No synopsis available.";
  const rating = copy.querySelector(".result-rating");
  rating.textContent = novel.average_rating == null ? "Not yet rated" : `★ ${Number(novel.average_rating).toFixed(1)} · ${novel.review_count} ${novel.review_count === 1 ? "review" : "reviews"}`;
  // Chapter/view counts are optional per novel -- only the stats that
  // actually exist are shown, compactly (e.g. "128.4K views").
  const statParts = [];
  const viewCount = Number(novel.view_count);
  if (Number.isFinite(viewCount) && viewCount >= 0) statParts.push(`${formatCompactNumber(viewCount)} views`);
  const chapterCount = Number(novel.chapter_count);
  if (Number.isFinite(chapterCount) && chapterCount >= 0) statParts.push(`${formatCompactNumber(chapterCount)} ${chapterCount === 1 ? "chapter" : "chapters"}`);
  const statsEl = copy.querySelector(".result-stats");
  statsEl.textContent = statParts.join(" · ");
  if (!statParts.length) statsEl.remove();
  link.append(cover, copy); return link;
}

async function loadSearchResults() {
  const params = new URLSearchParams(window.location.search); const query = params.get("q")?.trim() || "";
  const input = document.getElementById("novel-search"); const summary = document.querySelector("[data-results-summary]"); const results = document.querySelector("[data-search-results]");
  if (input) input.value = query; showActiveFilters(params);
  const hasFilters = [...params.values()].some((value) => value.trim());
  if (query) document.title = `${query} | Search | Axiom`;
  try {
    const response = await fetch(`${API_BASE}/api/search?${params.toString()}`); if (!response.ok) throw new Error("Search request failed");
    const novels = await response.json(); summary.textContent = hasFilters ? `${novels.length} matching series, ordered by relevance.` : `${novels.length} series in the Axiom catalogue.`; results.innerHTML = "";
    if (!novels.length) { results.innerHTML = '<p class="search-empty">No series match every filter. Try removing one of your criteria.</p>'; return; }
    novels.forEach((novel, index) => results.appendChild(resultCard(novel, index)));
  } catch { summary.textContent = "Search is temporarily unavailable."; results.innerHTML = "<p class=\"search-empty\">Couldn't load results. Make sure the backend is running on port 8000.</p>"; }
}
loadSearchResults();
