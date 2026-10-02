function renderActivityStars(container, rating) {
  const value = Number(rating) || 0;
  for (let index = 1; index <= 5; index += 1) {
    const star = document.createElement("span");
    star.textContent = "★";
    star.dataset.fill = value >= index ? "full" : value >= index - 0.5 ? "half" : "empty";
    container.appendChild(star);
  }
}

// "You reviewed" on your own page, "Reviewed" on someone else's.
function activityContextLabel(activity, isOwnActivity) {
  const verb = activity.type === "reply" ? "replied on" : activity.comment ? "reviewed" : "rated";
  return isOwnActivity ? `You ${verb}` : verb.charAt(0).toUpperCase() + verb.slice(1);
}

// One card layout for both tabs. Novels and reading lists only differ in where
// the card links, which image/title/byline it shows, and the anchor it targets.
function buildActivityCard({ activity, isOwnActivity, href, imageUrl, imageAlt, fallbackText, title, byline }) {
  const card = document.createElement("article");
  card.className = "user-activity-card";

  const cover = document.createElement("a");
  cover.className = "user-activity-cover";
  cover.href = href;
  if (imageUrl) {
    const image = document.createElement("img");
    image.referrerPolicy = "no-referrer";
    image.src = imageUrl;
    image.alt = imageAlt;
    image.addEventListener("error", () => {
      image.remove();
      cover.classList.add("has-fallback");
      cover.textContent = fallbackText;
    }, { once: true });
    cover.appendChild(image);
  } else {
    cover.classList.add("has-fallback");
    cover.textContent = fallbackText;
  }

  const body = document.createElement("div");
  body.className = "user-activity-body";
  const context = document.createElement("p");
  context.className = "user-activity-context";
  context.textContent = activityContextLabel(activity, isOwnActivity);
  const titleLink = document.createElement("a");
  titleLink.className = "user-activity-title";
  titleLink.href = href;
  titleLink.textContent = title;
  const author = document.createElement("span");
  author.className = "user-activity-author";
  author.textContent = byline;
  const meta = document.createElement("div");
  meta.className = "user-activity-meta";
  const date = document.createElement("time");
  date.dateTime = activity.updated_at;
  date.textContent = new Date(activity.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  if (activity.type !== "reply") {
    const stars = document.createElement("span");
    stars.className = "review-card-stars";
    stars.setAttribute("aria-label", `${activity.rating} out of 5 stars`);
    renderActivityStars(stars, activity.rating);
    meta.appendChild(stars);
  }
  meta.appendChild(date);
  body.append(context, titleLink, author, meta);

  if (activity.comment) {
    const comment = document.createElement("p");
    comment.className = "user-activity-comment";
    comment.textContent = activity.comment;
    body.appendChild(comment);
  }
  card.append(cover, body);
  return card;
}

function createActivityCard(activity, isOwnActivity) {
  const novel = activity.novel || {};
  const novelUrl = `/novel.html?id=${encodeURIComponent(activity.novel_id)}`;
  return buildActivityCard({
    activity,
    isOwnActivity,
    href: `${novelUrl}#${activity.type === "reply" ? "reply" : "review"}-${activity.id}`,
    imageUrl: novel.cover_image_url,
    imageAlt: `Cover of ${novel.title || "novel"}`,
    fallbackText: novel.title || "Axiom",
    title: novel.title || "Unknown novel",
    byline: novel.author ? `by ${novel.author}` : "",
  });
}

// Your own lists open in the owner view; everyone else's open in the shared view
// (the same routing the profile page uses).
function createListActivityCard(activity, isOwnActivity) {
  const list = activity.list || {};
  const viewerId = getStoredUser()?.id;
  const listUrl = list.owner_id && list.owner_id === viewerId
    ? `/list.html?id=${encodeURIComponent(list.id)}`
    : `/shared-list.html?user=${encodeURIComponent(list.owner_id)}&id=${encodeURIComponent(list.id)}`;
  return buildActivityCard({
    activity,
    isOwnActivity,
    href: `${listUrl}#${activity.type === "reply" ? "reply" : "review"}-${activity.id}`,
    imageUrl: list.cover_image_url,
    imageAlt: `Cover of a novel in ${list.name || "this reading list"}`,
    fallbackText: list.name || "Reading list",
    title: list.name || "Unknown list",
    byline: list.owner_username ? `by ${list.owner_username}` : "",
  });
}

function renderActivityFeed(feed, items, createCard, isOwnActivity, emptyMessage) {
  feed.innerHTML = "";
  if (!items?.length) {
    feed.innerHTML = `<div class="user-activity-empty"><strong>No activity yet</strong><p>${emptyMessage}</p></div>`;
    return;
  }
  items.forEach((item) => feed.appendChild(createCard(item, isOwnActivity)));
}

function describeActivityStats(reviewCount, averageRating, replyCount) {
  const count = Number(reviewCount) || 0;
  const replies = Number(replyCount) || 0;
  const parts = [];
  if (count) parts.push(`${count} ${count === 1 ? "review" : "reviews"} · ${Number(averageRating).toFixed(1)} average`);
  if (replies) parts.push(`${replies} ${replies === 1 ? "reply" : "replies"}`);
  return parts.join(" · ") || "No activity yet";
}

// Novels / Reading Lists tabs. `onChange(tab)` lets the page swap the stats
// line that sits beside the heading.
function setupActivityTabs(onChange) {
  const tabs = [...document.querySelectorAll("[data-activity-tab]")];
  const panels = [...document.querySelectorAll("[data-activity-panel]")];

  function select(tab, { focus = false } = {}) {
    const target = tab.dataset.activityTab;
    tabs.forEach((other) => {
      const isActive = other === tab;
      other.setAttribute("aria-selected", String(isActive));
      other.tabIndex = isActive ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.activityPanel !== target;
    });
    if (focus) tab.focus();
    onChange(target);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const step = event.key === "ArrowRight" ? 1 : -1;
      select(tabs[(index + step + tabs.length) % tabs.length], { focus: true });
    });
  });
}

async function loadOwnActivity() {
  const requestedUserId = new URLSearchParams(window.location.search).get("id");
  const signedInUser = getStoredUser();
  const userId = requestedUserId || signedInUser?.id;
  const isOwnActivity = !requestedUserId || requestedUserId === signedInUser?.id;
  if (!userId || (isOwnActivity && !getAccessToken())) {
    window.location.replace("/login.html");
    return;
  }

  const novelFeed = document.querySelector("[data-user-activity-feed]");
  const listFeed = document.querySelector("[data-user-list-activity-feed]");
  const stats = document.querySelector("[data-user-activity-stats]");
  const statsByTab = { novels: "", lists: "" };
  let activeTab = "novels";
  setupActivityTabs((tab) => {
    activeTab = tab;
    stats.textContent = statsByTab[tab];
  });

  try {
    // authFetch (not plain fetch) so the backend knows who is viewing: reading
    // list activity is only shown for lists the viewer is allowed to see.
    const response = await authFetch(`${API_BASE}/api/users/${encodeURIComponent(userId)}/activity`);
    if (!response.ok) throw new Error("Activity request failed");
    const payload = await response.json();
    const username = payload.profile?.username || "Reader";
    document.title = `${isOwnActivity ? "Your Activity" : `${username}'s Activity`} | Axiom`;
    if (!isOwnActivity) {
      document.querySelector(".activity-page .eyebrow").textContent = "Reader history";
      document.getElementById("activity-heading").textContent = `${username}'s activity`;
      document.querySelector(".activity-intro").textContent = `Every review and reply ${username} has shared, newest first.`;
    }

    statsByTab.novels = describeActivityStats(payload.review_count, payload.average_rating, payload.reply_count);
    statsByTab.lists = describeActivityStats(payload.list_review_count, payload.list_average_rating, payload.list_reply_count);
    stats.textContent = statsByTab[activeTab];

    const emptyMessage = isOwnActivity
      ? "Your ratings, reviews, and replies will appear here."
      : "This reader has not rated, reviewed, or replied here yet.";
    renderActivityFeed(novelFeed, payload.activity, createActivityCard, isOwnActivity, emptyMessage);
    renderActivityFeed(listFeed, payload.list_activity, createListActivityCard, isOwnActivity, emptyMessage);
  } catch (error) {
    console.error("[activity.js] failed to load activity:", error);
    const message = '<p class="user-profile-empty">Your activity is temporarily unavailable.</p>';
    novelFeed.innerHTML = message;
    listFeed.innerHTML = message;
  }
}

loadOwnActivity();
