MEASURES = (
    "impulsivity",
    "arrogance_pride",
    "kinship_friendship",
    "romantic_attachment",
    "sexual_desire",
    "selflessness",
)


RUBRIC = """
Use absolute 0-100 scales, not comparisons with other characters:
- impulsivity: 0 = consistently deliberate; 100 = acts without forethought.
- arrogance_pride: 0 = consistently humble; 100 = extremely arrogant/prideful.
- kinship_friendship: 0 = no meaningful family/friend bonds; 100 = bonds dominate decisions.
- romantic_attachment: 0 = explicitly no romantic attachment; 100 = romance dominates decisions.
  Apply these evidence floors: confirmed slow/minor romance = at least 25; a recurring
  romantic relationship, spouse, or partner = at least 40; romance that materially
  motivates decisions = at least 60. "Slow romance" describes pacing, not weak attachment.
- sexual_desire: 0 = explicitly absent; 100 = strongly drives behavior. Do not treat a
  lack of explicit scenes as proof of no desire. Confirmed sexual/partner-seeking behavior,
  a harem, multiple partners, pregnancy, or having children is evidence that normally
  requires at least 25; repeated or strongly motivating sexual behavior requires at least
  50. Go below these floors only when the evidence clearly gives a nonsexual explanation.
- selflessness: 0 = entirely self-interested; 100 = consistently self-sacrificing.
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

Treat comments as fallible reader opinions. Do not invent plot facts. A score of 50 is
not a default: use the evidence available. Reduce confidence when evidence is sparse,
conflicting, or does not clearly identify the protagonist. Keep the evidence summary
brief and avoid quotations. Explicit relationship evidence outweighs generic labels such
as "slow romance," "not romance-focused," or "no explicit scenes." Absence of evidence
should lower confidence rather than automatically producing a zero.
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
