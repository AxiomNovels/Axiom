// Dedicated voting page. Identity and eligibility are checked by the API.
const VOTING_TRAITS = [
  ["impulsivity", "Impulsivity", "Deliberate → impulsive"],
  ["arrogance_pride", "Ego", "Humble → prideful"],
  ["kinship_friendship", "Kinship and Friendship", "Detached → devoted"],
  ["romantic_attachment", "Romantic Attachment", "Unattached → romance-driven"],
  ["sexual_desire", "Lust", "Absent → strongly driven"],
  ["selflessness", "Selflessness", "Self-interested → self-sacrificing"],
];
const voteDrafts = {};
async function loadProtagonistVotes(novelId, message = "") {
  const host = document.getElementById("protagonist-votes");
  if (!host) return;
  const node = (tag, text) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    return el;
  };
  async function call(trait = "", method = "GET", score) {
    const response = await authFetch(`${API_BASE}/api/novels/${novelId}/protagonist-votes${trait ? `/${trait}` : ""}`, {
      method,
      ...(score !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ score }) } : {}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Voting is temporarily unavailable.");
    return data;
  }
  try {
    const data = await call();
    host.replaceChildren();
    if (!data.eligible) {
      host.append(node("p", "Voting opens when all six protagonist scores are filled in."));
      return;
    }
    const summary = node("div"); summary.className = "voting-summary";
    summary.append(node("h3", "Protagonist traits"), node("span", `${data.voter_count} reader${data.voter_count === 1 ? "" : "s"} voted`));
    host.append(summary);
    if (data.scores_locked) host.append(node("p", "Scores locked by a moderator. Your votes are still collected, but the displayed scores stay fixed until unlocked."));
    const signedIn = Boolean(getAccessToken());
    if (!signedIn) {
      const login = node("a", "Log in to vote"); login.href = "/login.html";
      login.className = "voting-login"; host.append(login);
    }
    const feedback = node("p", message);
    feedback.setAttribute("role", "status"); feedback.setAttribute("aria-live", "polite");
    host.append(feedback);
    const fields = node("fieldset");
    fields.append(node("legend", "Rate individual traits from 0 to 100"));
    host.append(fields);
    for (const [key, title, poles] of VOTING_TRAITS) {
      const form = node("form"); form.className = "trait-vote-form";
      const description = node("div"); description.className = "vote-trait-description";
      description.append(node("h4", title), node("p", poles));
      const current = node("span", String(data.profile[key])); current.className = "vote-current";
      const currentLabel = node("div"); currentLabel.className = "vote-current-label";
      currentLabel.append(node("small", "Current"), current);
      const label = node("label", "Your score");
      const input = node("input");
      input.setAttribute("aria-label", title);
      input.type = "number"; input.min = "0"; input.max = "100"; input.step = "1"; input.required = true;
      input.value = voteDrafts[key] ?? data.my_votes[key] ?? "";
      input.placeholder = "0–100";
      input.addEventListener("input", () => { voteDrafts[key] = input.value; });
      label.append(input);
      const details = node("small", `Default: ${data.baseline[key]} · Your vote: ${data.my_votes[key] ?? "Not voted"}`);
      const save = node("button", Object.hasOwn(data.my_votes, key) ? "Update vote" : "Vote");
      save.type = "submit";
      const remove = node("button", "Remove"); remove.type = "button";
      remove.className = "vote-remove"; remove.hidden = !Object.hasOwn(data.my_votes, key);
      remove.disabled = !Object.hasOwn(data.my_votes, key);
      input.disabled = !signedIn; save.disabled = !signedIn;
      async function submit(method) {
        fields.disabled = true;
        feedback.textContent = "Saving…";
        try {
          const result = await call(key, method, method === "PUT" ? Number(input.value) : undefined);
          delete voteDrafts[key];
          const outcome = result.scores_locked ? "Locked scores unchanged." : "Profile recalculated.";
          await loadProtagonistVotes(novelId, `${method === "PUT" ? "Vote saved." : "Vote removed."} ${outcome}`);
        } catch (error) { feedback.textContent = error.message; }
        finally { fields.disabled = false; }
      }
      form.addEventListener("submit", event => { event.preventDefault(); submit("PUT"); });
      remove.addEventListener("click", () => submit("DELETE"));
      const controls = node("div"); controls.className = "vote-controls";
      controls.append(label, save, remove);
      description.append(details);
      form.append(description, currentLabel, controls); fields.append(form);
    }
    const help = node("details"); help.className = "voting-explanation";
    help.append(node("summary", "How your vote shapes the profile"), node("p", "Each unlocked score averages the saved default and one vote per reader. You can update or remove your vote at any time. Locked profiles collect votes without changing their scores."));
    host.append(help);
  } catch (error) {
    host.replaceChildren(node("p", error.message));
    const retry = node("button", "Retry voting"); retry.type = "button";
    retry.addEventListener("click", () => loadProtagonistVotes(novelId)); host.append(retry);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const novelId = new URLSearchParams(location.search).get("id");
  const host = document.getElementById("protagonist-votes");
  if (!novelId || !/^\d+$/.test(novelId)) {
    document.getElementById("voting-title").textContent = "No novel selected";
    host.textContent = "Open a novel and choose Vote on traits to get started.";
    return;
  }
  document.getElementById("vote-back").href = `/novel.html?id=${encodeURIComponent(novelId)}`;
  try {
    const response = await fetch(`${API_BASE}/api/novels/${novelId}`);
    if (!response.ok) throw new Error("This novel could not be loaded. Go back to the novel and try again.");
    const novel = await response.json();
    document.getElementById("voting-title").textContent = novel.title;
    document.getElementById("voting-author").textContent = novel.author ? `by ${novel.author}` : "";
    document.title = `Vote on ${novel.title} | Axiom`;
    await loadProtagonistVotes(novelId);
  } catch (error) {
    document.getElementById("voting-title").textContent = "Voting unavailable";
    host.textContent = error.message;
  }
});
