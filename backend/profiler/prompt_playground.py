"""
To run:
python profile_novel.py NOVEL_ID

flags:
--save

Generates the protagonist profile.
"""

MEASURES = (
    "intellectual_drive",
    "arrogance_pride",
    "kinship_friendship",
    "romantic_attachment",
    "selflessness_selfishness",
    "pragmatism_morality",
    "individualist_collectivist",
    "ambition",
    "cautious_risk_taker",
    "leadership",
)


RUBRIC = """
SCORING RULES
- Use absolute 0-100 scales, not comparisons with other characters. The anchors below
  are authoritative; interpolate between them only when the evidence genuinely falls
  between two anchors.
- 0 means explicit, narratively meaningful absence where the trait is a presence/absence
  measure. Never assign 0 merely because the synopsis or comments do not mention a trait.
- For spectrum measures, 0 and 100 represent the two opposing behavioral poles described
  below. Do not interpret either endpoint as inherently good or bad.
- 20 is the cautious limited-evidence region when a trait is outside the main storyline,
  barely discussed, or supported by unclear evidence and nothing contradicts a low score.
- Score and confidence are different. Sparse/conflicting evidence lowers confidence. It
  does not prove a trait is absent. A score of 50 is not a default for uncertainty.
- Judge how strongly the trait shapes identity, behavior, relationships, and decisions,
  not how often a keyword occurs.
- Do not infer a trait merely from genre, tags, character archetypes, or the absence of
  explicit evidence. Use those only as contextual evidence.
- Distinguish traits that may look similar. For example, intellectual drive is about
  motivation to understand or discover, ambition is about pursuing advancement, and
  leadership is about directing or organizing other people.
- Treat reader comments as fallible opinions. Do not invent plot facts.


INTELLECTUAL_DRIVE (0 absent -> 100 major intellectual theme)
Measures how strongly the protagonist is motivated by curiosity, understanding,
investigation, learning, experimentation, discovery, or solving intellectual problems.
This is NOT a measure of intelligence, education, competence, or how knowledgeable the
protagonist happens to be.

0 means the protagonist shows no meaningful interest in exploring, understanding, or
discovering things, and intellectual exploration is not part of their characterization.
10 means there is almost no intellectual curiosity, with only isolated practical learning.
20 means intellectual curiosity is weak, incidental, or supported mainly by limited evidence.
30 means the protagonist sometimes investigates, learns, or asks questions beyond immediate
necessity, but intellectual exploration remains secondary.
40 means curiosity or learning regularly influences behavior but is not a major motivation.
50 means intellectual exploration is a clear recurring motivation alongside other goals.
60 means the protagonist frequently seeks knowledge, investigates systems, experiments,
or pursues understanding even when doing so is not strictly necessary.
70 means intellectual discovery or understanding materially shapes major decisions and plot
development.
80 means curiosity, investigation, experimentation, or mastery of knowledge is one of the
protagonist's principal motivations.
90 means intellectual exploration is a defining part of the protagonist's identity and
drives many major choices, sacrifices, or conflicts.
100 means the pursuit of understanding, discovery, knowledge, or intellectual mastery is
one of the dominant themes of the protagonist's story and virtually inseparable from
their major decisions.

Do not score highly simply because the protagonist is clever, strategic, educated, or
good at solving problems. A highly intelligent character can have low intellectual drive
if they rarely care about learning or discovering things.


ARROGANCE_PRIDE (0 humble -> 100 extremely egotistical)
Measures the protagonist's pride, ego, status-consciousness, sense of superiority, and
resistance to admitting weakness or inferiority.

0 means explicit, defining humility and little concern for status or superiority.
10 means very modest, with rare or minor expressions of pride.
20 means generally humble, or evidence of ego is weak and limited.
30 means occasional pride, competitiveness, sensitivity to disrespect, or desire to prove
themselves.
40 means pride sometimes affects behavior or decisions but remains secondary.
50 means confidence and humility are broadly balanced.
60 means the protagonist is often proud, status-conscious, or sensitive to challenges to
their competence or dignity.
70 means arrogance or pride regularly shapes conflict, judgment, relationships, or choices.
80 means the protagonist commonly assumes superiority, strongly resists humiliation, or
places substantial importance on status and personal greatness.
90 means overwhelming ego or pride governs many major choices and relationships.
100 means unquestioned superiority or extreme ego is a defining feature of virtually every
major decision and interaction.

Confidence or competence alone does not establish arrogance. Score based on the
protagonist's attitude toward their own status, superiority, and importance.


KINSHIP_FRIENDSHIP (0 detached -> 100 deeply devoted)
Measures how strongly the protagonist values and prioritizes friends, family, comrades,
companions, and other close personal bonds.

0 means explicit, defining detachment or absence of meaningful bonds.
10 means the protagonist is nearly isolated, with at most one faint or weak bond.
20 means relationships are outside the main story, unclear, or only weakly meaningful.
30 means a few bonds matter emotionally but rarely determine important choices.
40 means friendships or family relationships sometimes motivate meaningful action.
50 means close relationships and personal priorities receive roughly equal weight.
60 means relationships frequently affect risks, loyalties, priorities, or major decisions.
70 means protecting or supporting close people is a major recurring motivation.
80 means deep loyalty to friends, family, or comrades drives major sacrifices and decisions.
90 means the protagonist repeatedly accepts severe losses, danger, or setbacks for loved
ones or close companions.
100 means devotion to close relationships dominates virtually every major choice, with the
protagonist consistently prioritizing loved ones or comrades above personal interests.

Do not equate having many acquaintances with high kinship/friendship. The measure concerns
emotional importance, loyalty, and willingness to act for close relationships.


ROMANTIC_ATTACHMENT (0 unattached -> 100 romance-driven)
Measures how strongly romantic love, attachment to a partner, or pursuit of a romantic
relationship motivates the protagonist.

0 means explicit absence: the protagonist's romantic life is genuinely irrelevant to their
characterization and the story establishes this as meaningful.
10 means the protagonist is almost entirely unattached, with only an ambiguous or negligible
romantic element.
20 means romance is outside the main story, evidence is unclear, or attraction has little
meaningful influence.
30 means minor attraction or an early/limited romantic bond with little effect on the plot.
40 means a recurring romantic relationship or attachment exists but remains secondary.
50 means romance is a clear and regular motivation alongside other major priorities.
60 means romantic attachment materially shapes several important decisions.
70 means romantic love or pursuit is one of the protagonist's principal motivations.
80 means love repeatedly outweighs safety, strategy, ambition, duty, or other major goals.
90 means nearly every defining choice is substantially influenced by a romantic partner or
romantic attachment.
100 means romance wholly dominates the protagonist's major motivations and decisions.

Evidence floors:
- Confirmed slow/minor romance: generally >=25.
- Recurring partner, spouse, or significant romantic attachment: generally >=40.
- Romance materially motivating major decisions: generally >=60.

A slow romance describes pacing, not weakness. Do not infer low romantic attachment merely
because romance develops gradually. Explicit relationship evidence outweighs generic labels
such as "slow romance" or "not romance-focused."


SELFLESSNESS_SELFISHNESS (0 self-interested -> 100 self-sacrificing)
Measures the degree to which the protagonist prioritizes other people's welfare over their
own interests, resources, safety, ambitions, and opportunities.

0 means explicit, defining refusal to sacrifice for others and a consistent prioritization
of personal interests.
10 means the protagonist nearly always prioritizes themselves and rarely accepts meaningful
costs for other people.
20 means the protagonist is mostly self-interested, or altruism is weakly evidenced.
30 means the protagonist helps others at little personal cost but rarely gives up something
important for them.
40 means recurring generosity or concern for others exists, but personal goals usually come
first.
50 means the protagonist balances their own interests and the interests of others.
60 means the protagonist often accepts meaningful inconvenience, risk, expense, or lost
opportunities for other people.
70 means the protagonist regularly sacrifices meaningful resources, opportunities, safety,
or goals for others.
80 means other people's welfare usually outweighs the protagonist's own ambition or comfort.
90 means the protagonist repeatedly accepts severe personal loss, danger, or deprivation
for other people.
100 means extreme self-sacrifice is defining: the protagonist consistently places others'
welfare above their own survival, ambitions, freedom, or happiness.

Helping others does not automatically imply high selflessness. Consider the personal cost
and whether the protagonist's behavior is genuinely other-directed rather than transactional,
strategic, obligatory, or motivated by reputation.


PRAGMATISM_MORALITY (0 pragmatic/amoral -> 100 principled/moral)
Measures how strongly the protagonist adheres to moral principles, ethical rules, ideals,
or a consistent conception of right and wrong when those principles conflict with practical
advantage.

0 means the protagonist is strongly pragmatic or amoral, readily abandoning moral principles
whenever doing so advances their goals.
10 means practical outcomes overwhelmingly determine decisions, with little resistance to
morally questionable methods.
20 means the protagonist is generally pragmatic and flexible about moral boundaries.
30 means the protagonist has some moral limits but frequently compromises them for practical
reasons.
40 means morality matters but is often negotiable when stakes are high.
50 means practical considerations and moral principles are broadly balanced.
60 means the protagonist usually tries to preserve moral principles even when doing so is
costly or inefficient.
70 means ethical principles regularly constrain important decisions and methods.
80 means the protagonist strongly prioritizes doing what they believe is right even at
substantial practical cost.
90 means a consistent moral code governs most major choices, even when violating it would
produce obvious personal or strategic benefits.
100 means principled morality is defining: the protagonist would accept extreme personal loss,
danger, or failure rather than knowingly violate their core ethical principles.

Judge the protagonist's behavior when morality conflicts with practical advantage. Being
kind, heroic, or helpful is not by itself sufficient for a high score, and being effective
or strategic is not by itself sufficient for a low score.

Do not treat "pragmatic" as synonymous with intelligent, rational, cautious, or strategic.
A protagonist can be highly strategic while still being strongly principled.


INDIVIDUALIST_COLLECTIVIST (0 individualist -> 100 collectivist)
Measures whether the protagonist primarily understands themselves and makes decisions as an
independent individual or as a member of a group, community, family, organization, culture,
or collective.

0 means extreme individualism: personal autonomy and independent goals dominate, and the
protagonist strongly resists obligations or identity based on groups.
10 means the protagonist is highly self-directed and rarely allows group expectations to
constrain important choices.
20 means the protagonist generally prioritizes personal autonomy but maintains some meaningful
group ties.
30 means the protagonist is mostly independent while accepting some obligations to groups or
communities.
40 means individual priorities usually come first, but group identity and obligations are
meaningful.
50 means individual autonomy and collective belonging have roughly equal importance.
60 means the protagonist regularly considers the needs, expectations, or interests of their
group alongside their own.
70 means group loyalty, community identity, or collective goals frequently influence major
decisions.
80 means the protagonist strongly identifies with and prioritizes a family, community,
faction, nation, organization, or other collective.
90 means collective welfare and group obligations routinely outweigh personal preferences,
ambitions, or safety.
100 means collectivism is defining: the protagonist's identity and virtually all major
decisions are fundamentally organized around belonging to and serving a collective.

A protagonist can have strong friendships or be highly selfless without being collectivist.
This measure concerns the broader basis of identity, obligation, and decision-making rather
than simply whether the protagonist cares about other people.

Likewise, independence does not necessarily mean selfishness. A highly individualistic
protagonist may sacrifice heavily for others while still resisting group identity or
institutional obligations.


AMBITION (0 little ambition -> 100 extremely power-hungry/ambitious)
Measures how strongly the protagonist actively pursues advancement, power, status, wealth,
influence, achievement, mastery, or a substantially better position.

0 means the protagonist has virtually no meaningful desire for advancement and is content
with their existing circumstances.
10 means advancement is rarely desired and the protagonist generally accepts their position.
20 means ambition is weak, secondary, or supported mainly by limited evidence.
30 means the protagonist has some aspirations but rarely allows them to drive major decisions.
40 means advancement is a recurring goal but remains secondary to other motivations.
50 means the protagonist consistently wants to improve their position, abilities, status, or
circumstances but balances this against other major priorities.
60 means ambition frequently influences important choices and the protagonist actively seeks
opportunities for advancement.
70 means becoming stronger, more successful, influential, wealthy, skilled, or powerful is
a major recurring motivation.
80 means ambition is one of the protagonist's principal motivations and regularly outweighs
comfort, safety, relationships, or other competing interests.
90 means relentless advancement or power acquisition governs most major choices and the
protagonist is willing to accept substantial costs to keep progressing.
100 means extreme ambition or hunger for power is defining: continual advancement, mastery,
status, or power acquisition dominates virtually every major decision.

Do not equate competence or natural power with ambition. A protagonist can become extremely
powerful while having little desire for power, and an ambitious protagonist may begin weak.

"Power" should be interpreted broadly according to the story: physical strength, magical
power, social influence, wealth, political authority, knowledge, status, or other meaningful
forms of advancement.


CAUTIOUS_RISK_TAKER (0 cautious -> 100 risk-taking/reckless)
Measures the protagonist's willingness to accept uncertainty, danger, loss, or potentially
severe consequences in pursuit of an objective.

0 means extreme caution: the protagonist consistently avoids unnecessary danger and strongly
prioritizes minimizing uncertainty and potential losses.
10 means the protagonist is highly cautious and takes serious risks only under exceptional
circumstances.
20 means the protagonist generally avoids unnecessary risks, with limited evidence of
risk-taking.
30 means the protagonist is somewhat cautious but will accept manageable risks when justified.
40 means the protagonist usually weighs risks carefully but sometimes accepts substantial
uncertainty.
50 means caution and risk-taking are broadly balanced.
60 means the protagonist regularly accepts significant risks when opportunities or goals
justify them.
70 means the protagonist frequently chooses dangerous or uncertain approaches despite safer
alternatives.
80 means the protagonist actively embraces major risks and often treats danger as an
acceptable or desirable cost of pursuing their goals.
90 means extreme risk-taking is common: the protagonist repeatedly accepts severe danger,
uncertainty, or potentially catastrophic consequences.
100 means reckless risk-taking is defining, with the protagonist routinely choosing highly
dangerous courses of action despite obvious and substantial consequences.

Distinguish this from impulsivity. A protagonist can be highly deliberate and calculating
while still being an extreme risk-taker. Likewise, an impulsive protagonist may sometimes
make surprisingly cautious choices.

Judge willingness to accept risk, not simply how dangerous the protagonist's circumstances
are. Being placed in dangerous situations does not itself establish that the protagonist
is a risk-taker.


LEADERSHIP (0 non-leader -> 100 defining leader)
Measures how strongly the protagonist takes responsibility for directing, organizing,
motivating, protecting, coordinating, or governing other people.

0 means the protagonist does not meaningfully lead others and consistently avoids leadership
responsibilities when they arise.
10 means the protagonist almost always follows others and has little interest in directing
or organizing people.
20 means leadership is outside the main story, unclear, or limited to isolated situations.
30 means the protagonist occasionally takes charge in small or temporary situations.
40 means the protagonist sometimes organizes or directs others, but leadership remains
secondary.
50 means the protagonist regularly takes responsibility for coordinating or directing
others, while also functioning comfortably as a peer or follower.
60 means leadership frequently affects the protagonist's role, relationships, and decisions.
70 means the protagonist becomes a significant leader whose decisions materially affect a
group, organization, party, community, or faction.
80 means leadership is one of the protagonist's principal roles and they regularly accept
responsibility for other people's actions, welfare, or direction.
90 means the protagonist is a major leader whose ability to organize, command, inspire, or
govern others drives much of the story.
100 means leadership is defining: the protagonist's identity and virtually all major choices
are deeply connected to directing, protecting, organizing, or governing others.

Do not score leadership based solely on charisma, popularity, competence, or power. A
protagonist can be charismatic without leading anyone, or be an excellent leader despite
being socially awkward.

Similarly, commanding someone under duress or temporarily taking charge during an emergency
does not establish high leadership unless the behavior is recurring or narratively meaningful.
""".strip()


def build_prompt(novel: dict, protagonist_name: str, comments: list[str]) -> str:
    genres = ", ".join(novel.get("genres") or []) or "Not provided"
    tags = ", ".join(novel.get("tags") or []) or "Not provided"
    synopsis = (novel.get("synopsis") or "Not provided")[:12_000]
    evidence = "\n".join(f"- {comment}" for comment in comments) or "No reader comments provided."

    return f"""Create a cautious baseline protagonist profile for a novel catalog.

Novel: {novel.get('title', 'Unknown')}
Protagonist: {protagonist_name}
Genres: {genres}
Tags: {tags}
Synopsis:
{synopsis}

Selected public reader comments:
{evidence}

{RUBRIC}

Treat comments as fallible reader opinions. Do not invent plot facts. Apply every score
against the anchors above. Reduce confidence when evidence is sparse, conflicting, or
does not clearly identify the protagonist. Keep the evidence summary brief and avoid
quotations.

Important distinctions:
- Intellectual drive measures desire to learn, investigate, understand, or discover;
  it does not measure intelligence or competence.
- Ambition measures desire for advancement, power, status, achievement, or improvement;
  it does not measure how powerful the protagonist already is.
- Cautious/risk-taker measures willingness to accept danger and uncertainty; it does not
  measure impulsivity.
- Individualist/collectivist measures the protagonist's relationship to group identity,
  obligations, and collective goals; it is not simply a measure of kindness or friendship.
- Pragmatism/morality measures willingness to compromise moral principles for practical
  outcomes; it is not simply a measure of whether the protagonist is nice or effective.
- Leadership measures responsibility for directing or organizing other people; it is not
  simply charisma, competence, popularity, or power.

For spectrum measures, give the score according to the stated direction. For intellectual
drive and leadership, treat 0 as genuine absence and higher values as increasing narrative
importance rather than merely uncertainty. Do not use 50 as a default when evidence is weak.

In the evidence summary, briefly identify the strongest evidence for the scores and any
important uncertainty.
"""


def build_identification_prompt(novel: dict, comments: list[str]) -> str:
    genres = ", ".join(novel.get("genres") or []) or "Not provided"
    tags = ", ".join(novel.get("tags") or []) or "Not provided"
    synopsis = (novel.get("synopsis") or "Not provided")[:12_000]
    evidence = "\n".join(f"- {comment[:500]}" for comment in comments[:12])
    if not evidence:
        evidence = "No public reader feedback was available."

    return f"""Identify the primary protagonist of this novel.

Novel: {novel.get('title', 'Unknown')}
Genres: {genres}
Tags: {tags}
Synopsis:
{synopsis}

Public reader feedback sample:
{evidence}

Return the canonical character name, not labels such as MC, protagonist, narrator,
or the author. If the story has an ensemble cast or the evidence is ambiguous, choose
the most central viewpoint character but lower confidence. Do not invent a surname or
expand a partial name unless the supplied evidence supports it. Keep the evidence
summary brief and avoid quotations.
"""
