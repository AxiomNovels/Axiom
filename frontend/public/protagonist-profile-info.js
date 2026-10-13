// Show exactly the scoring rubric currently used by the profiler.
(async () => {
  const host = document.querySelector("[data-trait-guides]");
  try {
    const response = await fetch(`${API_BASE}/api/search/protagonist-definition`);
    if (!response.ok) throw new Error("Could not load trait definitions. Refresh to retry.");
    const definition = await response.json();
    const instructions = document.createElement("p");
    instructions.style.whiteSpace = "pre-wrap"; instructions.textContent = definition.instructions;
    host.append(instructions);
    definition.traits.forEach((trait, index) => {
      const details = document.createElement("details"); details.className = "trait-guide"; details.open = index === 0;
      const summary = document.createElement("summary"); summary.textContent = `${trait.name} · 0–100`;
      const body = document.createElement("div"); body.className = "trait-guide-body";
      const prompt = document.createElement("p"); prompt.style.whiteSpace = "pre-wrap"; prompt.textContent = trait.prompt;
      body.append(prompt); details.append(summary, body); host.append(details);
    });
  } catch (error) { host.textContent = error.message; }
})();
