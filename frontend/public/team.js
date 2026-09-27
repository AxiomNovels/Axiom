async function loadTeamAvatars() {
  try {
    const response = await fetch(`${API_BASE}/api/team`);
    const payload = await response.json();
    if (!response.ok) return;
    const members = new Map((payload.members || []).map((member) => [member.username.toLowerCase(), member]));
    document.querySelectorAll("[data-team-member]").forEach((card) => {
      const member = members.get(card.dataset.teamMember);
      if (!member) return;
      const specialBadge = card.querySelector("[data-team-special-badge]");
      if (specialBadge) specialBadge.hidden = !member.special;
      if (!member.avatar_url) return;
      const avatar = card.querySelector(".team-avatar");
      avatar.replaceChildren();
      const image = document.createElement("img");
      image.src = member.avatar_url;
      image.alt = `${member.username} profile picture`;
      image.referrerPolicy = "no-referrer";
      avatar.appendChild(image);
    });
  } catch {
    // The styled initials remain useful if a profile image cannot load.
  }
}

loadTeamAvatars();
