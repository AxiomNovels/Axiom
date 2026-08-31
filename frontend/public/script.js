const API_BASE = "http://localhost:8000";
const COVER_CLASSES = ["cover-one", "cover-two", "cover-three", "cover-four", "cover-five"];

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("axiomUser"));
  } catch {
    return null;
  }
}

function getStoredSession() {
  try {
    return JSON.parse(localStorage.getItem("axiomSession"));
  } catch {
    return null;
  }
}

function getAccessToken() {
  return getStoredSession()?.access_token || null;
}

async function authFetch(url, options = {}) {
  const token = getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return fetch(url, { ...options, headers });
}

function getUserName(user) {
  if (!user) {
    return "";
  }

  return user.user_metadata?.username || user.email || "reader";
}

function updateAccountNav() {
  const guestActions = document.querySelector("[data-guest-actions]");
  const userActions = document.querySelector("[data-user-actions]");
  const userGreeting = document.querySelector("[data-user-greeting]");
  const logoutButton = document.querySelector("[data-logout-button]");

  if (!guestActions || !userActions || !userGreeting || !logoutButton) {
    return;
  }

  const user = getStoredUser();

  if (user) {
    guestActions.classList.add("is-hidden");
    userActions.classList.remove("is-hidden");
    userGreeting.textContent = `Hi ${getUserName(user)}`;

    if (!userActions.querySelector("[data-my-lists-link]")) {
      const myListsLink = document.createElement("a");
      myListsLink.href = "/lists.html";
      myListsLink.className = "my-lists-link";
      myListsLink.innerHTML = `
        <svg class="my-lists-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.5 6.5h5v13h-5z" />
          <path d="M9.5 3.5h5.5v16H9.5z" />
          <path d="m16 6.2 4.4-1 2.5 13.6-4.4.8z" />
          <path class="book-detail" d="M5 9h2M11 7h2.5m-2.5 9h2.5m5.9-7.7 1.3-.2M2 21h21" />
        </svg>
        <span>My Lists</span>`;
      myListsLink.setAttribute("data-my-lists-link", "");
      userActions.insertBefore(myListsLink, userGreeting);
    }

    if (!userActions.querySelector("[data-account-menu]")) {
      const accountMenu = document.createElement("details");
      accountMenu.className = "account-menu";
      accountMenu.setAttribute("data-account-menu", "");

      const accountTrigger = document.createElement("summary");
      accountTrigger.className = "account-trigger";
      accountTrigger.setAttribute("aria-label", "Open account menu");
      accountTrigger.textContent = getUserName(user).charAt(0).toUpperCase();

      const popover = document.createElement("div");
      popover.className = "account-popover";
      userGreeting.textContent = getUserName(user);

      const manageProfileLink = document.createElement("a");
      manageProfileLink.href = "/profile.html";
      manageProfileLink.className = "account-popover-link";
      manageProfileLink.setAttribute("data-manage-profile-link", "");
      manageProfileLink.textContent = "Manage profile";

      const uploadNovelLink = document.createElement("a");
      uploadNovelLink.href = "/upload.html";
      uploadNovelLink.className = "account-popover-link";
      uploadNovelLink.setAttribute("data-upload-novel-link", "");
      uploadNovelLink.textContent = "Upload a novel";

      popover.append(userGreeting, manageProfileLink, uploadNovelLink, logoutButton);
      accountMenu.append(accountTrigger, popover);
      userActions.appendChild(accountMenu);
    }
  } else {
    guestActions.classList.remove("is-hidden");
    userActions.classList.add("is-hidden");
    userGreeting.textContent = "";
  }

  logoutButton.addEventListener("click", () => {
    localStorage.removeItem("axiomUser");
    localStorage.removeItem("axiomSession");
    window.location.href = "/";
  });
}

updateAccountNav();

function showAuthError(form, message) {
  const errorEl = form.querySelector("[data-auth-error]");
  if (!errorEl) {
    alert(message);
    return;
  }
  errorEl.textContent = message;
  errorEl.classList.remove("is-hidden");
}

function clearAuthError(form) {
  const errorEl = form.querySelector("[data-auth-error]");
  if (!errorEl) return;
  errorEl.textContent = "";
  errorEl.classList.add("is-hidden");
}

document.querySelectorAll(".auth-form").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearAuthError(form);

    const password = form.querySelector("#password");
    const confirmPassword = form.querySelector("#confirm-password");

    if (password && confirmPassword && password.value !== confirmPassword.value) {
      showAuthError(form, "Those passwords don't match. Please re-enter them.");
      confirmPassword.focus();
      return;
    }

    const button = form.querySelector("button");
    const originalText = button.textContent;
    const isSignup = window.location.pathname.includes("signup");
    const endpoint = isSignup ? "/api/signup" : "/api/login";

    const payload = isSignup
      ? {
          email: form.querySelector("#email").value.trim(),
          username: form.querySelector("#username").value.trim(),
          password: password.value
        }
      : {
          identifier: form.querySelector("#identifier").value.trim(),
          password: password.value
        };

    button.textContent = "Working...";
    button.disabled = true;

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const message =
          (typeof result.detail === "string" && result.detail) ||
          (Array.isArray(result.detail) && result.detail[0]?.msg) ||
          result.error ||
          "Something went wrong. Please try again.";
        showAuthError(form, message);
        return;
      }

      localStorage.setItem("axiomUser", JSON.stringify(result.user));
      localStorage.setItem("axiomSession", JSON.stringify(result.session));

      // Once a session exists the user is properly logged in, so send them
      // straight to their reading lists. Without a session (e.g. email
      // confirmation is required after signup) there's nothing to show
      // there yet, so send them to log in instead.
      // New accounts land on their profile page first so they can fill in
      // preferences right away; logging back in later goes straight to
      // reading lists as before.
      let destination = "/login.html";
      if (result.session) {
        destination = isSignup ? "/profile.html" : "/lists.html";
      }
      window.location.href = destination;
    } catch (error) {
      showAuthError(form, "Couldn't reach the backend. Make sure it is running on port 8000.");
    } finally {
      button.textContent = originalText;
      button.disabled = false;
    }
  });
});

document.querySelectorAll(".search-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const input = form.querySelector("input[type='search']");
    const query = input.value.trim();
    if (!query) {
      event.preventDefault();
      input.focus();
    }
  });
});

function createNovelCard(novel, index) {
  const link = document.createElement("a");
  link.href = `/novel.html?id=${novel.id}`;
  link.className = "book-card-link";

  const article = document.createElement("article");
  article.className = "book-card";

  const cover = document.createElement("div");
  cover.className = `book-cover ${COVER_CLASSES[index % COVER_CLASSES.length]}`;
  if (novel.cover_image_url) {
    const coverImage = document.createElement("img");
    coverImage.className = "book-cover-image";
    coverImage.src = novel.cover_image_url;
    coverImage.alt = `${novel.title} cover`;
    coverImage.referrerPolicy = "no-referrer";
    coverImage.addEventListener("error", () => {
      coverImage.remove();
      const coverSpan = document.createElement("span");
      coverSpan.textContent = novel.title;
      cover.appendChild(coverSpan);
    }, { once: true });
    cover.appendChild(coverImage);
  } else {
    const coverSpan = document.createElement("span");
    coverSpan.textContent = novel.title;
    cover.appendChild(coverSpan);
  }

  const title = document.createElement("h3");
  title.textContent = novel.title;

  const blurb = document.createElement("p");
  const synopsis = novel.synopsis || "";
  blurb.textContent = synopsis.length > 90 ? `${synopsis.slice(0, 90)}...` : synopsis;

  article.appendChild(cover);
  article.appendChild(title);
  article.appendChild(blurb);
  link.appendChild(article);

  return link;
}

async function loadFeaturedNovels() {
  const grid = document.querySelector("[data-novel-grid]");
  if (!grid) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/novels/featured`);
    if (!response.ok) {
      throw new Error("Failed to load featured novels");
    }
    const novels = await response.json();

    grid.innerHTML = "";
    novels.forEach((novel, index) => {
      grid.appendChild(createNovelCard(novel, index));
    });
  } catch (error) {
    grid.innerHTML = "<p>Couldn't load novels. Make sure the backend is running on port 8000.</p>";
  }
}

loadFeaturedNovels();