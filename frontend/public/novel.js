// Snake_case key -> display label, matching the trait definitions discussed
// for the info page. Kept here too so this page can render nice labels
// without depending on that endpoint existing yet.
const TRAIT_LABELS = {
  // Protagonist Profile. Slash labels read low -> high (0 -> 100).
  intellectual_drive: "Intellectual Drive",
  arrogance_pride: "Arrogance & Pride",
  kinship_friendship: "Kinship and Friendship",
  romantic_attachment: "Romantic Attachment",
  selflessness_selfishness: "Selfishness / Selflessness",
  pragmatism_morality: "Pragmatism / Morality",
  individualist_collectivist: "Individualist / Collectivist",
  ambition: "Ambition",
  cautious_risk_taker: "Cautious / Risk-taker",
  leadership: "Leadership",
};

// Display order follows TRAIT_LABELS.
const PROTAGONIST_MEASURES = Object.keys(TRAIT_LABELS).map((key) => ({ key }));

function getNovelIdFromUrl() {
  return new URLSearchParams(window.location.search).get("id");
}

function renderTraitRow(key, score) {
  const row = document.createElement("div");
  row.className = "trait-row";

  const label = document.createElement("div");
  label.className = "trait-label";
  label.textContent = TRAIT_LABELS[key] || key;

  const track = document.createElement("div");
  track.className = "trait-bar-track";
  const fill = document.createElement("div");
  fill.className = "trait-bar-fill";
  // A trait with no saved score yet (e.g. a novel not re-profiled since the
  // trait set changed) shows an empty bar and a dash instead of a misleading 0.
  const hasScore = Number.isFinite(score);
  fill.style.width = hasScore ? `${Math.max(0, Math.min(100, score))}%` : "0%";
  track.appendChild(fill);

  const scoreEl = document.createElement("div");
  scoreEl.className = "trait-score";
  scoreEl.textContent = hasScore ? score : "\u2014";

  row.appendChild(label);
  row.appendChild(track);
  row.appendChild(scoreEl);
  return row;
}

function normalizedScore(value) {
  const score = Number(value);
  return Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
}

function renderProtagonistProfile(profile) {
  const container = document.getElementById("protagonist-profile");
  if (!container) return;
  container.innerHTML = "";

  if (!profile) {
    container.innerHTML = "<p>No profile data yet for this novel.</p>";
    return;
  }

  PROTAGONIST_MEASURES.forEach((measure) => {
    const raw = profile[measure.key];
    const score = raw === null || raw === undefined ? null : normalizedScore(raw);
    const element = renderTraitRow(measure.key, score);

    if (!measure.poles) {
      container.appendChild(element);
      return;
    }

    const scale = document.createElement("div");
    scale.className = "trait-poles";
    measure.poles.forEach((pole) => {
      const label = document.createElement("span");
      label.textContent = pole;
      scale.appendChild(label);
    });
    const wrapper = document.createElement("div");
    wrapper.className = "trait-with-poles";
    wrapper.appendChild(element);
    wrapper.appendChild(scale);
    container.appendChild(wrapper);
  });
}


function setupSynopsis(synopsis) {
  const wrapper = document.getElementById("novel-synopsis-wrapper");
  const synopsisEl = document.getElementById("novel-synopsis");
  const readMoreButton = document.getElementById("novel-read-more");

  if (!wrapper || !synopsisEl || !readMoreButton) return;

  synopsisEl.textContent = synopsis || "No synopsis yet.";

  // If the synopsis fits within 10 lines, there is nothing to expand.
  // Wait until the browser has rendered the text so we can measure it.
  requestAnimationFrame(() => {
    const lineHeight = parseFloat(getComputedStyle(synopsisEl).lineHeight);
    const maxHeight = lineHeight * 10;

    const needsExpansion = synopsisEl.scrollHeight > maxHeight + 1;

    if (!needsExpansion) {
      readMoreButton.remove();
      wrapper.querySelector(".novel-synopsis-fade")?.remove();
      return;
    }

    synopsisEl.classList.add("is-collapsed");

    readMoreButton.addEventListener("click", () => {
      const expanded = wrapper.classList.toggle("is-expanded");

      synopsisEl.classList.toggle("is-collapsed", !expanded);

      readMoreButton.setAttribute("aria-expanded", String(expanded));
      readMoreButton.textContent = expanded ? "Read Less" : "Read More";
    });
  });
}

// Chapter count is optional (a source page may not expose it, or scraping
// it may have failed) -- it is only shown when a non-negative number is
// actually present, so the row simply shrinks rather than showing a
// misleading "0 chapters".
function renderNovelStats(novel) {
  const container = document.getElementById("novel-stats");
  if (!container) return;
  container.innerHTML = "";

  const stats = [
    { value: novel.chapter_count, singular: "chapter", plural: "chapters" },
  ];

  stats.forEach(({ value, singular, plural }) => {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) return;

    const chip = document.createElement("span");
    chip.className = "novel-stat-chip";
    chip.textContent = `${formatCompactNumber(number)} ${number === 1 ? singular : plural}`;
    chip.title = `${number.toLocaleString()} ${number === 1 ? singular : plural}`;
    container.appendChild(chip);
  });
}

// Shared by the genres row and the tags row: renders up to 5 chips plus
// a "+N more" toggle for the rest. `chipClassName` controls the pill
// style (genre-tag vs story-tag-chip); the "is-extra-tag" / "is-expanded"
// pattern is shared so both rows expand independently of one another.
function renderChipList(container, values, chipClassName) {
  if (!container) return;
  container.innerHTML = "";
  const items = values || [];

  items.forEach((value, index) => {
    const chip = document.createElement("span");
    chip.className = chipClassName;
    if (index >= 5) chip.classList.add("is-extra-tag");
    chip.textContent = value;
    container.appendChild(chip);
  });

  if (items.length > 5) {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "genre-toggle";
    toggle.textContent = `+${items.length - 5} more`;
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", () => {
      const expanded = container.classList.toggle("is-expanded");
      toggle.textContent = expanded ? "Show less" : `+${items.length - 5} more`;
      toggle.setAttribute("aria-expanded", String(expanded));
    });
    container.appendChild(toggle);
  }
}

function renderNovel(novel) {
  document.title = `${novel.title} | Axiom`;

  const titleEl = document.getElementById("novel-title");
  const authorEl = document.getElementById("novel-author");
  const statusEl = document.getElementById("novel-status");
  // const synopsisEl = document.getElementById("novel-synopsis");
  const coverEl = document.getElementById("novel-cover");
  const genresEl = document.getElementById("novel-genres");
  const tagsEl = document.getElementById("novel-tags");
  const linksEl = document.getElementById("novel-reading-links");

  if (titleEl) {
    const title = novel.title || "Untitled";
    titleEl.textContent = title;
    titleEl.classList.toggle("is-long-title", title.length > 24 && title.length <= 42);
    titleEl.classList.toggle("is-very-long-title", title.length > 42 && title.length <= 64);
    titleEl.classList.toggle("is-ultra-long-title", title.length > 64);
  }
  if (authorEl) authorEl.textContent = novel.author ? `by ${novel.author}` : "";
  if (statusEl) statusEl.textContent = novel.status;
  renderNovelStats(novel);
  setupSynopsis(novel.synopsis);

  if (coverEl) {
    if (novel.cover_image_url) {
      const coverImage = document.createElement("img");
      coverImage.className = "novel-cover-image";
      coverImage.referrerPolicy = "no-referrer";
      coverImage.src = novel.cover_image_url;
      coverImage.alt = `${novel.title} cover`;
      coverImage.addEventListener("error", () => {
        coverImage.remove();
        coverEl.textContent = novel.title;
      }, { once: true });
      coverEl.replaceChildren(coverImage);
    } else {
      coverEl.textContent = novel.title;
    }
  }

  renderChipList(genresEl, novel.genres, "genre-tag");
  renderChipList(tagsEl, novel.tags, "story-tag-chip");

  if (linksEl) {
    linksEl.innerHTML = "";
    (novel.reading_links || []).forEach((link) => {
      const a = document.createElement("a");
      a.href = link.url;
      a.textContent = `Read on ${link.platform}`;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.className = "reading-link";
      linksEl.appendChild(a);
    });
  }

  // The Supabase embed can come back as a single object (expected, since
  // each profile table has a UNIQUE(novel_id) constraint) or as a
  // single-item array on some PostgREST versions -- handle both.
  const unwrap = (value) => (Array.isArray(value) ? value[0] : value);

  renderProtagonistProfile(unwrap(novel.protagonist_profiles));
}

async function fetchReadingLists() {
  const response = await authFetch(`${API_BASE}/api/reading-lists`);
  if (!response.ok) throw new Error("Failed to load reading lists");
  return response.json();
}

async function fetchNovelMembership(novelId) {
  const response = await authFetch(`${API_BASE}/api/reading-lists/novel/${novelId}`);
  if (!response.ok) throw new Error("Failed to load reading list status");
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function buildReadingListLoginPrompt() {
  const wrapper = document.createElement("p");
  wrapper.className = "reading-list-status";
  wrapper.append("Log in to ");
  const link = document.createElement("a");
  link.href = "/login.html";
  link.textContent = "save this novel";
  wrapper.appendChild(link);
  wrapper.append(" to a reading list.");
  return wrapper;
}

// A small "Chapter N" control shown next to the reading-list picker when
// the novel is on one of the user's lists. Only rendered while membership
// exists -- if the novel is removed from every list, this disappears even
// though the chapter number itself is retained server-side.
function buildChapterTracker(novelId, currentChapter) {
  const wrapper = document.createElement("div");
  wrapper.className = "novel-chapter-tracker";

  const label = document.createElement("label");
  label.textContent = "Chapter";
  label.setAttribute("for", "novel-chapter-input");

  const input = document.createElement("input");
  input.type = "number";
  input.min = "1";
  input.step = "1";
  input.inputMode = "numeric";
  input.id = "novel-chapter-input";
  input.className = "novel-chapter-input";
  input.value = currentChapter || 1;
  input.setAttribute("aria-label", "Your current chapter for this novel");

  const status = document.createElement("span");
  status.className = "novel-chapter-status";
  status.setAttribute("aria-live", "polite");

  let savedChapter = currentChapter || 1;

  const save = async () => {
    const parsed = Math.max(1, Math.floor(Number(input.value)) || 1);
    input.value = parsed;
    if (parsed === savedChapter) return;

    status.textContent = "Saving…";
    try {
      const response = await authFetch(`${API_BASE}/api/reading-progress/${novelId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_chapter: parsed }),
      });
      if (response.status === 401) {
        window.location.href = "/login.html";
        return;
      }
      if (!response.ok) throw new Error("Update failed");
      savedChapter = parsed;
      status.textContent = "Saved";
      setTimeout(() => { status.textContent = ""; }, 1500);
    } catch (error) {
      status.textContent = "";
      alert("Couldn't save your chapter progress. Please try again.");
      input.value = savedChapter;
    }
  };

  input.addEventListener("change", save);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      input.blur();
    }
  });

  wrapper.append(label, input, status);
  return wrapper;
}

function buildReadingListControls(novelId, membership, lists) {
  const wrapper = document.createElement("div");
  wrapper.className = "reading-list-controls";

  const picker = document.createElement("details");
  picker.className = "reading-list-picker";
  const trigger = document.createElement("summary");
  trigger.className = "reading-list-trigger";
  const triggerIcon = document.createElement("span");
  triggerIcon.setAttribute("aria-hidden", "true");
  triggerIcon.textContent = membership ? "✓" : "＋";
  trigger.append(triggerIcon, membership ? ` In ${membership.name}` : " Add to reading list");
  picker.appendChild(trigger);

  const menu = document.createElement("div");
  menu.className = "reading-list-menu";
  const heading = document.createElement("strong");
  heading.textContent = membership ? "Move to another list" : "Choose a list";
  menu.appendChild(heading);

  const availableLists = lists.filter((list) => !membership || list.id !== membership.id);
  availableLists.forEach((list) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "reading-list-option";
    option.textContent = list.name;
    option.addEventListener("click", async () => {
      option.disabled = true;
      option.textContent = "Saving…";
      try {
        const response = await authFetch(`${API_BASE}/api/reading-lists/${list.id}/novels`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ novel_id: Number(novelId) }),
        });
        if (!response.ok) throw new Error("Update failed");
        await refreshReadingListControls(novelId);
      } catch { alert("Couldn't update this novel's reading list. Please try again."); option.disabled = false; option.textContent = list.name; }
    });
    menu.appendChild(option);
  });

  if (!availableLists.length) {
    const empty = document.createElement("p");
    empty.className = "reading-list-empty";
    empty.textContent = lists.length ? "This is your only list." : "You don't have a reading list yet.";
    menu.appendChild(empty);
  }

  const manageLink = document.createElement("a");
  manageLink.className = "reading-list-manage";
  manageLink.href = "/lists.html";
  manageLink.textContent = lists.length ? "Manage lists" : "Create a reading list";
  menu.appendChild(manageLink);

  if (membership) {
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "reading-list-remove-button";
    removeButton.textContent = "Remove from list";
    removeButton.addEventListener("click", async () => {
      removeButton.disabled = true; removeButton.textContent = "Removing…";
      try {
        const response = await authFetch(`${API_BASE}/api/reading-lists/${membership.id}/novels/${novelId}`, { method: "DELETE" });
        if (!response.ok) throw new Error("Remove failed");
        await refreshReadingListControls(novelId);
      } catch { alert("Couldn't remove this novel from the list. Please try again."); removeButton.disabled = false; removeButton.textContent = "Remove from list"; }
    });
    menu.appendChild(removeButton);
  }

  picker.appendChild(menu);
  wrapper.appendChild(picker);

  if (membership) {
    wrapper.appendChild(buildChapterTracker(novelId, membership.current_chapter));
  }

  return wrapper;
}

function renderStaticStars(container, rating) {
  container.replaceChildren();
  const value = Number(rating);
  for (let star = 1; star <= 5; star += 1) {
    const icon = document.createElement("span");
    icon.textContent = "★";
    icon.dataset.fill = value >= star ? "full" : value === star - 0.5 ? "half" : "empty";
    container.appendChild(icon);
  }
}

function createThumbsUpIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "review-like-icon");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute(
    "d",
    "M2 22h3.5a1 1 0 0 0 1-1V11a1 1 0 0 0-1-1H2Zm7.5-.4c.4.26.97.4 1.6.4h6.9a2 2 0 0 0 1.94-1.52l1.72-7A2 2 0 0 0 19.72 11H14.9l.62-3.6c.2-1.16-.35-2.3-1.4-2.85a1.9 1.9 0 0 0-2.55.72L8.5 10.6a2 2 0 0 0-.3 1.05V20a1.6 1.6 0 0 0 1.3 1.6Z"
  );
  svg.appendChild(path);
  return svg;
}

// Toggleable likes are shared by top-level reviews and replies. Authors see
// the current count but cannot like their own contribution.
function createLikeControl(item, kind = "review", reviewId = item.id) {
  const wrapper = document.createElement("div");
  wrapper.className = "review-like";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-like-button";
  button.appendChild(createThumbsUpIcon());

  const count = document.createElement("span");
  count.className = "review-like-count";
  count.textContent = String(item.like_count || 0);

  const isOwnContribution = item.user_id === currentUserId();
  const contributionName = kind === "reply" ? "reply" : "review";

  if (isOwnContribution) {
    button.disabled = true;
    button.classList.add("is-own");
    button.title = `You can't like your own ${contributionName}`;
    button.setAttribute("aria-label", `You can't like your own ${contributionName}`);
  } else {
    button.classList.toggle("is-liked", Boolean(item.viewer_has_liked));
    button.setAttribute("aria-pressed", String(Boolean(item.viewer_has_liked)));
    button.setAttribute("aria-label", item.viewer_has_liked ? `Unlike this ${contributionName}` : `Like this ${contributionName}`);

    button.addEventListener("click", async () => {
      if (!getAccessToken()) {
        window.location.href = "/login.html";
        return;
      }
      const currentlyLiked = button.classList.contains("is-liked");
      const likeUrl = kind === "reply"
        ? `${API_BASE}/api/reviews/${reviewId}/replies/${item.id}/like`
        : `${API_BASE}/api/reviews/${item.id}/like`;
      button.disabled = true;
      try {
        const response = await authFetch(likeUrl, {
          method: currentlyLiked ? "DELETE" : "POST",
        });
        if (response.status === 401) {
          window.location.href = "/login.html";
          return;
        }
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't update your like.");
        }
        item.like_count = result.like_count;
        item.viewer_has_liked = result.liked;
        button.classList.toggle("is-liked", result.liked);
        button.setAttribute("aria-pressed", String(result.liked));
        button.setAttribute("aria-label", result.liked ? `Unlike this ${contributionName}` : `Like this ${contributionName}`);
        count.textContent = String(result.like_count ?? 0);
      } catch (error) {
        alert(error.message || "Couldn't update your like. Please try again.");
      } finally {
        button.disabled = false;
      }
    });
  }

  wrapper.append(button, count);
  return wrapper;
}

function setupReviewRatingPicker(stars, valueField, output, clearButton, initialRating) {
  let selectedRating = Number(initialRating) || 0;
  let previewRating = selectedRating;

  function label(rating) {
    return rating ? `${rating} out of 5` : "Select a rating";
  }

  function render(rating, isPreview = false) {
    output.value = label(rating);
    output.classList.toggle("is-preview", isPreview && rating !== selectedRating);
    stars.querySelectorAll("[data-star]").forEach((button) => {
      const star = Number(button.dataset.star);
      button.dataset.fill = rating >= star ? "full" : rating === star - 0.5 ? "half" : "empty";
    });
  }

  function commit(value) {
    selectedRating = Math.max(0, Math.min(5, Math.round(Number(value) * 2) / 2));
    previewRating = selectedRating;
    valueField.value = selectedRating || "";
    clearButton.hidden = !selectedRating;
    stars.setAttribute("aria-valuenow", String(selectedRating));
    stars.setAttribute("aria-valuetext", label(selectedRating));
    render(selectedRating);
  }

  function valueAt(clientX) {
    for (const button of stars.querySelectorAll("[data-star]")) {
      const box = button.getBoundingClientRect();
      if (clientX <= box.right) {
        return Number(button.dataset.star) - (clientX < box.left + box.width / 2 ? 0.5 : 0);
      }
    }
    return 5;
  }

  function preview(event) {
    if (selectedRating) return;
    previewRating = valueAt(event.clientX);
    render(previewRating, true);
  }

  stars.addEventListener("pointermove", preview);
  stars.addEventListener("click", (event) => {
    commit(valueAt(event.clientX));
  });
  stars.addEventListener("pointerleave", () => {
    render(selectedRating);
  });
  stars.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") commit(0.5);
    else if (event.key === "End") commit(5);
    else commit(selectedRating + (["ArrowRight", "ArrowUp"].includes(event.key) ? 0.5 : -0.5));
  });
  clearButton.addEventListener("click", () => {
    commit(0);
    stars.focus();
  });
  commit(selectedRating);
}

function renderRatingSummary(payload) {
  const summary = document.getElementById("novel-rating-summary");
  const overview = document.querySelector("[data-reviews-overview]");
  const countLabel = `${payload.review_count} ${payload.review_count === 1 ? "review" : "reviews"}`;
  if (!payload.review_count) {
    if (summary) summary.textContent = "Not yet rated";
    if (overview) overview.textContent = "Be the first to rate this novel";
    return;
  }
  const average = Number(payload.average_rating).toFixed(1);
  if (summary) summary.innerHTML = `<span aria-hidden="true">★</span> <strong>${average}</strong><span> out of 5 · ${countLabel}</span>`;
  if (overview) overview.innerHTML = `<strong>${average}</strong><span aria-hidden="true">★</span><small>${countLabel}</small>`;
}

function currentUserId() {
  return getStoredUser()?.id || null;
}

function renderReviewComposer(novelId, reviews) {
  const container = document.querySelector("[data-review-composer]");
  if (!container) return;
  container.innerHTML = "";
  if (!getAccessToken()) {
    const prompt = document.createElement("p");
    prompt.className = "review-login-prompt";
    prompt.append("Have you read this novel? ");
    const link = document.createElement("a");
    link.href = "/login.html";
    link.textContent = "Log in to leave a review";
    prompt.appendChild(link);
    prompt.append(".");
    container.appendChild(prompt);
    return;
  }

  const mine = reviews.find((review) => review.user_id === currentUserId());
  const form = document.createElement("form");
  form.className = "review-form";
  form.innerHTML = `
    <div class="review-form-heading"><div><h3>${mine ? "Update your review" : "Share your review"}</h3><p>Your rating is required. Your comment is optional.</p></div></div>
    <fieldset class="star-picker"><legend>Your rating</legend><div class="review-rating-control"><div class="star-picker-options" role="slider" tabindex="0" aria-label="Your rating" aria-valuemin="0.5" aria-valuemax="5" aria-valuenow="0"></div><div class="review-rating-copy"><output class="review-rating-value" data-review-rating-output>Select a rating</output><button type="button" class="review-rating-clear" data-review-rating-clear hidden>Clear</button></div></div><input type="hidden" name="rating" data-review-rating></fieldset>
    <label class="review-comment-label">Comment <span>Optional</span><span class="review-comment-field"><textarea maxlength="2000" rows="4" placeholder="What stood out to you?" data-review-comment aria-describedby="review-comment-counter"></textarea><span class="review-comment-counter" id="review-comment-counter" data-review-comment-counter>0/2000</span></span></label>
    <div class="review-form-footer"><span data-review-message role="status"></span><button type="submit">${mine ? "Update review" : "Post review"}</button></div>`;
  const options = form.querySelector(".star-picker-options");
  for (let rating = 1; rating <= 5; rating += 1) {
    const button = document.createElement("button");
    button.type = "button"; button.tabIndex = -1; button.dataset.star = rating;
    button.setAttribute("aria-label", `${rating} ${rating === 1 ? "star" : "stars"}`);
    const icon = document.createElement("span"); icon.textContent = "★"; icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon); options.appendChild(button);
  }
  setupReviewRatingPicker(options, form.querySelector("[data-review-rating]"), form.querySelector("[data-review-rating-output]"), form.querySelector("[data-review-rating-clear]"), mine?.rating);
  const commentField = form.querySelector("[data-review-comment]");
  const commentCounter = form.querySelector("[data-review-comment-counter]");
  commentField.value = mine?.comment || "";
  const updateCommentCounter = () => {
    commentCounter.textContent = `${commentField.value.length}/2000`;
  };
  commentField.addEventListener("input", updateCommentCounter);
  updateCommentCounter();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    const message = form.querySelector("[data-review-message]");
    const rating = Number(form.querySelector("[data-review-rating]").value);
    if (!rating) { message.textContent = "Choose a star rating first."; return; }
    button.disabled = true; button.textContent = "Saving…"; message.textContent = "";
    try {
      const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment: commentField.value }),
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) { window.location.href = "/login.html"; return; }
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't save your review.");
      await loadReviews(novelId);
    } catch (error) {
      message.textContent = error.message || "Couldn't save your review.";
      button.disabled = false; button.textContent = mine ? "Update review" : "Post review";
    }
  });
  container.appendChild(form);
}

function createReplyAction(novelId, reviewId, parentReplyId, targetName) {
  const wrapper = document.createElement("div");
  wrapper.className = "review-reply-action-row";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-reply-button";
  button.textContent = "Reply";
  button.addEventListener("click", () => {
    if (!getAccessToken()) {
      window.location.href = "/login.html";
      return;
    }
    if (wrapper.querySelector("form")) return;

    const form = document.createElement("form");
    form.className = "review-reply-form";
    const label = document.createElement("label");
    label.textContent = `Reply to ${targetName || "this reader"}`;
    const textarea = document.createElement("textarea");
    textarea.maxLength = 2000;
    textarea.rows = 3;
    textarea.placeholder = "Add to the conversation…";
    textarea.required = true;
    const footer = document.createElement("div");
    footer.className = "review-reply-form-footer";
    const message = document.createElement("span");
    message.setAttribute("role", "status");
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ghost-link";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => form.remove());
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.textContent = "Post reply";
    footer.append(message, cancel, submit);
    label.appendChild(textarea);
    form.append(label, footer);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      submit.textContent = "Posting…";
      message.textContent = "";
      try {
        const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews/${reviewId}/replies`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comment: textarea.value, parent_reply_id: parentReplyId }),
        });
        const result = await response.json().catch(() => ({}));
        if (response.status === 401) { window.location.href = "/login.html"; return; }
        if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't post your reply.");
        await loadReviews(novelId);
      } catch (error) {
        message.textContent = error.message || "Couldn't post your reply.";
        submit.disabled = false;
        submit.textContent = "Post reply";
      }
    });
    wrapper.append(form);
    textarea.focus();
  });
  wrapper.appendChild(button);
  return wrapper;
}

function createPlaceholderAction(label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-thread-placeholder";
  button.textContent = label;
  button.disabled = true;
  button.title = "Coming soon";
  return button;
}

function createMoreActions({ isOwner, onEdit, onDelete }) {
  const menu = document.createElement("details");
  menu.className = "review-more-actions";
  const trigger = document.createElement("summary");
  trigger.setAttribute("aria-label", "More comment actions");
  trigger.textContent = "•••";
  const panel = document.createElement("div");
  panel.className = "review-more-menu";

  if (isOwner) {
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => { menu.open = false; onEdit?.(); });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "is-danger";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => { menu.open = false; onDelete?.(); });
    panel.append(edit, remove);
    panel.appendChild(document.createElement("hr"));
  }

  panel.append(
    createPlaceholderAction("Follow comment"),
    createPlaceholderAction("Report")
  );
  menu.append(trigger, panel);
  return menu;
}

function createThreadActionRow({ item, kind, novelId, reviewId, parentReplyId, targetName, onEdit, onDelete }) {
  const row = document.createElement("div");
  row.className = "review-thread-actions";
  row.appendChild(createLikeControl(item, kind, reviewId));
  row.appendChild(createPlaceholderAction("↓"));
  row.appendChild(createReplyAction(novelId, reviewId, parentReplyId, targetName));
  row.appendChild(createMoreActions({
    isOwner: item.user_id === currentUserId(),
    onEdit,
    onDelete,
  }));
  return row;
}

function openReplyEditor(novelId, reviewId, reply, article) {
  if (article.querySelector(".review-reply-edit-form")) return;
  const currentComment = article.querySelector(".review-reply-comment");
  if (!currentComment) return;

  const form = document.createElement("form");
  form.className = "review-reply-form review-reply-edit-form";
  const label = document.createElement("label");
  label.textContent = "Edit your reply";
  const textarea = document.createElement("textarea");
  textarea.maxLength = 2000;
  textarea.rows = 3;
  textarea.required = true;
  textarea.value = reply.comment;
  const footer = document.createElement("div");
  footer.className = "review-reply-form-footer";
  const message = document.createElement("span");
  message.setAttribute("role", "status");
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost-link";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => form.remove());
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Save changes";
  footer.append(message, cancel, submit);
  label.appendChild(textarea);
  form.append(label, footer);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    submit.textContent = "Saving…";
    message.textContent = "";
    try {
      const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews/${reviewId}/replies/${reply.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: textarea.value }),
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) { window.location.href = "/login.html"; return; }
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't update your reply.");
      await loadReviews(novelId);
    } catch (error) {
      message.textContent = error.message || "Couldn't update your reply.";
      submit.disabled = false;
      submit.textContent = "Save changes";
    }
  });
  currentComment.after(form);
  textarea.focus();
}

async function deleteReply(novelId, reviewId, reply) {
  const hasChildren = (reply.replies || []).length > 0;
  const prompt = hasChildren
    ? "Delete this reply and its nested replies? This can't be undone."
    : "Delete your reply? This can't be undone.";
  if (!window.confirm(prompt)) return;
  try {
    const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews/${reviewId}/replies/${reply.id}`, { method: "DELETE" });
    if (response.status === 401) { window.location.href = "/login.html"; return; }
    if (!response.ok) throw new Error("Delete failed");
    await loadReviews(novelId);
  } catch {
    window.alert("Couldn't delete your reply. Please try again.");
  }
}

function createReviewReply(novelId, reviewId, reply) {
  const profileValue = reply.profiles || {};
  const profile = Array.isArray(profileValue) ? (profileValue[0] || {}) : profileValue;
  const article = document.createElement("article");
  article.className = "review-reply";
  article.id = `reply-${reply.id}`;
  article.tabIndex = -1;
  const header = document.createElement("div");
  header.className = "review-reply-header";
  const avatar = document.createElement("div");
  avatar.className = "review-reply-avatar";
  if (profile.avatar_url) {
    const image = document.createElement("img");
    image.src = profile.avatar_url;
    image.alt = "";
    avatar.appendChild(image);
  } else {
    avatar.textContent = (profile.username || "?").charAt(0).toUpperCase();
  }
  const identity = document.createElement("div");
  const name = document.createElement("a");
  name.href = `/user.html?id=${encodeURIComponent(reply.user_id)}`;
  name.textContent = profile.username || "Axiom reader";
  const date = document.createElement("time");
  date.dateTime = reply.created_at;
  date.textContent = new Date(reply.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  identity.append(name, date);
  header.append(avatar, identity);
  const comment = document.createElement("p");
  comment.className = "review-reply-comment";
  comment.textContent = reply.comment;
  const children = document.createElement("div");
  children.className = "review-replies";
  (reply.replies || []).forEach((child) => children.appendChild(createReviewReply(novelId, reviewId, child)));
  const actions = createThreadActionRow({
    item: reply,
    kind: "reply",
    novelId,
    reviewId,
    parentReplyId: reply.id,
    targetName: profile.username,
    onEdit: () => openReplyEditor(novelId, reviewId, reply, article),
    onDelete: () => deleteReply(novelId, reviewId, reply),
  });
  article.append(header, comment, actions, children);
  return article;
}

function renderReviews(novelId, payload) {
  renderRatingSummary(payload);
  renderReviewComposer(novelId, payload.reviews);
  const list = document.querySelector("[data-reviews-list]");
  list.innerHTML = "";
  const reviewsWithComments = payload.reviews.filter((review) => review.comment);
  if (!reviewsWithComments.length) {
    list.innerHTML = `<p class="reviews-empty">${payload.review_count ? "No written comments yet." : "No reviews yet. Start the conversation."}</p>`;
    return;
  }
  reviewsWithComments.forEach((review) => {
    const profileValue = review.profiles || {};
    const profile = Array.isArray(profileValue) ? (profileValue[0] || {}) : profileValue;
    const article = document.createElement("article"); article.className = "review-card";
    article.id = `review-${review.id}`;
    article.tabIndex = -1;
    const header = document.createElement("div"); header.className = "review-card-header";
    const profileLink = document.createElement("a"); profileLink.className = "review-profile-link"; profileLink.href = `/user.html?id=${encodeURIComponent(review.user_id)}`; profileLink.setAttribute("aria-label", `View ${profile.username || "this reader"}'s profile`);
    const avatar = document.createElement("div"); avatar.className = "review-avatar";
    if (profile.avatar_url) { const image = document.createElement("img"); image.src = profile.avatar_url; image.alt = ""; avatar.appendChild(image); }
    else avatar.textContent = (profile.username || "?").charAt(0).toUpperCase();
    profileLink.appendChild(avatar);
    const identity = document.createElement("div");
    const nameLink = document.createElement("a"); nameLink.className = "review-author-link"; nameLink.href = `/user.html?id=${encodeURIComponent(review.user_id)}`;
    const name = document.createElement("strong"); name.textContent = profile.username || "Axiom reader"; nameLink.appendChild(name);
    const date = document.createElement("time"); date.dateTime = review.updated_at; date.textContent = new Date(review.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    identity.append(nameLink, date);
    const reviewMeta = document.createElement("div"); reviewMeta.className = "review-card-meta";
    const stars = document.createElement("span"); stars.className = "review-card-stars"; renderStaticStars(stars, review.rating); stars.setAttribute("aria-label", `${review.rating} out of 5 stars`);
    const topRow = document.createElement("div");
    topRow.className = "review-card-meta-top";
    topRow.append(stars);
    reviewMeta.appendChild(topRow);
    let editReview = null;
    let deleteReview = null;
    if (review.user_id === currentUserId()) {
      editReview = () => {
        const composer = document.querySelector("[data-review-composer]");
        composer?.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => composer?.querySelector("[data-review-comment]")?.focus(), 350);
      };
      deleteReview = async () => {
        if (!window.confirm("Delete your review? This can't be undone.")) return;
        try {
          const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews`, { method: "DELETE" });
          if (response.status === 401) { window.location.href = "/login.html"; return; }
          if (!response.ok) throw new Error("Delete failed");
          await loadReviews(novelId);
        } catch {
          window.alert("Couldn't delete your review. Please try again.");
        }
      };
    }
    header.append(profileLink, identity, reviewMeta);
    const comment = document.createElement("p"); comment.textContent = review.comment;
    const replies = document.createElement("div");
    replies.className = "review-replies";
    (review.replies || []).forEach((reply) => replies.appendChild(createReviewReply(novelId, review.id, reply)));
    const actions = createThreadActionRow({
      item: review,
      kind: "review",
      novelId,
      reviewId: review.id,
      parentReplyId: null,
      targetName: profile.username,
      onEdit: editReview,
      onDelete: deleteReview,
    });
    article.append(header, comment, actions, replies); list.appendChild(article);
  });
  focusReviewDiscussionTarget();
}

function focusReviewDiscussionTarget() {
  const targetId = decodeURIComponent(window.location.hash.slice(1));
  if (!/^(review|reply)-\d+$/.test(targetId)) return;
  const target = document.getElementById(targetId);
  if (!target) return;

  document.querySelectorAll(".is-activity-target").forEach((item) => {
    item.classList.remove("is-activity-target");
  });
  target.classList.add("is-activity-target");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.focus({ preventScroll: true });
}

window.addEventListener("hashchange", focusReviewDiscussionTarget);

async function loadReviews(novelId) {
  try {
    const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews`);
    if (!response.ok) throw new Error("Reviews request failed");
    renderReviews(novelId, await response.json());
  } catch {
    const list = document.querySelector("[data-reviews-list]");
    if (list) list.innerHTML = '<p class="reviews-empty">Reviews are temporarily unavailable.</p>';
  }
}

async function refreshReadingListControls(novelId) {
  const container = document.getElementById("novel-reading-list");
  if (!container) return;

  if (!getAccessToken()) {
    container.innerHTML = "";
    container.appendChild(buildReadingListLoginPrompt());
    return;
  }

  try {
    const [lists, membership] = await Promise.all([
      fetchReadingLists(),
      fetchNovelMembership(novelId),
    ]);
    container.innerHTML = "";
    container.appendChild(buildReadingListControls(novelId, membership, lists));
  } catch (error) {
    console.error("[novel.js] failed to load reading list controls:", error);
    container.innerHTML = "";
    const message = document.createElement("p");
    message.className = "reading-list-status";
    message.textContent = "Couldn't load your reading lists.";
    container.appendChild(message);
  }
}

async function loadSimilarNovels(novelId) {
  const section = document.getElementById("similar-section");
  const grid = document.getElementById("similar-novels");
  section.hidden = false;
  grid.setAttribute("aria-busy", "true");
  const message = document.createElement("p");
  message.className = "similar-message";
  message.textContent = "Finding similar stories…";
  grid.replaceChildren(message);
  try {
    const response = await fetch(`${API_BASE}/api/novels/${encodeURIComponent(novelId)}/similar`);
    if (!response.ok) throw new Error("Recommendations request failed");
    const novels = await response.json();
    grid.replaceChildren();
    if (!novels.length) {
      message.textContent = "No similar stories yet. Check back as the catalogue grows.";
      grid.appendChild(message);
    }
    novels.slice(0, 6).forEach((novel) => {
      const card = document.createElement("a");
      card.className = "similar-card";
      card.href = `/novel.html?id=${encodeURIComponent(novel.id)}`;
      const cover = document.createElement("div");
      cover.className = "similar-cover";
      cover.setAttribute("aria-hidden", "true");
      const fallback = document.createElement("span");
      fallback.textContent = novel.title || "Untitled";
      cover.appendChild(fallback);
      if (novel.cover_image_url) {
        const image = document.createElement("img");
        image.alt = "";
        image.loading = "lazy";
        image.referrerPolicy = "no-referrer";
        image.src = novel.cover_image_url;
        image.addEventListener("error", () => image.remove(), { once: true });
        cover.appendChild(image);
      }
      const copy = document.createElement("div");
      copy.className = "similar-copy";
      const title = document.createElement("h3");
      title.textContent = novel.title || "Untitled";
      const author = document.createElement("p");
      author.textContent = novel.author || "Unknown author";
      copy.append(title, author);
      const tags = document.createElement("div");
      tags.className = "similar-tags";
      (novel.shared_tags || []).slice(0, 3).forEach((tag) => {
        const chip = document.createElement("span");
        chip.textContent = tag;
        tags.appendChild(chip);
      });
      copy.appendChild(tags);
      card.append(cover, copy);
      grid.appendChild(card);
    });
  } catch {
    message.textContent = "Similar novels are temporarily unavailable.";
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "similar-retry";
    retry.textContent = "Try again";
    retry.addEventListener("click", () => loadSimilarNovels(novelId));
    message.append(" ", retry);
    grid.replaceChildren(message);
  } finally {
    grid.setAttribute("aria-busy", "false");
  }
}

async function loadNovel() {
  console.log("[novel.js] loadNovel() starting");

  const novelId = getNovelIdFromUrl();
  const titleEl = document.getElementById("novel-title");
  console.log("[novel.js] novel id from URL:", novelId);

  if (!novelId) {
    console.warn("[novel.js] no ?id= in the URL");
    if (titleEl) titleEl.textContent = "Novel not found";
    return;
  }

  try {
    const url = `${API_BASE}/api/novels/${novelId}`;
    console.log("[novel.js] fetching:", url);
    const response = await fetch(url);
    console.log("[novel.js] response status:", response.status);

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }
    const novel = await response.json();
    console.log("[novel.js] novel payload received:", novel);
    renderNovel(novel);
    const voteLink = document.getElementById("protagonist-vote-link");
    voteLink.href = `/vote.html?id=${encodeURIComponent(novelId)}`;
    voteLink.hidden = false;
    refreshReadingListControls(novelId);
    loadReviews(novelId);
    loadSimilarNovels(novelId);
    console.log("[novel.js] render complete");
  } catch (error) {
    console.error("[novel.js] failed to load novel:", error);
    if (titleEl) titleEl.textContent = "Couldn't load this novel";
    const synopsisEl = document.getElementById("novel-synopsis");
    if (synopsisEl) {
      synopsisEl.textContent = "Try again in a few minutes. If the issue persists, please report it to axiomnovels@gmail.com.";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("[novel.js] script loaded and DOM ready");
  loadNovel();
});

document.addEventListener("click", (event) => {
  document.querySelectorAll(".reading-list-picker[open]").forEach((picker) => {
    if (!picker.contains(event.target)) picker.removeAttribute("open");
  });
});
