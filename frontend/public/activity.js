function renderActivityStars(container, rating) {
  const value = Number(rating) || 0;
  for (let index = 1; index <= 5; index += 1) {
    const star = document.createElement("span");
    star.textContent = "★";
    star.dataset.fill = value >= index ? "full" : value >= index - 0.5 ? "half" : "empty";
    container.appendChild(star);
  }
}

function createActivityCard(activity) {
  const novel = activity.novel || {};
  const novelUrl = `/novel.html?id=${encodeURIComponent(activity.novel_id)}`;
  const card = document.createElement("article");
  card.className = "user-activity-card";

  const cover = document.createElement("a");
  cover.className = "user-activity-cover";
  cover.href = novelUrl;
  if (novel.cover_image_url) {
    const image = document.createElement("img");
    image.src = novel.cover_image_url;
    image.alt = `Cover of ${novel.title || "novel"}`;
    cover.appendChild(image);
  } else {
    cover.textContent = "A";
  }

  const body = document.createElement("div");
  body.className = "user-activity-body";
  const context = document.createElement("p");
  context.className = "user-activity-context";
  context.textContent = activity.comment ? "You reviewed" : "You rated";
  const title = document.createElement("a");
  title.className = "user-activity-title";
  title.href = novelUrl;
  title.textContent = novel.title || "Unknown novel";
  const author = document.createElement("span");
  author.className = "user-activity-author";
  author.textContent = novel.author ? `by ${novel.author}` : "";
  const meta = document.createElement("div");
  meta.className = "user-activity-meta";
  const stars = document.createElement("span");
  stars.className = "review-card-stars";
  stars.setAttribute("aria-label", `${activity.rating} out of 5 stars`);
  renderActivityStars(stars, activity.rating);
  const date = document.createElement("time");
  date.dateTime = activity.updated_at;
  date.textContent = new Date(activity.updated_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  meta.append(stars, date);
  body.append(context, title, author, meta);

  if (activity.comment) {
    const comment = document.createElement("p");
    comment.className = "user-activity-comment";
    comment.textContent = activity.comment;
    body.appendChild(comment);
  }
  card.append(cover, body);
  return card;
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

  const feed = document.querySelector("[data-user-activity-feed]");
  const stats = document.querySelector("[data-user-activity-stats]");
  try {
    const response = await fetch(`${API_BASE}/api/users/${encodeURIComponent(userId)}/activity`);
    if (!response.ok) throw new Error("Activity request failed");
    const payload = await response.json();
    const username = payload.profile?.username || "Reader";
    document.title = `${isOwnActivity ? "Your Activity" : `${username}'s Activity`} | Axiom`;
    if (!isOwnActivity) {
      document.querySelector(".activity-page .eyebrow").textContent = "Reader history";
      document.getElementById("activity-heading").textContent = `${username}'s activity`;
      document.querySelector(".activity-intro").textContent = `Every novel ${username} has rated or reviewed, newest first.`;
    }
    const count = Number(payload.review_count) || 0;
    stats.textContent = count
      ? `${count} ${count === 1 ? "review" : "reviews"} · ${Number(payload.average_rating).toFixed(1)} average`
      : "No reviews yet";
    feed.innerHTML = "";
    if (!payload.activity?.length) {
      feed.innerHTML = '<div class="user-activity-empty"><strong>No activity yet</strong><p>Your ratings and reviews will appear here.</p></div>';
      return;
    }
    payload.activity.forEach((activity) => {
      const card = createActivityCard(activity);
      if (!isOwnActivity) card.querySelector(".user-activity-context").textContent = activity.comment ? "Reviewed" : "Rated";
      feed.appendChild(card);
    });
  } catch (error) {
    console.error("[activity.js] failed to load activity:", error);
    feed.innerHTML = '<p class="user-profile-empty">Your activity is temporarily unavailable.</p>';
  }
}

loadOwnActivity();
