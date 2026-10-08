function countryKey(value) {
  return String(value || "").trim().toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "");
}

const countriesByAlias = new Map();
COUNTRY_OPTIONS.forEach((country) => {
  country.aliases.forEach((alias) => countriesByAlias.set(countryKey(alias), country));
});

function countryFlag(code) {
  return String.fromCodePoint(...[...code].map((char) => 0x1F1E6 + char.charCodeAt(0) - 65));
}

function formatCountry(value, fallback = "Not specified") {
  const country = countriesByAlias.get(countryKey(value));
  return country ? `${countryFlag(country.code)} ${country.name}` : (String(value || "").trim() || fallback);
}

function setupCountryCombobox() {
  const input = document.getElementById("country-search");
  const field = document.getElementById("country");
  const list = document.getElementById("country-options");
  const help = document.getElementById("country-help");
  let matches = [];
  let active = -1;

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }

  function select(country) {
    field.value = country?.name || "";
    input.value = country ? formatCountry(country.name) : "";
    input.setCustomValidity("");
    help.textContent = "Choose a country, or leave it blank.";
    close();
  }

  function highlight(index) {
    active = index;
    [...list.querySelectorAll('[role="option"]')].forEach((option, i) => {
      option.setAttribute("aria-selected", String(i === active));
      if (i === active) {
        input.setAttribute("aria-activedescendant", option.id);
        option.scrollIntoView({ block: "nearest" });
      }
    });
  }

  function render() {
    const query = countryKey(input.value === formatCountry(field.value, "") ? "" : input.value);
    matches = [null, ...COUNTRY_OPTIONS.filter((country) =>
      country.aliases.some((alias) => countryKey(alias).includes(query)))];
    list.replaceChildren();
    matches.forEach((country, index) => {
      const option = document.createElement("div");
      option.id = `country-option-${index}`;
      option.role = "option";
      option.setAttribute("aria-selected", "false");
      option.textContent = country ? formatCountry(country.name) : "Not specified";
      option.addEventListener("mousedown", (event) => event.preventDefault());
      option.addEventListener("click", () => { select(country); input.focus(); close(); });
      list.appendChild(option);
    });
    if (matches.length === 1 && query) {
      const empty = document.createElement("p");
      empty.textContent = "No matching countries";
      list.appendChild(empty);
    }
    active = -1;
    input.removeAttribute("aria-activedescendant");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  input.addEventListener("focus", render);
  input.addEventListener("click", render);
  input.addEventListener("input", () => {
    field.value = "";
    input.setCustomValidity(input.value.trim() ? "Select a country from the dropdown." : "");
    render();
  });
  input.addEventListener("blur", close);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { close(); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (list.hidden) render();
      const next = active < 0
        ? (event.key === "ArrowDown" ? 0 : matches.length - 1)
        : (active + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length;
      highlight(next);
    } else if (event.key === "Enter" && !list.hidden) {
      event.preventDefault();
      const exact = countriesByAlias.get(countryKey(input.value));
      if (active >= 0) select(matches[active]);
      else if (exact) select(exact);
      else if (matches.length === 2) select(matches[1]);
    }
  });
  return (value) => {
    const country = countriesByAlias.get(countryKey(value));
    select(country);
    if (value && !country) {
      input.value = value;
      input.setCustomValidity("Choose a country from the list or clear this field.");
      help.textContent = `Previously saved: ${value}. Choose a country from the list or clear this field.`;
    }
  };
}
