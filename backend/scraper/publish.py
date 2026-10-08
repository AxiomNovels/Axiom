'''
To run:
cd backend, then run
python -m scraper.publish

Publishes every pending scrape_staging row into the novels table AND generates
and saves each novel's protagonist profile with Gemini.

Options:
  --limit N            Only process the first N pending rows (good for a trial
                       run before the full ~500).
  --no-fetch-comments  Build profiles from the synopsis and tags only, skipping
                       the extra reader-review page requests.

Gemini handling:
  * HTTP 503 (unavailable): wait one minute and try that call again.
  * HTTP 429 / RESOURCE_EXHAUSTED: stop the whole run, after printing the URL
    and title of the last novel that was successfully added.
  * A 5 second pause separates one novel from the next.

Stopping is always safe to resume: the row being processed when the run stops
is left "pending", so running the command again carries on where it left off.
'''

import argparse
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from supabase import create_client

from profiler.comments import select_comments
from profiler.gemini import GeminiAPIError, generate_profile, identify_protagonist
# profile_novel is imported (rather than re-implementing its save) so the
# profile is written through the exact same RPC the profiler CLI uses, and
# because importing it also enables the OS certificate store (truststore) that
# the Gemini HTTPS calls rely on.
from profiler.profile_novel import save_profile
from profiler.prompt import build_identification_prompt, build_prompt
from profiler.sources import collect_public_comments
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


# --------------------------------------------------
# Gemini pacing / retry settings
# --------------------------------------------------

# Pause between one novel and the next, so the Gemini API isn't hit too fast.
NOVEL_DELAY_SECONDS = 5

# On a 503, wait this long and retry the same call...
GEMINI_UNAVAILABLE_WAIT_SECONDS = 60

# ...but give up after this many retries in a row, so a long outage ends the
# run (resumable) instead of looping forever.
GEMINI_UNAVAILABLE_MAX_RETRIES = 10

# Same default the profiler CLI uses for --minimum-name-confidence. Below this,
# the detected protagonist is too uncertain to profile.
MIN_PROTAGONIST_CONFIDENCE = 75


class StopPublishing(Exception):
    """Raised to end the whole run (Gemini quota exhausted, or a long outage).

    Deliberately NOT treated as a bad novel: the row stays "pending" so the
    next run picks it up again.
    """


@dataclass
class PublishResult:
    novel_id: int
    title: str | None
    already_published: bool = False
    protagonist_name: str | None = None
    profile_saved: bool = False


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
    # Validate chapter_count
    #
    # Optional stat scraped from the source site, so None (never
    # scraped/found) is valid, but if present it must be a
    # non-negative int -- matching the CHECK constraint on
    # novels.chapter_count.
    # --------------------------------------------------

    chapter_count = novel.get("chapter_count")

    if chapter_count is not None:
        if isinstance(chapter_count, bool) or not isinstance(chapter_count, int):
            raise ValueError("chapter_count must be an integer or None")

        if chapter_count < 0:
            raise ValueError("chapter_count cannot be negative")

    # --------------------------------------------------
    # Validate genres
    # --------------------------------------------------

    if not isinstance(novel["genres"], list):
        raise ValueError("genres must be a list")

    # --------------------------------------------------
    # Validate tags
    #
    # Optional for backward compatibility with any staged rows produced
    # before scraper/transform.py started returning it.
    # --------------------------------------------------

    if "tags" in novel and not isinstance(novel["tags"], list):
        raise ValueError("tags must be a list")

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


# --------------------------------------------------
# Protagonist profile (Gemini)
# --------------------------------------------------

def call_gemini(description: str, function, prompt: str):
    """
    Run one Gemini call (function(prompt)) with the run's error policy.

      * 429 / RESOURCE_EXHAUSTED -> raise StopPublishing immediately.
      * 503 / UNAVAILABLE        -> wait a minute, then call again. After
                                    GEMINI_UNAVAILABLE_MAX_RETRIES failures in
                                    a row, raise StopPublishing.
      * anything else            -> re-raised for the caller to handle.

    Retries are per call, so if the protagonist was already identified and only
    the scoring call gets a 503, only the scoring call is repeated.
    """

    retries = 0

    while True:
        try:
            return function(prompt)

        except GeminiAPIError as error:
            if error.is_rate_limited:
                raise StopPublishing(
                    "Gemini returned 429 Too Many Requests / "
                    "RESOURCE_EXHAUSTED."
                ) from error

            if not error.is_unavailable:
                raise

            retries += 1

            if retries > GEMINI_UNAVAILABLE_MAX_RETRIES:
                raise StopPublishing(
                    "Gemini stayed unavailable (HTTP 503) after "
                    f"{GEMINI_UNAVAILABLE_MAX_RETRIES} retries."
                ) from error

            print(
                f"  Gemini unavailable (HTTP 503) during {description}; "
                f"waiting {GEMINI_UNAVAILABLE_WAIT_SECONDS}s before retry "
                f"{retries}/{GEMINI_UNAVAILABLE_MAX_RETRIES}..."
            )
            time.sleep(GEMINI_UNAVAILABLE_WAIT_SECONDS)


def generate_protagonist_profile(
    novel: dict,
    fetch_comments: bool,
) -> dict | None:
    """
    Generate the protagonist profile for a normalized (not yet inserted) novel.

    Follows the same steps as profiler.profile_novel / regenerate_profiles:
    collect public reader comments (best effort), identify the protagonist,
    then score the ten traits.

    Returns {"name": str, "result": dict}, or None when the protagonist can't
    be identified confidently enough (a profile of the wrong character is worse
    than none). Raises StopPublishing on 429 / persistent 503; any other
    failure propagates and is handled by the caller.
    """

    raw_comments: list[str] = []

    if fetch_comments:
        try:
            raw_comments, _sources = collect_public_comments(
                novel.get("reading_links") or []
            )
        except Exception as error:
            # Comments are extra evidence, never required.
            print(f"  (reader comments unavailable: {error})")

    identification = call_gemini(
        "protagonist identification",
        identify_protagonist,
        build_identification_prompt(novel, raw_comments),
    )

    name = identification["protagonist_name"]
    confidence = identification["confidence"]

    if confidence < MIN_PROTAGONIST_CONFIDENCE:
        print(
            f"  Protagonist {name!r} detected with confidence {confidence} "
            f"(minimum {MIN_PROTAGONIST_CONFIDENCE}); no profile generated."
        )
        return None

    comments = select_comments(raw_comments, name)

    result = call_gemini(
        "protagonist profile",
        generate_profile,
        build_prompt(novel, name, comments),
    )

    return {"name": name, "result": result}


def publish_staged_record(
    staging_row: dict,
    fetch_comments: bool = True,
) -> PublishResult:
    """
    Transform, validate, and publish one staging record, together with its
    protagonist profile.

    Order matters:

      1. transform + validate (including the duplicate check) -- cheap, and
         means no Gemini call is ever spent on a novel that will be rejected;
      2. generate the profile -- if Gemini stops us (StopPublishing), nothing
         has been written yet, so the row simply stays pending;
      3. insert the novel -- exactly the same normalized record as before;
      4. save the profile against the new novel id;
      5. mark the staging row transformed.

    A profile problem (other than the stop conditions) never blocks the novel:
    it is published without a profile, which profiler.regenerate_profiles can
    fill in later.
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

        return PublishResult(
            novel_id=existing_novel_id,
            title=(staging_row.get("raw_payload") or {}).get("title"),
            already_published=True,
        )

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
    # Generate the protagonist profile
    #
    # The profile lives in its own variable and is never merged into
    # `normalized`, so the record inserted into novels is unchanged.
    # --------------------------------------------------

    profile = None

    try:
        profile = generate_protagonist_profile(
            normalized,
            fetch_comments,
        )

    except StopPublishing:
        raise

    except Exception as exc:
        print(
            f"  Protagonist profile NOT generated: "
            f"{type(exc).__name__}: {exc}"
        )

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
    # Save the protagonist profile
    # --------------------------------------------------

    profile_saved = False

    if profile:
        try:
            save_profile(
                novel_id,
                profile["name"],
                profile["result"],
            )
            profile_saved = True

        except Exception as exc:
            print(
                f"  Protagonist profile NOT saved: "
                f"{type(exc).__name__}: {exc}"
            )

    # --------------------------------------------------
    # Mark staging record as successfully published
    # --------------------------------------------------

    mark_transformed(
        staging_id=staging_id,
        novel_id=novel_id,
    )

    return PublishResult(
        novel_id=novel_id,
        title=normalized["title"],
        protagonist_name=profile["name"] if profile else None,
        profile_saved=profile_saved,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish staged novels and their protagonist profiles"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only process the first N pending staging rows",
    )
    parser.add_argument(
        "--no-fetch-comments",
        action="store_true",
        help="Use only the synopsis and tags (skips reader-review requests)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("AXIOM STAGING PUBLISHER")
    print("=" * 70)

    rows = fetch_pending_rows()

    if args.limit:
        rows = rows[: args.limit]

    print()
    print(
        f"Found {len(rows)} pending staging row(s)."
    )

    if not rows:
        print("Nothing to publish.")
        return

    published = 0
    already_published = 0
    rejected = 0
    without_profile: list[tuple[int, str | None]] = []

    # (title, source_url) of the most recent novel actually inserted this run.
    last_added: tuple[str | None, str] | None = None
    current_row: dict | None = None
    stop_reason: str | None = None

    try:
        for position, row in enumerate(rows):
            # Space the novels out so Gemini isn't called too quickly.
            if position > 0:
                time.sleep(NOVEL_DELAY_SECONDS)

            current_row = row

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
                result = publish_staged_record(
                    row,
                    fetch_comments=not args.no_fetch_comments,
                )

            except StopPublishing:
                # Not this novel's fault: leave the row pending and end the run.
                raise

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
                continue

            if result.already_published:
                already_published += 1
                continue

            print()
            print("PUBLISHED")
            print(f"  novel id: {result.novel_id}")

            if result.profile_saved:
                print(
                    f"  protagonist profile: saved "
                    f"({result.protagonist_name})"
                )
            else:
                print("  protagonist profile: NOT saved")
                without_profile.append((result.novel_id, result.title))

            published += 1
            last_added = (result.title, source_url)

    except StopPublishing as stop:
        stop_reason = str(stop)

    print()
    print("=" * 70)
    print("PUBLISH STOPPED" if stop_reason else "PUBLISH COMPLETE")
    print("=" * 70)
    print(f"  published: {published}")
    print(f"  rejected:  {rejected}")

    if already_published:
        print(f"  already published: {already_published}")

    if without_profile:
        ids = " ".join(str(novel_id) for novel_id, _title in without_profile)
        print(f"  published without a protagonist profile: {len(without_profile)}")
        for novel_id, title in without_profile:
            print(f"    novel {novel_id}: {title}")
        print("  To generate these later, run:")
        print(f"    python -m profiler.regenerate_profiles --novel-ids {ids}")

    if stop_reason:
        print()
        print(f"STOPPED: {stop_reason}")

        if current_row is not None:
            print(
                f"  Interrupted while processing staging id "
                f"{current_row['id']} ({current_row['source_url']}); "
                f"it is still pending."
            )

        print()
        print("Last novel successfully added:")

        if last_added:
            title, url = last_added
            print(f"  title: {title}")
            print(f"  url:   {url}")
        else:
            print("  (none -- no novel was added during this run)")

        print()
        print("Run the command again to resume with the remaining pending rows.")

        raise SystemExit(1)


if __name__ == "__main__":
    main()