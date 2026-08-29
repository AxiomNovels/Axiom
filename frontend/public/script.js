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

// Wrapper around fetch that attaches the logged-in user's Supabase access
// token, so the backend can tell which account a reading-list request
// belongs to. Falls back to a plain, unauthenticated fetch when logged out.
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

  return user.user_metadata?.display_name || user.email || "reader";
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
      myListsLink.textContent = "My Lists";
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
      popover.append(userGreeting, logoutButton);
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

document.querySelectorAll(".auth-form").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = form.querySelector("#email");
    const password = form.querySelector("#password");
    const confirmPassword = form.querySelector("#confirm-password");

    if (password && confirmPassword && password.value !== confirmPassword.value) {
      alert("Passwords do not match.");
      confirmPassword.focus();
      return;
    }

    const button = form.querySelector("button");
    const originalText = button.textContent;
    const isSignup = window.location.pathname.includes("signup");
    const endpoint = isSignup ? "/api/signup" : "/api/login";

    button.textContent = "Working...";
    button.disabled = true;

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          email: email.value.trim(),
          password: password.value
        })
      });

      const result = await response.json();

      if (!response.ok) {
        const message = result.error || result.detail || "Something went wrong.";
        alert(Array.isArray(message) ? message[0]?.msg || "Something went wrong." : message);
        return;
      }

      localStorage.setItem("axiomUser", JSON.stringify(result.user));
      localStorage.setItem("axiomSession", JSON.stringify(result.session));

      // Once a session exists the user is properly logged in, so send them
      // straight to their reading lists. Without a session (e.g. email
      // confirmation is required after signup) there's nothing to show
      // there yet, so send them to log in instead.
      const destination = result.session ? "/lists.html" : "/login.html";
      alert(isSignup ? "Account created." : "Logged in.");
      window.location.href = destination;
    } catch (error) {
      alert("Could not reach the backend. Make sure it is running on port 8000.");
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
    // Some book CDNs reject hotlinks when the requesting page is sent as the
    // Referer. An <img> lets us suppress it and detect failed image loads.
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
