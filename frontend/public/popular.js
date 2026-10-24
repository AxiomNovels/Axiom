(() => {
  const results = document.querySelector("[data-popular-results]");
  const summary = document.querySelector("[data-popular-summary]");
  const pagination = document.querySelector("[data-popular-pagination]");
  const params = new URLSearchParams(window.location.search);
  const requestedPage = Number(params.get("page") || 1);
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  // Keep random ties stable across page links, reloads, and browser Back.
  const seed = /^[a-zA-Z0-9-]{1,64}$/.test(params.get("seed") || "")
    ? params.get("seed") : crypto.randomUUID();

  function pageUrl(number) {
    return `/popular.html?${new URLSearchParams({ page: number, seed })}`;
  }

  history.replaceState(null, "", pageUrl(page));

  function novelCard(novel, index) {
    const link = document.createElement("a");
    link.href = `/novel.html?id=${encodeURIComponent(novel.id)}`;
    link.className = "series-result";
    const cover = document.createElement("div");
    cover.className = `result-cover ${COVER_CLASSES[index % COVER_CLASSES.length]}`;
    if (novel.cover_image_url) {
      const image = document.createElement("img");
      image.src = novel.cover_image_url;
      image.alt = `${novel.title} cover`;
      image.loading = "lazy";
      image.referrerPolicy = "no-referrer";
      image.addEventListener("error", () => {
        cover.textContent = novel.title || "Axiom";
      }, { once: true });
      cover.appendChild(image);
    } else {
      cover.textContent = novel.title || "Axiom";
    }
    const copy = document.createElement("div");
    copy.innerHTML = '<div class="result-title-row"><div><h2></h2><p class="result-author"></p></div><span class="result-status"></span></div><div class="result-rating"></div><div class="result-stats"></div><p class="result-synopsis"></p><div class="result-tags"></div>';
    copy.querySelector("h2").textContent = novel.title;
    copy.querySelector(".result-author").textContent = `by ${novel.author || "Unknown"}`;
    copy.querySelector(".result-status").textContent = novel.status || "Unknown";
    copy.querySelector(".result-synopsis").textContent = novel.synopsis || "No synopsis available.";
    copy.querySelector(".result-rating").textContent = novel.average_rating == null
      ? "Not yet rated"
      : `★ ${Number(novel.average_rating).toFixed(2)} / 5 · ${novel.review_count.toLocaleString()} ${novel.review_count === 1 ? "review" : "reviews"}`;
    const chapters = formatCompactNumber(novel.chapter_count);
    copy.querySelector(".result-stats").textContent = chapters === null ? ""
      : `${chapters} ${Number(novel.chapter_count) === 1 ? "chapter" : "chapters"}`;
    const tags = copy.querySelector(".result-tags");
    (novel.tags || []).slice(0, 6).forEach((tag) => {
      const chip = document.createElement("span");
      chip.textContent = tag;
      tags.appendChild(chip);
    });
    link.append(cover, copy);
    return link;
  }

  function renderPagination(current, totalPages) {
    pagination.replaceChildren();
    pagination.hidden = totalPages < 2;
    if (totalPages < 2) return;
    const addLink = (number, label) => {
      const link = document.createElement("a");
      link.href = pageUrl(number);
      link.textContent = label;
      link.setAttribute("aria-label", /^\d+$/.test(label) ? `Page ${number}` : label);
      pagination.appendChild(link);
    };
    if (current > 1) addLink(current - 1, "Previous");
    const visiblePages = new Set([1, totalPages, current - 1, current, current + 1]);
    let previous = 0;
    [...visiblePages].filter((number) => number >= 1 && number <= totalPages).sort((a, b) => a - b).forEach((number) => {
      if (previous && number - previous > 1) {
        const gap = document.createElement("span");
        gap.textContent = "…";
        pagination.appendChild(gap);
      }
      if (number === current) {
        const active = document.createElement("span");
        active.textContent = number;
        active.setAttribute("aria-current", "page");
        active.setAttribute("aria-label", `Page ${number}`);
        pagination.appendChild(active);
      } else {
        addLink(number, String(number));
      }
      previous = number;
    });
    if (current < totalPages) addLink(current + 1, "Next");
  }

  async function loadNovels() {
    results.setAttribute("aria-busy", "true");
    summary.textContent = "Loading novels…";
    results.innerHTML = '<p class="search-empty">Loading novels…</p>';
    pagination.hidden = true;
    try {
      const response = await fetch(`${API_BASE}/api/novels/popular?${new URLSearchParams({ page, seed })}`);
      if (!response.ok) throw new Error("Could not load popular novels");
      const data = await response.json();
      results.replaceChildren();
      if (!data.total) {
        summary.textContent = "No novels in the catalogue yet.";
        results.innerHTML = '<p class="search-empty">Check back soon to discover your next read.</p>';
        return;
      }
      history.replaceState(null, "", pageUrl(data.page));
      document.title = `Popular novels · Page ${data.page} | Axiom`;
      const first = (data.page - 1) * data.page_size + 1;
      summary.textContent = `${first}–${first + data.novels.length - 1} of ${data.total.toLocaleString()} novels · Page ${data.page} of ${data.total_pages}`;
      data.novels.forEach((novel, index) => results.appendChild(novelCard(novel, index)));
      renderPagination(data.page, data.total_pages);
    } catch {
      summary.textContent = "Popular novels are temporarily unavailable.";
      results.innerHTML = '<p class="search-empty">Couldn’t load novels. Please try again.</p>';
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "popular-retry";
      retry.textContent = "Try again";
      retry.addEventListener("click", loadNovels);
      results.appendChild(retry);
    } finally {
      results.setAttribute("aria-busy", "false");
    }
  }

  loadNovels();
})();
