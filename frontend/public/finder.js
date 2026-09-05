const PROFILE_MEASURES = [
  ["impulsivity", "Impulsivity", "Deliberate", "Impulsive"],
  ["arrogance_pride", "Ego", "Humble", "Egotistical"],
  ["kinship_friendship", "Kinship & friendship", "Detached", "Devoted"],
  ["romantic_attachment", "Romantic attachment", "Unattached", "Romantic"],
  ["sexual_desire", "Lust", "Absent", "Dominant"],
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

function setupRatingFilter() {
  const stars = document.querySelector("[data-rating-stars]");
  const valueField = document.querySelector("[data-rating-value]");
  const output = document.querySelector("[data-rating-output]");
  const clearButton = document.querySelector("[data-rating-clear]");
  if (!stars || !valueField || !output || !clearButton) return;

  let selectedRating = 0;
  let previewRating = 0;

  function ratingLabel(rating) {
    return rating ? `${rating} ${rating === 1 ? "star" : "stars"} & up` : "Any rating";
  }

  function renderRating(rating, isPreview = false) {
    output.value = ratingLabel(rating);
    output.classList.toggle("is-preview", isPreview && rating !== selectedRating);
    stars.querySelectorAll("[data-star]").forEach((button) => {
      const star = Number(button.dataset.star);
      const fill = rating >= star ? "full" : rating === star - 0.5 ? "half" : "empty";
      button.dataset.fill = fill;
      button.setAttribute("aria-pressed", String(fill !== "empty"));
    });
  }

  function setRating(value) {
    selectedRating = Math.max(0, Math.min(5, Math.round(Number(value) * 2) / 2));
    previewRating = selectedRating;
    valueField.value = selectedRating || "";
    clearButton.hidden = !selectedRating;
    stars.setAttribute("aria-valuenow", String(selectedRating));
    stars.setAttribute("aria-valuetext", ratingLabel(selectedRating));
    renderRating(selectedRating);
  }

  function ratingFromPointer(clientX) {
    const buttons = [...stars.querySelectorAll("[data-star]")];
    for (const button of buttons) {
      const box = button.getBoundingClientRect();
      if (clientX <= box.right) {
        return Number(button.dataset.star) - (clientX < box.left + box.width / 2 ? 0.5 : 0);
      }
    }
    return 5;
  }

  function previewFromPointer(event) {
    if (selectedRating) return;
    previewRating = ratingFromPointer(event.clientX);
    renderRating(previewRating, true);
  }

  stars.addEventListener("pointermove", previewFromPointer);

  stars.addEventListener("click", (event) => {
    setRating(ratingFromPointer(event.clientX));
  });

  stars.addEventListener("pointerleave", () => {
    renderRating(selectedRating);
  });

  stars.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = Number(valueField.value) || 0;
    if (event.key === "Home") setRating(0.5);
    else if (event.key === "End") setRating(5);
    else setRating(current + (["ArrowRight", "ArrowUp"].includes(event.key) ? 0.5 : -0.5));
  });

  clearButton.addEventListener("click", () => {
    setRating(0);
  });
  setRating(0);
}

function createProfileFilters(grid, measures) {
  const header = document.createElement("div");
  header.className = "profile-filter-header";
  header.innerHTML = "<span>Trait</span><span>Selected range</span>";
  grid.appendChild(header);

  measures.forEach(([key, label, low, high]) => {
    const field = document.createElement("div");
    field.className = "profile-filter";

    field.innerHTML = `
      <div class="profile-filter-name">
        <label class="profile-filter-toggle">
          <input
            type="checkbox"
            class="profile-filter-checkbox"
            data-profile-enabled
            aria-label="Use ${label} as a search filter"
          >
          <span class="profile-checkbox-box" aria-hidden="true"></span>
          <span class="profile-filter-label">
            <strong>${label}</strong>
            <small>${low} <i aria-hidden="true">→</i> ${high}</small>
          </span>
        </label>
      </div>

      <div
        class="profile-range is-disabled"
        data-profile-range
        style="--range-min:0%; --range-max:100%"
      >
        <div class="profile-range-values" aria-hidden="true">
          <output data-range-min>0</output>
          <span>to</span>
          <output data-range-max>100</output>
        </div>

        <div class="profile-range-track" aria-hidden="true"></div>

        <input
          class="profile-range-input range-min"
          type="range"
          min="0"
          max="100"
          value="0"
          aria-label="Minimum ${label}"
          disabled
        >

        <input
          class="profile-range-input range-max"
          type="range"
          min="0"
          max="100"
          value="100"
          aria-label="Maximum ${label}"
          disabled
        >

        <input
          type="hidden"
          name="${key}_min"
          data-range-min-field
        >

        <input
          type="hidden"
          name="${key}_max"
          data-range-max-field
        >
      </div>
    `;

    grid.appendChild(field);

    const range = field.querySelector("[data-profile-range]");
    const minSlider = range.querySelector(".range-min");
    const maxSlider = range.querySelector(".range-max");
    const minField = range.querySelector("[data-range-min-field]");
    const maxField = range.querySelector("[data-range-max-field]");
    const minOutput = range.querySelector("[data-range-min]");
    const maxOutput = range.querySelector("[data-range-max]");
    const checkbox = field.querySelector("[data-profile-enabled]");

    function syncRange(changedSlider) {
      if (Number(minSlider.value) > Number(maxSlider.value)) {
        if (changedSlider === minSlider) {
          maxSlider.value = minSlider.value;
        } else {
          minSlider.value = maxSlider.value;
        }
      }

      const minimum = Number(minSlider.value);
      const maximum = Number(maxSlider.value);

      range.style.setProperty("--range-min", `${minimum}%`);
      range.style.setProperty("--range-max", `${maximum}%`);

      minOutput.value = minimum;
      maxOutput.value = maximum;

      // Only submit the range when this trait is enabled.
      // Unlike the previous implementation, 0 and 100 are
      // intentionally preserved when the trait is checked.
      if (checkbox.checked) {
        minField.value = minimum;
        maxField.value = maximum;
      } else {
        minField.value = "";
        maxField.value = "";
      }
    }

    function syncEnabledState() {
      const enabled = checkbox.checked;

      minSlider.disabled = !enabled;
      maxSlider.disabled = !enabled;

      range.classList.toggle("is-disabled", !enabled);
      field.classList.toggle("is-enabled", enabled);

      syncRange();
    }

    checkbox.addEventListener("change", syncEnabledState);
    minSlider.addEventListener("input", () => syncRange(minSlider));
    maxSlider.addEventListener("input", () => syncRange(maxSlider));

    // Initial state: trait is not part of the search.
    syncEnabledState();
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

  setTimeout(() => {
    document.querySelector("[data-rating-clear]")?.click();
    renderSelectedTags();
    renderSuggestions();

    document.querySelectorAll("[data-profile-range]").forEach((range) => {
      const field = range.closest(".profile-filter");
      const checkbox = field.querySelector("[data-profile-enabled]");
      const minSlider = range.querySelector(".range-min");
      const maxSlider = range.querySelector(".range-max");
      const minField = range.querySelector("[data-range-min-field]");
      const maxField = range.querySelector("[data-range-max-field]");

      checkbox.checked = false;

      minSlider.value = 0;
      maxSlider.value = 100;
      minSlider.disabled = true;
      maxSlider.disabled = true;

      minField.value = "";
      maxField.value = "";

      range.style.setProperty("--range-min", "0%");
      range.style.setProperty("--range-max", "100%");

      range.querySelector("[data-range-min]").value = 0;
      range.querySelector("[data-range-max]").value = 100;

      range.classList.add("is-disabled");
      field.classList.remove("is-enabled");
    });
  }, 0);
});

createProfileFilters(document.querySelector('[data-profile-filters="protagonist"]'), PROFILE_MEASURES);
createProfileFilters(document.querySelector('[data-profile-filters="philosophy"]'), PHILOSOPHY_MEASURES);
createProfileFilters(document.querySelector('[data-profile-filters="storytelling"]'), STORYTELLING_MEASURES);
setupRatingFilter();
loadOptions();
