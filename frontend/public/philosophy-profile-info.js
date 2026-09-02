const PHILOSOPHY_GUIDES = [
  {
    name: "Freedom",
    low: "Collective",
    high: "Individual",
    description:
      "How the novel weighs the freedom of the individual against the needs, values, or survival of the collective. A high score means individual autonomy is treated as especially important; a low score means individuals are expected to surrender freedom when doing so benefits the larger group.",
    levels: [
      "The collective is paramount. Individuals are expected to sacrifice their freedom whenever the group's needs require it.",
      "Individual freedom is given very little weight when it conflicts with the interests of the collective.",
      "The collective generally takes priority, though the novel acknowledges that individuals have legitimate claims to freedom.",
      "The novel tends to favor collective interests, but makes meaningful room for individual autonomy.",
      "Both individual freedom and collective welfare are treated as legitimate values, with neither consistently winning.",
      "The novel gives roughly equal philosophical weight to individual autonomy and collective responsibility.",
      "Individual freedom usually takes priority, though meaningful limits are accepted when collective interests are at stake.",
      "The novel strongly favors individual autonomy and questions attempts to restrict it for the sake of the collective.",
      "Individual freedom is treated as a fundamental value that should rarely be sacrificed for others.",
      "The novel strongly prioritizes individual autonomy even when protecting it creates serious costs for the collective.",
      "Individual freedom is paramount. The right of each person to choose their own path outweighs virtually all collective considerations.",
    ],
  },
  {
    name: "Survival",
    low: "Provided for",
    high: "Constant struggle",
    description:
      "How intensely characters must struggle to survive and secure their basic existence. A low score means survival is largely provided for or guaranteed, while a high score means staying alive is a persistent and demanding challenge.",
    levels: [
      "Characters are largely insulated from survival concerns; their basic needs and safety are effectively guaranteed or provided for.",
      "Survival requires very little effort, with protection and basic necessities readily available.",
      "Characters occasionally face survival concerns, but these rarely demand sustained effort or sacrifice.",
      "Survival presents meaningful difficulties from time to time, but characters are generally secure.",
      "Characters must make genuine efforts to survive, but survival is only one concern among many.",
      "Survival is a persistent consideration, with characters regularly balancing it against other goals and values.",
      "Characters frequently struggle to secure safety, resources, or basic necessities.",
      "Survival is a major recurring challenge that forces characters to make difficult choices and sacrifices.",
      "Characters live under severe and sustained survival pressure, with little room for comfort or security.",
      "Survival is an almost constant struggle, repeatedly forcing characters to risk themselves, compromise, or adapt.",
      "Survival dominates everyday life. Characters are in a near-constant struggle to remain alive, safe, or capable of continuing.",
    ],
  },
  {
    name: "Existentialism",
    low: "Predefined purpose",
    high: "Self-created meaning",
    description:
      "How the novel treats the question of where meaning and purpose come from. A low score means purpose is fundamentally predetermined by fate, society, religion, nature, or another external source; a high score means characters create or choose their own meaning.",
    levels: [
      "Purpose is fundamentally predetermined. Characters have a meaningful role or destiny that exists independently of their choices.",
      "The novel strongly suggests that meaning and purpose are given to people rather than created by them.",
      "Purpose is mostly predefined, though characters retain some ability to interpret or respond to it.",
      "Characters have some meaningful freedom to determine their purpose, but external forces still provide much of the answer.",
      "The novel leaves the source of meaning genuinely uncertain, balancing predetermined purpose with personal choice.",
      "Characters have substantial freedom to define what makes their lives meaningful, though external expectations remain influential.",
      "The novel increasingly treats purpose as something individuals must discover or construct for themselves.",
      "Characters actively reject inherited purposes and begin defining meaning through their own choices.",
      "Personal creation of meaning is central. Characters must decide what makes their existence worthwhile rather than receiving an easy answer.",
      "The novel strongly rejects predetermined purpose and emphasizes the individual's responsibility to create meaning.",
      "Meaning is fundamentally self-created. Characters must choose their own purpose in an otherwise purposeless or uncertain existence.",
    ],
  },
  {
    name: "Moral Ambiguity",
    low: "Moral certainty",
    high: "Moral ambiguity",
    description:
      "How the novel treats the boundary between right and wrong. A low score means moral principles are relatively clear and stable; a high score means competing moral frameworks make simple judgments increasingly difficult.",
    levels: [
      "Moral distinctions are exceptionally clear. The story strongly establishes what is right and wrong.",
      "The novel has a clear moral framework, with only rare complications or exceptions.",
      "Most moral questions have understandable answers, though the story occasionally introduces genuine complications.",
      "The novel generally distinguishes right from wrong but meaningfully challenges those distinctions in some situations.",
      "The novel occupies a genuine middle ground, presenting both clear moral principles and situations where those principles conflict.",
      "Characters frequently face situations where two defensible moral choices come into conflict.",
      "Moral judgments become increasingly difficult as different values, perspectives, and circumstances compete.",
      "The novel regularly asks whether apparently good or bad actions can be understood differently from another perspective.",
      "Simple moral judgments are repeatedly undermined, with major characters often having defensible reasons for questionable actions.",
      "The novel strongly resists clear moral categories and repeatedly forces the reader to reconsider who is right or wrong.",
      "Moral ambiguity is pervasive. The story offers no simple moral framework and consistently presents competing, difficult-to-reconcile ideas of right and wrong.",
    ],
  },
  {
    name: "Self-Improvement",
    low: "Little growth",
    high: "Constant development",
    description:
      "How strongly personal growth, self-mastery, and deliberate improvement are explored. The focus can be entirely on the protagonist, but the score can be higher when many characters meaningfully pursue self-improvement.",
    levels: [
      "Characters barely change or improve. Personal development is almost irrelevant to the story.",
      "Growth is minimal, with characters remaining largely the same despite their experiences.",
      "Some development occurs, but it is incidental rather than a meaningful focus of the story.",
      "Characters improve in noticeable ways, though personal development remains secondary to other concerns.",
      "Self-improvement is a recurring part of the story, with meaningful growth occurring over time.",
      "Personal development is a substantial theme. Characters regularly learn, adapt, or work to overcome their weaknesses.",
      "Self-improvement strongly influences the protagonist's goals, decisions, and progression.",
      "Deliberate growth and self-mastery are major focuses, with characters actively seeking to become better or more capable.",
      "The story places heavy emphasis on overcoming limitations, cultivating abilities, and consciously improving oneself.",
      "Continuous development is central to the narrative, with major characters repeatedly pushing themselves to improve.",
      "Self-improvement is a defining focus of the novel. Characters are constantly striving to become better versions of themselves, often as a central purpose of their lives.",
    ],
  },
  {
    name: "Determinism",
    low: "Fate-driven",
    high: "Free will",
    description:
      "How the novel treats the relationship between fate and free will. A low score means events and choices are fundamentally determined by fate, destiny, causality, or forces beyond individual control. A high score means personal choice and agency play a major role in determining what happens.",
    levels: [
      "The world is overwhelmingly fate-driven. Major events and choices are effectively predetermined.",
      "Fate, destiny, or unavoidable causality strongly constrains what characters can choose.",
      "Characters have limited agency, with important aspects of their lives effectively determined in advance.",
      "External forces strongly influence outcomes, though characters retain some meaningful ability to choose.",
      "The novel genuinely balances fate and free will, leaving meaningful room for both interpretations.",
      "Characters have substantial agency, but their choices remain meaningfully constrained by circumstances or prior causes.",
      "Free will is an important force in the story, even though characters must contend with powerful external constraints.",
      "The novel strongly emphasizes the ability of characters to choose their own actions and change their circumstances.",
      "Personal agency plays a dominant role, with characters repeatedly overcoming circumstances through their choices.",
      "The novel strongly favors free will and treats individuals as responsible for determining their own paths.",
      "Free will is fundamental. Characters' choices and agency play an enormous role in shaping their lives and the course of the story.",
    ],
  },
  {
    name: "Revenge",
    low: "Forgiveness",
    high: "Vengeance",
    description:
      "How the novel approaches the response to wrongdoing. A low score means the story explores forgiveness, reconciliation, or letting go; a high score means it explores the desire for vengeance, retaliation, or making wrongdoers pay.",
    levels: [
      "The novel strongly favors forgiveness, reconciliation, or letting go of past wrongs over retaliation.",
      "Forgiveness is treated as especially meaningful, while vengeance is portrayed as largely destructive or misguided.",
      "The novel generally leans toward forgiveness, though it acknowledges why characters may desire revenge.",
      "Forgiveness receives greater weight than vengeance, though vengeance is possible for major wrongdoing.",
      "The novel presents forgiveness and vengeance as competing responses to wrongdoing without clearly favoring either.",
      "Both forgiveness and revenge are explored seriously, with their consequences and justifications given comparable weight.",
      "The novel increasingly validates the desire for retaliation while still acknowledging the value of forgiveness.",
      "Vengeance becomes a major philosophical and emotional response to wrongdoing, though forgiveness remains possible.",
      "The novel strongly explores the desire to make wrongdoers suffer or pay for what they have done.",
      "Thirst for vengeance is a dominant response to wrongdoing, repeatedly outweighing forgiveness or reconciliation.",
      "Vengeance is central. The novel intensely explores the desire for retribution and the belief that wrongdoers must be made to pay.",
    ],
  },
  {
    name: "Romance",
    low: "Scorned",
    high: "Major theme",
    description:
      "How the novel treats romantic love and romantic relationships. A low score means romantic attachment is rejected, criticized, or treated as undesirable; a high score means romance is a major and meaningful part of the story.",
    levels: [
      "The novel actively scorns or rejects romantic interest, portraying it as undesirable, foolish, or fundamentally incompatible with its values.",
      "Romantic attachment is strongly discouraged or treated as a weakness, distraction, or source of unnecessary suffering.",
      "The novel is largely skeptical of romance, though it may acknowledge limited value in romantic relationships.",
      "Romantic relationships receive some attention, but the story generally places greater importance on other forms of connection or purpose.",
      "Romance occupies a genuine middle ground: it is neither rejected nor a dominant concern.",
      "Romantic relationships are meaningfully explored and carry comparable importance to other major interpersonal themes.",
      "Romance is a significant recurring theme that substantially affects characters and their decisions.",
      "Romantic attachment is one of the major emotional and narrative concerns of the story.",
      "Romance plays a major role in character development, conflicts, motivations, and the story's themes.",
      "Romantic relationships are central to much of the novel and frequently drive major character decisions and events.",
      "Romance is a defining theme. Romantic love and relationships are among the primary forces shaping the characters and story.",
    ],
  },
];

function renderPhilosophyGuide(trait, index) {
  const details = document.createElement("details");
  details.className = "trait-guide";

  if (index === 0) {
    details.open = true;
  }

  const summary = document.createElement("summary");

  const summaryCopy = document.createElement("span");

  const title = document.createElement("strong");
  title.textContent = trait.name;

  const poles = document.createElement("small");
  poles.textContent = `${trait.low} → ${trait.high}`;

  summaryCopy.append(title, poles);

  const hint = document.createElement("i");
  hint.textContent = "0–100";

  summary.append(summaryCopy, hint);

  const body = document.createElement("div");
  body.className = "trait-guide-body";

  const description = document.createElement("p");
  description.className = "trait-guide-description";
  description.textContent = trait.description;

  const scale = document.createElement("ol");
  scale.className = "trait-scale-list";

  trait.levels.forEach((text, level) => {
    const item = document.createElement("li");

    const score = document.createElement("strong");
    score.textContent = String(level * 10);

    const explanation = document.createElement("p");
    explanation.textContent = text;

    item.append(score, explanation);
    scale.appendChild(item);
  });

  body.append(description, scale);
  details.append(summary, body);

  return details;
}

const guideContainer = document.querySelector("[data-philosophy-guides]");

if (guideContainer) {
  PHILOSOPHY_GUIDES.forEach((trait, index) => {
    guideContainer.appendChild(renderPhilosophyGuide(trait, index));
  });
}
