let voteView = null;
let voteViewVersion = 0;
const VOTE_LABELS = {
  impulsivity: "Impulsivity", arrogance_pride: "Ego", kinship_friendship: "Kinship and Friendship",
  romantic_attachment: "Romantic Attachment", sexual_desire: "Lust", selflessness: "Selflessness",
};

async function deleteAllUserVotes(id, name) {
  if (!confirm(`Delete ALL protagonist trait votes by ${name} across every novel? Unlocked profiles will be recalculated; locked scores stay fixed.`)) return;
  await request(`/users/${id}/protagonist-votes`, { method: "DELETE" });
  await refreshVoteWorkspace();
  status(`All votes by ${name} deleted. Unlocked profiles recalculated; locked scores unchanged.`);
}

async function refreshVoteWorkspace() {
  // Scores in an already-open editor may now be stale. Preserve unsaved work,
  // otherwise close it so reopening fetches the newly recalibrated scores.
  if (!dirty) {
    ++editorVersion;
    document.getElementById("profile-editor").replaceChildren();
  }
  if (voteView) await openVotes(voteView.kind, voteView.id, voteView.name, voteView.page, false);
}

async function openVotes(kind, id, name, page = 1, scroll = true) {
  const version = ++voteViewVersion;
  const data = await request(`/${kind}/${id}/protagonist-votes?page=${page}`);
  if (version !== voteViewVersion) return;
  if (!data.votes.length && page > 1) return openVotes(kind, id, name, page - 1, scroll);
  voteView = { kind, id, name, page };
  const host = document.getElementById("vote-workspace");
  host.hidden = false;
  host.replaceChildren(element("p", "COMMUNITY VOTES", "eyebrow"), element("h2", name));
  if (kind === "users") host.append(action("Delete all votes by this user", () => deleteAllUserVotes(id, name)));
  if (data.summary) {
    const summary = data.summary;
    host.append(element("p", `${summary.voter_count} reader${summary.voter_count === 1 ? "" : "s"} · ${summary.vote_count} trait vote${summary.vote_count === 1 ? "" : "s"}. The default counts as one score in each unlocked trait's average.`));
    if (!summary.eligible) host.append(element("p", "Voting opens when all six protagonist scores are filled in, including zeros."));
    host.append(element("p", summary.scores_locked
      ? "Scores locked. Votes are collected without changing the displayed profile. Moderators can still edit scores."
      : "Scores unlocked. Reader votes can change this profile."));
    if (summary.profile) host.append(action(summary.scores_locked ? "Unlock scores" : "Lock scores", async () => {
      if (summary.scores_locked && !confirm("Unlock all protagonist scores? They will immediately recalculate using the defaults and all current votes.")) return;
      await request(`/novels/${id}/protagonist-score-lock`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locked: !summary.scores_locked }),
      });
      await refreshVoteWorkspace();
      status(summary.scores_locked ? "Scores unlocked and recalculated." : "All protagonist scores locked. Votes will still be collected.");
    }));
    const grid = element("div", undefined, "vote-distributions");
    for (const [trait, label] of Object.entries(VOTE_LABELS)) {
      const card = element("section", undefined, "vote-distribution");
      card.append(element("h3", label), element("p", `Default: ${summary.baseline?.[trait] ?? "Not set"} · Current: ${summary.profile?.[trait] ?? "Not set"}`));
      const bins = summary.distribution[trait] || [];
      const total = bins.reduce((sum, bin) => sum + bin.count, 0);
      card.append(element("small", `${total} reader vote${total === 1 ? "" : "s"}`));
      if (!bins.length) card.append(element("p", "No votes yet."));
      for (const bin of bins) {
        const row = element("div", undefined, "vote-bin");
        const bar = element("meter"); bar.min = 0; bar.max = total; bar.value = bin.count;
        bar.setAttribute("aria-label", `${label}, score ${bin.score}: ${bin.count} votes`);
        row.append(element("span", String(bin.score)), bar, element("span", `${bin.count} (${Math.round(bin.count / total * 100)}%)`));
        card.append(row);
      }
      grid.append(card);
    }
    host.append(grid);
  }
  host.append(element("h3", "Individual votes"));
  if (!data.votes.length) host.append(element("p", "No votes found."));
  for (const vote of data.votes) {
    const row = element("div", undefined, "admin-row vote-record");
    const username = vote.profiles?.username || vote.user_id;
    const title = vote.novels?.novels?.title || `Novel ${vote.novel_id}`;
    const description = element("div", `${kind === "novels" ? username : title} · ${VOTE_LABELS[vote.trait]}: ${vote.score}`);
    description.append(element("small", `User: ${vote.user_id} · Updated ${new Date(vote.updated_at).toLocaleString()}`));
    row.append(description);
    if (kind === "novels") row.append(action("All votes by user", () => openVotes("users", vote.user_id, username)));
    row.append(action("Delete vote", async () => {
      if (!confirm(`Delete this ${VOTE_LABELS[vote.trait]} vote (${vote.score})? Unlocked scores will be recalculated; locked scores stay fixed.`)) return;
      await request(`/protagonist-votes/${vote.id}`, { method: "DELETE" });
      await refreshVoteWorkspace(); status("Vote deleted. Unlocked scores recalculated; locked scores unchanged.");
    }));
    host.append(row);
  }
  const pages = element("div", undefined, "admin-pages");
  const previous = action("Previous", () => openVotes(kind, id, name, page - 1)); previous.disabled = page === 1;
  const next = action("Next", () => openVotes(kind, id, name, page + 1)); next.disabled = page * 25 >= data.total;
  pages.append(previous, element("span", `Page ${page} · ${data.total} votes`), next); host.append(pages);
  if (scroll) host.scrollIntoView({ behavior: "smooth", block: "start" });
}
