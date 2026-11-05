"""Canonical genre spelling shared by imports and catalogue searches."""

NONFICTION_GENRE = "Non-Fiction"
NONFICTION_ALIASES = frozenset({"nonfiction", "non fiction", "non-fiction"})


def canonicalize_genre(value: str) -> str:
    if value.strip().casefold() in NONFICTION_ALIASES:
        return NONFICTION_GENRE
    return value


def canonicalize_genres(values: list[str]) -> list[str]:
    """Merge nonfiction aliases at their first position; preserve other entries."""
    result = []
    seen_nonfiction = False
    for value in values:
        genre = canonicalize_genre(value) if isinstance(value, str) else value
        if genre == NONFICTION_GENRE:
            if seen_nonfiction:
                continue
            seen_nonfiction = True
        result.append(genre)
    return result
