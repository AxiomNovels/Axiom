"""Deterministic content similarity, without relying on user history."""
import math

from services.search_service import (
    PROFILE_MEASURES, PHILOSOPHY_MEASURES, STORYTELLING_MEASURES,
)

PROFILE_GROUPS = (
    ("protagonist_profiles", PROFILE_MEASURES),
    ("philosophy_profiles", PHILOSOPHY_MEASURES),
    ("storytelling_style_profiles", STORYTELLING_MEASURES),
)
CARD_FIELDS = ("id", "title", "author", "cover_image_url")


def _tags(novel):
    return {str(tag).strip().casefold() for tag in novel.get("genres") or [] if str(tag).strip()}


def _scores(novel, table, keys):
    profile = novel.get(table) or {}
    if isinstance(profile, list):
        profile = profile[0] if profile else {}
    result = {}
    for key in keys:
        value = profile.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 100:
            result[key] = value
    return result


def recommend_novels(source, candidates, limit=5):
    """Weight tags at 40%, profiles at 20% each when source data exists.

    Missing candidate dimensions contribute zero, rather than rewarding sparse
    profiles. Source dimensions without data are omitted from the denominator.
    Tags use Jaccard overlap; traits use closeness on the 0–100 scale.
    Zero-evidence candidates are omitted. Ties resolve by title then ID.
    """
    source_tags = _tags(source)
    profiles = [(table, keys, _scores(source, table, keys)) for table, keys in PROFILE_GROUPS]
    denominator = (0.4 if source_tags else 0) + sum(0.2 for _, _, values in profiles if values)
    if not denominator:
        return []
    ranked = []
    seen = {str(source["id"])}
    for novel in candidates:
        identity = str(novel["id"])
        if identity in seen:
            continue
        seen.add(identity)
        tags = _tags(novel)
        shared = source_tags & tags
        score = 0.4 * len(shared) / len(source_tags | tags) if source_tags else 0
        for table, keys, values in profiles:
            if values:
                other = _scores(novel, table, keys)
                score += 0.2 * sum(1 - abs(value - other[key]) / 100 for key, value in values.items() if key in other) / len(values)
        if score <= 0:
            continue
        card = {key: novel.get(key) for key in CARD_FIELDS}
        card["shared_tags"] = sorted({str(tag).strip() for tag in novel.get("genres") or [] if str(tag).strip().casefold() in shared}, key=str.casefold)[:2]
        ranked.append((score / denominator, card))
    ranked.sort(key=lambda item: (-item[0], (item[1]["title"] or "").casefold(), str(item[1]["id"])))
    return [card for _, card in ranked[:limit]]
