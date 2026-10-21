// Natural Earth outlines and label points are projected together at build time.
const CONTINENT_COLORS = {
  "North America": "#c999e8", "South America": "#f0b276", Europe: "#80c6bd",
  Africa: "#ed9b9b", Asia: "#9fb8ee", Oceania: "#e8cf76", Antarctica: "#b6bbc8", Other: "#a5a5b8",
};
let countryMapVersion = 0;
let countryGeography;

function clearCountryMap(message) {
  ++countryMapVersion;
  document.getElementById("country-map").replaceChildren();
  document.getElementById("country-table-body").replaceChildren();
  document.getElementById("country-status").textContent = message;
}

function loadCountryGeography() {
  if (!countryGeography) {
    countryGeography = fetch("/assets/analytics-world.json").then(response => {
      if (!response.ok) throw new Error("Map unavailable");
      return response.json();
    }).catch(error => { countryGeography = null; throw error; });
  }
  return countryGeography;
}

function mapSvgNode(tag, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

async function renderCountryMap(countries) {
  clearCountryMap(countries.length ? "Loading map..." : "No measured browser visits for this range.");
  if (!countries.length) return;
  const version = countryMapVersion;
  const host = document.getElementById("country-map");
  const body = document.getElementById("country-table-body");
  let geography;
  try { geography = await loadCountryGeography(); }
  catch {
    if (version !== countryMapVersion) return;
    geography = { countries: [] };
  }
  if (version !== countryMapVersion) return;
  const locations = new Map(geography.countries.map(country => [country.code, country]));
  const rows = countries.map(country => ({ ...country, location: locations.get(country.code) }));
  // The table always includes every country, including Cloudflare's unknowns.
  rows.forEach(country => {
    const continent = country.location?.continent || "Other";
    const row = element("tr");
    const continentCell = element("td", continent);
    continentCell.style.color = CONTINENT_COLORS[continent] || CONTINENT_COLORS.Other;
    row.append(element("td", `${country.name} (${country.code})`), continentCell,
      element("td", formatTrafficNumber(country.visits)), element("td", formatTrafficNumber(country.page_views)));
    body.append(row);
  });
  if (!geography.countries.length) {
    document.getElementById("country-status").textContent = "Map could not load. Country visits are available in the table.";
    return;
  }
  const svg = mapSvgNode("svg", { viewBox: "0 0 1000 500", role: "group", "aria-label": "Browser visits by country" });
  const title = mapSvgNode("title"); title.textContent = "Website visits by country, excluding known bots"; svg.append(title);
  geography.countries.forEach(country => {
    svg.append(mapSvgNode("path", { d: country.path, class: "country-land", "fill-rule": "evenodd" }));
  });
  const max = Math.max(1, ...rows.map(country => country.visits));
  const tooltip = element("div", undefined, "country-map-tooltip");
  tooltip.hidden = true; tooltip.setAttribute("role", "tooltip");
  const bubbles = [];
  // Large circles go behind small circles so nearby low-traffic countries remain reachable.
  rows.filter(country => country.location && country.visits > 0)
    .sort((left, right) => right.visits - left.visits).forEach(country => {
      const [cx, cy] = country.location.point;
      const circle = mapSvgNode("circle", {
        cx, cy, r: 25 * Math.sqrt(country.visits / max), class: "country-bubble",
        fill: CONTINENT_COLORS[country.location.continent] || CONTINENT_COLORS.Other,
        tabindex: "0", role: "button", "data-country": country.code,
        "aria-label": `${country.name}: ${formatTrafficNumber(country.visits)} visits, ${formatTrafficNumber(country.page_views)} page views`,
      });
      const label = mapSvgNode("title"); label.textContent = circle.getAttribute("aria-label"); circle.append(label);
      function show() {
        bubbles.forEach(bubble => bubble.classList.remove("is-selected"));
        circle.classList.add("is-selected");
        tooltip.textContent = circle.getAttribute("aria-label"); tooltip.hidden = false;
        const bounds = circle.getBoundingClientRect();
        const mapBounds = host.getBoundingClientRect();
        const desiredLeft = bounds.left - mapBounds.left + bounds.width / 2;
        tooltip.style.left = `${Math.max(8, Math.min(desiredLeft, host.clientWidth - tooltip.offsetWidth - 8))}px`;
        tooltip.style.top = `${Math.max(8, bounds.top - mapBounds.top - tooltip.offsetHeight - 8)}px`;
      }
      function hide() { tooltip.hidden = true; circle.classList.remove("is-selected"); }
      circle.addEventListener("pointerenter", show);
      circle.addEventListener("pointerleave", hide);
      circle.addEventListener("focus", show); circle.addEventListener("blur", hide);
      circle.addEventListener("click", show);
      circle.addEventListener("keydown", event => {
        if (event.key === "Escape") hide();
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(); }
      });
      bubbles.push(circle); svg.append(circle);
    });
  const legend = element("div", undefined, "country-map-legend");
  Object.entries(CONTINENT_COLORS).forEach(([name, color]) => {
    if (!rows.some(country => (country.location?.continent || "Other") === name)) return;
    const item = element("span", undefined, "country-legend-item");
    item.style.setProperty("--continent-color", color); item.append(element("i"), element("span", name)); legend.append(item);
  });
  const credit = element("small", "Map: Natural Earth · circle area scales with visits", "country-map-credit");
  host.append(svg, tooltip, legend, credit);
  const unplaced = rows.filter(country => !country.location).length;
  document.getElementById("country-status").textContent =
    "Hover, tap, or focus a circle for visits and page views." + (unplaced ? ` ${unplaced} unmapped location(s) are included in the table.` : "");
}
