import re
from pathlib import Path


TRAIT_TERMS = {
    # intellectual drive
    "curious", "curiosity", "inquisitive", "investigate", "investigates", "research",
    "experiment", "experiments", "study", "studies", "scholar", "learning", "knowledge",
    "discovery", "analyze", "analytical",
    # arrogance / pride
    "arrogant", "arrogance", "pride", "prideful", "proud", "humble", "humility", "ego",
    # kinship / friendship
    "family", "friend", "friends", "friendship", "loyal", "loyalty", "bond", "kin",
    "child", "children", "offspring", "son", "daughter", "sister", "brother",
    # romantic attachment
    "romance", "romantic", "love", "lover", "relationship", "partner",
    "marriage", "married", "marries", "wedding", "spouse", "wife", "husband",
    "girlfriend", "boyfriend", "attracted", "attraction", "harem", "pregnant", "pregnancy",
    # selflessness / selfishness
    "selfless", "selfish", "sacrifice", "sacrifices", "compassion", "altruistic",
    # pragmatism / morality
    "moral", "morality", "amoral", "ruthless", "principled", "ethical", "ethics",
    "pragmatic", "honorable", "manipulative", "unscrupulous",
    # individualist / collectivist
    "loner", "independent", "individualist", "collectivist", "clan", "sect",
    "community", "faction", "nation", "duty", "obligation",
    # ambition
    "ambition", "ambitious", "power", "powerhungry", "conquer", "conquest",
    "throne", "dominate", "advancement", "status",
    # cautious / risk-taker
    "cautious", "careful", "caution", "risk", "risky", "gamble", "gambles",
    "reckless", "calculated", "paranoid", "patient",
    # leadership
    "leader", "leadership", "lead", "leads", "command", "commander", "ruler",
    "king", "general", "organizes", "governs",
}


def load_comments(path: str | None) -> list[str]:
    """Load one-comment-per-line text while tolerating blank lines."""
    if not path:
        return []

    comment_path = Path(path)
    if not comment_path.is_file():
        raise FileNotFoundError(f"Comment file not found: {comment_path}")

    return [line.strip() for line in comment_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select_comments(
    comments: list[str],
    protagonist_name: str,
    limit: int = 60,
    max_characters: int = 18_000,
) -> list[str]:
    """Deduplicate and rank comments most likely to discuss profile traits."""
    unique: dict[str, str] = {}
    for comment in comments:
        cleaned = re.sub(r"\s+", " ", comment).strip()
        key = cleaned.casefold()
        if len(cleaned) >= 12 and key not in unique:
            unique[key] = cleaned

    name_parts = {part.casefold() for part in protagonist_name.split() if len(part) > 2}

    def relevance(comment: str) -> tuple[int, int]:
        words = set(re.findall(r"[a-zA-Z']+", comment.casefold()))
        score = 4 * len(words & name_parts) + 2 * len(words & TRAIT_TERMS)
        return score, min(len(comment), 600)

    ranked = sorted(unique.values(), key=relevance, reverse=True)
    selected: list[str] = []
    character_count = 0

    for comment in ranked:
        shortened = comment[:600]
        if selected and character_count + len(shortened) > max_characters:
            continue
        selected.append(shortened)
        character_count += len(shortened)
        if len(selected) >= limit or character_count >= max_characters:
            break

    return selected
