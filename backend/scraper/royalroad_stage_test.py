'''
To run:
cd to the backend folder, then run:
python -m scraper.royalroad_stage_test
'''

from scraper.royalroad import scrape_royalroad
from scraper.staging import save_to_staging


URLS = [
    "https://www.royalroad.com/fiction/126975/tism-just-a-hypothesis-you-are-the-thesis",
    "https://www.royalroad.com/fiction/36735/the-perfect-run",
    "https://www.royalroad.com/fiction/21220/mother-of-learning",
    "https://www.royalroad.com/fiction/16344/the-last-philosopher",
]


def main():
    for url in URLS:
        print()
        print("=" * 70)
        print("SOURCE:", url)
        print("=" * 70)

        print("\nFetching and parsing...")

        novel = scrape_royalroad(url)

        print("\nParsed novel:")
        print(f"  title:             {novel['title']}")
        print(f"  author:            {novel['author']}")
        print(f"  fiction_id:        {novel['fiction_id']}")
        print(f"  status:             {novel['status']}")
        print(f"  chapter_count:      {novel['chapter_count']}")
        print(f"  genres:             {novel['genres']}")
        print(f"  tags:               {novel['tags']}")
        print(f"  cover_image_url:    {novel['cover_image_url']}")
        print(f"  reading_url:        {novel['reading_url']}")
        print(f"  synopsis length:    {len(novel['synopsis'])}")

        print("\nWriting to scrape_staging...")

        staged = save_to_staging(novel)

        print("\nStaged successfully:")
        print(f"  staging id:         {staged['id']}")
        print(f"  source:             {staged['source']}")
        print(f"  source_url:         {staged['source_url']}")
        print(f"  status:             {staged['status']}")
        print(f"  fetched_at:         {staged['fetched_at']}")

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()