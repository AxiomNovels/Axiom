
/* Campaign settings. Array order decides exact ties. */
(function (root) {
  const config = {
    version: 3,
    nearTieThreshold: 3,

    // These are the only seven traits shown or compared with characters.
    traits: [
      {
        key: "intelligence",
        name: "Intelligence",
        description: "How you think, learn, and solve problems.\nNot how much you know or how well educated you are."
      },
      {
        key: "charisma",
        name: "Charisma",
        description: "How you connect with, inspire, and persuade others.\nNot your looks, fame, or popularity."
      },
      {
        key: "courage",
        name: "Courage",
        description: "How you face fear, danger, and the unknown.\nNot acting without thinking or never feeling afraid."
      },
      {
        key: "moral_integrity",
        name: "Moral Integrity",
        description: "How well you stick to your values under pressure.\nNot simply following rules."
      },
      {
        key: "kinship_friendship",
        name: "Kinship & Friendship",
        description: "How much you value your friends, family, and chosen family.\nNot how much they value you."
      },
      {
        key: "romantic_attachment",
        name: "Romantic Attachment",
        description: "How much you value romance, attraction, and close romantic bonds.\nNot how attractive others find you."
      },
      {
        key: "arrogance_pride",
        name: "Arrogance & Pride",
        description: "How much you see yourself as better than others, expect special treatment, or refuse to admit you're wrong.\nNot confidence or skill alone."
      },
    ],

    patterns: ["independence", "unconventionality"],

    archetypes: [
      {
        id: "mastermind",
        title: "The Mastermind",
        quote: "You see the bigger picture.",
        description: "You look beyond the next move and see how things fit together. You prepare, study the rules, understand your rivals, and find chances others miss.",
        strength: "Finding patterns and making plans that can handle surprises.",
        tension: "People are not problems to solve. Too much planning can lead to control, manipulation, or waiting too long to act.",
        weights: { intelligence: 0.7, strategic_influence: 0.2, courage: 0.1 },
      },
      {
        id: "leader",
        title: "The Natural Leader",
        quote: "People follow when they believe in you.",
        description: "You bring people together around a shared goal. You listen, help others understand each other, and give people a reason to keep going.",
        strength: "Building trust and helping people work toward the same goal.",
        tension: "You may take on too much or worry too much about approval. Good leadership also means allowing others to disagree.",
        weights: { charisma: 0.65, kinship_friendship: 0.2, courage: 0.1, moral_integrity: 0.05 },
      },
      {
        id: "idealist",
        title: "The Idealist",
        quote: "Some things are worth standing up for.",
        description: "Winning is not enough if you have to give up what matters to you. Your choices are guided by your values, even when doing the right thing comes at a cost.",
        strength: "Standing by your beliefs, even when it is difficult.",
        tension: "Strong beliefs can make you unwilling to change. Stay open to new ideas, and remember that you do not have to sacrifice everything to help.",
        weights: { moral_integrity: 0.7, courage: 0.2, kinship_friendship: 0.1 },
      },
      {
        id: "guardian",
        title: "The Guardian",
        quote: "You fight for the people you love.",
        description: "The people close to you give your life meaning. You care about their needs, stay by their side, and find strength in protecting those who matter to you.",
        strength: "Showing loyalty through care, support, and commitment.",
        tension: "Wanting to protect people can turn into controlling them. Let others make their own choices, and remember to care for yourself too.",
        weights: { kinship_friendship: 0.7, courage: 0.15, moral_integrity: 0.1, romantic_attachment: 0.05 },
      },
      {
        id: "romantic",
        title: "The Romantic",
        quote: "Love can change everything.",
        description: "Love and attraction play a big part in your life. Your choices are shaped by the people you desire, the bonds you build, and the future you imagine with someone.",
        strength: "Finding meaning through love, closeness, and emotional connection.",
        tension: "Strong feelings can make you see people as you wish they were. Remember to see them as they really are, and make room for the rest of your life.",
        weights: { romantic_attachment: 0.8, courage: 0.1, kinship_friendship: 0.1 },
      },
      {
        id: "conqueror",
        title: "The Conqueror",
        quote: "You refuse to stay beneath anyone.",
        description: "You push back when others try to limit you. Pride and courage drive you to face challenges, prove your worth, and earn the success you believe you deserve.",
        strength: "Facing challenges and refusing to give up on your goals.",
        tension: "Pride can make it hard to accept criticism. Being feared is not the same as being respected, and someone else's success does not make yours less important.",
        weights: { arrogance_pride: 0.65, courage: 0.2, intelligence: 0.1, charisma: 0.05 },
        requires: { arrogance_pride: 60, courage: 50 },
      },
      {
        id: "lone-wolf",
        title: "The Lone Wolf",
        quote: "You choose your own path.",
        description: "You want control over your own life. You trust your judgment, make your own choices, and decide when to work with others.",
        strength: "Making your own decisions and taking charge of your life.",
        tension: "Being independent can turn into shutting people out. Accepting help does not mean giving up control.",
        weights: { independence: 0.6, low_kinship: 0.15, intelligence: 0.1, courage: 0.15 },
        requires: { independence: 65 },
      },
      {
        id: "wildcard",
        title: "The Wildcard",
        quote: "There is always another way.",
        description: "You do not always follow the usual path. You enjoy trying new things, questioning old ideas, and finding different ways to handle problems.",
        strength: "Thinking on your feet and finding options others overlook.",
        tension: "Doing something different is not always better. Make sure your choices have a purpose beyond simply being unexpected.",
        weights: { unconventionality: 0.65, intelligence: 0.15, courage: 0.1, trait_range: 0.1 },
        requires: { unconventionality: 65 },
      },
    ],
  };

  if (typeof module !== "undefined" && module.exports) module.exports = config;
  else root.AxiomQuizConfig = config;
})(typeof globalThis !== "undefined" ? globalThis : this);
