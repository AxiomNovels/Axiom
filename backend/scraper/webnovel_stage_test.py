"""
To run:
cd to the backend folder, then run:

python -m scraper.webnovel_stage_test
"""

from scraper.webnovel import scrape_webnovel
from scraper.staging import save_to_staging


URLS = [
  "https://www.webnovel.com/book/shattered-sanity_35891611308041805",
  "https://www.webnovel.com/book/shocking-the-whole-internet!-you-are-not-a-psychologist-at-all!_26546254106695305",
  "https://www.webnovel.com/book/a-snail's-wisdom_10342917705010105",
  "https://www.webnovel.com/book/reverend-insanity_7996858406002505",
  "https://www.webnovel.com/book/thriller-paradise_7997164706002605",
  "https://www.webnovel.com/book/my-sister-exposed-my-identity-as-a-villainous-godfather_21276835205793705",
  "https://www.webnovel.com/book/reverend-insanity(english)_32605619408374705",
  "https://www.webnovel.com/book/hero-of-darkness_20433994506434305",
  "https://www.webnovel.com/book/why-reincarnate-as-a-useless-skeleton_21398850606386705",
  "https://www.webnovel.com/book/my-infinite-cultivation-system_34724106100242905",
  "https://www.webnovel.com/book/the-world's-consciousness_24007809206430005",
  "https://www.webnovel.com/book/sorcerer's-shadow_26720650205010005",
  "https://www.webnovel.com/book/the-royal-military-academy's-impostor-owns-a-dungeon-%5Bbl%5D_31554304608491405",
  "https://www.webnovel.com/book/i-reincarnated-as-the-ancient-philosopher's-stone!_17186726305789205",
  "https://www.webnovel.com/book/greed-all-for-what_21535882606809905",
  "https://www.webnovel.com/book/transmigrating-as-the-younger-sister-of-a-bigshot-with-multiple-identities_26313190705717605",
  "https://www.webnovel.com/book/beauty-and-the-beasts_16731346305020705",
  "https://www.webnovel.com/book/muchuan-and-xiang-wan_11057219106244805",
  "https://www.webnovel.com/book/when-the-top-hacker-becomes-a-female-supporting-character-she-amazes-the-world_22303571206703905",
  "https://www.webnovel.com/book/fragments-of-time-%5Bfree-completed%5D_12606628305103005",
  "https://www.webnovel.com/book/blood-warlock-succubus-partner-in-the-apocalypse_20134751006091605",
  "https://www.webnovel.com/book/solo-leveling(only-i-level-up)_12507348206677105",
  "https://www.webnovel.com/book/sss-awakening-i-can-class-change-at-will_34285443300774305",
  "https://www.webnovel.com/book/radiant-blade-of-the-wilderness_35970900108664305",
  "https://www.webnovel.com/book/natural-disaster-i-started-by-hoarding-tens-of-billions-of-supplies_30313659405853705",
  "https://www.webnovel.com/book/the-hunter's-gonna-lay-low-%5Bbl%5D_32528733200319505",
  "https://www.webnovel.com/book/got-dropped-in-a-ghost-story-still-gotta-work_36103796300498305",
  "https://www.webnovel.com/book/the-husky-and-his-white-cat-shizun-erha-he-ta-de-bai-mao-shizun-vol1-5_26825133806608205",
  "https://www.webnovel.com/book/i%E2%80%99m-a-young-god-won%E2%80%99t-you-raise-me_36319132800427205",
  "https://www.webnovel.com/book/nine-deaths-of-the-sword_36674652900309405",
  "https://www.webnovel.com/book/hellbound-with-you_16699683105884505",
  "https://www.webnovel.com/book/free-fall-(pyramid-of-gold)_21071740706351705",
  "https://www.webnovel.com/book/evil-husband-glutton-wife-buy-miss-piggy-get-free-little-buns_17692472606489105",
  "https://www.webnovel.com/book/trash-of-the-count's-family-%5Bcomplete%5D_33277691908858405",
  "https://www.webnovel.com/book/sss-awakening-i-am-the-first-legendary-mage_36357645008976005",
  "https://www.webnovel.com/book/supreme-magus_12820870105509205",
  "https://www.webnovel.com/book/the-reincarnated-assassin-is-a-genius-swordsman-(full)_27682225208752005",
  "https://www.webnovel.com/book/marry-a-sweetheart-and-get-another-free-president-please-sign-this!_16466212206154905",
  "https://www.webnovel.com/book/22196546206090805",
  "https://www.webnovel.com/book/shadow-slave_22196546206090805",
  "https://www.webnovel.com/book/supremacy-games_17669339406351905",
  "https://www.webnovel.com/book/the-innkeeper_22426985405158405",
  "https://www.webnovel.com/book/weakest-beast-tamer-gets-all-sss-dragons_31285370600463505",
  "https://www.webnovel.com/book/my-vampire-system_16709365405930105",
  "https://www.webnovel.com/book/the-mech-touch_10636300105085505",
  "https://www.webnovel.com/book/grace-of-a-wolf_32072057300309605",
  "https://www.webnovel.com/book/genetic-ascension_29441378000931905",
  "https://www.webnovel.com/book/humanity's-greatest-mecha-warrior-system_23118185006257505",
  "https://www.webnovel.com/book/madam%E2%80%99s-identities-shocks-the-entire-city-again_19099756306397805",
  "https://www.webnovel.com/book/short-light-free_9432183306002205"
]


def main():
    total = len(URLS)
    successful = 0
    failed = 0
    staged = 0

    print("=" * 70)
    print("WEBNOVEL BATCH SCRAPE")
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
            novel = scrape_webnovel(url)

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
        print(f"  status:             {novel['status']}")
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
        # Save to staging / Supabase
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
        print(f"  source:              {staged_record['source']}")
        print(
            f"  source_url:         "
            f"{staged_record['source_url']}"
        )
        print(
            f"  status:             "
            f"{staged_record['status']}"
        )
        print(
            f"  fetched_at:         "
            f"{staged_record['fetched_at']}"
        )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("BATCH SCRAPE COMPLETE")
    print("=" * 70)
    print(f"URLs attempted:        {total}")
    print(f"Scrapes successful:     {successful}")
    print(f"Scrapes/staging failed: {failed}")
    print(f"Records staged:         {staged}")
    print("=" * 70)


if __name__ == "__main__":
    main()