document.querySelectorAll(".auth-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();

    const password = form.querySelector("#password");
    const confirmPassword = form.querySelector("#confirm-password");

    if (password && confirmPassword && password.value !== confirmPassword.value) {
      alert("Passwords do not match.");
      confirmPassword.focus();
      return;
    }

    const button = form.querySelector("button");
    const originalText = button.textContent;
    const message = form.dataset.demoMessage || "Local demo only: authentication is not connected yet.";

    button.textContent = "Working...";
    button.disabled = true;

    window.setTimeout(() => {
      button.textContent = originalText;
      button.disabled = false;
      alert(message);
    }, 600);
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
