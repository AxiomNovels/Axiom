'''
To run:
cd backend, then run
python -m scraper.publish
'''

import os

from dotenv import load_dotenv
from supabase import create_client

from scraper.transform import transform_staged_record


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL:
    raise RuntimeError(
        "Missing SUPABASE_URL in backend/.env"
    )

if not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_SECRET_KEY in backend/.env"
    )


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


def fetch_pending_rows() -> list[dict]:
    """
    Fetch all staging records that have not yet been processed.
    """

    response = (
        supabase
        .table("scrape_staging")
        .select(
            "id, source, source_url, raw_payload, "
            "fetched_at, status, published_novel_id, error_message"
        )
        .eq("status", "pending")
        .order("id")
        .execute()
    )

    return response.data or []


def validate_novel(novel: dict) -> None:
    """
    Validate the normalized object immediately before publication.

    This is intentionally stricter than the transformer's job.

    Also checks that a novel with the same title AND author
    does not already exist in the novels table.
    """

    required_fields = (
        "title",
        "status",
        "genres",
        "reading_links",
    )

    for field in required_fields:
        if field not in novel:
            raise ValueError(
                f"Normalized novel missing required field: {field}"
            )

    # --------------------------------------------------
    # Validate title
    # --------------------------------------------------

    if not isinstance(novel["title"], str):
        raise ValueError("title must be a string")

    title = novel["title"].strip()

    if not title:
        raise ValueError("title cannot be empty")

    # --------------------------------------------------
    # Validate author
    # --------------------------------------------------

    author = novel.get("author")

    if author is not None and not isinstance(author, str):
        raise ValueError("author must be a string or None")

    if isinstance(author, str):
        author = author.strip()

    # --------------------------------------------------
    # Validate chapter_count / view_count
    #
    # Both are optional stats scraped from the source site, so None
    # (never scraped/found) is valid, but if present they must be a
    # non-negative int -- matching the CHECK constraints added in
    # database/novel_stats.sql.
    # --------------------------------------------------

    for field_name in ("chapter_count", "view_count"):
        value = novel.get(field_name)

        if value is None:
            continue

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer or None")

        if value < 0:
            raise ValueError(f"{field_name} cannot be negative")

    # --------------------------------------------------
    # Validate genres
    # --------------------------------------------------

    if not isinstance(novel["genres"], list):
        raise ValueError("genres must be a list")

    # --------------------------------------------------
    # Validate reading links
    # --------------------------------------------------

    if not isinstance(novel["reading_links"], list):
        raise ValueError(
            "reading_links must be a list"
        )

    for link in novel["reading_links"]:
        if not isinstance(link, dict):
            raise ValueError(
                "Each reading link must be an object"
            )

        if not link.get("platform"):
            raise ValueError(
                "Reading link is missing platform"
            )

        if not link.get("url"):
            raise ValueError(
                "Reading link is missing url"
            )

    # --------------------------------------------------
    # Check for an existing novel with the same
    # title AND author
    # --------------------------------------------------

    duplicate_query = (
        supabase
        .table("novels")
        .select("id, title, author")
        .eq("title", title)
    )

    # Because author is nullable, handle NULL separately.
    if author is None or author == "":
        duplicate_query = duplicate_query.is_(
            "author",
            "null",
        )
    else:
        duplicate_query = duplicate_query.eq(
            "author",
            author,
        )

    duplicate_response = duplicate_query.limit(1).execute()

    existing_rows = duplicate_response.data or []

    if existing_rows:
        existing_novel = existing_rows[0]
        existing_novel_id = existing_novel["id"]

        raise ValueError(
            "Duplicate novel already exists: "
            f"title={title!r}, "
            f"author={author!r}, "
            f"existing novel id={existing_novel_id}"
        )


def mark_transformed(
    staging_id: int,
    novel_id: int,
) -> None:
    """
    Mark a staging record as successfully published.
    """

    (
        supabase
        .table("scrape_staging")
        .update(
            {
                "status": "transformed",
                "published_novel_id": novel_id,
                "error_message": None,
            }
        )
        .eq("id", staging_id)
        .execute()
    )


def mark_rejected(
    staging_id: int,
    error_message: str,
) -> None:
    """
    Mark a staging record as rejected without touching novels.
    """

    (
        supabase
        .table("scrape_staging")
        .update(
            {
                "status": "rejected",
                "error_message": error_message[:2000],
            }
        )
        .eq("id", staging_id)
        .execute()
    )


def publish_staged_record(
    staging_row: dict,
) -> int:
    """
    Transform, validate, and publish one staging record.

    Returns the resulting novels.id.
    """

    staging_id = staging_row["id"]

    # --------------------------------------------------
    # Idempotency guard
    # --------------------------------------------------

    existing_novel_id = staging_row.get(
        "published_novel_id"
    )

    if existing_novel_id:
        print(
            f"  Already published as novel "
            f"id={existing_novel_id}"
        )

        return existing_novel_id

    # --------------------------------------------------
    # Transform
    # --------------------------------------------------

    normalized = transform_staged_record(
        staging_row
    )

    # --------------------------------------------------
    # Validate
    #
    # This includes the duplicate title + author check.
    # --------------------------------------------------

    validate_novel(normalized)

    # --------------------------------------------------
    # Insert into novels
    # --------------------------------------------------

    response = (
        supabase
        .table("novels")
        .insert(normalized)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase returned no row after novels insert"
        )

    novel_row = response.data[0]

    novel_id = novel_row["id"]

    # --------------------------------------------------
    # Mark staging record as successfully published
    # --------------------------------------------------

    mark_transformed(
        staging_id=staging_id,
        novel_id=novel_id,
    )

    return novel_id


def main():
    print("=" * 70)
    print("AXIOM STAGING PUBLISHER")
    print("=" * 70)

    rows = fetch_pending_rows()

    print()
    print(
        f"Found {len(rows)} pending staging row(s)."
    )

    if not rows:
        print("Nothing to publish.")
        return

    published = 0
    rejected = 0

    for row in rows:
        staging_id = row["id"]
        source = row["source"]
        source_url = row["source_url"]

        print()
        print("=" * 70)
        print(f"STAGING ID: {staging_id}")
        print(f"SOURCE:     {source}")
        print(f"URL:        {source_url}")
        print("=" * 70)

        try:
            novel_id = publish_staged_record(row)

            print()
            print("PUBLISHED")
            print(f"  novel id: {novel_id}")

            published += 1

        except Exception as exc:
            error_message = (
                f"{type(exc).__name__}: {exc}"
            )

            print()
            print("REJECTED")
            print(f"  reason: {error_message}")

            mark_rejected(
                staging_id=staging_id,
                error_message=error_message,
            )

            rejected += 1

    print()
    print("=" * 70)
    print("PUBLISH COMPLETE")
    print("=" * 70)
    print(f"  published: {published}")
    print(f"  rejected:  {rejected}")


if __name__ == "__main__":
    main()