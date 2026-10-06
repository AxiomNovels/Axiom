const TRAIT_GUIDES = [
  {
    name: "Intellectual drive", low: "Absent", high: "Defining",
    description: "How strongly the protagonist is motivated by curiosity, understanding, investigation, learning, experimentation, or discovery. It measures motivation, not intelligence, education, or competence.",
    levels: [
      "No meaningful interest in exploring, understanding, or discovering things; intellectual exploration is not part of their characterization.",
      "Almost no intellectual curiosity, with only isolated practical learning.",
      "Curiosity is weak, incidental, or supported mainly by limited evidence.",
      "Sometimes investigates, learns, or asks questions beyond immediate necessity, but it remains secondary.",
      "Curiosity or learning regularly influences behavior but is not a major motivation.",
      "Intellectual exploration is a clear recurring motivation alongside other goals.",
      "Frequently seeks knowledge, investigates systems, or experiments even when it is not strictly necessary.",
      "Intellectual discovery or understanding materially shapes major decisions and plot development.",
      "Curiosity, investigation, experimentation, or mastery of knowledge is one of their principal motivations.",
      "Intellectual exploration is a defining part of their identity and drives many major choices, sacrifices, or conflicts.",
      "The pursuit of understanding is one of the dominant themes of their story and virtually inseparable from their major decisions."
    ]
  },
  {
    name: "Arrogance & pride", low: "Humble", high: "Egotistical",
    description: "How strongly pride, ego, status-consciousness, and a sense of superiority shape the protagonist, including resistance to admitting weakness. Confidence or competence alone does not establish arrogance.",
    levels: [
      "Explicit, defining humility and little concern for status or superiority.",
      "Very modest, with rare or minor expressions of pride.",
      "Generally humble, or evidence of ego is weak and limited.",
      "Occasional pride, competitiveness, sensitivity to disrespect, or a desire to prove themselves.",
      "Pride sometimes affects behavior or decisions but remains secondary.",
      "Confidence and humility are broadly balanced.",
      "Often proud, status-conscious, or sensitive to challenges to their competence or dignity.",
      "Arrogance or pride regularly shapes conflict, judgment, relationships, or choices.",
      "Commonly assumes superiority, strongly resists humiliation, or places substantial importance on status and personal greatness.",
      "Overwhelming ego or pride governs many major choices and relationships.",
      "Unquestioned superiority or extreme ego is a defining feature of virtually every major decision and interaction."
    ]
  },
  {
    name: "Kinship & friendship", low: "Detached", high: "Devoted",
    description: "How strongly family, friendship, loyalty, and chosen bonds motivate the protagonist. It measures influence on decisions, not the number of acquaintances.",
    levels: [
      "Explicit, defining detachment or absence of meaningful bonds.",
      "Nearly isolated, with at most one faint or weak bond.",
      "Relationships are outside the main story, unclear, or only weakly meaningful.",
      "A few bonds matter emotionally but rarely determine important choices.",
      "Friendships or family relationships sometimes motivate meaningful action.",
      "Close relationships and personal priorities receive roughly equal weight.",
      "Relationships frequently affect risks, loyalties, priorities, or major decisions.",
      "Protecting or supporting close people is a major recurring motivation.",
      "Deep loyalty to friends, family, or comrades drives major sacrifices and decisions.",
      "Repeatedly accepts severe losses, danger, or setbacks for loved ones or close companions.",
      "Devotion to close relationships dominates virtually every major choice, above personal interests."
    ]
  },
  {
    name: "Romantic attachment", low: "Unattached", high: "Romance-driven",
    description: "How strongly romantic love, attachment to a partner, or pursuit of a romantic relationship motivates the protagonist. A slow-burning romance describes pacing, not weakness.",
    levels: [
      "Explicitly absent: romantic life is genuinely irrelevant to their characterization, and the story treats this as meaningful.",
      "Almost entirely unattached, with only an ambiguous or negligible romantic element.",
      "Romance is outside the main story, evidence is unclear, or attraction has little meaningful influence.",
      "Minor attraction or an early, limited romantic bond with little effect on the plot.",
      "A recurring romantic relationship or attachment exists but remains secondary.",
      "Romance is a clear and regular motivation alongside other major priorities.",
      "Romantic attachment materially shapes several important decisions.",
      "Romantic love or pursuit is one of their principal motivations.",
      "Love repeatedly outweighs safety, strategy, ambition, duty, or other major goals.",
      "Nearly every defining choice is substantially influenced by a romantic partner or attachment.",
      "Romance wholly dominates their major motivations and decisions."
    ]
  },
  {
    name: "Selfishness / selflessness", low: "Self-interested", high: "Self-sacrificing",
    description: "How readily the protagonist places other people's welfare above their own interests, safety, and ambitions. Helping others is not automatically selflessness: personal cost and a genuinely other-directed motive matter.",
    levels: [
      "Explicit, defining refusal to sacrifice for others and a consistent prioritization of personal interests.",
      "Nearly always prioritizes themselves and rarely accepts meaningful costs for other people.",
      "Mostly self-interested, or altruism is weakly evidenced.",
      "Helps others at little personal cost but rarely gives up something important for them.",
      "Recurring generosity or concern for others, but personal goals usually come first.",
      "Balances their own interests and the interests of others.",
      "Often accepts meaningful inconvenience, risk, expense, or lost opportunities for other people.",
      "Regularly sacrifices meaningful resources, opportunities, safety, or goals for others.",
      "Other people's welfare usually outweighs their own ambition or comfort.",
      "Repeatedly accepts severe personal loss, danger, or deprivation to protect or benefit others.",
      "Extreme self-sacrifice is defining: consistently places others' welfare above their own survival, ambitions, freedom, or happiness."
    ]
  },
  {
    name: "Pragmatism / morality", low: "Pragmatic", high: "Principled",
    description: "How strongly the protagonist holds to moral principles when they conflict with practical advantage. Being kind or heroic is not enough for a high score, and being effective or strategic is not enough for a low one.",
    levels: [
      "Strongly pragmatic or amoral, readily abandoning moral principles whenever it advances their goals.",
      "Practical outcomes overwhelmingly determine decisions, with little resistance to morally questionable methods.",
      "Generally pragmatic and flexible about moral boundaries.",
      "Has some moral limits but frequently compromises them for practical reasons.",
      "Morality matters but is often negotiable when stakes are high.",
      "Practical considerations and moral principles are broadly balanced.",
      "Usually tries to preserve moral principles even when doing so is costly or inefficient.",
      "Ethical principles regularly constrain important decisions and methods.",
      "Strongly prioritizes doing what they believe is right even at substantial practical cost.",
      "A consistent moral code governs most major choices, even when violating it would bring obvious benefits.",
      "Principled morality is defining: they would accept extreme loss, danger, or failure rather than knowingly violate their core ethics."
    ]
  },
  {
    name: "Individualist / collectivist", low: "Individualist", high: "Collectivist",
    description: "Whether the protagonist understands themselves and decides as an independent individual or as a member of a group, community, family, or organization. Strong friendships or selflessness do not by themselves make a protagonist collectivist.",
    levels: [
      "Extreme individualism: personal autonomy and independent goals dominate, and group-based obligations or identity are strongly resisted.",
      "Highly self-directed; rarely lets group expectations constrain important choices.",
      "Generally prioritizes personal autonomy but maintains some meaningful group ties.",
      "Mostly independent while accepting some obligations to groups or communities.",
      "Individual priorities usually come first, but group identity and obligations are meaningful.",
      "Individual autonomy and collective belonging are of roughly equal importance.",
      "Regularly weighs the needs, expectations, or interests of their group alongside their own.",
      "Group loyalty, community identity, or collective goals frequently influence major decisions.",
      "Strongly identifies with and prioritizes a family, community, faction, nation, or organization.",
      "Collective welfare and group obligations routinely outweigh personal preferences, ambitions, or safety.",
      "Collectivism is defining: identity and virtually all major decisions are organized around belonging to and serving a collective."
    ]
  },
  {
    name: "Ambition", low: "Unambitious", high: "Power-hungry",
    description: "How strongly the protagonist actively pursues advancement, power, status, wealth, influence, achievement, or mastery. Being powerful is not the same as wanting power.",
    levels: [
      "Virtually no desire for advancement; content with their existing circumstances.",
      "Advancement is rarely desired and they generally accept their position.",
      "Ambition is weak, secondary, or supported mainly by limited evidence.",
      "Has some aspirations but rarely lets them drive major decisions.",
      "Advancement is a recurring goal but remains secondary to other motivations.",
      "Consistently wants to improve their position, abilities, or status, balanced against other major priorities.",
      "Ambition frequently influences important choices; actively seeks opportunities for advancement.",
      "Becoming stronger, more successful, influential, or powerful is a major recurring motivation.",
      "Ambition is a principal motivation and regularly outweighs comfort, safety, relationships, or other interests.",
      "Relentless advancement governs most major choices, accepting substantial costs to keep progressing.",
      "Extreme hunger for power is defining: continual advancement dominates virtually every major decision."
    ]
  },
  {
    name: "Cautious / risk-taker", low: "Cautious", high: "Risk-taking",
    description: "The protagonist's willingness to accept uncertainty, danger, or loss in pursuit of a goal. It is separate from impulsivity (a careful planner can still be an extreme risk-taker), and being placed in dangerous situations does not by itself make someone a risk-taker.",
    levels: [
      "Extreme caution: consistently avoids unnecessary danger and strongly prioritizes minimizing uncertainty and loss.",
      "Highly cautious; takes serious risks only under exceptional circumstances.",
      "Generally avoids unnecessary risks, with limited evidence of risk-taking.",
      "Somewhat cautious but accepts manageable risks when justified.",
      "Usually weighs risks carefully but sometimes accepts substantial uncertainty.",
      "Caution and risk-taking are broadly balanced.",
      "Regularly accepts significant risks when opportunities or goals justify them.",
      "Frequently chooses dangerous or uncertain approaches despite safer alternatives.",
      "Actively embraces major risks and treats danger as an acceptable cost of pursuing their goals.",
      "Extreme risk-taking is common: repeatedly accepts severe danger or potentially catastrophic consequences.",
      "Reckless risk-taking is defining, routinely choosing highly dangerous courses of action despite obvious consequences."
    ]
  },
  {
    name: "Leadership", low: "Non-leader", high: "Defining leader",
    description: "How strongly the protagonist takes responsibility for directing, organizing, motivating, protecting, or governing other people. Charisma, popularity, competence, or power alone do not establish leadership.",
    levels: [
      "Does not meaningfully lead others and consistently avoids leadership responsibilities when they arise.",
      "Almost always follows others and has little interest in directing or organizing people.",
      "Leadership is outside the main story, unclear, or limited to isolated situations.",
      "Occasionally takes charge in small or temporary situations.",
      "Sometimes organizes or directs others, but leadership remains secondary.",
      "Regularly takes responsibility for coordinating or directing others while also functioning comfortably as a peer or follower.",
      "Leadership frequently affects their role, relationships, and decisions.",
      "A significant leader whose decisions materially affect a group, organization, party, community, or faction.",
      "Leadership is one of their principal roles; regularly accepts responsibility for others' actions, welfare, or direction.",
      "A major leader whose ability to organize, command, inspire, or govern drives much of the story.",
      "Leadership is defining: identity and virtually all major choices are tied to directing, protecting, organizing, or governing others."
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
