// Shared by the Admin Hub and novel detail page; permissions are enforced by API.
async function confirmNovelDeletion(novel) {
  if (!confirm(`Permanently delete “${novel.title}” from Axiom for violating its content policy?\n\nThis removes all associated novel data, including reviews and votes, and cannot be undone. Readers who saved or uploaded it will receive an Inbox notice.`)) return false;
  const response = await authFetch(`${API_BASE}/api/admin/novels/${encodeURIComponent(novel.id)}`, { method: "DELETE" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "The novel could not be deleted. Please try again.");
  return true;
}
