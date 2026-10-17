// These private pages are available only to Admin Hub users. Everyone else is
// sent to one shared under-construction page.
async function revealAdminPreview() {
  const preview = document.querySelector("[data-admin-preview]");
  if (!preview) return;

  function showConstructionPage() {
    window.location.replace("/under-construction.html");
  }

  try {
    const response = await authFetch(`${API_BASE}/api/admin/me`);
    if (!response.ok) {
      showConstructionPage();
      return;
    }

    preview.hidden = false;
    document.title = preview.dataset.previewTitle || document.title;
  } catch {
    showConstructionPage();
  }
}

revealAdminPreview();
