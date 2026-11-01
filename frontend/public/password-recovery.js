(() => {
  const form = document.querySelector('[data-password-form]');
  if (!form) return;
  const isReset = form.dataset.passwordForm === 'reset';
  // Read and remove recovery credentials before shared scripts or analytics run.
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  let accessToken = isReset && fragment.get('type') === 'recovery' ? fragment.get('access_token') : null;
  let refreshToken = accessToken ? fragment.get('refresh_token') : null;
  if (isReset) window.history.replaceState(null, '', window.location.pathname);
  const error = form.querySelector('[data-auth-error]');
  const status = form.querySelector('[data-password-status]');
  const button = form.querySelector('button');

  function showError(message) {
    error.textContent = message;
    error.classList.remove('is-hidden');
  }

  if (isReset && (!accessToken || !refreshToken)) {
    showError('This reset link is missing, invalid, or expired. Please request a new reset link.');
    form.querySelectorAll('input, button').forEach((element) => { element.disabled = true; });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    error.classList.add('is-hidden');
    status.classList.add('is-hidden');
    if (isReset && (!accessToken || !refreshToken)) return;
    if (isReset && form.elements.password.value !== form.elements['confirm-password'].value) {
      showError('Those passwords don’t match. Please re-enter them.');
      form.elements['confirm-password'].focus();
      return;
    }
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Working...';
    let completed = false;
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (isReset) headers.Authorization = `Bearer ${accessToken}`;
      const response = await fetch(`${API_BASE}/api/password/${isReset ? 'reset' : 'forgot'}`, {
        method: 'POST', headers,
        body: JSON.stringify(isReset
          ? { password: form.elements.password.value, refresh_token: refreshToken }
          : { email: form.elements.email.value.trim() })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        showError(typeof result.detail === 'string' ? result.detail : 'Something went wrong. Please try again.');
        return;
      }
      completed = true;
      status.textContent = result.message;
      status.classList.remove('is-hidden');
      if (isReset) {
        accessToken = null;
        refreshToken = null;
        clearAuthState();
        form.querySelectorAll('input').forEach((input) => { input.value = ''; input.disabled = true; });
      }
    } catch {
      showError('Couldn’t connect. Please check your connection and try again.');
    } finally {
      button.textContent = completed ? (isReset ? 'Password updated' : 'Reset link requested') : originalText;
      button.disabled = completed;
    }
  });
})();
