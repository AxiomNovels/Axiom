"""
To run:
cd to the backend folder, then run:

python -m scraper.wattpad_stage_test
"""

from scraper.wattpad import scrape_wattpad
from scraper.staging import save_to_staging


URLS = [
  "https://www.wattpad.com/story/391415617",
  "https://www.wattpad.com/story/246002648",
  "https://www.wattpad.com/story/192690761",
  "https://www.wattpad.com/story/254314754",
]


def main():
    total = len(URLS)
    successful = 0
    failed = 0
    staged = 0

    print("=" * 70)
    print("WATTPAD BATCH SCRAPE")
    print("=" * 70)
    print(f"URLs to process: {total}")

    for index, url in enumerate(URLS, start=1):

        print()
        print("=" * 70)
        print(f"NOVEL {index} OF {total}")
        print("=" * 70)
        print("SOURCE:", url)

        # -----------------------------------------------------
        # Scrape
        # -----------------------------------------------------

        print("\nFetching and parsing...")

        try:
            novel = scrape_wattpad(url)

        except Exception as exc:
            failed += 1

            print("\nSCRAPE FAILED")
            print(f"  error type: {type(exc).__name__}")
            print(f"  error:      {exc}")

            # Continue to the next URL.
            continue

        successful += 1

        # -----------------------------------------------------
        # Display scraped data
        # -----------------------------------------------------

        print("\nParsed novel:")
        print(f"  title:             {novel['title']}")
        print(f"  author:            {novel['author']}")
        print(f"  story_id:          {novel['story_id']}")
        print(f"  status:            {novel['status']}")
        print(f"  chapter_count:      {novel['chapter_count']}")
        print(f"  view_count:         {novel['view_count']}")
        print(f"  genres:             {novel['genres']}")
        print(f"  tags:               {novel['tags']}")
        print(
            f"  cover_image_url:    "
            f"{novel['cover_image_url']}"
        )
        print(
            f"  reading_url:        "
            f"{novel['reading_url']}"
        )
        print(
            f"  synopsis length:    "
            f"{len(novel['synopsis'] or '')}"
        )

        # -----------------------------------------------------
        # Save to staging
        # -----------------------------------------------------

        print("\nWriting to scrape_staging...")

        try:
            staged_record = save_to_staging(novel)

        except Exception as exc:
            failed += 1

            print("\nSTAGING FAILED")
            print(f"  error type: {type(exc).__name__}")
            print(f"  error:      {exc}")

            # The novel was scraped successfully, but it
            # could not be written to staging.
            continue

        staged += 1

        print("\nStaged successfully:")
        print(f"  staging id:         {staged_record['id']}")
        print(f"  source:             {staged_record['source']}")
        print(
            f"  source_url:         "
            f"{staged_record['source_url']}"
        )
        print(f"  status:             {staged_record['status']}")
        print(
            f"  fetched_at:        "
            f"{staged_record['fetched_at']}"
        )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("BATCH SCRAPE COMPLETE")
    print("=" * 70)
    print(f"URLs attempted:       {total}")
    print(f"Scrapes successful:    {successful}")
    print(f"Scrapes/staging failed:{failed}")
    print(f"Records staged:        {staged}")
    print("=" * 70)


if __name__ == "__main__":
    main()