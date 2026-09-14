"""Deterministic content similarity, without relying on user history."""
import math

from services.search_service import (
    PROFILE_MEASURES, PHILOSOPHY_MEASURES, STORYTELLING_MEASURES,
)

PROFILE_GROUPS = (
    ("protagonist_profiles", PROFILE_MEASURES, 0.40),
    ("philosophy_profiles", PHILOSOPHY_MEASURES, 0.10),
    ("storytelling_style_profiles", STORYTELLING_MEASURES, 0.10),
)
CARD_FIELDS = ("id", "title", "author", "cover_image_url")


def _tags(novel):
    # Similarity is deliberately based on the free-form "tags" field
    # (e.g. "Reincarnation", "System") rather than the small, canonical
    # "genres" field (e.g. "Fantasy") -- tags are far more discriminating
    # for "novels like this one" than a handful of broad genre buckets.
    return {str(tag).strip().casefold() for tag in novel.get("tags") or [] if str(tag).strip()}


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


def recommend_novels(source, candidates, limit=6):
    """Weight protagonist and tags at 40% each, and other profiles at 10% each.

    Missing candidate dimensions contribute zero, rather than rewarding sparse
    profiles. Source dimensions without data are omitted from the denominator.
    Tags use Jaccard overlap; traits use closeness on the 0–100 scale.
    Zero-evidence candidates fill remaining slots after matches. Ties resolve by title then ID.
    """
    source_tags = _tags(source)
    profiles = [(table, keys, weight, _scores(source, table, keys)) for table, keys, weight in PROFILE_GROUPS]
    denominator = (0.40 if source_tags else 0) + sum(weight for _, _, weight, values in profiles if values)
    ranked = []
    seen = {str(source["id"])}
    for novel in candidates:
        identity = str(novel["id"])
        if identity in seen:
            continue
        seen.add(identity)
        tags = _tags(novel)
        shared = source_tags & tags
        score = 0.40 * len(shared) / len(source_tags | tags) if source_tags else 0
        for table, keys, weight, values in profiles:
            if values:
                other = _scores(novel, table, keys)
                score += weight * sum(1 - abs(value - other[key]) / 100 for key, value in values.items() if key in other) / len(values)
        card = {key: novel.get(key) for key in CARD_FIELDS}
        card["shared_tags"] = sorted({str(tag).strip() for tag in novel.get("tags") or [] if str(tag).strip().casefold() in shared}, key=str.casefold)[:3]
        ranked.append((score / denominator if denominator else 0, card))
    ranked.sort(key=lambda item: (-item[0], (item[1]["title"] or "").casefold(), str(item[1]["id"])))
    return [card for _, card in ranked[:limit]]
