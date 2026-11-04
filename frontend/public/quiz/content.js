/* Nine dilemmas; four defensible choices each. See frontend/QUIZ.md for the audit.
 * Every trait has 16 achievable points across six answer opportunities.
 * 30 answers award one trait; six also award a smaller secondary trait.
 * Independence and unconventionality are separate archetype signals, not traits.
 */
(function (root) {
  const question = (id, chapter, title, answers) => ({
    id, chapter, title,
    answers: answers.map(([text, points]) => ({ text, points })),
  });
  const questions = [
    question("last-ferry", "The city beyond the rain", "The last ferry leaves at dusk. Across the flooded city wait a sealed archive, people counting on your arrival, and someone whose last letter you keep rereading. There is time for one detour.", [
      ["Enter the unstable bell tower to compare its flood marks with the map. A reliable crossing could buy everyone more time.", { intelligence: 2, courage: 1 }],
      ["Visit the rival boat crews. If each agrees to carry the other's stranded passengers, neither has to sail half-empty.", { charisma: 3 }],
      ["Return a mistakenly issued travel seal. Keeping it would get you across, but leave its rightful holder behind.", { moral_integrity: 3 }],
      ["Follow the address on the letter. Even a brief meeting matters more than reaching the far bank tonight.", { romantic_attachment: 3 }],
    ]),
    question("glass-bridge", "The city beyond the rain", "A glass bridge can bear only four people at a time. The queue is growing, cracks are spreading, and the engineer cannot promise another safe crossing. Your traveling companions are scattered through the crowd.", [
      ["Ask the rival group leaders to announce the same boarding order. People may accept a delay if someone they trust explains it.", { charisma: 3 }],
      ["Take the first uncertain crossing with the inspection rope, then surrender your place on the waiting coach so the agreed queue stays fair.", { courage: 3, moral_integrity: 1 }],
      ["Gather your companions and cross in a later group together. You would rather share their uncertainty than leave anyone facing it alone.", { kinship_friendship: 3 }],
      ["Ask for the dispatcher's sash. You judge your decisions better than the committee's and want the final word before the cracks spread.", { arrogance_pride: 3 }],
    ]),
    question("borrowed-summer", "The city beyond the rain", "A winterbound village can borrow one evening of summer. The orchard would thaw, but the spell needs a memory you will never recall again. The villagers leave the choice to you.", [
      ["Offer a memory and enter the spell circle yourself. The loss frightens you, but someone must accept the uncertainty for the thaw to begin.", { courage: 3 }],
      ["Explain the permanent cost to every volunteer before proceeding. An informed refusal is worth the risk of losing tonight's chance.", { moral_integrity: 3 }],
      ["Give up the memory of a first kiss rather than the family reunion beside it. You would visit that person afterward to begin a new memory together.", { romantic_attachment: 3, kinship_friendship: 1 }],
      ["Test whether several small recollections can power a miniature thaw. The old rule may describe one working method rather than the only one.", { intelligence: 3, unconventionality: 2 }],
    ]),
    question("masked-auction", "What the city asks", "At a masked auction, one bid buys a stolen atlas, a friend's passage out of debt, or a private audience. You have enough silver for one, and the doors close at midnight.", [
      ["Buy the atlas and return it to the surveyors who made it. They should not have to pay for someone else's theft.", { moral_integrity: 3 }],
      ["Buy your friend's passage. Whatever opportunities the atlas holds, you came here knowing what their freedom would mean.", { kinship_friendship: 3 }],
      ["Bid for the audience, on the condition that you are received as an equal. You can offer useful news, but will not queue behind inherited titles.", { arrogance_pride: 3 }],
      ["Persuade the host to accept a performance instead of silver, and invite the guest you are drawn to as your partner. An improvised duet might buy you both an audience.", { charisma: 3, romantic_attachment: 1, unconventionality: 2 }],
    ]),
    question("rooms-at-the-inn", "What the city asks", "The only inn above the flood has one quiet room and a crowded attic. Your exhausted companions need rest; someone you are falling for asks whether you might stay up together. A warning bell keeps sounding outside.", [
      ["Give your companions the room and insist the innkeeper waive the usual allocation rule for your party. You believe your people deserve that exception.", { kinship_friendship: 3, arrogance_pride: 1 }],
      ["Take two chairs by the kitchen fire with the person who asked. You would trade a good night's sleep for time alone together.", { romantic_attachment: 3 }],
      ["Compare the bell intervals with the water marks before settling in. Knowing whether the warning is worsening will determine where everyone sleeps.", { intelligence: 3 }],
      ["Take a lantern and check the nearby embankment yourself. You prefer choosing your own watch to waiting for the inn's reassuring reports.", { courage: 3, independence: 2 }],
    ]),
    question("the-second-name", "What the city asks", "A renowned mapmaker offers to publish your discovery under their name. Their reputation would put it into every rescue boat by morning; negotiating could delay distribution. The person you love sails at dawn.", [
      ["Hand over your notes and spend the remaining hours at the harbor. You do not want this last evening together to become another negotiation.", { romantic_attachment: 3 }],
      ["Require your name above theirs and offer to spend the night briefing their crews. You will help earn the endorsement, but equal billing would still understate your contribution.", { arrogance_pride: 3 }],
      ["Find the wording that lets the mapmaker endorse the work without claiming it. You want both their cooperation and a public record you can accept.", { charisma: 3 }],
      ["Release the notes yourself, crediting every contributor and accepting the smaller reach. You would rather own that decision than sign someone else's account.", { moral_integrity: 3, independence: 2 }],
    ]),
    question("the-sleeping-machine", "Beneath the lanterns", "An ancient machine could drain the lower streets, but nobody agrees on its controls. You have one hour before the tide turns. Each approach has a credible advocate.", [
      ["Accept advice, but reserve the final decision for yourself. You trust your reading of the situation more than theirs and will put your name to the outcome.", { arrogance_pride: 3 }],
      ["Trace the channels, then test the pump in reverse on a small scale. Holding back new water might work better than trying to drain what is already inside.", { intelligence: 3, unconventionality: 2 }],
      ["Climb onto the exposed platform for a controlled trial, explaining each step to the frightened crew so they will stay at their posts.", { courage: 3, charisma: 1 }],
      ["Use the hour to bring your companions' households upstairs. You cannot settle the machine's mysteries, but you can make sure your people face the tide together.", { kinship_friendship: 3 }],
    ]),
    question("unwritten-road", "Beneath the lanterns", "At a crossroads, the guidebook describes two reliable routes. A third, unmarked road might save a day. You have promised to carry testimony to a hearing, while an unexpected invitation could change where you go afterward.", [
      ["Compare the abandoned milestones with the river's bends and chart your own route. You would rather navigate from your findings than place the choice in a guide's hands.", { intelligence: 2, independence: 2 }],
      ["Convince the two passing caravans to exchange scouts. Each can share what the other lacks, even if agreeing on terms costs the morning.", { charisma: 3 }],
      ["Keep to the dependable causeway to deliver the testimony on time. The witness relied on your promise, even if honoring it means passing up the other destinations.", { moral_integrity: 3 }],
      ["Choose the longer route past the invitation's address. You want to discover whether the connection you felt deserves more than a letter.", { romantic_attachment: 3 }],
    ]),
    question("the-last-page", "What you carry onward", "A patron offers to fund your next journey, provided their council chooses the destination. You could also travel with old companions, try an untested vessel, or pursue a smaller expedition on your own terms.", [
      ["Win the patron over, but make funding conditional on your having the final say. You believe your judgment deserves precedence over the council's, even if they withdraw.", { arrogance_pride: 3, independence: 2 }],
      ["Compare the supply records, seasonal winds, and likely returns before selecting a route. You would accept a smaller beginning for a sounder plan.", { intelligence: 3 }],
      ["Trial the new vessel on a short, demanding crossing with an escape boat nearby. Its unfamiliar design might open routes the established ships cannot reach.", { courage: 3, unconventionality: 2 }],
      ["Ask your old companions where they need to go, then build the journey around staying together. You care more about the company than the destination on the charter.", { kinship_friendship: 3 }],
    ]),
  ];
  if (typeof module !== "undefined" && module.exports) module.exports = questions;
  else root.AxiomQuizQuestions = questions;
})(typeof globalThis !== "undefined" ? globalThis : this);
