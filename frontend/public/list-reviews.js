// Ratings and comments on reading lists. Shared by list.html (the owner's
// view) and shared-list.html (everyone else). Mirrors the review UI in
// novel.js but talks to /api/reading-lists/{id}/reviews.

function listReviewUserId() {
  return getStoredUser()?.id || null;
}

function renderListReviewStars(container, rating) {
  container.replaceChildren();
  const value = Number(rating);
  for (let star = 1; star <= 5; star += 1) {
    const icon = document.createElement("span");
    icon.textContent = "★";
    icon.dataset.fill = value >= star ? "full" : value === star - 0.5 ? "half" : "empty";
    container.appendChild(icon);
  }
}

function createListThumbsUpIcon() {
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

// Toggleable thumbs-up on a list review, mirroring createLikeControl in
// novel.js. The review's own author sees a disabled button (you can't like
// your own review); everyone else toggles their like on and off.
function createListLikeControl(listId, review) {
  const wrapper = document.createElement("div");
  wrapper.className = "review-like";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-like-button";
  button.appendChild(createListThumbsUpIcon());

  const count = document.createElement("span");
  count.className = "review-like-count";
  count.textContent = String(review.like_count || 0);

  if (review.user_id === listReviewUserId()) {
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
        const response = await authFetch(
          `${API_BASE}/api/reading-lists/${encodeURIComponent(listId)}/reviews/${encodeURIComponent(review.id)}/like`,
          { method: currentlyLiked ? "DELETE" : "POST" }
        );
        if (response.status === 401) {
          window.location.href = "/login.html";
          return;
        }
        if (response.status === 404) {
          // The owner tightened visibility (or the review was removed) while this page was open.
          window.alert("This reading list is no longer shared with you.");
          await loadListReviews(listId);
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
        window.alert(error.message || "Couldn't update your like. Please try again.");
      } finally {
        button.disabled = false;
      }
    });
  }

  wrapper.append(button, count);
  return wrapper;
}

function setupListRatingPicker(stars, valueField, output, clearButton, initialRating) {
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

  stars.addEventListener("pointermove", (event) => {
    if (selectedRating) return;
    previewRating = valueAt(event.clientX);
    render(previewRating, true);
  });
  stars.addEventListener("click", (event) => commit(valueAt(event.clientX)));
  stars.addEventListener("pointerleave", () => render(selectedRating));
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

function renderListReviewSummary(payload) {
  const overview = document.querySelector("[data-reviews-overview]");
  if (!overview) return;
  if (!payload.review_count) {
    overview.textContent = payload.is_owner ? "No reviews yet" : "Be the first to rate this list";
    return;
  }
  const average = Number(payload.average_rating).toFixed(1);
  const label = `${payload.review_count} ${payload.review_count === 1 ? "review" : "reviews"}`;
  overview.innerHTML = `<strong>${average}</strong><span aria-hidden="true">★</span><small>${label}</small>`;
}

function renderListReviewComposer(listId, payload) {
  const container = document.querySelector("[data-review-composer]");
  if (!container) return;
  container.innerHTML = "";

  if (payload.is_owner) {
    const note = document.createElement("p");
    note.className = "review-login-prompt";
    note.textContent =
      "This is your reading list. Readers who can see it may rate and comment here, " +
      "and you can see every review left on it, including ones left under a different visibility setting.";
    container.appendChild(note);
    return;
  }

  if (!getAccessToken()) {
    const prompt = document.createElement("p");
    prompt.className = "review-login-prompt";
    prompt.append("Enjoyed this list? ");
    const link = document.createElement("a");
    link.href = "/login.html";
    link.textContent = "Log in to leave a review";
    prompt.appendChild(link);
    prompt.append(".");
    container.appendChild(prompt);
    return;
  }

  const mine = payload.reviews.find((review) => review.user_id === listReviewUserId());
  const form = document.createElement("form");
  form.className = "review-form";
  form.innerHTML = `
    <div class="review-form-heading"><div><h3>${mine ? "Update your review" : "Share your review"}</h3><p>Your rating is required. Your comment is optional.</p></div></div>
    <fieldset class="star-picker"><legend>Your rating</legend><div class="review-rating-control"><div class="star-picker-options" role="slider" tabindex="0" aria-label="Your rating" aria-valuemin="0.5" aria-valuemax="5" aria-valuenow="0"></div><div class="review-rating-copy"><output class="review-rating-value" data-review-rating-output>Select a rating</output><button type="button" class="review-rating-clear" data-review-rating-clear hidden>Clear</button></div></div><input type="hidden" name="rating" data-review-rating></fieldset>
    <label class="review-comment-label">Comment <span>Optional</span><span class="review-comment-field"><textarea maxlength="2000" rows="4" placeholder="What did you think of this list?" data-review-comment aria-describedby="review-comment-counter"></textarea><span class="review-comment-counter" id="review-comment-counter" data-review-comment-counter>0/2000</span></span></label>
    <div class="review-form-footer"><span data-review-message role="status"></span><button type="submit">${mine ? "Update review" : "Post review"}</button></div>`;

  const options = form.querySelector(".star-picker-options");
  for (let rating = 1; rating <= 5; rating += 1) {
    const button = document.createElement("button");
    button.type = "button";
    button.tabIndex = -1;
    button.dataset.star = rating;
    button.setAttribute("aria-label", `${rating} ${rating === 1 ? "star" : "stars"}`);
    const icon = document.createElement("span");
    icon.textContent = "★";
    icon.setAttribute("aria-hidden", "true");
    button.appendChild(icon);
    options.appendChild(button);
  }
  setupListRatingPicker(
    options,
    form.querySelector("[data-review-rating]"),
    form.querySelector("[data-review-rating-output]"),
    form.querySelector("[data-review-rating-clear]"),
    mine?.rating
  );

  const commentField = form.querySelector("[data-review-comment]");
  const commentCounter = form.querySelector("[data-review-comment-counter]");
  commentField.value = mine?.comment || "";
  const updateCounter = () => { commentCounter.textContent = `${commentField.value.length}/2000`; };
  commentField.addEventListener("input", updateCounter);
  updateCounter();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    const message = form.querySelector("[data-review-message]");
    const rating = Number(form.querySelector("[data-review-rating]").value);
    if (!rating) { message.textContent = "Choose a star rating first."; return; }

    button.disabled = true;
    button.textContent = "Saving…";
    message.textContent = "";
    try {
      const response = await authFetch(`${API_BASE}/api/reading-lists/${encodeURIComponent(listId)}/reviews`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment: commentField.value }),
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) { window.location.href = "/login.html"; return; }
      if (response.status === 404) {
        // The owner tightened visibility while this page was open.
        window.alert("This reading list is no longer shared with you.");
        await loadListReviews(listId);
        return;
      }
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Couldn't save your review.");
      await loadListReviews(listId);
    } catch (error) {
      message.textContent = error.message || "Couldn't save your review.";
      button.disabled = false;
      button.textContent = mine ? "Update review" : "Post review";
    }
  });

  container.appendChild(form);
}

function createListReviewCard(listId, review) {
  const profileValue = review.profiles || {};
  const profile = Array.isArray(profileValue) ? (profileValue[0] || {}) : profileValue;
  const username = profile.username || "Axiom reader";
  const profileUrl = `/user.html?id=${encodeURIComponent(review.user_id)}`;

  const article = document.createElement("article");
  article.className = "review-card";

  const header = document.createElement("div");
  header.className = "review-card-header";

  const profileLink = document.createElement("a");
  profileLink.className = "review-profile-link";
  profileLink.href = profileUrl;
  profileLink.setAttribute("aria-label", `View ${username}'s profile`);
  const avatar = document.createElement("div");
  avatar.className = "review-avatar";
  if (profile.avatar_url) {
    const image = document.createElement("img");
    image.src = profile.avatar_url;
    image.alt = "";
    avatar.appendChild(image);
  } else {
    avatar.textContent = username.charAt(0).toUpperCase();
  }
  profileLink.appendChild(avatar);

  const identity = document.createElement("div");
  const nameLink = document.createElement("a");
  nameLink.className = "review-author-link";
  nameLink.href = profileUrl;
  const name = document.createElement("strong");
  name.textContent = username;
  nameLink.appendChild(name);
  const date = document.createElement("time");
  date.dateTime = review.updated_at;
  date.textContent = new Date(review.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  identity.append(nameLink, date);

  const meta = document.createElement("div");
  meta.className = "review-card-meta";
  const stars = document.createElement("span");
  stars.className = "review-card-stars";
  renderListReviewStars(stars, review.rating);
  stars.setAttribute("aria-label", `${review.rating} out of 5 stars`);
  const topRow = document.createElement("div");
  topRow.className = "review-card-meta-top";
  topRow.append(stars, createListLikeControl(listId, review));
  meta.appendChild(topRow);

  header.append(profileLink, identity, meta);
  article.appendChild(header);

  if (review.comment) {
    const comment = document.createElement("p");
    comment.textContent = review.comment;
    article.appendChild(comment);
  }

  if (review.user_id === listReviewUserId()) {
    article.classList.add("is-own-review");
    const actions = document.createElement("div");
    actions.className = "review-card-actions";

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => {
      const composer = document.querySelector("[data-review-composer]");
      composer?.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => composer?.querySelector("[data-review-comment]")?.focus(), 350);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "is-delete";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async () => {
      if (!window.confirm("Delete your review? This can't be undone.")) return;
      deleteButton.disabled = true;
      deleteButton.textContent = "Deleting…";
      try {
        const response = await authFetch(`${API_BASE}/api/reading-lists/${encodeURIComponent(listId)}/reviews`, { method: "DELETE" });
        if (response.status === 401) { window.location.href = "/login.html"; return; }
        if (response.status === 404) {
          window.alert("This reading list is no longer shared with you.");
          await loadListReviews(listId);
          return;
        }
        if (!response.ok) throw new Error("Delete failed");
        await loadListReviews(listId);
      } catch {
        deleteButton.disabled = false;
        deleteButton.textContent = "Delete";
        window.alert("Couldn't delete your review. Please try again.");
      }
    });

    actions.append(editButton, deleteButton);
    article.appendChild(actions);
  }

  return article;
}

function renderListReviews(listId, payload) {
  renderListReviewSummary(payload);
  renderListReviewComposer(listId, payload);

  const list = document.querySelector("[data-reviews-list]");
  list.innerHTML = "";

  // Like the novel feed, only reviews with a written comment get a card.
  // Rating-only reviews still count toward the average shown in the overview.
  const reviewsWithComments = payload.reviews.filter((review) => review.comment);
  if (!reviewsWithComments.length) {
    const empty = document.createElement("p");
    empty.className = "reviews-empty";
    if (payload.review_count) {
      empty.textContent = "No written comments yet.";
    } else {
      empty.textContent = payload.is_owner
        ? "No reviews yet. Readers who can see this list can rate and comment on it."
        : "No reviews yet. Start the conversation.";
    }
    list.appendChild(empty);
    return;
  }
  reviewsWithComments.forEach((review) => list.appendChild(createListReviewCard(listId, review)));
}

async function loadListReviews(listId) {
  const section = document.querySelector("[data-list-reviews-section]");
  const list = document.querySelector("[data-reviews-list]");
  if (!section || !list) return;

  try {
    const response = await authFetch(`${API_BASE}/api/reading-lists/${encodeURIComponent(listId)}/reviews`);
    if (response.status === 404) {
      // Not found, or the viewer no longer has permission: show nothing.
      section.hidden = true;
      return;
    }
    if (!response.ok) throw new Error("Reviews request failed");
    const payload = await response.json();
    section.hidden = false;
    renderListReviews(listId, payload);
  } catch {
    section.hidden = false;
    list.innerHTML = '<p class="reviews-empty">Reviews are temporarily unavailable.</p>';
  }
}

function initListReviews(listId) {
  if (!listId) return;
  loadListReviews(listId);
}