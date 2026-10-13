"""
To run:
python profile_novel.py NOVEL_ID

flags:
--save

Generates the protagonist profile.
"""

import json
from pathlib import Path

# Seed/compatibility constants only. Runtime prompts always use the database snapshot.
DEFAULT_DEFINITION = json.loads(Path(__file__).with_name("default_definition.json").read_text(encoding="utf-8"))
MEASURES = tuple(t["key"] for t in DEFAULT_DEFINITION["traits"])
RUBRIC = DEFAULT_DEFINITION["instructions"] + "\n\n" + "\n\n".join(t["prompt"] for t in DEFAULT_DEFINITION["traits"])


class ProfilePrompt(str):
    """Carry the same definition snapshot into Gemini's schema and result revision."""
    def __new__(cls, text, definition):
        instance = super().__new__(cls, text)
        instance.definition = definition
        return instance


def build_prompt(novel: dict, protagonist_name: str, comments: list[str], definition=None) -> str:
    from services.protagonist_definition_service import load_definition

    definition = definition or load_definition()
    rubric = f"Score exactly {len(definition['traits'])} protagonist traits from 0 to 100.\n\n" + definition["instructions"] + "\n\n" + "\n\n".join(
        f"{trait['key']} - {trait['name']}\n{trait['prompt']}" for trait in definition["traits"]
    )
    genres = ", ".join(novel.get("genres") or []) or "Not provided"
    tags = ", ".join(novel.get("tags") or []) or "Not provided"
    synopsis = (novel.get("synopsis") or "Not provided")[:12_000]
    evidence = "\n".join(f"- {comment}" for comment in comments) or "No reader comments provided."

    return ProfilePrompt(f"""Create a cautious baseline protagonist profile for a novel catalog.

Novel: {novel.get('title', 'Unknown')}
Protagonist: {protagonist_name}
Genres: {genres}
Tags: {tags}
Synopsis:
{synopsis}

Selected public reader comments:
{evidence}

{rubric}

Treat comments as fallible reader opinions. Do not invent plot facts. Apply every score
against the anchors above. Reduce confidence when evidence is sparse, conflicting, or
does not clearly identify the protagonist. Keep the evidence summary brief and avoid
quotations.

In the evidence summary, briefly identify the strongest evidence for the scores and any
important uncertainty.
""", definition)


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
