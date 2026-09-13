// Snake_case key -> display label, matching the trait definitions discussed
// for the info page. Kept here too so this page can render nice labels
// without depending on that endpoint existing yet.
const TRAIT_LABELS = {
  // Protagonist Profile
  impulsivity: "Impulsivity",
  arrogance_pride: "Ego",
  kinship_friendship: "Kinship and Friendship",
  romantic_attachment: "Romantic Attachment",
  sexual_desire: "Lust",
  selflessness: "Selflessness",
  // Philosophy Profile
  freedom: "Freedom",
  survival: "Survival",
  existentialism: "Existentialism",
  moral_ambiguity: "Moral Ambiguity",
  self_improvement: "Self-Improvement",
  determinism: "Determinism",
  revenge: "Revenge",
  romance: "Romance",
  // Storytelling Style
  political_intrigue: "Political Intrigue",
  psychological_warfare: "Psychological Warfare",
  kingdom_building: "Kingdom Building",
  action: "Action",
  slice_of_life: "Slice of Life",
  mystery: "Mystery",
  worldbuilding: "Worldbuilding",
};

const PROTAGONIST_MEASURES = [
  { key: "impulsivity" },
  { key: "arrogance_pride" },
  { key: "kinship_friendship" },
  { key: "romantic_attachment" },
  { key: "sexual_desire" },
  { key: "selflessness" },
];
const PHILOSOPHY_KEYS = [
  "freedom", "survival", "existentialism", "moral_ambiguity",
  "self_improvement", "determinism", "revenge", "romance",
];
const STYLE_KEYS = [
  "political_intrigue", "psychological_warfare", "kingdom_building",
  "action", "slice_of_life", "mystery", "worldbuilding",
];

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
  fill.style.width = `${Math.max(0, Math.min(100, score))}%`;
  track.appendChild(fill);

  const scoreEl = document.createElement("div");
  scoreEl.className = "trait-score";
  scoreEl.textContent = score;

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
    const score = normalizedScore(profile[measure.key]);
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

function renderProfileSection(containerId, keys, profile) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  container.innerHTML = "";

  if (!profile) {
    container.innerHTML = "<p>No profile data yet for this novel.</p>";
    return;
  }

  keys.forEach((key) => {
    container.appendChild(renderTraitRow(key, profile[key] ?? 0));
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

// Chapter count and view count are both optional (a source page may not
// expose one, or scraping it may have failed) -- each stat is only shown
// when a non-negative number is actually present, so the row simply
// shrinks rather than showing a misleading "0 chapters".
function renderNovelStats(novel) {
  const container = document.getElementById("novel-stats");
  if (!container) return;
  container.innerHTML = "";

  const stats = [
    { value: novel.chapter_count, singular: "chapter", plural: "chapters" },
    { value: novel.view_count, singular: "view", plural: "views" },
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

function renderNovel(novel) {
  document.title = `${novel.title} | Axiom`;

  const titleEl = document.getElementById("novel-title");
  const authorEl = document.getElementById("novel-author");
  const statusEl = document.getElementById("novel-status");
  // const synopsisEl = document.getElementById("novel-synopsis");
  const coverEl = document.getElementById("novel-cover");
  const genresEl = document.getElementById("novel-genres");
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

  if (genresEl) {
    genresEl.innerHTML = "";
    const genres = novel.genres || [];
    genres.forEach((genre, index) => {
      const tag = document.createElement("span");
      tag.className = "genre-tag";
      if (index >= 5) tag.classList.add("is-extra-tag");
      tag.textContent = genre;
      genresEl.appendChild(tag);
    });
    if (genres.length > 5) {
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "genre-toggle";
      toggle.textContent = `+${genres.length - 5} more`;
      toggle.setAttribute("aria-expanded", "false");
      toggle.addEventListener("click", () => {
        const expanded = genresEl.classList.toggle("is-expanded");
        toggle.textContent = expanded ? "Show less" : `+${genres.length - 5} more`;
        toggle.setAttribute("aria-expanded", String(expanded));
      });
      genresEl.appendChild(toggle);
    }
  }

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
  renderProfileSection("philosophy-profile", PHILOSOPHY_KEYS, unwrap(novel.philosophy_profiles));
  renderProfileSection("storytelling-profile", STYLE_KEYS, unwrap(novel.storytelling_style_profiles));
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

// Toggleable like button shown on every review comment. The comment's
// own author sees a disabled version of the same button (you can never
// like your own review); everyone else can toggle their like on and off,
// mirroring the filled/hollow thumbs-up pattern YouTube uses.
function createLikeControl(review) {
  const wrapper = document.createElement("div");
  wrapper.className = "review-like";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-like-button";
  button.appendChild(createThumbsUpIcon());

  const count = document.createElement("span");
  count.className = "review-like-count";
  count.textContent = String(review.like_count || 0);

  const isOwnReview = review.user_id === currentUserId();

  if (isOwnReview) {
    button.disabled = true;
    button.classList.add("is-own");
    button.title = "You can't like your own review";
    button.setAttribute("aria-label", "You can't like your own review");
  } else {
    button.classList.toggle("is-liked", Boolean(review.viewer_has_liked));
    button.setAttribute("aria-pressed", String(Boolean(review.viewer_has_liked)));
    button.setAttribute("aria-label", review.viewer_has_liked ? "Unlike this review" : "Like this review");

    button.addEventListener("click", async () => {
      if (!getAccessToken()) {
        window.location.href = "/login.html";
        return;
      }
      const currentlyLiked = button.classList.contains("is-liked");
      button.disabled = true;
      try {
        const response = await authFetch(`${API_BASE}/api/reviews/${review.id}/like`, {
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
        review.like_count = result.like_count;
        review.viewer_has_liked = result.liked;
        button.classList.toggle("is-liked", result.liked);
        button.setAttribute("aria-pressed", String(result.liked));
        button.setAttribute("aria-label", result.liked ? "Unlike this review" : "Like this review");
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
    topRow.append(stars, createLikeControl(review));
    reviewMeta.appendChild(topRow);
    if (review.user_id === currentUserId()) {
      article.classList.add("is-own-review");
      const actions = document.createElement("div"); actions.className = "review-card-actions";
      const editButton = document.createElement("button"); editButton.type = "button"; editButton.textContent = "Edit";
      editButton.addEventListener("click", () => {
        const composer = document.querySelector("[data-review-composer]");
        composer?.scrollIntoView({ behavior: "smooth", block: "center" });
        setTimeout(() => composer?.querySelector("[data-review-comment]")?.focus(), 350);
      });
      const deleteButton = document.createElement("button"); deleteButton.type = "button"; deleteButton.className = "is-delete"; deleteButton.textContent = "Delete";
      deleteButton.addEventListener("click", async () => {
        if (!window.confirm("Delete your review? This can't be undone.")) return;
        deleteButton.disabled = true; deleteButton.textContent = "Deleting…";
        try {
          const response = await authFetch(`${API_BASE}/api/novels/${novelId}/reviews`, { method: "DELETE" });
          if (response.status === 401) { window.location.href = "/login.html"; return; }
          if (!response.ok) throw new Error("Delete failed");
          await loadReviews(novelId);
        } catch {
          deleteButton.disabled = false; deleteButton.textContent = "Delete";
          window.alert("Couldn't delete your review. Please try again.");
        }
      });
      actions.append(editButton, deleteButton); reviewMeta.appendChild(actions);
    }
    header.append(profileLink, identity, reviewMeta);
    const comment = document.createElement("p"); comment.textContent = review.comment;
    article.append(header, comment); list.appendChild(article);
  });
}

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
    refreshReadingListControls(novelId);
    loadReviews(novelId);
    loadSimilarNovels(novelId);
    console.log("[novel.js] render complete");
  } catch (error) {
    console.error("[novel.js] failed to load novel:", error);
    if (titleEl) titleEl.textContent = "Couldn't load this novel";
    const synopsisEl = document.getElementById("novel-synopsis");
    if (synopsisEl) {
      synopsisEl.textContent = "Make sure the backend is running on port 8000, and that this novel exists.";
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