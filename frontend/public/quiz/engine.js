/* Pure scoring and catalogue matching: no DOM, network, storage, or randomness. */
(function (root) {
  function scoreAnswers(questions, answers, config) {
    if (answers.length !== questions.length || questions.some((q, i) => !Number.isInteger(answers[i]) || !q.answers[answers[i]])) {
      throw new Error("Answer every question before revealing your result.");
    }
    const values = {};
    for (const key of [...config.traits.map(t => t.key), ...config.patterns]) {
      let total = 0, minimum = 0, maximum = 0;
      questions.forEach((q, i) => {
        const options = q.answers.map(a => a.points[key] ?? 0);
        total += q.answers[answers[i]].points[key] ?? 0;
        minimum += Math.min(...options);
        maximum += Math.max(...options);
      });
      if (maximum === minimum) throw new Error(`No scoring range for ${key}`);
      values[key] = 100 * (total - minimum) / (maximum - minimum);
    }
    const traits = Object.fromEntries(config.traits.map(t => [t.key, values[t.key]]));
    const inputs = { ...values, strategic_influence: Math.max(values.charisma, values.arrogance_pride),
      low_kinship: 100 - values.kinship_friendship,
      trait_range: Math.max(...Object.values(traits)) - Math.min(...Object.values(traits)) };
    const ranked = config.archetypes.map((archetype, priority) => ({
      archetype, priority,
      eligible: Object.entries(archetype.requires || {}).every(([key, min]) => inputs[key] >= min),
      score: Object.entries(archetype.weights).reduce((sum, [key, weight]) => sum + inputs[key] * weight, 0),
    })).filter(a => a.eligible).sort((a, b) => Math.abs(b.score - a.score) < 1e-9 ? a.priority - b.priority : b.score - a.score);
    return { traits, patterns: Object.fromEntries(config.patterns.map(key => [key, values[key]])),
      primary: ranked[0].archetype,
      secondary: ranked[1] && ranked[0].score - ranked[1].score <= config.nearTieThreshold + 1e-9 ? ranked[1].archetype : null,
      ranked };
  }

  function matchProtagonists(traits, novels, definition, config) {
    if (!Array.isArray(novels) || !Array.isArray(definition?.traits) || !definition.traits.length) {
      throw new Error("The catalogue response is unavailable.");
    }
    const active = new Set(definition.traits.map(t => t.key));
    const compared = config.traits.filter(t => active.has(t.key));
    const omitted = config.traits.filter(t => !compared.includes(t));
    const matches = [];
    if (!compared.length) return { matches, compared, omitted };
    const validScore = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 100;
    if (!compared.every(t => validScore(traits[t.key]))) throw new Error("Invalid quiz scores.");
    const seen = new Set();
    for (const novel of novels) {
      if (!Number.isSafeInteger(Number(novel.id)) || Number(novel.id) <= 0 || seen.has(String(novel.id))) continue;
      const profiles = Array.isArray(novel.protagonist_profiles) ? novel.protagonist_profiles : [novel.protagonist_profiles];
      let best = null;
      for (const profile of profiles) {
        if (!profile?.protagonist_name?.trim() || !compared.every(t => validScore(profile[t.key]))) continue;
        const gaps = compared.map(t => ({ trait: t, gap: Math.abs(traits[t.key] - profile[t.key]), score: profile[t.key] }));
        // Euclidean distance divided by sqrt(n): 0..100, regardless of dimension count.
        const distance = Math.sqrt(gaps.reduce((sum, item) => sum + item.gap ** 2, 0) / compared.length);
        gaps.sort((a, b) => a.gap - b.gap || traits[b.trait.key] - traits[a.trait.key]);
        const match = { novel, protagonist: profile.protagonist_name, distance, similarity: 100 - distance, overlap: gaps[0] };
        if (!best || distance < best.distance) best = match;
      }
      if (best) { matches.push(best); seen.add(String(novel.id)); }
    }
    matches.sort((a, b) => a.distance - b.distance || Number(a.novel.id) - Number(b.novel.id));
    return { matches: matches.slice(0, 10), compared, omitted };
  }
  const engine = { scoreAnswers, matchProtagonists };
  if (typeof module !== "undefined" && module.exports) module.exports = engine;
  else root.AxiomQuizEngine = engine;
})(typeof globalThis !== "undefined" ? globalThis : this);
