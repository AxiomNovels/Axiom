MEASURES = (
    "impulsivity",
    "arrogance_pride",
    "kinship_friendship",
    "romantic_attachment",
    "sexual_desire",
    "selflessness",
)


RUBRIC = """
SCORING RULES
- Use absolute 0-100 scales, not comparisons with other characters. The anchors below
  are authoritative; interpolate between them only when the evidence genuinely falls
  between two anchors.
- 0 means explicit, narratively meaningful absence. Never assign 0 merely because the
  synopsis or comments do not mention a trait.
- 20 is the cautious limited-evidence region when a trait is outside the main storyline,
  barely discussed, or supported by unclear evidence and nothing contradicts a low score.
- Score and confidence are different. Sparse/conflicting evidence lowers confidence. It
  does not prove a trait is absent. A score of 50 is not a default for uncertainty.
- Judge how strongly the trait shapes identity and decisions, not how often a keyword occurs.

IMPULSIVITY (0 deliberate -> 100 impulsive)
0 explicit, defining deliberation; 10 almost always plans, one isolated rushed choice;
20 mostly deliberate or sparse/questionable evidence; 30 occasional quick action;
40 recurring but secondary impulsivity; 50 equal mix of planning and instinct;
60 frequently acts first but can restrain themself; 70 impulsive choices redirect the plot;
80 immediate emotion/instinct usually beats forethought; 90 rarely considers consequences;
100 extreme impulsivity defines virtually every major choice.

EGO (database key arrogance_pride; 0 humble -> 100 extremely egotistical)
0 explicit, defining humility; 10 very modest with rare pride; 20 generally humble or
weak evidence; 30 occasional ego/competitiveness; 40 pride sometimes affects choices;
50 confidence and humility are balanced; 60 often proud/status-conscious; 70 arrogance
regularly shapes conflict and judgment; 80 assumes superiority in most situations;
90 overwhelming ego governs major choices; 100 unquestioned superiority is defining.

KINSHIP_FRIENDSHIP (0 detached -> 100 devoted)
0 explicit, defining absence of meaningful bonds; 10 nearly isolated with one faint bond;
20 relationships are outside the main story or unclear; 30 a few bonds matter emotionally;
40 bonds sometimes motivate action; 50 bonds and personal priorities have equal weight;
60 relationships frequently affect risks and loyalty; 70 protecting close people is a
major motivation; 80 deep loyalty drives major sacrifice; 90 repeatedly accepts severe
loss for loved ones; 100 devotion dominates virtually every major choice.

ROMANTIC_ATTACHMENT (0 unattached -> 100 romance-driven)
0 explicit absence: the protagonist's heart never wavers and the story establishes this
as part of their identity; 10 almost entirely unattached with one ambiguous moment;
20 romance is outside the main story or evidence is unclear; 30 minor attraction/early
bond with little plot influence; 40 recurring relationship or attachment that remains
secondary; 50 clear regular motivation; 60 materially shapes several major decisions;
70 one of the principal motivations; 80 love repeatedly outweighs safety, strategy, or
duty; 90 nearly every defining choice centers on a partner; 100 romance wholly dominates.
Evidence floors: confirmed slow/minor romance >=25; recurring partner/spouse >=40;
romance materially motivating decisions >=60. Slow romance describes pacing, not weakness.

LUST (database key sexual_desire; 0 absent -> 100 very lustful)
Keep lust separate from romantic love and emotional attachment. 0 explicit, defining
absence with no wavering; 10 nearly absent with one or two questionable moments;
20 outside the main story or unclear evidence; 30 some occasional lust/sexual attraction;
40 recurring acknowledged desire that remains secondary; 50 regular motivation balanced
by restraint and other goals; 60 frequently influences attention, relationships, or choices;
70 strongly motivates repeated behavior with consequences; 80 sexual pursuit regularly
outweighs judgment; 90 persistently lust-driven; 100 extreme lust dominates relationships
and choices. Lack of explicit scenes is not proof of absence. Confirmed sexual or
partner-seeking behavior, harem/multiple partners, pregnancy, or children normally >=25;
repeated or strongly motivating sexual behavior >=50 unless evidence clearly shows a
nonsexual explanation.

SELFLESSNESS (0 self-interested -> 100 self-sacrificing)
0 explicit, defining refusal to sacrifice for others; 10 nearly always prioritizes self;
20 mostly self-interested or altruism is weakly evidenced; 30 helps at little personal cost;
40 recurring generosity but own goals usually come first; 50 balances self and others;
60 often accepts inconvenience/risk for others; 70 regularly sacrifices meaningful
opportunities, resources, or safety; 80 others' welfare usually outweighs ambition;
90 repeatedly accepts severe personal loss; 100 extreme self-sacrifice is defining.
""".strip()


def build_prompt(novel: dict, protagonist_name: str, comments: list[str]) -> str:
    genres = ", ".join(novel.get("genres") or []) or "Not provided"
    synopsis = (novel.get("synopsis") or "Not provided")[:12_000]
    evidence = "\n".join(f"- {comment}" for comment in comments) or "No reader comments provided."

    return f"""Create a cautious baseline protagonist profile for a novel catalog.

Novel: {novel.get('title', 'Unknown')}
Protagonist: {protagonist_name}
Genres/tags: {genres}
Synopsis:
{synopsis}

Selected public reader comments:
{evidence}

{RUBRIC}

Treat comments as fallible reader opinions. Do not invent plot facts. Apply every score
against the anchors above. Reduce confidence when evidence is sparse, conflicting, or
does not clearly identify the protagonist. Keep the evidence summary brief and avoid
quotations. Explicit relationship evidence outweighs generic labels such as "slow
romance," "not romance-focused," or "no explicit scenes." In the evidence summary,
briefly identify the strongest evidence and any important uncertainty.
"""


def build_identification_prompt(novel: dict, comments: list[str]) -> str:
    genres = ", ".join(novel.get("genres") or []) or "Not provided"
    synopsis = (novel.get("synopsis") or "Not provided")[:12_000]
    evidence = "\n".join(f"- {comment[:500]}" for comment in comments[:12])
    if not evidence:
        evidence = "No public reader feedback was available."

    return f"""Identify the primary protagonist of this novel.

Novel: {novel.get('title', 'Unknown')}
Genres/tags: {genres}
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
