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
            <small>${low} <i aria-hidden="true">â†’</i> ${high}</small>
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

const tagFields = [...document.querySelectorAll("[data-tag-field]")];

function renderSelectedTags() {
  tagFields.forEach((field) => {
    const mode = field.dataset.tagField;
    const container = field.querySelector("[data-selected-tags]");
    container.replaceChildren();
    selectedTags[mode].forEach((tag) => {
      const chip = document.createElement("div");
      chip.className = "selected-tag";
      chip.dataset.state = mode;
      const name = document.createElement("span");
      name.textContent = tag;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "tag-remove";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Remove ${tag} from ${mode === "include" ? "included" : "excluded"} tags`);
      remove.addEventListener("click", () => {
        selectedTags[mode].delete(tag);
        renderSelectedTags();
        field.querySelector("input").focus();
      });
      chip.append(name, remove);
      container.appendChild(chip);
    });
  });
  syncTags();
}

function closeSuggestions(field) {
  field.querySelector("[data-tag-suggestions]").hidden = true;
  field.querySelector("input").setAttribute("aria-expanded", "false");
}

function addTag(tag, field) {
  const mode = field.dataset.tagField;
  selectedTags[mode === "include" ? "exclude" : "include"].delete(tag);
  selectedTags[mode].add(tag);
  const input = field.querySelector("input");
  input.value = "";
  input.focus();
  renderSelectedTags();
  closeSuggestions(field);
}

function renderSuggestions(field) {
  const input = field.querySelector("input");
  const list = field.querySelector("[data-tag-suggestions]");
  const query = input.value.trim().toLowerCase();
  if (!query) { closeSuggestions(field); return; }
  const matches = allTags.filter((tag) => tag.toLowerCase().includes(query) && !selectedTags[field.dataset.tagField].has(tag)).slice(0, 8);
  list.replaceChildren();
  matches.forEach((tag) => {
    const option = document.createElement("button");
    option.type = "button";
    option.role = "option";
    option.textContent = tag;
    option.addEventListener("click", () => addTag(tag, field));
    list.appendChild(option);
  });
  if (!matches.length) {
    const empty = document.createElement("p");
    empty.textContent = "No matching tags";
    list.appendChild(empty);
  }
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
}

async function loadOptions() {
  const tagInputs = tagFields.map((field) => field.querySelector("input"));
  const status = document.querySelector("select[name='status']");
  try {
    const response = await fetch(`${API_BASE}/api/search/options`);
    if (!response.ok) throw new Error("Options request failed");
    const options = await response.json();
    allTags = options.tags || [];
    tagInputs.forEach((input, index) => {
      input.disabled = !allTags.length;
      input.placeholder = allTags.length ? `Search tags to ${tagFields[index].dataset.tagField}...` : "No tags are available yet";
    });
    (options.statuses || []).forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value.charAt(0).toUpperCase() + value.slice(1);
      status.appendChild(option);
    });
  } catch {
    tagInputs.forEach((input) => {
      input.disabled = true;
      input.placeholder = "Couldn't load tags";
    });
  }
}

tagFields.forEach((field) => {
  const input = field.querySelector("input");
  const list = field.querySelector("[data-tag-suggestions]");
  input.addEventListener("input", () => renderSuggestions(field));
  input.addEventListener("focus", () => {
    tagFields.filter((other) => other !== field).forEach(closeSuggestions);
    renderSuggestions(field);
  });
  field.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      input.focus();
      closeSuggestions(field);
    }
    if (event.key === "Enter" && event.target === input && !list.hidden) {
      event.preventDefault();
      list.querySelector("button")?.click();
    }
    if (["ArrowDown", "ArrowUp"].includes(event.key) && !list.hidden) {
      const options = [...list.querySelectorAll("button")];
      if (!options.length) return;
      event.preventDefault();
      const index = options.indexOf(document.activeElement);
      options[(index + (event.key === "ArrowDown" ? 1 : options.length - 1)) % options.length].focus();
    }
  });
  field.addEventListener("focusout", (event) => {
    if (!field.contains(event.relatedTarget)) closeSuggestions(field);
  });
});
document.addEventListener("click", (event) => {
  tagFields.forEach((field) => {
    if (!field.contains(event.target)) closeSuggestions(field);
  });
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
    tagFields.forEach(closeSuggestions);

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
