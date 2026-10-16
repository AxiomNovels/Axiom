// These pages are being written privately before their public launch. The
// content remains available to Admin Hub users for review; everyone else sees
// the launch placeholder.
async function revealAdminPreview() {
  const preview = document.querySelector("[data-admin-preview]");
  const placeholder = document.querySelector("[data-admin-preview-placeholder]");
  if (!preview || !placeholder) return;

  try {
    const response = await authFetch(`${API_BASE}/api/admin/me`);
    if (!response.ok) return;

    preview.hidden = false;
    placeholder.hidden = true;
    document.title = preview.dataset.previewTitle || document.title;
  } catch {
    // Guests and ordinary accounts intentionally stay on the placeholder.
  }
}

revealAdminPreview();
