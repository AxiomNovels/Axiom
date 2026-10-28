/* Each vignette measures one dimension independently. Pattern questions are not extra Axiom traits. */
(function (root) {
  const question = (id, dimension, chapter, title, answers) => ({
    id, chapter, title,
    answers: answers.map(([text, points]) => ({ text, points: { [dimension]: points } })),
  });
  const questions = [
    question("sealed-door", "intelligence", "An unfamiliar world", "A sealed door has three clues. Your first attempt fails. What happens next?", [
      ["I compare the clues, test an explanation, and use the failure to revise it.", 100],
      ["I work out a simpler explanation and try the most likely solution.", 67],
      ["I follow an example, but struggle if the clues work differently.", 33],
      ["I keep repeating my first attempt, even after it clearly fails.", 0],
    ]),
    question("divided-table", "charisma", "An unfamiliar world", "Two groups at the inn refuse to cooperate. How does your attempt to bring them together go?", [
      ["I connect with a few people, but cannot shift the room.", 33],
      ["I understand their concerns and persuade both sides to try a shared plan.", 100],
      ["My explanation makes the disagreement worse; I cannot find a way through.", 0],
      ["I make a convincing case, though the most skeptical people remain unsure.", 67],
    ]),
    question("bridge", "courage", "An unfamiliar world", "Crossing a guarded bridge matters to your quest. You are afraid, even with a sensible plan. You…", [
      ["Turn back as soon as the fear arrives.", 0],
      ["Wait for someone to remove almost all the risk.", 33],
      ["Take precautions and cross, accepting that the fear may stay.", 100],
      ["Make an attempt after reassurance, but might retreat if the pressure rises.", 67],
    ]),
    question("reward", "moral_integrity", "The price of a choice", "You can claim a reward by blaming someone innocent. Nobody would discover the lie. You…", [
      ["Refuse and make sure the innocent person is safe, even if it costs the reward.", 100],
      ["Usually refuse, but might make an exception if the reward mattered enough.", 67],
      ["Feel uneasy, then take the reward if it solves my problems.", 33],
      ["Take it. Their fate is not a reason to give up an advantage.", 0],
    ]),
    question("letter", "kinship_friendship", "The price of a choice", "A close friend writes that they need you. Helping would interrupt a long-awaited opportunity. You…", [
      ["Offer what is easy, but keep my plans if helping becomes costly.", 33],
      ["Make meaningful time to help while trying to preserve some of my plans.", 67],
      ["Feel no personal pull to help; the bond does not affect my choice.", 0],
      ["Change my plans substantially. Their wellbeing matters deeply to me.", 100],
    ]),
    question("connection", "romantic_attachment", "The price of a choice", "On this imagined journey, what place do romantic or sexual feelings have in your life?", [
      ["They are a recurring, meaningful part of life alongside other ambitions.", 67],
      ["I do not experience those feelings; I can still care deeply in other ways.", 0],
      ["They are a central pull, often reshaping what I want and choose.", 100],
      ["They appear rarely or faintly, and seldom influence my priorities.", 33],
    ]),
    question("correction", "arrogance_pride", "The price of a choice", "A newcomer correctly points out a flaw in your plan in front of everyone. Your reaction?", [
      ["I thank them and change the plan. Their status does not matter.", 0],
      ["I bristle briefly, then accept the correction and give them credit.", 33],
      ["I resist admitting it and look for a way to preserve my superiority.", 67],
      ["I see it as an insult. Someone beneath me should not challenge me.", 100],
    ]),
    question("own-route", "independence", "Choose your own path", "Trusted companions offer a safe, workable route. You could also plan your own. What do you prefer?", [
      ["Their route. I want others to set the direction for me.", 0],
      ["My own route and responsibility, even though their help is available.", 100],
      ["A shared route with a little room for my own decisions.", 33],
      ["My own direction, with advice and occasional company along the way.", 67],
    ]),
    question("old-method", "unconventionality", "Choose your own path", "The guild has used the same method for years. It works, but the situation has changed. You…", [
      ["Try a small variation while keeping most of the familiar method.", 33],
      ["Keep the old method exactly; a different approach feels wrong by itself.", 0],
      ["Test a radically different approach on a small scale and adapt to what I learn.", 100],
      ["Question the assumptions and combine familiar tools in a new way.", 67],
    ]),
    question("contradiction", "intelligence", "When the plot turns", "New evidence contradicts your explanation of a mystery. How do you make sense of it?", [
      ["I miss the contradiction and stick with the explanation despite repeated failures.", 0],
      ["I weigh competing explanations and identify a test that distinguishes them.", 100],
      ["I recognize the problem, but need someone to explain what follows from it.", 33],
      ["I revise my explanation using the clearest evidence and learn from the mistake.", 67],
    ]),
    question("rally", "charisma", "When the plot turns", "Your group is discouraged. You try to restore their confidence. What is most like you?", [
      ["I help several people feel understood and willing to try again.", 67],
      ["I struggle to express myself and leave people more disconnected.", 0],
      ["I reach one familiar friend, but have little influence on the group.", 33],
      ["I find words that connect with different people and inspire real commitment.", 100],
    ]),
    question("opposition", "courage", "When the plot turns", "A powerful rival opposes something important to you. There is a real risk of failure. You…", [
      ["Act despite fear, preparing carefully for consequences I cannot remove.", 100],
      ["Give up the moment opposition appears, even when action is possible.", 0],
      ["Try if I have support, though sustained pressure may stop me.", 67],
      ["Only act if someone else takes on most of the danger.", 33],
    ]),
    question("own-harm", "moral_integrity", "What remains", "You discover that your successful plan unfairly harmed strangers. Repairing it would cost you. You…", [
      ["Hide it. Winning matters more than the harm.", 0],
      ["Take responsibility and make meaningful repairs even at a serious cost.", 100],
      ["Make repairs unless doing so would threaten something I badly want.", 67],
      ["Express regret, but do little if fixing it becomes inconvenient.", 33],
    ]),
    question("bonds", "kinship_friendship", "What remains", "Beyond a dramatic rescue, how do your closest bonds shape an ordinary chapter of life?", [
      ["I value them and make regular space for them among other priorities.", 67],
      ["They rarely matter beyond convenient company.", 33],
      ["Caring for these people is a defining motivation that repeatedly shapes my future.", 100],
      ["I feel no personal investment in maintaining them.", 0],
    ]),
    question("attachment", "romantic_attachment", "What remains", "When you imagine attraction or a romantic relationship, how much does your own desire influence your choices?", [
      ["It does not: I do not feel that attraction or desire for a romantic bond.", 0],
      ["It often redirects major choices; pursuing or preserving that connection is central.", 100],
      ["It has a small, occasional place that rarely changes my plans.", 33],
      ["It matters enough to make room for connection, alongside other goals.", 67],
    ]),
    question("recognition", "arrogance_pride", "What remains", "Someone less experienced receives recognition you hoped to earn. What runs through your mind?", [
      ["I deserve deference. I cannot tolerate being outshone by someone beneath me.", 100],
      ["I feel a little jealous, but can appreciate their work and learn from it.", 33],
      ["Their success is welcome; it does not make me worth less.", 0],
      ["I dismiss their achievement and assume I deserve more recognition.", 67],
    ]),
    question("autonomy", "independence", "The next chapter", "You are offered a place in a welcoming group, with support but little control over your direction. You…", [
      ["Prefer to set my own course and take responsibility, even if it is harder.", 100],
      ["Gladly let the group choose my goals and next steps.", 0],
      ["Want substantial autonomy, while staying open to useful collaboration.", 67],
      ["Prefer the shared structure, with occasional choices of my own.", 33],
    ]),
    question("improvise", "unconventionality", "The next chapter", "Your carefully prepared approach stops working. Another route would break with convention. You…", [
      ["Adjust a small detail, but strongly prefer the familiar approach.", 33],
      ["Try a new combination of tools and change course as feedback arrives.", 67],
      ["Reframe the problem, test an unexpected option, and freely revise my tactics.", 100],
      ["Keep following the original approach because it is the accepted way.", 0],
    ]),
  ];
  if (typeof module !== "undefined" && module.exports) module.exports = questions;
  else root.AxiomQuizQuestions = questions;
})(typeof globalThis !== "undefined" ? globalThis : this);
