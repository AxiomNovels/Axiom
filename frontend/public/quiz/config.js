/* Campaign configuration. Array order is the fixed exact-tie priority. */
(function (root) {
  const config = {
    version: 1,
    nearTieThreshold: 3,
    // Only these seven dimensions are displayed or compared with protagonists.
    traits: [
      { key: "intelligence", name: "Intelligence", description: "Reasoning, learning, and problem-solving; not education or knowing everything." },
      { key: "charisma", name: "Charisma", description: "Persuading, inspiring, and connecting; not beauty, fame, or popularity." },
      { key: "courage", name: "Courage", description: "Facing fear, danger, and uncertainty; not recklessness or an absence of fear." },
      { key: "moral_integrity", name: "Moral Integrity", description: "Upholding ethical principles under pressure; not simply following rules." },
      { key: "kinship_friendship", name: "Kinship & Friendship", description: "Your investment in friends, family, and chosen family; not how much they love you." },
      { key: "romantic_attachment", name: "Romantic Attachment", description: "Romantic or sexual attraction and investment in romantic bonds; not being desirable to others." },
      { key: "arrogance_pride", name: "Arrogance & Conceit", description: "Superiority, entitlement, and resistance to correction; not confidence or competence alone." },
    ],
    patterns: ["independence", "unconventionality"],
    archetypes: [
      {
        id: "mastermind", title: "The Mastermind", quote: "The one who sees the whole board.",
        description: "While others watch the next move, you notice the pattern behind it. In your story, preparation is a quiet kind of power: you learn the rules, read the opposition, and make the opening nobody else saw.",
        strength: "Turning scattered clues into a plan that can survive a setback.",
        tension: "People are not puzzles. Your instinct to calculate can become overplanning, manipulation, or a reluctance to act without certainty.",
        weights: { intelligence: 0.7, strategic_influence: 0.2, courage: 0.1 },
      },
      {
        id: "leader", title: "The Natural Leader", quote: "People follow because you give them a reason.",
        description: "You turn a room of separate voices into a shared purpose. Your protagonist power is connection: listening across divides, finding words that matter, and helping people believe the difficult thing is possible.",
        strength: "Building trust and giving a group the resolve to move together.",
        tension: "You may carry everyone's burdens or mistake approval for trust. Leadership sometimes means letting people disagree with you.",
        weights: { charisma: 0.65, kinship_friendship: 0.2, courage: 0.1, moral_integrity: 0.05 },
      },
      {
        id: "idealist", title: "The Idealist", quote: "Some lines are worth refusing to cross.",
        description: "An easier victory is not always a victory you can live with. Your story is driven by convictions that survive pressure, and by the difficult choice to protect what is right when it costs you something.",
        strength: "Giving principles weight through action, especially when compromise would be convenient.",
        tension: "Conviction can harden into rigidity. Leave room to learn, and remember that sacrificing yourself is not the only way to help.",
        weights: { moral_integrity: 0.7, courage: 0.2, kinship_friendship: 0.1 },
      },
      {
        id: "guardian", title: "The Guardian", quote: "Your people are your reason to fight.",
        description: "For you, the stakes have names. Friends, family, and the people you choose become the heart of your story. You make space for their needs and find strength in having someone worth showing up for.",
        strength: "Making loyalty tangible through care, commitment, and protection.",
        tension: "Protection can become control. Your people need room to choose, and your own needs deserve a place in the story too.",
        weights: { kinship_friendship: 0.7, courage: 0.15, moral_integrity: 0.1, romantic_attachment: 0.05 },
      },
      {
        id: "romantic", title: "The Romantic", quote: "Some bonds change the course of a life.",
        description: "Attraction and attachment are forces that can redraw your map. Your fictional identity is shaped by the connections you feel: the person you long for, the intimacy you pursue, and the future a relationship makes imaginable.",
        strength: "Letting love and desire bring meaning, vulnerability, and possibility into your choices.",
        tension: "A powerful feeling can become an idealized story. Keep sight of the person in front of you and the other parts of your life.",
        weights: { romantic_attachment: 0.8, courage: 0.1, kinship_friendship: 0.1 },
      },
      {
        id: "conqueror", title: "The Conqueror", quote: "You were not made to remain beneath anyone.",
        description: "You push against the place the world assigns you. Pride and the courage to challenge opposition give your story its momentum. You want achievement to make your claim impossible to ignore.",
        strength: "Meeting resistance with the determination to act and prove yourself.",
        tension: "Entitlement can turn criticism into a feud. Being feared is not being respected, and another person's success does not diminish yours.",
        weights: { arrogance_pride: 0.65, courage: 0.2, intelligence: 0.1, charisma: 0.05 },
        requires: { arrogance_pride: 60, courage: 50 },
      },
      {
        id: "lone-wolf", title: "The Lone Wolf", quote: "Your path is yours to choose.",
        description: "You want a life you can steer yourself. Your answers point to deliberate self-direction: taking responsibility for your route, trusting your judgment, and choosing when to walk alongside others.",
        strength: "Acting with autonomy, even when there is no ready-made group to guide you.",
        tension: "Independence can become isolation. Accepting good help does not mean handing someone else the pen.",
        weights: { independence: 0.6, low_kinship: 0.15, intelligence: 0.1, courage: 0.15 },
        requires: { independence: 65 },
      },
      {
        id: "wildcard", title: "The Wildcard", quote: "The expected move is rarely the only move.",
        description: "When a familiar route closes, you look for a different kind of doorway. Your answers suggest a taste for testing conventions and changing tactics. Your protagonist story finds possibility in the unscripted moment.",
        strength: "Improvising thoughtfully and noticing options that habit makes invisible.",
        tension: "A surprising move is not always a useful one. Let your experiments serve something you care about, rather than disruption for its own sake.",
        weights: { unconventionality: 0.65, intelligence: 0.15, courage: 0.1, trait_range: 0.1 },
        requires: { unconventionality: 65 },
      },
    ],
  };
  if (typeof module !== "undefined" && module.exports) module.exports = config;
  else root.AxiomQuizConfig = config;
})(typeof globalThis !== "undefined" ? globalThis : this);
