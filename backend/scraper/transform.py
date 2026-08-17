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


def normalize_genres(tags: Any) -> list[str]:
    """
    Convert source tags into the genres array expected by Axiom.

    For the first pass, we preserve Royal Road's tags rather than
    trying to make subjective genre decisions.

    We can introduce explicit tag -> genre mapping later.
    """

    if not tags:
        return []

    if not isinstance(tags, list):
        raise ValueError(
            "Expected Royal Road tags to be a list"
        )

    genres = []

    for tag in tags:
        tag = clean_string(tag)

        if not tag:
            continue

        if tag not in genres:
            genres.append(tag)

    return genres


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

    title = clean_string(payload.get("title"))

    if not title:
        raise ValueError(
            "Cannot transform Royal Road novel without a title"
        )

    author = clean_string(payload.get("author"))
    synopsis = clean_string(payload.get("synopsis"))
    cover_image_url = clean_string(
        payload.get("cover_image_url")
    )

    status = normalize_status(
        payload.get("status")
    )

    genres = normalize_genres(
        payload.get("tags")
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

    genres = normalize_genres(
        payload.get("tags")
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

    raise ValueError(
        f"Unsupported staging source: {source}"
    )