// Definition changes are staged locally and committed in one versioned transaction.
let definitionDraft = null;
let definitionOriginal = null;
let definitionDirty = false;
let definitionTraitIndex = 0;

async function loadDefinitionEditor() {
  if (definitionDirty && !confirm("Discard unsaved trait changes and reload?")) return;
  const fields = document.getElementById("definition-fields");
  const reload = document.getElementById("reload-definition");
  fields.disabled = reload.disabled = true;
  try {
    const data = await request("/protagonist-definition");
    definitionOriginal = structuredClone(data);
    definitionDraft = structuredClone(data);
    definitionDirty = false;
    renderDefinitionEditor();
    document.getElementById("definition-status").textContent = `Loaded revision ${data.revision}. Changes are saved only when you choose Save definition.`;
  } finally { fields.disabled = !definitionDraft; reload.disabled = false; }
}

function definitionImpact() {
  if (!definitionOriginal || !definitionDraft) return [];
  const sharedChanged = definitionOriginal.instructions !== definitionDraft.instructions;
  return definitionOriginal.traits.filter(old => {
    const trait = definitionDraft.traits.find(current => current.key === old.key);
    return sharedChanged || !trait || trait.name !== old.name || trait.prompt !== old.prompt;
  });
}

function updateDefinitionImpact() {
  definitionDirty = JSON.stringify(definitionDraft) !== JSON.stringify(definitionOriginal);
  const affected = definitionImpact();
  document.getElementById("definition-impact").textContent = affected.length
    ? `Saving clears scores, defaults, and reader votes across every novel (including locked profiles) for: ${affected.map(t => t.name).join(", ")}.`
    : "Existing trait data will be preserved. New traits start without scores.";
  document.getElementById("save-definition").disabled = !definitionDirty;
}

function renderDefinitionEditor() {
  const host = document.getElementById("definition-traits");
  host.replaceChildren();
  document.getElementById("definition-instructions").value = definitionDraft.instructions;
  definitionTraitIndex = Math.max(0, Math.min(definitionTraitIndex, definitionDraft.traits.length - 1));
  const trait = definitionDraft.traits[definitionTraitIndex];
  const navigation = element("nav", undefined, "definition-trait-navigation");
  navigation.setAttribute("aria-label", "Trait navigation");
  const previous = element("button", "‹", "definition-trait-arrow");
  previous.type = "button"; previous.disabled = definitionTraitIndex === 0;
  previous.setAttribute("aria-label", "Previous trait");
  previous.addEventListener("click", () => { definitionTraitIndex -= 1; renderDefinitionEditor(); });
  const steps = element("div", undefined, "definition-trait-steps");
  definitionDraft.traits.forEach((item, index) => {
    const step = element("button", String(index + 1), "definition-trait-step");
    step.type = "button"; step.title = item.name || `Trait ${index + 1}`;
    step.setAttribute("aria-label", `Edit trait ${index + 1}: ${item.name || "New trait"}`);
    step.setAttribute("aria-current", String(index === definitionTraitIndex));
    step.addEventListener("click", () => { definitionTraitIndex = index; renderDefinitionEditor(); });
    steps.append(step);
  });
  const next = element("button", "›", "definition-trait-arrow");
  next.type = "button"; next.disabled = definitionTraitIndex === definitionDraft.traits.length - 1;
  next.setAttribute("aria-label", "Next trait");
  next.addEventListener("click", () => { definitionTraitIndex += 1; renderDefinitionEditor(); });
  navigation.append(previous, steps, next);

  const card = element("section", undefined, "definition-trait");
  const heading = element("div", undefined, "definition-trait-heading");
  const traitNumber = element("span", `TRAIT ${definitionTraitIndex + 1} OF ${definitionDraft.traits.length}`, "definition-trait-number");
  const title = element("h3", trait.name || "New trait");
  heading.append(traitNumber, title);
  const fields = element("div", undefined, "definition-trait-fields");
  const nameLabel = element("label", "Trait name");
  const name = element("input"); name.value = trait.name; name.required = true; name.maxLength = 100;
  name.setAttribute("aria-label", `Trait name: ${trait.name || "New trait"}`);
  nameLabel.append(name);
  const keyLabel = element("label", "Trait key");
  const key = element("input"); key.value = trait.key; key.required = true; key.maxLength = 48;
  key.pattern = "[a-z][a-z0-9_]{0,47}";
  key.readOnly = definitionOriginal.traits.some(t => t.key === trait.key);
  keyLabel.append(key, element("small", "Unique lowercase key. Existing keys stay fixed when you rename a trait."));
  fields.append(nameLabel, keyLabel);
  const promptLabel = element("label", "Scoring prompt");
  const prompt = element("textarea"); prompt.rows = 12; prompt.value = trait.prompt; prompt.required = true; prompt.maxLength = 12000;
  promptLabel.append(prompt);
  name.addEventListener("input", () => { trait.name = name.value.trim(); title.textContent = trait.name || "New trait"; updateDefinitionImpact(); });
  key.addEventListener("input", () => { trait.key = key.value.trim(); updateDefinitionImpact(); });
  prompt.addEventListener("input", () => { trait.prompt = prompt.value.trim(); updateDefinitionImpact(); });
  const remove = action("Delete this trait", () => {
    definitionDraft.traits = definitionDraft.traits.filter(t => t !== trait);
    definitionTraitIndex = Math.min(definitionTraitIndex, definitionDraft.traits.length - 1);
    renderDefinitionEditor();
  });
  remove.disabled = definitionDraft.traits.length <= 1;
  card.append(heading, fields, promptLabel, remove);
  host.append(navigation, card);
  updateDefinitionImpact();
}

document.getElementById("definition-tab").addEventListener("click", () => {
  for (const section of ["users", "novels", "home", "definition"]) {
    document.getElementById(`${section}-panel`).hidden = section !== "definition";
    document.getElementById(`${section}-tab`).setAttribute("aria-pressed", String(section === "definition"));
  }
  if (!definitionDraft) loadDefinitionEditor().catch(error => status(error.message, true));
});
document.getElementById("reload-definition").addEventListener("click", () => loadDefinitionEditor().catch(error => status(error.message, true)));
document.getElementById("definition-instructions").addEventListener("input", event => {
  definitionDraft.instructions = event.target.value.trim(); updateDefinitionImpact();
});
document.getElementById("add-definition-trait").addEventListener("click", () => {
  if (!definitionDraft || definitionDraft.traits.length >= 50) return;
  definitionDraft.traits.push({ key: "", name: "", prompt: "" });
  definitionTraitIndex = definitionDraft.traits.length - 1;
  renderDefinitionEditor();
  document.querySelector(".definition-trait input").focus();
});
document.getElementById("definition-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!definitionDirty) return;
  if (dirty && !confirm("Saving the definition closes the open novel score editor and discards its unsaved edits. Continue?")) return;
  const affected = definitionImpact();
  if (!confirm(affected.length
    ? `Save this definition and permanently clear all novel scores, defaults, and votes for ${affected.map(t => t.name).join(", ")}? This cannot be undone.`
    : "Save the updated protagonist definition?")) return;
  const fields = document.getElementById("definition-fields");
  const reload = document.getElementById("reload-definition");
  const feedback = document.getElementById("definition-status");
  fields.disabled = reload.disabled = true; feedback.textContent = "Saving definition…";
  try {
    const saved = await request("/protagonist-definition", {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(definitionDraft),
    });
    definitionOriginal = structuredClone(saved); definitionDraft = structuredClone(saved);
    definitionDirty = false;
    renderDefinitionEditor();
    feedback.textContent = `Saved revision ${saved.revision}. ${affected.length ? "Affected trait data was cleared. Use the existing profile rebuild tools when ready." : "Existing trait data was preserved."}`;
    // Close stale scores and distributions; leave other admin sections intact.
    ++editorVersion; document.getElementById("profile-editor").replaceChildren(); dirty = false;
    ++voteViewVersion; voteView = null; document.getElementById("vote-workspace").hidden = true;
  } catch (error) { feedback.textContent = error.message; }
  finally { fields.disabled = reload.disabled = false; }
});
window.addEventListener("beforeunload", event => {
  if (definitionDirty) { event.preventDefault(); event.returnValue = ""; }
});
