const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../../frontend/public/quiz/config.js");
const questions = require("../../frontend/public/quiz/content.js");
const { scoreAnswers, matchProtagonists } = require("../../frontend/public/quiz/engine.js");
const keys = config.traits.map(t => t.key);
const definition = { traits: config.traits };
const scores = n => Object.fromEntries(keys.map(key => [key, n]));
const chooseFor = (key, maximize = true) => questions.map(q => q.answers.reduce((best, answer, i) => {
  const value = answer.points[key] ?? 0;
  const previous = q.answers[best].points[key] ?? 0;
  return (maximize ? value > previous : value < previous) ? i : best;
}, 0));
const novel = (id, value, extra = {}) => ({ id, title: `Novel ${id}`, protagonist_profiles: [{ protagonist_name: `Hero ${id}`, ...scores(value), ...extra }] });

test("9 four-choice dilemmas give every trait the same total, attainable maximum, and six answer opportunities", () => {
  assert.deepEqual(keys, ["intelligence", "charisma", "courage", "moral_integrity", "kinship_friendship", "romantic_attachment", "arrogance_pride"]);
  assert.equal(questions.length, 9);
  assert.equal(new Set(questions.map(q => q.id)).size, 9);
  let dualAwards = 0;
  for (const question of questions) {
    assert.equal(question.answers.length, 4);
    for (const answer of question.answers) {
      const awards = keys.filter(key => key in answer.points).map(key => answer.points[key]).sort();
      assert.ok(JSON.stringify(awards) === '[2]' || JSON.stringify(awards) === '[1,2]' || JSON.stringify(awards) === '[3]' || JSON.stringify(awards) === '[1,3]');
      if (awards.length === 2) dualAwards++;
      assert.ok(Object.keys(answer.points).every(key => [...keys, ...config.patterns].includes(key)));
    }
  }
  assert.equal(dualAwards, 6);
  for (const key of keys) {
    const awards = questions.flatMap(q => q.answers.map(a => a.points[key] ?? 0));
    assert.equal(awards.filter(value => value > 0).length, 6, key);
    assert.equal(awards.filter(value => value === 3).length, key === "intelligence" ? 4 : 5, key);
    assert.equal(awards.filter(value => value === 2).length, key === "intelligence" ? 2 : 0, key);
    assert.equal(awards.filter(value => value === 1).length, key === "intelligence" ? 0 : 1, key);
    assert.equal(awards.reduce((sum, value) => sum + value, 0), 16, key);
    assert.equal(questions.reduce((sum, q) => sum + Math.max(...q.answers.map(a => a.points[key] ?? 0)), 0), 16, key);
    for (let position = 0; position < 4; position++) {
      // 36 main awards cannot divide evenly across seven traits and four positions.
      // Each trait must still occur as a main award once or twice per position.
      const count = questions.filter(q => (q.answers[position].points[key] ?? 0) >= 2).length;
      assert.ok(count >= 1 && count <= 2, `${key} at ${position}`);
    }
  }
  for (const pattern of config.patterns) {
    const awards = questions.flatMap(q => q.answers.map(a => a.points[pattern] ?? 0));
    assert.equal(awards.filter(value => value === 2).length, 4);
    assert.equal(awards.reduce((sum, value) => sum + value, 0), 8);
  }
  for (const archetype of config.archetypes) assert.ok(Math.abs(Object.values(archetype.weights).reduce((a, b) => a + b) - 1) < 1e-9);
});

test("each dimension can independently reach both normalized endpoints", () => {
  for (const key of [...keys, ...config.patterns]) {
    const high = scoreAnswers(questions, chooseFor(key), config);
    const low = scoreAnswers(questions, chooseFor(key, false), config);
    const section = keys.includes(key) ? "traits" : "patterns";
    assert.equal(high[section][key], 100, key);
    assert.equal(low[section][key], 0, key);
  }
});

test("a dual-credit choice adds only its specified primary and secondary traits", () => {
  const answers = Array(9).fill(0);
  const first = scoreAnswers(questions, answers, config);
  // In the ferry dilemma, change Intelligence + Courage to Romantic Attachment.
  answers[0] = 3;
  const second = scoreAnswers(questions, answers, config);
  const difference = { intelligence: -2, courage: -1, romantic_attachment: 3 };
  for (const key of keys) {
    assert.ok(Math.abs(second.traits[key] - first.traits[key] - (difference[key] ?? 0) * 100 / 16) < 1e-9, key);
  }
  assert.deepEqual(first.patterns, second.patterns);
  assert.equal(first.traits.kinship_friendship, second.traits.kinship_friendship);
});

test("all mandatory questions must be valid, including sparse arrays", () => {
  for (const answers of [[], Array(9), Array(9).fill(null), Array(9).fill(-1), Array(9).fill(4), Array(9).fill("0"), Array(14).fill(0)]) {
    assert.throws(() => scoreAnswers(questions, answers, config), /Answer every question/);
  }
});

test("all eight archetypes remain reachable with the revised dilemmas", () => {
  const targets = { mastermind: "intelligence", leader: "charisma", idealist: "moral_integrity", guardian: "kinship_friendship", romantic: "romantic_attachment", "lone-wolf": "independence", wildcard: "unconventionality" };
  for (const [expected, key] of Object.entries(targets)) {
    assert.equal(scoreAnswers(questions, chooseFor(key), config).primary.id, expected);
  }
  // Prioritize personal authority, while accepting danger at the tower, spell,
  // embankment, and vessel trial; pride alone is still insufficient.
  const conqueror = [0, 3, 0, 2, 3, 1, 0, 0, 2];
  const result = scoreAnswers(questions, conqueror, config);
  assert.equal(result.primary.id, "conqueror");
  assert.ok(result.traits.arrogance_pride >= 60 && result.traits.courage >= 50);
});

test("low friendship, balanced scores, and timid conceit alone do not grant special archetypes", () => {
  const points = { ...scores(50), kinship_friendship: 0, arrogance_pride: 100, courage: 0, independence: 0, unconventionality: 0 };
  const fixture = [{ answers: [{ points: { ...scores(0), independence: 0, unconventionality: 0 } }, { points: { ...scores(100), independence: 100, unconventionality: 100 } }, { points }] }];
  const result = scoreAnswers(fixture, [2], config);
  assert.ok(result.ranked.every(r => !["lone-wolf", "wildcard", "conqueror"].includes(r.archetype.id)));
});

test("fixed ties and inclusive three-point secondary threshold use unrounded scores", () => {
  const fakeQuestions = [{ answers: [0, 100].map(value => ({ points: { ...scores(value), independence: value, unconventionality: value } })) }];
  const custom = difference => ({ ...config, archetypes: [
    { id: "first", weights: { intelligence: 1 } },
    { id: "second", weights: { intelligence: 1 - difference / 100 } },
  ] });
  for (const difference of [0, 2.99, 3]) {
    const result = scoreAnswers(fakeQuestions, [1], custom(difference));
    assert.equal(result.primary.id, "first"); assert.equal(result.secondary.id, "second");
  }
  assert.equal(scoreAnswers(fakeQuestions, [1], custom(3.01)).secondary, null);
});

test("normalized Euclidean distance has known endpoints and ranks the full catalog before taking ten", () => {
  const ranked = matchProtagonists(scores(100), Array.from({ length: 25 }, (_, i) => novel(i + 1, i * 4)), definition, config);
  assert.equal(ranked.matches.length, 10);
  assert.equal(ranked.matches[0].novel.id, 25);
  assert.equal(ranked.matches[0].distance, 4);
  assert.equal(ranked.matches[0].similarity, 96);
  const endpoints = matchProtagonists(scores(100), [novel(1, 0), novel(2, 100)], definition, config).matches;
  assert.equal(endpoints[0].similarity, 100); assert.equal(endpoints[1].similarity, 0);
  const varied = matchProtagonists(scores(0), [novel(1, 0, { courage: 100 })], definition, config).matches[0];
  assert.ok(Math.abs(varied.distance - 100 / Math.sqrt(7)) < 1e-9);
});

test("invalid, missing, and unnamed profiles are excluded; zero is a real score", () => {
  const bad = [null, undefined, "50", NaN, Infinity, -1, 101].map((value, i) => novel(i + 1, 50, { intelligence: value }));
  bad.push(novel(20, 50, { protagonist_name: " " }));
  bad.push({ id: 21, protagonist_profiles: [] });
  const result = matchProtagonists(scores(0), [...bad, novel(22, 0)], definition, config);
  assert.deepEqual(result.matches.map(m => m.novel.id), [22]);
});

test("shared dimensions are consistent across candidates and omissions are explicit", () => {
  const partialDefinition = { traits: config.traits.filter(t => t.key !== "courage") };
  const result = matchProtagonists(scores(50), [novel(1, 50, { courage: null }), novel(2, 50, { courage: 100 })], partialDefinition, config);
  assert.equal(result.compared.length, 6);
  assert.deepEqual(result.omitted.map(t => t.key), ["courage"]);
  assert.equal(result.matches[0].similarity, result.matches[1].similarity);
  assert.equal(matchProtagonists(scores(50), [novel(1, 50)], { traits: [{ key: "unknown" }] }, config).matches.length, 0);
});

test("stable catalog ties, strongest overlap, object embeds and duplicates", () => {
  const first = novel(3, 50, { intelligence: 70 });
  first.protagonist_profiles = first.protagonist_profiles[0];
  const result = matchProtagonists({ ...scores(50), intelligence: 70 }, [first, novel(2, 50), first], definition, config);
  assert.equal(result.matches.length, 2);
  assert.equal(result.matches[0].novel.id, 3);
  assert.equal(result.matches[0].overlap.trait.key, "intelligence");
  const ties = matchProtagonists(scores(50), [novel(10, 50), novel(1, 50)], definition, config);
  assert.deepEqual(ties.matches.map(m => m.novel.id), [1, 10]);
});
