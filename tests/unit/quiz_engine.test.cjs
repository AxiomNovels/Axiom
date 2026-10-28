const test = require("node:test");
const assert = require("node:assert/strict");
const config = require("../../frontend/public/quiz/config.js");
const questions = require("../../frontend/public/quiz/content.js");
const { scoreAnswers, matchProtagonists } = require("../../frontend/public/quiz/engine.js");
const keys = config.traits.map(t => t.key);
const definition = { traits: config.traits };
const scores = n => Object.fromEntries(keys.map(key => [key, n]));
const selections = values => questions.map(q => {
  const key = Object.keys(q.answers[0].points)[0];
  const target = values[key] ?? 33;
  return q.answers.reduce((best, a, i) => Math.abs(a.points[key] - target) < Math.abs(q.answers[best].points[key] - target) ? i : best, 0);
});
const novel = (id, value, extra = {}) => ({ id, title: `Novel ${id}`, protagonist_profiles: [{ protagonist_name: `Hero ${id}`, ...scores(value), ...extra }] });

test("exactly the requested seven independent traits, each with two measurable questions", () => {
  assert.deepEqual(keys, ["intelligence", "charisma", "courage", "moral_integrity", "kinship_friendship", "romantic_attachment", "arrogance_pride"]);
  for (const key of [...keys, ...config.patterns]) assert.equal(questions.filter(q => key in q.answers[0].points).length, 2);
  for (const archetype of config.archetypes) assert.ok(Math.abs(Object.values(archetype.weights).reduce((a, b) => a + b) - 1) < 1e-9);
});

test("normalizes attainable bounds and does not conflate romance with friendship", () => {
  const low = Object.fromEntries([...keys, ...config.patterns].map(key => [key, 0]));
  const high = Object.fromEntries([...keys, ...config.patterns].map(key => [key, 100]));
  assert.deepEqual(scoreAnswers(questions, selections(low), config).traits, scores(0));
  assert.deepEqual(scoreAnswers(questions, selections(high), config).traits, scores(100));
  assert.equal(scoreAnswers(questions, selections(high), config).primary.id, "mastermind");
  const result = scoreAnswers(questions, selections({ ...low, kinship_friendship: 100 }), config);
  assert.equal(result.traits.romantic_attachment, 0);
  assert.equal(result.traits.kinship_friendship, 100);
});

test("all mandatory questions must be valid, including sparse arrays", () => {
  for (const answers of [[], Array(18), Array(18).fill(null), Array(18).fill(-1), Array(18).fill(4), Array(18).fill("0")]) {
    assert.throws(() => scoreAnswers(questions, answers, config), /Answer every question/);
  }
});

test("each archetype is reachable through a representative answer pattern", () => {
  const patterns = {
    mastermind: { intelligence: 100, charisma: 67 },
    leader: { charisma: 100, kinship_friendship: 67, courage: 67 },
    idealist: { moral_integrity: 100, courage: 67 },
    guardian: { kinship_friendship: 100, courage: 67 },
    romantic: { romantic_attachment: 100 },
    conqueror: { arrogance_pride: 100, courage: 100 },
    "lone-wolf": { independence: 100, kinship_friendship: 0, courage: 67, intelligence: 67 },
    wildcard: { unconventionality: 100, intelligence: 67, courage: 67 },
  };
  for (const [expected, values] of Object.entries(patterns)) assert.equal(scoreAnswers(questions, selections(values), config).primary.id, expected);
});

test("low friendship, balanced scores, and timid conceit alone do not grant special archetypes", () => {
  const result = scoreAnswers(questions, selections({ kinship_friendship: 0, arrogance_pride: 100, courage: 0, independence: 0, unconventionality: 0 }), config);
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
