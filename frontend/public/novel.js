// Snake_case key -> display label, matching the trait definitions discussed
// for the info page. Kept here too so this page can render nice labels
// without depending on that endpoint existing yet.
const TRAIT_LABELS = {
  // Protagonist Profile
  strategic_thinking: "Strategic Thinking",
  long_term_planning: "Long-Term Planning",
  manipulation: "Manipulation",
  ruthlessness: "Ruthlessness",
  emotional_attachment: "Emotional Attachment",
  internal_consistency: "Internal Consistency",
  adaptability: "Adaptability",
  curiosity: "Curiosity",
  compassion: "Compassion",
  ambition: "Ambition",
  // Philosophy Profile
  freedom: "Freedom",
  survival: "Survival",
  existentialism: "Existentialism",
  moral_ambiguity: "Moral Ambiguity",
  self_improvement: "Self-Improvement",
  determinism: "Determinism",
  revenge: "Revenge",
  romance: "Romance",
  // Storytelling Style
  political_intrigue: "Political Intrigue",
  psychological_warfare: "Psychological Warfare",
  kingdom_building: "Kingdom Building",
  action: "Action",
  slice_of_life: "Slice of Life",
  mystery: "Mystery",
  worldbuilding: "Worldbuilding",
};

const PROTAGONIST_KEYS = [
  "strategic_thinking", "long_term_planning", "manipulation", "ruthlessness",
  "emotional_attachment", "internal_consistency", "adaptability", "curiosity",
  "compassion", "ambition",
];
const PHILOSOPHY_KEYS = [
  "freedom", "survival", "existentialism", "moral_ambiguity",
  "self_improvement", "determinism", "revenge", "romance",
];
const STYLE_KEYS = [
  "political_intrigue", "psychological_warfare", "kingdom_building",
  "action", "slice_of_life", "mystery", "worldbuilding",
];

function getNovelIdFromUrl() {
  return new URLSearchParams(window.location.search).get("id");
}

function renderTraitRow(key, score) {
  const row = document.createElement("div");
  row.className = "trait-row";

  const label = document.createElement("div");
  label.className = "trait-label";
  label.textContent = TRAIT_LABELS[key] || key;

  const track = document.createElement("div");
  track.className = "trait-bar-track";
  const fill = document.createElement("div");
  fill.className = "trait-bar-fill";
  fill.style.width = `${Math.max(0, Math.min(100, score))}%`;
  track.appendChild(fill);

  const scoreEl = document.createElement("div");
  scoreEl.className = "trait-score";
  scoreEl.textContent = score;

  row.appendChild(label);
  row.appendChild(track);
  row.appendChild(scoreEl);
  return row;
}

function renderProfileSection(containerId, keys, profile) {
  const container = document.getElementById(containerId);
  if (!container) {
    return;
  }
  container.innerHTML = "";

  if (!profile) {
    container.innerHTML = "<p>No profile data yet for this novel.</p>";
    return;
  }

  keys.forEach((key) => {
    container.appendChild(renderTraitRow(key, profile[key] ?? 0));
  });
}

function renderNovel(novel) {
  document.title = `${novel.title} | Axiom`;

  const titleEl = document.getElementById("novel-title");
  const authorEl = document.getElementById("novel-author");
  const statusEl = document.getElementById("novel-status");
  const synopsisEl = document.getElementById("novel-synopsis");
  const coverEl = document.getElementById("novel-cover");
  const genresEl = document.getElementById("novel-genres");
  const linksEl = document.getElementById("novel-reading-links");

  if (titleEl) titleEl.textContent = novel.title;
  if (authorEl) authorEl.textContent = novel.author ? `by ${novel.author}` : "";
  if (statusEl) statusEl.textContent = novel.status;
  if (synopsisEl) synopsisEl.textContent = novel.synopsis || "No synopsis yet.";

  if (coverEl) {
    if (novel.cover_image_url) {
      coverEl.style.backgroundImage = `url(${novel.cover_image_url})`;
      coverEl.textContent = "";
    } else {
      coverEl.textContent = novel.title;
    }
  }

  if (genresEl) {
    genresEl.innerHTML = "";
    (novel.genres || []).forEach((genre) => {
      const tag = document.createElement("span");
      tag.className = "genre-tag";
      tag.textContent = genre;
      genresEl.appendChild(tag);
    });
  }

  if (linksEl) {
    linksEl.innerHTML = "";
    (novel.reading_links || []).forEach((link) => {
      const a = document.createElement("a");
      a.href = link.url;
      a.textContent = `Read on ${link.platform}`;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.className = "reading-link";
      linksEl.appendChild(a);
    });
  }

  // The Supabase embed can come back as a single object (expected, since
  // each profile table has a UNIQUE(novel_id) constraint) or as a
  // single-item array on some PostgREST versions -- handle both.
  const unwrap = (value) => (Array.isArray(value) ? value[0] : value);

  renderProfileSection("protagonist-profile", PROTAGONIST_KEYS, unwrap(novel.protagonist_profiles));
  renderProfileSection("philosophy-profile", PHILOSOPHY_KEYS, unwrap(novel.philosophy_profiles));
  renderProfileSection("storytelling-profile", STYLE_KEYS, unwrap(novel.storytelling_style_profiles));
}

async function loadNovel() {
  console.log("[novel.js] loadNovel() starting");

  const novelId = getNovelIdFromUrl();
  const titleEl = document.getElementById("novel-title");
  console.log("[novel.js] novel id from URL:", novelId);

  if (!novelId) {
    console.warn("[novel.js] no ?id= in the URL");
    if (titleEl) titleEl.textContent = "Novel not found";
    return;
  }

  try {
    const url = `${API_BASE}/api/novels/${novelId}`;
    console.log("[novel.js] fetching:", url);
    const response = await fetch(url);
    console.log("[novel.js] response status:", response.status);

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }
    const novel = await response.json();
    console.log("[novel.js] novel payload received:", novel);
    renderNovel(novel);
    console.log("[novel.js] render complete");
  } catch (error) {
    console.error("[novel.js] failed to load novel:", error);
    if (titleEl) titleEl.textContent = "Couldn't load this novel";
    const synopsisEl = document.getElementById("novel-synopsis");
    if (synopsisEl) {
      synopsisEl.textContent = "Make sure the backend is running on port 8000, and that this novel exists.";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("[novel.js] script loaded and DOM ready");
  loadNovel();
});