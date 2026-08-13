"""
Axiom - Seed real webnovels into Supabase, replacing the placeholder rows.

Purpose: verify that cover images and reading links actually render
correctly on index.html / novel.html, using real data instead of demo
placeholders.

Design notes
------------
- This intentionally does NOT touch protagonist_profiles / philosophy_profiles
  / storytelling_style_profiles. Those tables key off novel_id via a foreign
  key, and generating real scores for them is task 3 (scraped trait
  generation), not this step. By upserting onto the *existing* novel ids,
  whatever demo profile data already sits in those tables keeps rendering on
  novel.html exactly as before -- this only swaps the bibliographic fields
  (title / author / synopsis / cover / links / genres / status).

- Two of the five novels (Mother of Learning, Beware of Chicken) are hosted
  on Royal Road, whose cover CDN follows a stable, documented URL pattern:
      https://www.royalroadcdn.com/public/covers-full/{fiction_id}-{slug}.jpg
  This was confirmed against several live Royal Road covers before being
  used here, not guessed.

  For the other three (Webnovel, and two author-run sites) there's no
  reliable, verifiable direct-image URL, so cover_image_url is deliberately
  left as None. script.js / novel.js already fall back to a text-on-gradient
  cover when cover_image_url is missing -- so this run exercises BOTH the
  real-image path and the fallback path in one go. Fill the other three in
  by right-clicking -> "Copy image address" on the source page, or replace
  this whole approach with the task 2/3 scraper's output once that exists.

- Synopses below are original paraphrases, not copied from any source.

Run with:
    cd backend
    python seed_real_novels.py
"""

import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in backend/.env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


REAL_NOVELS = [
    {
        "title": "Mother of Learning",
        "author": "nobody103",
        "status": "completed",
        "genres": ["Fantasy", "Adventure", "Mystery"],
        "synopsis": (
            "A magic student who dies on the eve of his city's summer festival "
            "wakes up a month in the past, trapped in a repeating time loop. "
            "He has to use each reset to get sharper, stronger, and better "
            "informed, because whatever is behind the loop is not on his side."
        ),
        "cover_image_url": "https://www.royalroadcdn.com/public/covers-full/21220-mother-of-learning.jpg",
        "reading_links": [
            {"platform": "Royal Road", "url": "https://www.royalroad.com/fiction/21220/mother-of-learning"},
        ],
    },
    {
        "title": "Solo Leveling",
        "author": "Chugong",
        "status": "completed",
        "genres": ["Action", "Fantasy"],
        "synopsis": (
            "In a world where 'hunters' fight monsters pouring out of dungeons, "
            "the weakest hunter alive is chosen by a mysterious system that lets "
            "him grow stronger through effort -- something no other hunter's "
            "power can do."
        ),
        "cover_image_url": None,  # see module docstring
        "reading_links": [
            {
                "platform": "Webnovel",
                "url": "https://www.webnovel.com/book/solo-leveling(only-i-level-up)_12507348206677105",
            },
        ],
    },
    {
        "title": "The Wandering Inn",
        "author": "pirateaba",
        "status": "ongoing",
        "genres": ["Fantasy", "Slice of Life", "Adventure"],
        "synopsis": (
            "A young woman stranded in another world ends up running an inn at "
            "the edge of civilization. What starts as a story about serving "
            "food and drink slowly widens into a sprawling saga about everyone "
            "who passes through her door."
        ),
        "cover_image_url": None,  # see module docstring
        "reading_links": [
            {"platform": "Official Site", "url": "https://wanderinginn.com/"},
        ],
    },
    {
        "title": "Beware of Chicken",
        "author": "CasualFarmer",
        "status": "ongoing",
        "genres": ["Fantasy", "Comedy", "Cultivation"],
        "synopsis": (
            "A cultivator convinced he'll never measure up to his peers fakes "
            "his own death and retires to a quiet backwater, only to end up "
            "building a farm, a found family, and a reputation he never wanted "
            "while trying his hardest to stay unremarkable."
        ),
        "cover_image_url": "https://www.royalroadcdn.com/public/covers-full/39408-beware-of-chicken.jpg",
        "reading_links": [
            {"platform": "Royal Road", "url": "https://www.royalroad.com/fiction/39408/beware-of-chicken"},
        ],
    },
    {
        "title": "A Practical Guide to Evil",
        "author": "ErraticErrata",
        "status": "completed",
        "genres": ["Fantasy", "Political Intrigue"],
        "synopsis": (
            "In a world where playing the hero or the villain grants real "
            "supernatural power, an orphan girl deliberately claws her way up "
            "the villain's path through a corrupt empire, testing whether doing "
            "wrong for the right reasons actually works."
        ),
        "cover_image_url": "https://m.media-amazon.com/images/I/41GRf78NZqL.jpg",
        "reading_links": [
            {"platform": "Official Site", "url": "https://practicalguidetoevil.wordpress.com/"},
        ],
    },
]


def main():
    existing = (
        supabase.table("novels")
        .select("id, title")
        .order("id")
        .execute()
        .data
    )

    print(f"Found {len(existing)} existing novel row(s):")
    for row in existing:
        print(f"  id={row['id']}: {row['title']}")

    existing_ids = [row["id"] for row in existing]

    # `id` is a Postgres GENERATED ALWAYS AS IDENTITY column, so it can never
    # be written explicitly -- not even to an id that doesn't exist yet.
    # For rows that already exist we UPDATE in place (keeps the id, and keeps
    # any profile data already attached to it). For any novels beyond what
    # already exists, we INSERT without an id and let Postgres assign one.
    print()

    test = (
        supabase.table("novels")
        .select("id, title")
        .eq("id", 1)
        .execute()
    )

    print("SELECT TEST:", test)

    test = (
        supabase.table("novels")
        .update({"title": "TEST UPDATE"})
        .eq("id", 1)
        .execute()
    )

    print("UPDATE TEST:", test)

    test = (
        supabase.table("novels")
        .select("id, title")
        .eq("id", 1)
        .execute()
    )

    print("POST-UPDATE SELECT:", test)

    results = []
    for index, novel in enumerate(REAL_NOVELS):
        if index < len(existing_ids):
            novel_id = existing_ids[index]
            response = (
                supabase.table("novels")
                .update(novel)
                .eq("id", novel_id)
                .select("*")
                .execute()
            )
            action = "updated"
            action = "updated"
        else:
            response = supabase.table("novels").insert(novel).execute()
            action = "inserted"
        row = response.data[0]
        results.append(row)
        print(f"  {action} id={row['id']}: {row['title']}")

    print("\nDone. Check each one at:")
    for row in results:
        print(f"  /novel.html?id={row['id']}")


if __name__ == "__main__":
    main()