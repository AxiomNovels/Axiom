const STORYTELLING_GUIDES = [
  ["Political Intrigue", "How strongly power struggles, alliances, governance, diplomacy, and institutional maneuvering drive the story."],
  ["Psychological Warfare", "How strongly deception, manipulation, prediction, intimidation, and battles of will shape conflicts."],
  ["Kingdom Building", "How prominently the creation, management, growth, or reform of an organization, settlement, territory, or civilization appears."],
  ["Action", "How prominently physical conflict, combat, pursuit, danger, and other fast-moving set pieces shape the reading experience."],
  ["Slice of Life", "How much attention the story gives to everyday routines, relationships, small moments, and life between major conflicts."],
  ["Mystery", "How strongly unanswered questions, investigation, hidden information, and gradual revelation organize the narrative."],
  ["Worldbuilding", "How prominently the story develops its cultures, history, geography, institutions, magic, technology, or social systems."],
];

const LEVEL_TEXT = [
  "Explicitly absent or deliberately avoided.",
  "Nearly absent, with at most an isolated trace.",
  "Light or weakly evidenced; peripheral to the story.",
  "Occasional and recognizable, but clearly secondary.",
  "Recurring, though other storytelling elements receive more attention.",
  "Substantial and regularly important alongside other elements.",
  "Prominent enough to shape several major scenes or arcs.",
  "A major recurring focus that strongly affects the reading experience.",
  "Central across much of the novel and difficult to separate from its appeal.",
  "Dominant in nearly every major arc or conflict.",
  "Defining: the novel is fundamentally structured around this element.",
];

function renderStorytellingGuide([name, description], index) {
  const details = document.createElement("details");
  details.className = "trait-guide";
  details.open = index === 0;
  const summary = document.createElement("summary");
  const copy = document.createElement("span");
  const title = document.createElement("strong"); title.textContent = name;
  const poles = document.createElement("small"); poles.textContent = "Light → Prominent";
  copy.append(title, poles);
  const hint = document.createElement("i"); hint.textContent = "0–100";
  summary.append(copy, hint);
  const body = document.createElement("div"); body.className = "trait-guide-body";
  const intro = document.createElement("p"); intro.className = "trait-guide-description"; intro.textContent = description;
  const scale = document.createElement("ol"); scale.className = "trait-scale-list";
  LEVEL_TEXT.forEach((text, level) => {
    const item = document.createElement("li");
    const score = document.createElement("strong"); score.textContent = String(level * 10);
    const explanation = document.createElement("p"); explanation.textContent = text;
    item.append(score, explanation); scale.appendChild(item);
  });
  body.append(intro, scale); details.append(summary, body);
  return details;
}

const container = document.querySelector("[data-storytelling-guides]");
if (container) STORYTELLING_GUIDES.forEach((trait, index) => container.appendChild(renderStorytellingGuide(trait, index)));
