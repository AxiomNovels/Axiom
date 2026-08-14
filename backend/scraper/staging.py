import os

from dotenv import load_dotenv
from supabase import create_client


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


def save_to_staging(novel: dict) -> dict:
    """
    Insert one scraped novel into scrape_staging.

    This function intentionally does not:
      - update novels
      - insert into novels
      - transform the scraped data
      - modify existing staging rows

    The raw parser output is stored untouched inside raw_payload.
    """

    source = novel.get("source")
    source_url = novel.get("source_url")

    if not source:
        raise ValueError(
            "Cannot stage record without 'source'"
        )

    if not source_url:
        raise ValueError(
            "Cannot stage record without 'source_url'"
        )

    payload = {
        "source": source,
        "source_url": source_url,
        "raw_payload": novel,
        "status": "pending",
    }

    response = (
        supabase
        .table("scrape_staging")
        .insert(payload)
        .select("id, source, source_url, fetched_at, status")
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase returned no row after staging insert"
        )

    return response.data[0]