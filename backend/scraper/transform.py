from typing import Any


ALLOWED_STATUSES = {
    "ongoing",
    "completed",
    "hiatus",
    "dropped",
    "stub",
    "inactive",
}


def clean_string(value: Any) -> str | None:
    """
    Convert a value to a cleaned string.

    Returns None for missing/empty values.
    """

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def clean_count(value: Any) -> int | None:
    """
    Convert a scraped chapter count into a clean non-negative int.

    Every scraper (royalroad.py, webnovel.py, wattpad.py) already parses
    this as a plain int when it can find it, but this stays defensive
    against None, numeric strings, floats, or a negative/garbage value
    slipping through -- novels.chapter_count is nullable, so "we don't
    know" is represented as None rather than a misleading 0.
    """

    if value is None:
        return None

    try:
        number = int(value)
    except (TypeError, ValueError):
        return None

    return number if number >= 0 else None


def normalize_status(value: Any) -> str:
    """
    Normalize a source status to an Axiom status.

    Falls back to 'ongoing' because novels.status is NOT NULL
    and has 'ongoing' as its database default.
    """

    status = clean_string(value)

    if not status:
        return "ongoing"

    status = status.lower()

    if status in ALLOWED_STATUSES:
        return status

    # Unknown source status.
    # Don't let an unexpected scraper value break the catalog.
    return "ongoing"


def normalize_string_list(values: Any) -> list[str]:
    """
    Clean and dedupe a list of strings, preserving order.

    Used for both of a scraper's list fields: the canonical genre
    classification (payload["genres"], e.g. "Fantasy", "Romance") and the
    free-form community tags (payload["tags"], e.g. "Reincarnation",
    "System") -- the cleaning rules are identical for both, only the
    source field differs.
    """

    if not values:
        return []

    if not isinstance(values, list):
        raise ValueError(
            "Expected a list of strings"
        )

    cleaned = []

    for value in values:
        value = clean_string(value)

        if not value:
            continue

        if value not in cleaned:
            cleaned.append(value)

    return cleaned


# Kept as an alias: earlier versions of this module only had a
# `normalize_genres` name, and it was (incorrectly) fed each scraper's
# `tags` field. The cleaning logic hasn't changed, only which raw field
# each list is built from -- see transform_royalroad/_wattpad/_webnovel.
normalize_genres = normalize_string_list


def normalize_reading_links(
    source: str | None,
    reading_url: str | None,
) -> list[dict[str, str]]:
    """
    Convert the scraper's single reading URL into the JSONB
    structure expected by novels.reading_links.
    """

    if not reading_url:
        return []

    platform_map = {
        "royalroad": "Royal Road",
        "wattpad": "Wattpad",
        "webnovel": "WebNovel",
    }

    platform = platform_map.get(
        (source or "").lower(),
        source or "Unknown",
    )

    return [
        {
            "platform": platform,
            "url": reading_url,
        }
    ]


def transform_royalroad(payload: dict) -> dict:
    """
    Transform one Royal Road raw payload into the Axiom novels
    schema.

    This function does NOT write to Supabase.
    """

    title = clean_string(
        payload.get("title")
    )

    if not title:
        raise ValueError(
            "Cannot transform Royal Road novel without a title"
        )

    author = clean_string(
        payload.get("author")
    )

    synopsis = clean_string(
        payload.get("synopsis")
    )

    cover_image_url = clean_string(
        payload.get("cover_image_url")
    )

    status = normalize_status(
        payload.get("status")
    )

    # This scraper returns two distinct lists: "genres" (canonical
    # classification, e.g. "Fantasy") and "tags" (free-form community
    # tags, e.g. "Reincarnation") -- each maps to its own column.
    genres = normalize_string_list(
        payload.get("genres")
    )

    tags = normalize_string_list(
        payload.get("tags")
    )

    chapter_count = clean_count(
        payload.get("chapter_count")
    )

    reading_links = normalize_reading_links(
        source=payload.get("source"),
        reading_url=clean_string(
            payload.get("reading_url")
        ),
    )

    return {
        "title": title,
        "author": author,
        "cover_image_url": cover_image_url,
        "synopsis": synopsis,
        "status": status,
        "genres": genres,
        "tags": tags,
        "chapter_count": chapter_count,
        "reading_links": reading_links,
    }


def transform_wattpad(payload: dict) -> dict:
    """
    Transform one Wattpad raw payload into the Axiom novels
    schema.

    This function does NOT write to Supabase.
    """

    title = clean_string(
        payload.get("title")
    )

    if not title:
        raise ValueError(
            "Cannot transform Wattpad novel without a title"
        )

    author = clean_string(
        payload.get("author")
    )

    synopsis = clean_string(
        payload.get("synopsis")
    )

    cover_image_url = clean_string(
        payload.get("cover_image_url")
    )

    status = normalize_status(
        payload.get("status")
    )

    # This scraper returns two distinct lists: "genres" (canonical
    # classification, e.g. "Fantasy") and "tags" (free-form community
    # tags, e.g. "Reincarnation") -- each maps to its own column.
    genres = normalize_string_list(
        payload.get("genres")
    )

    tags = normalize_string_list(
        payload.get("tags")
    )

    chapter_count = clean_count(
        payload.get("chapter_count")
    )

    reading_links = normalize_reading_links(
        source=payload.get("source"),
        reading_url=clean_string(
            payload.get("reading_url")
        ),
    )

    return {
        "title": title,
        "author": author,
        "cover_image_url": cover_image_url,
        "synopsis": synopsis,
        "status": status,
        "genres": genres,
        "tags": tags,
        "chapter_count": chapter_count,
        "reading_links": reading_links,
    }


def transform_webnovel(payload: dict) -> dict:
    """
    Transform one WebNovel raw payload into the Axiom novels
    schema.

    This function does NOT write to Supabase.
    """

    title = clean_string(
        payload.get("title")
    )

    if not title:
        raise ValueError(
            "Cannot transform WebNovel novel without a title"
        )

    author = clean_string(
        payload.get("author")
    )

    synopsis = clean_string(
        payload.get("synopsis")
    )

    cover_image_url = clean_string(
        payload.get("cover_image_url")
    )

    status = normalize_status(
        payload.get("status")
    )

    # This scraper returns two distinct lists: "genres" (canonical
    # classification, e.g. "Fantasy") and "tags" (free-form community
    # tags, e.g. "Reincarnation") -- each maps to its own column.
    genres = normalize_string_list(
        payload.get("genres")
    )

    tags = normalize_string_list(
        payload.get("tags")
    )

    chapter_count = clean_count(
        payload.get("chapter_count")
    )

    reading_links = normalize_reading_links(
        source=payload.get("source"),
        reading_url=clean_string(
            payload.get("reading_url")
        ),
    )

    return {
        "title": title,
        "author": author,
        "cover_image_url": cover_image_url,
        "synopsis": synopsis,
        "status": status,
        "genres": genres,
        "tags": tags,
        "chapter_count": chapter_count,
        "reading_links": reading_links,
    }


def transform_staged_record(
    staged_record: dict,
) -> dict:
    """
    Transform a scrape_staging row.

    The staging row's raw_payload is treated as immutable source data.
    """

    source = clean_string(
        staged_record.get("source")
    )

    if not source:
        raise ValueError(
            "Staged record is missing source"
        )

    raw_payload = staged_record.get(
        "raw_payload"
    )

    if not isinstance(raw_payload, dict):
        raise ValueError(
            "Staged record raw_payload must be a JSON object"
        )

    if source.lower() == "royalroad":
        return transform_royalroad(
            raw_payload
        )

    if source.lower() == "wattpad":
        return transform_wattpad(
            raw_payload
        )

    if source.lower() == "webnovel":
        return transform_webnovel(
            raw_payload
        )

    raise ValueError(
        f"Unsupported staging source: {source}"
    )