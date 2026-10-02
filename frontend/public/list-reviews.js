// Ratings, comments and threaded replies on reading lists. Shared by list.html
// (the owner's view) and shared-list.html (everyone else). Mirrors the review
// and reply UI in novel.js but talks to /api/reading-lists/{id}/reviews.
//
// All function names here are prefixed "List" on purpose: every page loads its
// scripts into one shared global scope, so they must not collide with
// script.js (createListLikeControl is the heart on a whole list) or novel.js.

function listReviewUserId() {
  return getStoredUser()?.id || null;
}

function listReviewsUrl(listId) {
  return `${API_BASE}/api/reading-lists/${encodeURIComponent(listId)}/reviews`;
}

// The profile may arrive as an object or a single-item array.
function listReviewProfile(item) {
  const value = item.profiles || {};
  return Array.isArray(value) ? (value[0] || {}) : value;
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

// Something the viewer tried to touch is gone, most often because the owner
// tightened the list's visibility while this page was open. Tell them, then
// reload so the page reflects what they can actually see now.
async function handleListThreadNotFound(listId, result) {
  const detail = typeof result?.detail === "string" ? result.detail : "";
  window.alert(
    !detail || detail === "Reading list not found."
      ? "This reading list is no longer shared with you."
      : `${detail} The discussion will refresh.`
  );
  await loadListReviews(listId);
}

// Shared tail of every reply write: handles auth/not-found/errors, then
// reloads the discussion. Throws an Error with a readable message on failure.
async function finishListThreadRequest(listId, response, fallback) {
  if (response.status === 401) {
    window.location.href = "/login.html";
    return;
  }
  const result = await response.json().catch(() => ({}));
  if (response.status === 404) {
    await handleListThreadNotFound(listId, result);
    return;
  }
  if (!response.ok) {
    throw new Error(typeof result.detail === "string" ? result.detail : fallback);
  }
  await loadListReviews(listId);
}

// Toggleable thumbs-up shared by reviews and replies, mirroring createLikeControl
// in novel.js. Authors see the current count but cannot like their own
// contribution; everyone else toggles their like on and off.
function createListReviewLikeControl(listId, item, kind = "review", reviewId = item.id) {
  const wrapper = document.createElement("div");
  wrapper.className = "review-like";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-like-button";
  button.appendChild(createListThumbsUpIcon());

  const count = document.createElement("span");
  count.className = "review-like-count";
  count.textContent = String(item.like_count || 0);

  const contributionName = kind === "reply" ? "reply" : "review";

  if (item.user_id === listReviewUserId()) {
    button.disabled = true;
    button.classList.add("is-own");
    button.title = `You can't like your own ${contributionName}`;
    button.setAttribute("aria-label", `You can't like your own ${contributionName}`);
  } else {
    button.classList.toggle("is-liked", Boolean(item.viewer_has_liked));
    button.setAttribute("aria-pressed", String(Boolean(item.viewer_has_liked)));
    button.setAttribute(
      "aria-label",
      item.viewer_has_liked ? `Unlike this ${contributionName}` : `Like this ${contributionName}`
    );

    button.addEventListener("click", async () => {
      if (!getAccessToken()) {
        window.location.href = "/login.html";
        return;
      }
      const currentlyLiked = button.classList.contains("is-liked");
      const likeUrl = kind === "reply"
        ? `${listReviewsUrl(listId)}/${encodeURIComponent(reviewId)}/replies/${encodeURIComponent(item.id)}/like`
        : `${listReviewsUrl(listId)}/${encodeURIComponent(item.id)}/like`;
      button.disabled = true;
      try {
        const response = await authFetch(likeUrl, { method: currentlyLiked ? "DELETE" : "POST" });
        if (response.status === 401) {
          window.location.href = "/login.html";
          return;
        }
        const result = await response.json().catch(() => ({}));
        if (response.status === 404) {
          await handleListThreadNotFound(listId, result);
          return;
        }
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
      const response = await authFetch(listReviewsUrl(listId), {
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

// ---------------------------------------------------------------------------
// Threaded discussion: reply / edit / delete / like, mirroring novel.js
// ---------------------------------------------------------------------------

// One form for both "reply" and "edit your reply" (novel.js builds the two
// separately). `request(comment)` performs the write and reloads the page's
// discussion; if it throws, the message is shown and the form is re-enabled.
function buildListReplyForm({ label, placeholder = "", initial = "", submitLabel, busyLabel, fallback, className = "", onCancel, request }) {
  const form = document.createElement("form");
  form.className = `review-reply-form ${className}`.trim();

  const labelEl = document.createElement("label");
  labelEl.textContent = label;
  const textarea = document.createElement("textarea");
  textarea.maxLength = 2000;
  textarea.rows = 3;
  textarea.required = true;
  textarea.placeholder = placeholder;
  textarea.value = initial;
  labelEl.appendChild(textarea);

  const footer = document.createElement("div");
  footer.className = "review-reply-form-footer";
  const message = document.createElement("span");
  message.setAttribute("role", "status");
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost-link";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", onCancel);
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = submitLabel;
  footer.append(message, cancel, submit);

  form.append(labelEl, footer);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    submit.textContent = busyLabel;
    message.textContent = "";
    try {
      await request(textarea.value);
    } catch (error) {
      message.textContent = error.message || fallback;
      submit.disabled = false;
      submit.textContent = submitLabel;
    }
  });
  return { form, textarea };
}

function createListReplyAction(listId, reviewId, parentReplyId, targetName) {
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

    const { form, textarea } = buildListReplyForm({
      label: `Reply to ${targetName || "this reader"}`,
      placeholder: "Add to the conversation…",
      submitLabel: "Post reply",
      busyLabel: "Posting…",
      fallback: "Couldn't post your reply.",
      onCancel: () => form.remove(),
      request: async (comment) => {
        const response = await authFetch(`${listReviewsUrl(listId)}/${encodeURIComponent(reviewId)}/replies`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comment, parent_reply_id: parentReplyId }),
        });
        await finishListThreadRequest(listId, response, "Couldn't post your reply.");
      },
    });
    wrapper.append(form);
    textarea.focus();
  });
  wrapper.appendChild(button);
  return wrapper;
}

function createListPlaceholderAction(label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "review-thread-placeholder";
  button.textContent = label;
  button.disabled = true;
  button.title = "Coming soon";
  return button;
}

function createListMoreActions({ isOwner, onEdit, onDelete }) {
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
    createListPlaceholderAction("Follow comment"),
    createListPlaceholderAction("Report")
  );
  menu.append(trigger, panel);
  return menu;
}

function createListThreadActionRow({ item, kind, listId, reviewId, parentReplyId, targetName, onEdit, onDelete }) {
  const row = document.createElement("div");
  row.className = "review-thread-actions";
  row.appendChild(createListReviewLikeControl(listId, item, kind, reviewId));
  row.appendChild(createListPlaceholderAction("↓"));
  row.appendChild(createListReplyAction(listId, reviewId, parentReplyId, targetName));
  row.appendChild(createListMoreActions({
    isOwner: item.user_id === listReviewUserId(),
    onEdit,
    onDelete,
  }));
  return row;
}

function openListReplyEditor(listId, reviewId, reply, article) {
  if (article.querySelector(".review-reply-edit-form")) return;
  const currentComment = article.querySelector(".review-reply-comment");
  if (!currentComment) return;

  const { form, textarea } = buildListReplyForm({
    label: "Edit your reply",
    initial: reply.comment,
    submitLabel: "Save changes",
    busyLabel: "Saving…",
    fallback: "Couldn't update your reply.",
    className: "review-reply-edit-form",
    onCancel: () => form.remove(),
    request: async (comment) => {
      const response = await authFetch(
        `${listReviewsUrl(listId)}/${encodeURIComponent(reviewId)}/replies/${encodeURIComponent(reply.id)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comment }),
        }
      );
      await finishListThreadRequest(listId, response, "Couldn't update your reply.");
    },
  });
  currentComment.after(form);
  textarea.focus();
}

async function deleteListReply(listId, reviewId, reply) {
  const hasChildren = (reply.replies || []).length > 0;
  const prompt = hasChildren
    ? "Delete this reply and its nested replies? This can't be undone."
    : "Delete your reply? This can't be undone.";
  if (!window.confirm(prompt)) return;
  try {
    const response = await authFetch(
      `${listReviewsUrl(listId)}/${encodeURIComponent(reviewId)}/replies/${encodeURIComponent(reply.id)}`,
      { method: "DELETE" }
    );
    await finishListThreadRequest(listId, response, "Delete failed");
  } catch {
    window.alert("Couldn't delete your reply. Please try again.");
  }
}

async function deleteListReview(listId) {
  if (!window.confirm("Delete your review? This can't be undone.")) return;
  try {
    const response = await authFetch(listReviewsUrl(listId), { method: "DELETE" });
    if (response.status === 401) { window.location.href = "/login.html"; return; }
    if (response.status === 404) {
      window.alert("This reading list is no longer shared with you.");
      await loadListReviews(listId);
      return;
    }
    if (!response.ok) throw new Error("Delete failed");
    await loadListReviews(listId);
  } catch {
    window.alert("Couldn't delete your review. Please try again.");
  }
}

function createListReviewReply(listId, reviewId, reply) {
  const profile = listReviewProfile(reply);
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
  (reply.replies || []).forEach((child) => children.appendChild(createListReviewReply(listId, reviewId, child)));

  const actions = createListThreadActionRow({
    item: reply,
    kind: "reply",
    listId,
    reviewId,
    parentReplyId: reply.id,
    targetName: profile.username,
    onEdit: () => openListReplyEditor(listId, reviewId, reply, article),
    onDelete: () => deleteListReply(listId, reviewId, reply),
  });

  article.append(header, comment, actions, children);
  return article;
}

function createListReviewCard(listId, review) {
  const profile = listReviewProfile(review);
  const username = profile.username || "Axiom reader";
  const profileUrl = `/user.html?id=${encodeURIComponent(review.user_id)}`;

  const article = document.createElement("article");
  article.className = "review-card";
  article.id = `review-${review.id}`;
  article.tabIndex = -1;

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
  topRow.append(stars);
  meta.appendChild(topRow);

  header.append(profileLink, identity, meta);

  const comment = document.createElement("p");
  comment.textContent = review.comment;

  const replies = document.createElement("div");
  replies.className = "review-replies";
  (review.replies || []).forEach((reply) => replies.appendChild(createListReviewReply(listId, review.id, reply)));

  let editReview = null;
  let removeReview = null;
  if (review.user_id === listReviewUserId()) {
    editReview = () => {
      const composer = document.querySelector("[data-review-composer]");
      composer?.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => composer?.querySelector("[data-review-comment]")?.focus(), 350);
    };
    removeReview = () => deleteListReview(listId);
  }

  const actions = createListThreadActionRow({
    item: review,
    kind: "review",
    listId,
    reviewId: review.id,
    parentReplyId: null,
    targetName: username,
    onEdit: editReview,
    onDelete: removeReview,
  });

  article.append(header, comment, actions, replies);
  return article;
}

// Scroll to and highlight #review-<id> / #reply-<id>, like the novel page does.
function focusListReviewDiscussionTarget() {
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

window.addEventListener("hashchange", focusListReviewDiscussionTarget);

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
  focusListReviewDiscussionTarget();
}

async function loadListReviews(listId) {
  const section = document.querySelector("[data-list-reviews-section]");
  const list = document.querySelector("[data-reviews-list]");
  if (!section || !list) return;

  try {
    const response = await authFetch(listReviewsUrl(listId));
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