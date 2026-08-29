const TRAIT_GUIDES = [
  {
    name: "Impulsivity", low: "Deliberate", high: "Impulsive",
    description: "How readily the protagonist acts before thinking through consequences. It measures decision style, not intelligence or speed.",
    levels: [
      "Explicitly and consistently deliberate; refusing rash action is central to their identity.",
      "Almost always plans first, with only an isolated rushed or emotional decision.",
      "Mostly deliberate, though evidence may be sparse or a few questionable choices appear.",
      "Occasionally acts too quickly, but reflection and planning remain the norm.",
      "A noticeable mix: impulsive choices recur without defining their behavior.",
      "Equally likely to plan or act on instinct depending on the situation.",
      "Frequently acts first and deals with consequences later, though capable of restraint.",
      "Impulsive decisions regularly redirect the plot or create serious problems.",
      "Strongly driven by immediate emotion, instinct, or opportunity rather than forethought.",
      "Rarely pauses to consider consequences even when the risks are obvious.",
      "Extreme impulsivity is a defining identity; virtually every major choice is immediate and unrestrained."
    ]
  },
  {
    name: "Ego", low: "Humble", high: "Egotistical",
    description: "How strongly superiority, ego, status, or refusal to yield shapes the protagonist’s self-image and decisions.",
    levels: [
      "Explicitly humble; lack of ego is repeatedly emphasized as a core quality.",
      "Very modest, with only rare flashes of pride or sensitivity about status.",
      "Generally humble, or pride is largely outside the story and weakly evidenced.",
      "Shows occasional pride, competitiveness, or reluctance to admit fault.",
      "Pride is noticeable and sometimes affects relationships or decisions.",
      "Balances confidence and humility; ego matters but does not consistently lead.",
      "Often proud and status-conscious, with recurring difficulty yielding or apologizing.",
      "Arrogance regularly shapes judgments, conflicts, and treatment of others.",
      "Assumes superiority and resists humiliation or correction in most situations.",
      "Overwhelming ego governs major choices despite repeated consequences.",
      "Extreme arrogance is defining; the protagonist consistently treats their superiority as unquestionable."
    ]
  },
  {
    name: "Kinship & friendship", low: "Detached", high: "Devoted",
    description: "How strongly family, friendship, loyalty, and chosen bonds motivate the protagonist. It measures influence on decisions, not the number of acquaintances.",
    levels: [
      "The story explicitly establishes no meaningful personal bonds, and detachment is central to the character.",
      "Nearly isolated; one faint bond may exist but has almost no influence.",
      "Relationships are not part of the main storyline, evidence is unclear, or bonds remain weak.",
      "A few connections matter emotionally but rarely alter important decisions.",
      "Friends or family sometimes motivate action, though personal goals usually come first.",
      "Bonds and individual priorities carry roughly equal weight.",
      "Relationships frequently affect risks, loyalties, and important choices.",
      "Protecting or supporting close people is a major recurring motivation.",
      "Deep loyalty governs many central decisions, often at substantial personal cost.",
      "The protagonist repeatedly sacrifices major goals or safety for loved ones.",
      "Devotion to family or friends is defining and dominates virtually every major choice."
    ]
  },
  {
    name: "Romantic attachment", low: "Unattached", high: "Romance-driven",
    description: "How strongly romantic love or attachment influences the protagonist’s inner life and choices. It is separate from lust and sexual behavior.",
    levels: [
      "Romantic attachment is explicitly absent: the protagonist’s heart never wavers, and the story treats this as part of their identity.",
      "Almost entirely unattached, with at most one slight or ambiguous emotional moment.",
      "Romance is outside the main storyline, barely discussed, or evidence is too limited for a stronger score.",
      "Minor attraction or a slow, early bond appears without materially driving the plot.",
      "A recurring romantic relationship or attachment matters, but remains secondary.",
      "Romance is a clear and regular motivation alongside other equally important goals.",
      "Romantic attachment materially shapes several major decisions or risks.",
      "The relationship is one of the protagonist’s principal emotional and narrative motivations.",
      "Love repeatedly outweighs safety, strategy, duty, or other major priorities.",
      "Nearly every defining choice is organized around a romantic partner or attachment.",
      "Romantic attachment wholly defines the protagonist’s motivations and dominates the story."
    ]
  },
  {
    name: "Lust", low: "Absent", high: "Very lustful",
    description: "How strongly sexual desire appears and influences behavior. It is separate from romantic devotion, affection, or emotional attachment.",
    levels: [
      "Lust is explicitly absent: the protagonist never wavers sexually, and this absence is specifically established by the story.",
      "Sexual desire is nearly absent, with only one or two slight or questionable moments.",
      "Lust is not part of the main storyline, comments provide little evidence, or available evidence is unclear.",
      "Some lust or attraction is present, but it remains occasional and has little effect on decisions.",
      "Sexual desire recurs and is clearly acknowledged, though it remains secondary.",
      "Lust is a regular motivation but shares influence with relationships, goals, and restraint.",
      "Sexual desire frequently influences attention, relationships, or meaningful choices.",
      "Lust strongly motivates repeated behavior and produces notable consequences.",
      "Sexual pursuit is prominent and regularly outweighs judgment or other priorities.",
      "The protagonist is persistently lust-driven across most relevant situations.",
      "Extreme lust is a defining characteristic and dominates virtually all relationships and choices."
    ]
  },
  {
    name: "Selflessness", low: "Self-interested", high: "Self-sacrificing",
    description: "How readily the protagonist places other people’s welfare above personal benefit, safety, or ambition.",
    levels: [
      "Explicitly self-interested; refusal to sacrifice for others is central to their identity.",
      "Almost always prioritizes personal gain, with only a rare minor act for someone else.",
      "Mostly self-interested, or altruistic behavior is weakly evidenced and outside the main story.",
      "Sometimes helps others when the personal cost is small or interests overlap.",
      "Shows recurring generosity, but generally protects their own goals first.",
      "Balances personal needs and others’ welfare with no consistent priority.",
      "Often accepts inconvenience or risk for others, though limits remain.",
      "Regularly sacrifices meaningful opportunities, resources, or safety for others.",
      "Other people’s welfare usually outweighs personal ambition and comfort.",
      "Repeatedly accepts severe personal loss to protect or benefit others.",
      "Extreme self-sacrifice is defining; the protagonist consistently places everyone else before themselves."
    ]
  }
];

function renderTraitGuide(trait, index) {
  const details = document.createElement("details");
  details.className = "trait-guide";
  if (index === 0) details.open = true;

  const summary = document.createElement("summary");
  const summaryCopy = document.createElement("span");
  const title = document.createElement("strong"); title.textContent = trait.name;
  const poles = document.createElement("small"); poles.textContent = `${trait.low} → ${trait.high}`;
  summaryCopy.append(title, poles);
  const hint = document.createElement("i"); hint.textContent = "0–100";
  summary.append(summaryCopy, hint);

  const body = document.createElement("div"); body.className = "trait-guide-body";
  const description = document.createElement("p"); description.className = "trait-guide-description"; description.textContent = trait.description;
  const scale = document.createElement("ol"); scale.className = "trait-scale-list";
  trait.levels.forEach((text, level) => {
    const item = document.createElement("li");
    const score = document.createElement("strong"); score.textContent = String(level * 10);
    const explanation = document.createElement("p"); explanation.textContent = text;
    item.append(score, explanation); scale.appendChild(item);
  });
  body.append(description, scale); details.append(summary, body);
  return details;
}

const guideContainer = document.querySelector("[data-trait-guides]");
TRAIT_GUIDES.forEach((trait, index) => guideContainer.appendChild(renderTraitGuide(trait, index)));
