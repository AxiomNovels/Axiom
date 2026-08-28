'''
To run:
cd to the backend folder, then run:
python -m scraper.royalroad_stage_test
'''

from scraper.royalroad import scrape_royalroad
from scraper.staging import save_to_staging


URLS = [
  "https://www.royalroad.com/fiction/126975/tism-just-a-hypothesis-you-are-the-thesis",
  "https://www.royalroad.com/fiction/145867/why-my-genius-successor-life-is-a-trivial-cliche",
  "https://www.royalroad.com/fiction/116887/enter-the-darkzone-contract-one",
  "https://www.royalroad.com/fiction/124574/wellspring-chronicles",
  "https://www.royalroad.com/fiction/126851/knights-into-dreams-the-chronicles-of-lucy-lockhart",
  "https://www.royalroad.com/fiction/122723/concept-of-consciousness",
  "https://www.royalroad.com/fiction/139843/lunch-on-the-phaeton",
  "https://www.royalroad.com/fiction/86021/shattered-glass-a-cyberpunk-noir-crime-thriller",
  "https://www.royalroad.com/fiction/22531/couplet-a-greater-madness-book-1-complete",
  "https://www.royalroad.com/fiction/142672/otherworld-therapy",
  "https://www.royalroad.com/fiction/28806/the-flower-that-bloomed-nowhere",
  "https://www.royalroad.com/fiction/114897/the-triads-great-evolution-portuguesenglish",
  "https://www.royalroad.com/fiction/91799/reign-of-the-blood-witch-volume-i-complete-slow",
  "https://www.royalroad.com/fiction/140449/avaria",
  "https://www.royalroad.com/fiction/92186/love-volume-three-of-ebb-flow-psychological-superpowered",
  "https://www.royalroad.com/fiction/128190/breaking-the-seam",
  "https://www.royalroad.com/fiction/134605/descent-of-madness",
  "https://www.royalroad.com/fiction/122374/stars-dancing-telepathypsychicsromance",
  "https://www.royalroad.com/fiction/127353/the-gaming-warlock-a-video-game-inspired-litrpg",
  "https://www.royalroad.com/fiction/156892/thorns-edge-a-system-apocalypse-litrpg",
  "https://www.royalroad.com/fiction/130876/beyond-adam",
  "https://www.royalroad.com/fiction/48402/magical-girl-gunslinger",
  "https://www.royalroad.com/fiction/145896/dao-of-the-world-walker-craft-based-slice-of-life",
  "https://www.royalroad.com/fiction/95704/an-elders-revolution-the-art-of-sect-politics",
  "https://www.royalroad.com/fiction/135125/white-witch-of-the-void",
  "https://www.royalroad.com/fiction/130714/bleeding-ego-book-4-silver-age-the-blood-of-the",
  "https://www.royalroad.com/fiction/138721/wanderer-of-dust-serial-transmigration",
  "https://www.royalroad.com/fiction/116829/ideworld-chronicles-the-art-mage",
  "https://www.royalroad.com/fiction/105968/loopshard",
  "https://www.royalroad.com/fiction/28023/katalepsis",
  "https://www.royalroad.com/fiction/97093/the-blade-that-cut-the-mouses-tail-medieval-fantasy",
  "https://www.royalroad.com/fiction/134560/neophyte-world-builder-book-2-complete",
  "https://www.royalroad.com/fiction/152470/traps-tricks-and-beasts-book-2-completefantasy",
  "https://www.royalroad.com/fiction/118846/mythos",
  "https://www.royalroad.com/fiction/54237/nowhere-stars",
  "https://www.royalroad.com/fiction/29286/the-gilded-hero",
  "https://www.royalroad.com/fiction/51358/dungeon-devotee",
  "https://www.royalroad.com/fiction/114160/genesis-protocol-spark",
  "https://www.royalroad.com/fiction/141066/the-gembound-the-price-of-keeping",
  "https://www.royalroad.com/fiction/34009/a-practical-guide-to-sorcery-now-in-book-7",
  "https://www.royalroad.com/fiction/142177/crusaders-of-vampires",
  "https://www.royalroad.com/fiction/91172/the-5th-hero-is-a-beast-queer-litrpg-isekai",
  "https://www.royalroad.com/fiction/128880/the-machine-god",
  "https://www.royalroad.com/fiction/64438/daily-life-in-another-world-isekai-no-nichijou",
  "https://www.royalroad.com/fiction/114617/ominus-vau-god-prince-of-draan",
  "https://www.royalroad.com/fiction/139727/the-fall-of-dol-guldur-a-lotr-fanfiction",
  "https://www.royalroad.com/fiction/94582/sunspot",
  "https://www.royalroad.com/fiction/59967/necroepilogos",
  "https://www.royalroad.com/fiction/18574",
  "https://www.royalroad.com/fiction/88287/blue-star-enterprises",
  "https://www.royalroad.com/fiction/13468/paladin",
  "https://www.royalroad.com/fiction/127257/fantasy-game",
  "https://www.royalroad.com/fiction/19206/lone-the-wanderer",
  "https://www.royalroad.com/fiction/137498/symphony-of-the-stars",
  "https://www.royalroad.com/fiction/120928/courting-death-xianxia-reincarnation",
  "https://www.royalroad.com/fiction/174101/psychic-immortal",
  "https://www.royalroad.com/fiction/59663/godclads",
  "https://www.royalroad.com/fiction/133728/devils-daughter",
  "https://www.royalroad.com/fiction/69543/lavender-eyes",
  "https://www.royalroad.com/fiction/128991/cafe-stardust",
  "https://www.royalroad.com/fiction/122779/bloodstone-volume-i-imminence",
  "https://www.royalroad.com/fiction/141808/awakeners-truth-villain-mc-mastermind-ruthless",
  "https://www.royalroad.com/fiction/138224/and-yet-the-lotus-blooms-xianxia",
  "https://www.royalroad.com/fiction/126468/second-soul",
  "https://www.royalroad.com/fiction/124727/the-monkey-kings-odyssey",
  "https://www.royalroad.com/fiction/141701/ashes-of-the-old-law",
  "https://www.royalroad.com/fiction/141865/to-be-a-supernova",
  "https://www.royalroad.com/fiction/134217/children-of-caber",
  "https://www.royalroad.com/fiction/145429/mage",
  "https://www.royalroad.com/fiction/183537/feasting-on-immortalsdark-xianxia",
  "https://www.royalroad.com/fiction/142206/animal-instinct",
  "https://www.royalroad.com/fiction/91902/the-infamous-denor-kara",
  "https://www.royalroad.com/fiction/135618/globus",
  "https://www.royalroad.com/fiction/129283/the-tribulations-of-lucas-bagge-classic-cartoon",
  "https://www.royalroad.com/fiction/141733/soul--the-killer-king-progression-fantasy-time"
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