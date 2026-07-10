const API_BASE = "http://localhost:8000";

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("axiomUser"));
  } catch {
    return null;
  }
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
      alert(isSignup ? "Account created." : "Logged in.");
      window.location.href = "/";
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
    event.preventDefault();

    const input = form.querySelector("input[type='search']");
    const query = input.value.trim();
    const message = query
      ? `Local demo only: search for "${query}" is not connected yet.`
      : "Try searching for a novel, theme, or philosophical mood.";

    alert(message);
  });
});
