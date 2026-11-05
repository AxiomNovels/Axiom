/*
 * Nine dilemmas; four defensible choices each.
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
    question("last-ferry", "The world according to you", "The last ferry leaves in one hour. Across the river, a town is waiting for supplies. You also have a letter from someone you have not seen in years. There is time to do only one thing before the ferry leaves.", [
      ["Climb the old tower and check how high the water has risen. A better estimate could help everyone cross safely.", { intelligence: 2, courage: 1 }],
      ["Bring the two arguing ferry crews together. If they work as one team, more people can make the crossing.", { charisma: 3 }],
      ["Return a ticket you found in your coat. It could get someone else onto the ferry, but you would lose your only chance.", { moral_integrity: 3 }],
      ["Go to the address on the letter. You may miss the ferry, but you cannot ignore the chance to see that person again.", { romantic_attachment: 3 }],
    ]),

    question("glass-bridge", "The world according to you", "A glass bridge connects two parts of the city. It can only carry four people at a time, and cracks are starting to spread. Your friends are somewhere in the growing crowd. Everyone wants to cross but is also afraid.", [
      ["Talk to the group leaders and agree on a fair order. People may be willing to wait if someone they trust explains the plan.", { charisma: 3 }],
      ["Cross first with a safety rope and help test the bridge.", { courage: 3, moral_integrity: 1 }],
      ["Find your friends and wait for a crossing together. Getting everyone across matters more than getting there first.", { kinship_friendship: 3 }],
      ["Take charge of the crossing yourself. Too many people are arguing, and you think you can make better decisions.", { arrogance_pride: 3 }],
    ]),

    question("borrowed-summer", "The world according to you", "A village has been trapped in winter for years. A spell could bring back summer for one evening, but someone must give up a precious memory forever. The villagers have asked you to decide what happens.", [
      ["Give up one of your own memories. It is frightening, but you are willing to take the risk yourself.", { courage: 3 }],
      ["Tell everyone exactly what the spell will cost. Nobody should have to make this choice without knowing the truth.", { moral_integrity: 3 }],
      ["Give up the memory of your first love. You can make new memories with that person, but you cannot ask someone else to pay.", { romantic_attachment: 3, kinship_friendship: 1 }],
      ["Look for another way to power the spell. Perhaps several small memories could work instead of one precious one.", { intelligence: 3, unconventionality: 2 }],
    ]),

    question("masked-auction", "Pride and friendship", "At a secret auction, you have enough money for one prize. An old map could reveal a lost city. Your closest friend needs money to escape a dangerous debt. Or you could meet someone who may have answers about your past. The auction ends at midnight.", [
      ["Buy the map and return it to the people it was stolen from. They should not have to pay for someone else's theft.", { moral_integrity: 3 }],
      ["Pay your friend's debt. You can search for lost cities another day, but your friend needs help now.", { kinship_friendship: 3 }],
      ["Buy the private meeting, but insist on being treated as an equal. You have something to offer, and you will not beg for someone's attention.", { arrogance_pride: 3 }],
      ["Offer to perform at the auction instead of paying. Invite the person you want to meet to join you. A good performance might win you both a chance to talk.", { charisma: 3, romantic_attachment: 1, unconventionality: 2 }],
    ]),

    question("rooms-at-the-inn", "Pride and friendship", "A storm has forced you and your companions into a small inn. There is only one proper room left. Your friends are exhausted, someone you have feelings for asks you to stay by the fire, and a warning bell keeps ringing outside.", [
      ["Give the room to your friends. Then ask the innkeeper to make an exception and find space for everyone else.", { kinship_friendship: 3, arrogance_pride: 1 }],
      ["Stay by the fire with the person who asked. You may be tired tomorrow, but tonight feels worth it.", { romantic_attachment: 3 }],
      ["Check the warning bell and compare it with the rising water. You want to know how serious the danger really is before choosing where everyone sleeps.", { intelligence: 3 }],
      ["Take a lantern and inspect the nearby road yourself. You would rather face the danger than wait for someone else to tell you what is happening.", { courage: 3, independence: 2 }],
    ]),

    question("the-second-name", "Pride and friendship", "You have discovered a new route that could save hundreds of lives. A famous explorer offers to publish it under their name. Their reputation could spread the news by morning, but you would get no credit. Someone you love is leaving at dawn.", [
      ["Let them publish it. Spend your remaining time with the person you love. There are things more important than recognition.", { romantic_attachment: 3 }],
      ["Demand that your name comes first. You made the discovery, and you will not pretend otherwise just to please someone famous.", { arrogance_pride: 3 }],
      ["Find a way to share the credit. They have the influence to spread the news, and you have the work to back it up.", { charisma: 3 }],
      ["Publish the discovery yourself and name everyone who helped. It may reach fewer people, but the decision will be yours.", { moral_integrity: 3, independence: 2 }],
    ]),

    question("the-sleeping-machine", "The great decision", "An old machine beneath the city could stop a flood. Nobody knows exactly how it works, and the water will reach the streets in one hour. Some people want to turn it on right away. Others say it could make things worse.", [
      ["Listen to the advice, but make the final decision yourself. You trust your intelligence and are ready to take responsibility.", { arrogance_pride: 3 }],
      ["Study the pipes and test one small part first. There may be a safer way to stop the water than simply turning the machine on.", { intelligence: 3, unconventionality: 2 }],
      ["Go down to the machine and try to start it. Explain your plan to the others and ask them to help.", { courage: 3, charisma: 1 }],
      ["Move your friends and their families to higher ground. You cannot save the whole city alone, but you can protect the people close to you.", { kinship_friendship: 3 }],
    ]),

    question("unwritten-road", "The great decision", "You are carrying an important message to a distant town. The map shows two safe roads, but a stranger tells you about a third road that could save a whole day. Along the way, you receive an invitation from someone you would like to meet.", [
      ["Study the land and try to find the third road yourself. You trust what you can discover more than what someone tells you.", { intelligence: 2, independence: 2 }],
      ["Ask two passing travelers to share what they know. Together, you might find a better route than any of you could find alone.", { charisma: 3 }],
      ["Take the safe road and deliver the message on time. Someone is counting on you, and you will not break your promise.", { moral_integrity: 3 }],
      ["Take the longer road past the invitation's address. You want to meet this person, even if it means arriving a day late.", { romantic_attachment: 3 }],
    ]),

    question("the-last-page", "The great decision", "Your journey is almost over. A wealthy patron offers to pay for your next adventure, but only if they choose where you go. Your old friends want to travel with you, and a strange new ship has just arrived at the harbor. You must decide what comes next.", [
      ["Tell the patron you will accept the money, but only if you can choose the destination yourself. There is a chance they may say no.", { arrogance_pride: 3, independence: 2 }],
      ["Study the routes, costs, and weather yourself before making a choice. A good plan is worth more than an exciting promise.", { intelligence: 3 }],
      ["Take your friends with you on the new ship on a short test journey. It may be risky, but you would rather discover what is possible than keep doing what is familiar.", { courage: 3, unconventionality: 2 }],
      ["Ask your friends where they want to go and plan the journey together. The people beside you matter more than the place you reach.", { kinship_friendship: 3 }],
    ]),
  ];

  if (typeof module !== "undefined" && module.exports) module.exports = questions;
  else root.AxiomQuizQuestions = questions;
})(typeof globalThis !== "undefined" ? globalThis : this);