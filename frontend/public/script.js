const form = document.querySelector(".login-form");

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const button = form.querySelector("button");

  button.textContent = "Logging in...";
  button.disabled = true;

  window.setTimeout(() => {
    button.textContent = "Log in";
    button.disabled = false;
    alert("Local demo only: authentication is not connected yet.");
  }, 600);
});
