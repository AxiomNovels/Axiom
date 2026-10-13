const TRAIT_GUIDES = [
  ["Intelligence", "Low", "Exceptional", "Reasoning, learning, insight, strategy, and problem-solving ability."],
  ["Charisma", "Low", "Exceptional", "Ability to attract, persuade, inspire, charm, or socially influence others."],
  ["Moral Integrity", "Unprincipled", "Principled", "Consistency in acting according to ethical principles, including when that comes at a cost."],
  ["Kinship & Friendship", "Detached", "Devoted", "Emotional investment, loyalty, and care toward family, friends, and found family."],
  ["Romantic Attachment", "Absent", "Defining", "The importance of romantic love, partnership, and attachment in the protagonist's life."],
  ["Erotic Desire", "Absent", "Defining", "How strongly sexual attraction, desire, or pursuit is expressed as a meaningful motivation."],
  ["Arrogance & Conceit", "Humble", "Extremely conceited", "Ego, superiority, status-consciousness, and resistance to admitting weakness."],
].map(([name, low, high, description]) => ({
  name, low, high, description,
  levels: [
    `The ${low.toLowerCase()} end of this trait is clearly and repeatedly established.`,
    `The trait is very weak and rarely affects choices or relationships.`,
    `There is limited or uncertain evidence for the trait.`,
    `The trait appears sometimes, but remains secondary.`,
    `The trait is a recurring part of characterization without being central.`,
    `The trait is clearly present and materially affects important choices.`,
    `The trait frequently shapes relationships, behavior, or major decisions.`,
    `The trait is a strong, recurring force in the protagonist's story.`,
    `The trait is one of the protagonist's principal defining characteristics.`,
    `The trait is extreme and drives many major decisions or conflicts.`,
    `The ${high.toLowerCase()} end of this trait is defining and inseparable from the protagonist's story.`
  ]
}));

function renderTraitGuide(trait, index) {
  const details = document.createElement("details");
  details.className = "trait-guide";
  if (index === 0) details.open = true;
  const summary = document.createElement("summary");
  const copy = document.createElement("span");
  const title = document.createElement("strong"); title.textContent = trait.name;
  const poles = document.createElement("small"); poles.textContent = `${trait.low} → ${trait.high}`;
  copy.append(title, poles);
  const hint = document.createElement("i"); hint.textContent = "0–100";
  summary.append(copy, hint);
  const body = document.createElement("div"); body.className = "trait-guide-body";
  const description = document.createElement("p"); description.className = "trait-guide-description"; description.textContent = trait.description;
  const scale = document.createElement("ol"); scale.className = "trait-scale-list";
  trait.levels.forEach((text, level) => {
    const item = document.createElement("li");
    const score = document.createElement("strong"); score.textContent = String(level * 10);
    const explanation = document.createElement("p"); explanation.textContent = text;
    item.append(score, explanation); scale.append(item);
  });
  body.append(description, scale); details.append(summary, body);
  return details;
}

const guideContainer = document.querySelector("[data-trait-guides]");
TRAIT_GUIDES.forEach((trait, index) => guideContainer.appendChild(renderTraitGuide(trait, index)));
