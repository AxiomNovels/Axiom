/* UI state stays in memory; neither quiz answers nor scores are transmitted. */
(() => {
  const config = window.AxiomQuizConfig;
  const questions = window.AxiomQuizQuestions;
  const engine = window.AxiomQuizEngine;
  const byId = id => document.getElementById(id);
  let answers = Array(questions.length).fill(null);
  let index = 0;
  let result = null;
  let requestController = null;
  const start = byId("start-quiz");
  start.disabled = false;

  function showScreen(name, focusId) {
    for (const id of ["intro", "questions", "result"]) byId(id).hidden = id !== name;
    if (focusId) byId(focusId).focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function renderQuestion() {
    const question = questions[index];
    byId("chapter").textContent = question.chapter;
    byId("progress-text").textContent = `Question ${index + 1} of ${questions.length}`;
    byId("quiz-progress").max = questions.length;
    byId("quiz-progress").value = answers.filter(Number.isInteger).length;
    byId("question-title").textContent = question.title;
    byId("answers").replaceChildren();
    question.answers.forEach((answer, answerIndex) => {
      const label = document.createElement("label");
      label.className = "answer-option";
      const radio = document.createElement("input");
      radio.type = "radio"; radio.name = "answer"; radio.value = String(answerIndex); radio.required = true;
      radio.checked = answers[index] === answerIndex;
      radio.addEventListener("change", () => {
        answers[index] = answerIndex;
        byId("next").disabled = false;
        byId("quiz-progress").value = answers.filter(Number.isInteger).length;
      });
      const text = document.createElement("span");
      text.textContent = answer.text;
      label.append(radio, text);
      byId("answers").append(label);
    });
    byId("next").disabled = !Number.isInteger(answers[index]);
    byId("next").textContent = index === questions.length - 1 ? "Reveal my archetype →" : "Next →";
    showScreen("questions", "question-title");
  }

  start.addEventListener("click", () => renderQuestion());
  byId("back").addEventListener("click", () => {
    if (index === 0) showScreen("intro", "start-quiz");
    else { index--; renderQuestion(); }
  });
  byId("question-form").addEventListener("submit", event => {
    event.preventDefault();
    if (!Number.isInteger(answers[index])) return;
    if (index < questions.length - 1) { index++; renderQuestion(); }
    else renderResult();
  });

  function renderResult() {
    result = engine.scoreAnswers(questions, answers, config);
    byId("result-title").textContent = result.primary.title;
    byId("result-quote").textContent = `“${result.primary.quote}”`;
    byId("result-description").textContent = result.primary.description;
    byId("result-strength").textContent = result.primary.strength;
    byId("result-tension").textContent = result.primary.tension;
    byId("result-art").src = `/quiz/art/${result.primary.id}.svg`;
    byId("result-art").alt = `An illustrated emblem for ${result.primary.title}`;
    byId("secondary").hidden = !result.secondary;
    byId("secondary").textContent = result.secondary ? `A secondary influence: ${result.secondary.title}. Your two closest archetypes are within ${config.nearTieThreshold} points.` : "";
    byId("trait-scores").replaceChildren();
    config.traits.forEach(trait => {
      const score = Math.round(result.traits[trait.key]);
      const row = document.createElement("div"); row.className = "trait-row";
      const label = document.createElement("div"); label.className = "trait-label";
      const name = document.createElement("span"); name.textContent = trait.name;
      const value = document.createElement("output"); value.textContent = `${score}%`;
      value.setAttribute("aria-label", `${trait.name}: ${score} out of 100`);
      label.append(name, value);
      const track = document.createElement("div"); track.className = "trait-track"; track.setAttribute("aria-hidden", "true");
      const bar = document.createElement("span"); bar.style.width = `${score}%`; track.append(bar);
      const details = document.createElement("details");
      const summary = document.createElement("summary"); summary.textContent = `What ${trait.name} measures`;
      const description = document.createElement("p"); description.textContent = trait.description;
      details.append(summary, description); row.append(label, track, details);
      byId("trait-scores").append(row);
    });
    byId("result").querySelectorAll("details").forEach(details => { details.open = false; });
    showScreen("result", "result-title");
    void loadMatches();
  }

  function card(match, rank) {
    const item = document.createElement("li"); item.className = "match-card";
    const cover = document.createElement("div"); cover.className = "match-cover";
    cover.textContent = "✦"; cover.setAttribute("aria-label", "Cover unavailable");
    try {
      const url = new URL(match.novel.cover_image_url);
      if (["https:", "http:"].includes(url.protocol)) {
        const img = document.createElement("img"); img.src = url.href;
        img.alt = `${match.novel.title} cover`; img.loading = "lazy"; img.referrerPolicy = "no-referrer";
        img.addEventListener("error", () => { img.remove(); cover.textContent = "✦"; cover.setAttribute("aria-label", "Cover unavailable"); });
        cover.replaceChildren(img); cover.removeAttribute("aria-label");
      }
    } catch { /* Keep the local placeholder when a cover is missing or invalid. */ }
    const copy = document.createElement("div"); copy.className = "match-copy";
    const similarity = document.createElement("span"); similarity.className = "match-similarity";
    similarity.textContent = `${String(rank).padStart(2, "0")} · ${match.similarity.toFixed(1)}% similarity`;
    const title = document.createElement("h3"); const link = document.createElement("a");
    link.href = `/novel.html?id=${encodeURIComponent(match.novel.id)}`; link.textContent = match.novel.title || "Untitled novel"; title.append(link);
    const protagonist = document.createElement("p"); protagonist.textContent = `Protagonist: ${match.protagonist}`;
    const overlap = document.createElement("p");
    overlap.textContent = `Strongest overlap: ${match.overlap.trait.name}`;
    copy.append(similarity, title, protagonist, overlap); item.append(cover, copy);
    return item;
  }

  async function loadMatches() {
    requestController?.abort();
    const controller = new AbortController(); requestController = controller;
    const timeout = setTimeout(() => controller.abort(), 20000);
    byId("match-list").replaceChildren(); byId("match-list").setAttribute("aria-busy", "true");
    byId("match-status").textContent = "Finding familiar spirits in the Axiom catalog…";
    byId("match-basis").textContent = ""; byId("retry-matches").hidden = true;
    try {
      const responses = await Promise.all([
        fetch(`${API_BASE}/api/search`, { signal: controller.signal }),
        fetch(`${API_BASE}/api/search/protagonist-definition`, { signal: controller.signal }),
      ]);
      if (responses.some(response => !response.ok)) throw new Error("Catalog unavailable");
      const [novels, definition] = await Promise.all(responses.map(response => response.json()));
      if (requestController !== controller) return;
      const ranked = engine.matchProtagonists(result.traits, novels, definition, config);
      byId("match-basis").textContent = ranked.omitted.length
        ? `Compared on ${ranked.compared.length} shared traits: ${ranked.compared.map(t => t.name).join(", ")}. Not compared because they are absent from the current catalog definition: ${ranked.omitted.map(t => t.name).join(", ")}.`
        : "Compared across all seven traits, with equal weight. Closest profiles appear first.";
      byId("match-status").textContent = ranked.matches.length
        ? `${ranked.matches.length} closest ${ranked.matches.length === 1 ? "match" : "matches"}${ranked.matches.length < 10 ? " available with complete comparable profiles" : ""}.`
        : "No protagonists with complete comparable profiles are available yet. Try the Finder or browse popular novels while the catalog grows.";
      ranked.matches.forEach((match, i) => byId("match-list").append(card(match, i + 1)));
    } catch {
      if (requestController !== controller) return;
      byId("match-status").textContent = "Your archetype is ready, but protagonist matches could not load. Please try again; your result and answers are still here.";
      byId("retry-matches").hidden = false;
    } finally {
      clearTimeout(timeout);
      if (requestController === controller) byId("match-list").setAttribute("aria-busy", "false");
    }
  }
  function cancelMatches() { requestController?.abort(); requestController = null; }
  byId("retry-matches").addEventListener("click", () => void loadMatches());
  byId("retake").addEventListener("click", () => {
    cancelMatches(); answers = Array(questions.length).fill(null); index = 0; result = null;
    renderQuestion();
  });
  byId("review-answers").addEventListener("click", () => { cancelMatches(); index = 0; renderQuestion(); });
})();
