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
  "https://www.wattpad.com/story/392848764",
  "https://www.wattpad.com/story/89141665",
  "https://www.wattpad.com/story/120255658-cognitive-deviance",
  "https://www.wattpad.com/story/210056770",
  "https://www.wattpad.com/story/177895996",
  "https://www.wattpad.com/story/276427858",
  "https://www.wattpad.com/story/283980611",
  "https://www.wattpad.com/story/124816840",
  "https://www.wattpad.com/story/350925259",
  "https://www.wattpad.com/story/133085783",
  "https://www.wattpad.com/story/278770795-the-university-of-gangsters",
  "https://www.wattpad.com/story/212695496",
  "https://www.wattpad.com/story/394887764",
  "https://www.wattpad.com/story/333100433",
  "https://www.wattpad.com/story/72534980",
  "https://www.wattpad.com/story/50519321",
  "https://www.wattpad.com/story/139779570",
  "https://www.wattpad.com/story/3169587",
  "https://www.wattpad.com/story/69648678",
  "https://www.wattpad.com/story/38446006",
  "https://www.wattpad.com/story/126462571",
  "https://www.wattpad.com/story/343606089",
  "https://www.wattpad.com/story/411669919-the-monster-she-calmed",
  "https://www.wattpad.com/story/311006502",
  "https://www.wattpad.com/story/17572328",
  "https://www.wattpad.com/story/112634081-tales-of-the-pearly-city-pearly-tales-vol-1",
  "https://www.wattpad.com/story/228962490",
  "https://www.wattpad.com/story/26538982",
  "https://www.wattpad.com/story/5971819-my-perfect-bride",
  "https://www.wattpad.com/story/408146181",
  "https://www.wattpad.com/story/231112966",
  "https://www.wattpad.com/story/337320320",
  "https://www.wattpad.com/story/266012174",
  "https://www.wattpad.com/story/95059501",
  "https://www.wattpad.com/story/35650795",
  "https://www.wattpad.com/story/150504152",
  "https://www.wattpad.com/story/189297945",
  "https://www.wattpad.com/story/19230171",
  "https://www.wattpad.com/story/353325140-dead-man%27s-match",
  "https://www.wattpad.com/story/145519856",
  "https://www.wattpad.com/story/354353384",
  "https://www.wattpad.com/story/65343138",
  "https://www.wattpad.com/story/393915235",
  "https://www.wattpad.com/story/356017567",
  "https://www.wattpad.com/story/220648404"
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