// Snake_case key -> display label, matching the trait definitions discussed
// for the info page. Kept here too so this page can render nice labels
// without depending on that endpoint existing yet.
const TRAIT_LABELS = {
  // Protagonist Profile
  emotional_regulation: "Emotional Regulation",
  arrogance_pride: "Arrogance / Pride",
  attachment: "Attachment",
  family_friend_bonds: "Family / Friend Bonds",
  partner_attachment: "Partner Attachment (Romance)",
  lustful_desire: "Lustful Desire",
  intelligence: "Intelligence",
  family_dynamics: "Family Dynamics",
  individualism: "Individualist",
  collectivism: "Collectivist",
  identity_change_growth: "Identity Change / Growth",
  alienation_from_society: "Alienation From Society",
  mental_health: "Mental Health Challenges",
  anxiety: "Anxiety",
  depression: "Depression",
  toxic_relationships: "Toxic Relationships",
  emotional_repression: "Emotional Repression",
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

const PROTAGONIST_MEASURES = [
  { key: "emotional_regulation" },
  { key: "arrogance_pride" },
  {
    key: "attachment",
    children: ["family_friend_bonds", "partner_attachment", "lustful_desire"],
    alwaysAverage: true,
  },
  { key: "intelligence" },
  { key: "family_dynamics" },
  { key: "individualism" },
  { key: "collectivism" },
  { key: "identity_change_growth" },
  { key: "alienation_from_society" },
  {
    key: "mental_health",
    children: ["anxiety", "depression", "toxic_relationships", "emotional_repression"],
  },
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

function normalizedScore(value) {
  const score = Number(value);
  return Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
}

function averageScores(profile, keys) {
  const total = keys.reduce((sum, key) => sum + normalizedScore(profile[key]), 0);
  return Math.round(total / keys.length);
}

function averageValues(...values) {
  return Math.round(values.reduce((sum, value) => sum + normalizedScore(value), 0) / values.length);
}

// Populate the revised measures from the original profile while the five demo
// novels are being rescored by hand. Explicit new scores always win.
function withDerivedProtagonistMeasures(profile) {
  if (!profile) return profile;
  const value = (key, fallback) => profile[key] ?? fallback;
  const emotionalAttachment = normalizedScore(profile.emotional_attachment);

  return {
    ...profile,
    emotional_regulation: value(
      "emotional_regulation",
      averageValues(profile.internal_consistency, profile.adaptability),
    ),
    arrogance_pride: value("arrogance_pride", averageValues(profile.ambition, profile.ruthlessness)),
    family_friend_bonds: value("family_friend_bonds", emotionalAttachment),
    partner_attachment: value("partner_attachment", emotionalAttachment),
    lustful_desire: value(
      "lustful_desire",
      averageValues(100 - normalizedScore(profile.internal_consistency), profile.ambition),
    ),
    intelligence: value(
      "intelligence",
      averageValues(profile.strategic_thinking, profile.long_term_planning, profile.curiosity),
    ),
    family_dynamics: value("family_dynamics", averageValues(emotionalAttachment, profile.compassion)),
    individualism: value(
      "individualism",
      averageValues(profile.ambition, profile.curiosity, 100 - emotionalAttachment),
    ),
    collectivism: value("collectivism", averageValues(profile.compassion, emotionalAttachment)),
    identity_change_growth: value("identity_change_growth", profile.adaptability),
    alienation_from_society: value(
      "alienation_from_society",
      averageValues(profile.manipulation, profile.ruthlessness, 100 - normalizedScore(profile.compassion)),
    ),
    anxiety: value("anxiety", 100 - normalizedScore(profile.internal_consistency)),
    depression: value("depression", 100 - normalizedScore(profile.ambition)),
    toxic_relationships: value(
      "toxic_relationships",
      averageValues(profile.manipulation, profile.ruthlessness),
    ),
    emotional_repression: value("emotional_repression", 100 - emotionalAttachment),
  };
}

function renderCompositeMeasure(measure, profile) {
  const details = document.createElement("details");
  details.className = "trait-composite";

  const summary = document.createElement("summary");
  summary.className = "trait-composite-summary";
  const score = measure.alwaysAverage || profile[measure.key] == null
    ? averageScores(profile, measure.children)
    : normalizedScore(profile[measure.key]);
  summary.appendChild(renderTraitRow(measure.key, score));

  const children = document.createElement("div");
  children.className = "trait-subfactors";
  measure.children.forEach((key) => {
    children.appendChild(renderTraitRow(key, normalizedScore(profile[key])));
  });

  details.appendChild(summary);
  details.appendChild(children);
  return details;
}

function renderProtagonistProfile(profile) {
  const container = document.getElementById("protagonist-profile");
  if (!container) return;
  container.innerHTML = "";

  if (!profile) {
    container.innerHTML = "<p>No profile data yet for this novel.</p>";
    return;
  }

  profile = withDerivedProtagonistMeasures(profile);

  PROTAGONIST_MEASURES.forEach((measure) => {
    const element = measure.children
      ? renderCompositeMeasure(measure, profile)
      : renderTraitRow(measure.key, normalizedScore(profile[measure.key]));

    if (!measure.poles) {
      container.appendChild(element);
      return;
    }

    const scale = document.createElement("div");
    scale.className = "trait-poles";
    measure.poles.forEach((pole) => {
      const label = document.createElement("span");
      label.textContent = pole;
      scale.appendChild(label);
    });
    const wrapper = document.createElement("div");
    wrapper.className = "trait-with-poles";
    wrapper.appendChild(element);
    wrapper.appendChild(scale);
    container.appendChild(wrapper);
  });
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

  renderProtagonistProfile(unwrap(novel.protagonist_profiles));
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
