// Definition changes are staged locally and committed in one versioned transaction.
let definitionDraft = null;
let definitionOriginal = null;
let definitionDirty = false;

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
  for (const trait of definitionDraft.traits) {
    const card = element("section", undefined, "definition-trait");
    const nameLabel = element("label", "Trait name");
    const name = element("input"); name.value = trait.name; name.required = true; name.maxLength = 100;
    name.setAttribute("aria-label", `Trait name: ${trait.name || "New trait"}`);
    nameLabel.append(name);
    const keyLabel = element("label", "Trait key");
    const key = element("input"); key.value = trait.key; key.required = true; key.maxLength = 48;
    key.pattern = "[a-z][a-z0-9_]{0,47}";
    key.readOnly = definitionOriginal.traits.some(t => t.key === trait.key);
    keyLabel.append(key, element("small", "Unique lowercase key. Existing keys stay fixed when you rename a trait."));
    const promptLabel = element("label", "Scoring prompt");
    const prompt = element("textarea"); prompt.rows = 12; prompt.value = trait.prompt; prompt.required = true; prompt.maxLength = 12000;
    promptLabel.append(prompt);
    name.addEventListener("input", () => { trait.name = name.value.trim(); updateDefinitionImpact(); });
    key.addEventListener("input", () => { trait.key = key.value.trim(); updateDefinitionImpact(); });
    prompt.addEventListener("input", () => { trait.prompt = prompt.value.trim(); updateDefinitionImpact(); });
    const remove = action("Delete trait", () => {
      definitionDraft.traits = definitionDraft.traits.filter(t => t !== trait);
      renderDefinitionEditor();
    });
    remove.disabled = definitionDraft.traits.length <= 1;
    card.append(nameLabel, keyLabel, promptLabel, remove);
    host.append(card);
  }
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
  renderDefinitionEditor();
  document.querySelector(".definition-trait:last-child input").focus();
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
