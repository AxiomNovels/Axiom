'''
To run:
cd to backend, then run the following:
python -m scraper.transform_test
'''

import json
import os

from dotenv import load_dotenv
from supabase import create_client

from scraper.transform import transform_staged_record


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL:
    raise RuntimeError(
        "Missing SUPABASE_URL"
    )

if not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_SECRET_KEY"
    )


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


def main():
    response = (
        supabase
        .table("scrape_staging")
        .select(
            "id, source, source_url, raw_payload, status"
        )
        .eq("status", "pending")
        .order("id")
        .execute()
    )

    rows = response.data or []

    print(f"Found {len(rows)} pending staging row(s).")

    for row in rows:
        print()
        print("=" * 70)
        print(f"STAGING ID: {row['id']}")
        print(f"SOURCE:     {row['source']}")
        print(f"URL:        {row['source_url']}")
        print("=" * 70)

        normalized = transform_staged_record(row)

        print("\nNORMALIZED Axiom novel:")
        print(
            json.dumps(
                normalized,
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()