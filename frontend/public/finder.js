const PROFILE_MEASURES = [
  ["impulsivity", "Impulsivity", "Deliberate", "Impulsive"],
  ["arrogance_pride", "Arrogance & pride", "Humble", "Proud"],
  ["kinship_friendship", "Kinship & friendship", "Detached", "Devoted"],
  ["romantic_attachment", "Romantic attachment", "Unattached", "Romantic"],
  ["sexual_desire", "Sexual desire", "Absent", "Prominent"],
  ["selflessness", "Selflessness", "Self-interested", "Self-sacrificing"]
];

const PHILOSOPHY_MEASURES = [
  ["freedom", "Freedom"], ["survival", "Survival"], ["existentialism", "Existentialism"],
  ["moral_ambiguity", "Moral ambiguity"], ["self_improvement", "Self-improvement"],
  ["determinism", "Determinism"], ["revenge", "Revenge"], ["romance", "Romance"]
].map(([key, label]) => [key, label, "Low emphasis", "Central theme"]);

const STORYTELLING_MEASURES = [
  ["political_intrigue", "Political intrigue"], ["psychological_warfare", "Psychological warfare"],
  ["kingdom_building", "Kingdom building"], ["action", "Action"], ["slice_of_life", "Slice of life"],
  ["mystery", "Mystery"], ["worldbuilding", "Worldbuilding"]
].map(([key, label]) => [key, label, "Light", "Prominent"]);

const selectedTags = { include: new Set(), exclude: new Set() };
let allTags = [];

function createProfileFilters(grid, measures) {
  const header = document.createElement("div");
  header.className = "profile-filter-header";
  header.innerHTML = "<span>Trait</span><span>Minimum</span><span>Maximum</span>";
  grid.appendChild(header);
  measures.forEach(([key, label, low, high]) => {
    const field = document.createElement("div");
    field.className = "profile-filter";
    field.innerHTML = `
      <div class="profile-filter-name">
        <strong>${label}</strong>
        <span>${low} <i aria-hidden="true">→</i> ${high}</span>
      </div>
      <label><span class="profile-input-label">Minimum ${label}</span><input name="${key}_min" type="number" min="0" max="100" placeholder="0"></label>
      <label><span class="profile-input-label">Maximum ${label}</span><input name="${key}_max" type="number" min="0" max="100" placeholder="100"></label>`;
    grid.appendChild(field);
  });
}

function syncTags() {
  document.querySelector("[data-included-tags]").value = [...selectedTags.include].join(",");
  document.querySelector("[data-excluded-tags]").value = [...selectedTags.exclude].join(",");
}

function renderSelectedTags() {
  const container = document.querySelector("[data-selected-tags]");
  container.innerHTML = "";
  const tags = [...selectedTags.include, ...selectedTags.exclude];
  if (!tags.length) {
    container.innerHTML = "<p>No tags added yet.</p>";
    syncTags();
    return;
  }
  tags.forEach((tag) => {
    const chip = document.createElement("div");
    chip.className = "selected-tag";
    chip.dataset.state = selectedTags.exclude.has(tag) ? "exclude" : "include";
    const name = document.createElement("span"); name.textContent = tag;
    const toggle = document.createElement("button"); toggle.type = "button"; toggle.className = "tag-toggle";
    toggle.textContent = selectedTags.exclude.has(tag) ? "Excluded" : "Included";
    toggle.addEventListener("click", () => {
      if (selectedTags.include.delete(tag)) selectedTags.exclude.add(tag);
      else { selectedTags.exclude.delete(tag); selectedTags.include.add(tag); }
      renderSelectedTags();
    });
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "tag-remove"; remove.textContent = "×"; remove.setAttribute("aria-label", `Remove ${tag}`);
    remove.addEventListener("click", () => { selectedTags.include.delete(tag); selectedTags.exclude.delete(tag); renderSelectedTags(); renderSuggestions(); });
    chip.append(name, toggle, remove); container.appendChild(chip);
  });
  syncTags();
}

function addTag(tag) {
  if (!selectedTags.include.has(tag) && !selectedTags.exclude.has(tag)) selectedTags.include.add(tag);
  const input = document.getElementById("tag-search"); input.value = ""; input.focus();
  renderSelectedTags(); renderSuggestions();
}

function renderSuggestions() {
  const input = document.getElementById("tag-search");
  const list = document.querySelector("[data-tag-suggestions]");
  const query = input.value.trim().toLowerCase();
  if (!query) { list.hidden = true; input.setAttribute("aria-expanded", "false"); return; }
  const matches = allTags.filter((tag) => tag.toLowerCase().includes(query) && !selectedTags.include.has(tag) && !selectedTags.exclude.has(tag)).slice(0, 8);
  list.innerHTML = "";
  matches.forEach((tag) => {
    const option = document.createElement("button"); option.type = "button"; option.role = "option"; option.textContent = tag;
    option.addEventListener("click", () => addTag(tag)); list.appendChild(option);
  });
  if (!matches.length) { const empty = document.createElement("p"); empty.textContent = "No matching tags"; list.appendChild(empty); }
  list.hidden = false; input.setAttribute("aria-expanded", "true");
}

async function loadOptions() {
  const tagInput = document.getElementById("tag-search");
  const status = document.querySelector("select[name='status']");
  try {
    const response = await fetch(`${API_BASE}/api/search/options`);
    if (!response.ok) throw new Error("Options request failed");
    const options = await response.json();
    allTags = options.tags || [];
    tagInput.disabled = !allTags.length;
    tagInput.placeholder = allTags.length ? "Start typing a tag..." : "No tags are available yet";
    (options.statuses || []).forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value.charAt(0).toUpperCase() + value.slice(1);
      status.appendChild(option);
    });
  } catch {
    tagInput.disabled = true;
    tagInput.placeholder = "Couldn't load tags";
  }
}

const tagInput = document.getElementById("tag-search");
tagInput.addEventListener("input", renderSuggestions);
tagInput.addEventListener("focus", renderSuggestions);
tagInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const first = document.querySelector("[data-tag-suggestions] button");
    if (first) { event.preventDefault(); first.click(); }
  }
  if (event.key === "Escape") { document.querySelector("[data-tag-suggestions]").hidden = true; tagInput.setAttribute("aria-expanded", "false"); }
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".tag-combobox")) { document.querySelector("[data-tag-suggestions]").hidden = true; tagInput.setAttribute("aria-expanded", "false"); }
});

const finderForm = document.querySelector("[data-finder-form]");

finderForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const compactParams = new URLSearchParams();
  new FormData(finderForm).forEach((value, key) => {
    const cleanValue = String(value).trim();
    if (!cleanValue) return;
    if (key === "tag_mode" && cleanValue === "and") return;
    compactParams.set(key, cleanValue);
  });
  const query = compactParams.toString();
  window.location.href = query ? `/search.html?${query}` : "/search.html";
});

finderForm.addEventListener("reset", () => {
  selectedTags.include.clear();
  selectedTags.exclude.clear();
  setTimeout(() => { renderSelectedTags(); renderSuggestions(); }, 0);
});

createProfileFilters(document.querySelector('[data-profile-filters="protagonist"]'), PROFILE_MEASURES);
createProfileFilters(document.querySelector('[data-profile-filters="philosophy"]'), PHILOSOPHY_MEASURES);
createProfileFilters(document.querySelector('[data-profile-filters="storytelling"]'), STORYTELLING_MEASURES);
loadOptions();
