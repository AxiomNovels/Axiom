"""
Discover ~250 of the most popular WebNovel novels, spread across a
variety of genres, with explicit sexual content hard-filtered out.

This replaces the older philosophy/psychology-focused discovery script.
The selection logic now has three priorities, in this order:

    1. Hard filter: explicit sexual content is excluded outright.
    2. Popularity: WebNovel's own review score and review count.
    3. Genre diversity: no single genre is allowed to dominate the
       final list.

Method
------
1. Crawl WebNovel's cross-genre "all_time" ranking pages (popular,
   collection, best sellers, engagement) as well as a keyword search
   for each of WebNovel's own top-level genre categories (Fantasy,
   Urban, History, Horror, Sci-fi, Sports, Games, Eastern, Realistic,
   Action, War, Teen -- see https://en.webnovel.com/category), so the
   candidate pool spans genres instead of being dominated by whatever
   is broadly trending.
2. Deduplicate all discovered book URLs.
3. Scrape every candidate with scraper.webnovel.scrape_webnovel(),
   which already fetches WebNovel's own review statistics
   (totalScore / totalReviewNum) as part of the normal scrape.
4. Hard-exclude any novel whose tags indicate explicit sexual content
   (see EXCLUDED_TAGS below).
5. Require a minimum review score/count floor so obscure or
   low-engagement novels don't dilute the pool.
6. Rank the remaining candidates by a popularity score, then select
   up to TARGET novels using a per-genre cap so that popularity
   dominates the ordering while no single genre can fill the whole
   list. Unfilled seats are backfilled by raw popularity so the
   target count is still reached.

Banned-tag research
--------------------
WebNovel allows free-text "Additional Tags" on user-uploaded original
novels (distinct from its fixed top-level genre categories), and a
large share of the explicit/adult titles on the platform advertise
this openly in their own tag lists (e.g. "R18", "NSFW", "Hentai",
"Smut", "Harem", "Netorare", "Mature", "18+", "Ecchi"). EXCLUDED_TAGS
below was built by inspecting real WebNovel tag soups for these
platform-specific explicit-content markers, mirroring the same intent
as the existing Wattpad filter but adapted to WebNovel's own tag
vocabulary.

Output
------
popular_webnovel_urls.txt
popular_webnovel_audit.csv
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from scraper.webnovel import HEADERS, scrape_webnovel


BASE_URL = "https://www.webnovel.com"


# Cross-genre "all time" rankings. Several independent surfaces are
# combined since rankings can change and one family alone can be
# unstable.
RANKING_SEED_URLS = [
    f"{BASE_URL}/ranking/novel/all_time/popular_rank",
    f"{BASE_URL}/ranking/novel/all_time/collection_rank",
    f"{BASE_URL}/ranking/novel/all_time/best_sellers",
    f"{BASE_URL}/ranking/novel/all_time/engagement_rank",
]

# WebNovel's own top-level genre categories (see
# https://en.webnovel.com/category). Searching each by name is a more
# robust discovery path than guessing WebNovel's internal numeric
# category IDs, and it reuses the same working search/crawl code as
# the ranking pages.
GENRE_QUERIES = [
    "fantasy",
    "urban",
    "history",
    "horror",
    "sci-fi",
    "sports",
    "games",
    "eastern",
    "realistic fiction",
    "action",
    "war",
    "teen",
]

TARGET = 250
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.35
MAX_PAGES_PER_SEED = 40

# No single genre may take up more than this share of the final list.
MAX_GENRE_SHARE = 0.15
MIN_GENRE_CAP = 8

# WebNovel review-statistics floor. Only enforced when the statistics
# were actually retrieved.
MIN_TOTAL_SCORE = 3.0
MIN_TOTAL_REVIEW_NUM = 10

# Tags that indicate explicit sexual content on WebNovel. This is a
# hard filter: any match excludes the novel regardless of popularity
# or genre. WebNovel normalizes tags to uppercase internally; matching
# is done against the lowercased form (see normalize_text below).
EXCLUDED_TAGS = {
    # explicit / mature labels
    "adult", "adult content", "mature content",
    "mature", "mature romance", "adult romance", "nsfw", "explicit",
    "explicit content", "hentai", "ecchi", "sex stories", "sex story",
    "smut", "erotica", "erotic", "erotic fiction", "steamy", "spicy",

    # explicit-scene shorthand
    "lemon", "lemons", "lime", "sex scene", "sex scenes",
    "sexual content",

    # harem / multi-partner
    "harem", "reverse harem", "all male harem", "all female harem",
    "harem seeking", "polygamy", "polyamory", "multiple partners",

    # fetish / bdsm / non-consensual
    "bdsm", "bondage", "domination", "domination play", "fetish",
    "kink", "kinky", "submissive", "dominant", "master and slave",
    "sex slave", "noncon", "non-con", "nonconsensual",
    "non-consensual", "dubcon", "dub-con", "rape", "rape fantasy",
    "netorare", "ntr", "netori", "cuckold",

    # bestiality / extreme
    "bestiality", "beastality",

    # incest
    "incest",

    # pregnancy/breeding fetish framing
    "mpreg", "breeding", "impregnation",

    # omegaverse
    "omegaverse", "alpha mate", "alpha romance",

    # explicit-coded character/content descriptors seen in WebNovel
    # "Additional Tags" lists
    "milf", "loli", "legal loli", "lolicon", "shota", "shotacon",
}


@dataclass
class Candidate:
    url: str
    story_id: int | None
    title: str | None
    synopsis: str | None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    total_score: float | None = None
    total_review_num: int | None = None

    popularity_hits: int = 0
    popularity_score: float = 0.0

    quality_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# URL discovery
# ---------------------------------------------------------------------

def canonical_book_url(url: str) -> str | None:
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)

    if parsed.netloc.lower() not in {"www.webnovel.com", "webnovel.com"}:
        return None

    match = re.search(r"/book/[^?#]+", parsed.path)
    if not match:
        return None

    path = match.group(0).rstrip("/")

    if not (re.search(r"_\d+$", path) or re.search(r"/book/\d+$", path)):
        return None

    return urlunparse(("https", "www.webnovel.com", path, "", "", ""))


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return response.text


def extract_book_urls(html: str, page_url: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()

    for a in soup.select("a[href]"):
        book = canonical_book_url(urljoin(page_url, a["href"]))
        if book:
            urls.add(book)

    return urls


def is_same_listing_family(seed_url: str, candidate_url: str) -> bool:
    seed = urlparse(seed_url)
    candidate = urlparse(candidate_url)

    if candidate.netloc.lower() not in {"www.webnovel.com", "webnovel.com"}:
        return False

    if seed.path.startswith("/ranking/"):
        return candidate.path.startswith("/ranking/")

    if seed.path == "/search":
        return candidate.path == "/search"

    return False


def listing_next_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []

    for a in soup.select("a[href]"):
        text = " ".join(a.stripped_strings).strip().lower()
        href = urljoin(page_url, a["href"])

        if not is_same_listing_family(page_url, href):
            continue

        rel = {str(x).lower() for x in (a.get("rel") or [])}

        if (
            "next" in rel
            or text in {"next", "next >", ">", "\u203a", "\u2192"}
            or text.isdigit()
        ):
            found.append(href)

    return found


def crawl_listing(
    session: requests.Session,
    seed_url: str,
    page_limit: int,
) -> list[set[str]]:
    queue = deque([seed_url])
    seen_pages: set[str] = set()
    pages: list[set[str]] = []

    while queue and len(pages) < page_limit:
        url = queue.popleft()

        if url in seen_pages:
            continue
        seen_pages.add(url)

        try:
            html = fetch_html(session, url)
        except requests.RequestException as exc:
            print("LISTING FAILED:", url, type(exc).__name__, exc)
            continue

        pages.append(extract_book_urls(html, url))

        for next_url in listing_next_links(html, url):
            if next_url not in seen_pages:
                queue.append(next_url)

        time.sleep(REQUEST_DELAY)

    return pages


def search_url(query: str) -> str:
    return f"{BASE_URL}/search?{urlencode({'keywords': query})}"


def discover_candidates() -> dict[str, int]:
    """
    Return {url: number_of_listing_pages_it_appeared_on}.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    popularity_hits: dict[str, int] = {}

    print("\n=== DISCOVERING CROSS-GENRE RANKING CANDIDATES ===")

    for seed in RANKING_SEED_URLS:
        print("RANKING:", seed)

        for books in crawl_listing(session, seed, MAX_PAGES_PER_SEED):
            for url in books:
                popularity_hits[url] = popularity_hits.get(url, 0) + 1

        print("Unique candidates so far:", len(popularity_hits))

    print("\n=== DISCOVERING PER-GENRE CANDIDATES ===")

    for genre in GENRE_QUERIES:
        print("GENRE:", genre)

        for books in crawl_listing(
            session, search_url(genre), MAX_PAGES_PER_SEED
        ):
            for url in books:
                popularity_hits[url] = popularity_hits.get(url, 0) + 1

        time.sleep(REQUEST_DELAY)

    print("Total discovered candidates:", len(popularity_hits))
    return popularity_hits


# ---------------------------------------------------------------------
# Popularity scoring (no more relevance scoring)
# ---------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def synopsis_quality_penalty(
    title: str | None,
    synopsis: str | None,
) -> tuple[float, list[str]]:
    text = f"{title or ''} {synopsis or ''}".strip()

    if not text:
        return 12.0, ["missing-synopsis"]

    penalty = 0.0
    reasons: list[str] = []

    letters = [char for char in text if char.isalpha()]
    if letters and len(letters) > 30:
        upper_ratio = sum(char.isupper() for char in letters) / len(letters)
        if upper_ratio > 0.45:
            penalty += 4
            reasons.append("excessive-capitalization")

    words = re.findall(r"[A-Za-z']+", (synopsis or "").lower())

    if len(words) < 20:
        penalty += 4
        reasons.append("very-short-synopsis")

    if len(words) >= 40:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.35:
            penalty += 3
            reasons.append("low-lexical-variety")

    return penalty, reasons


def score_popularity(
    *,
    title: str | None,
    synopsis: str | None,
    total_score: float | None,
    total_review_num: int | None,
    popularity_hits: int,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if total_score is not None:
        confidence = (
            min(total_review_num or 0, 500) / 500
            if total_review_num is not None
            else 0.35
        )
        adjusted_score = confidence * total_score + (1 - confidence) * 3.8
        score += max(-2.0, (adjusted_score - 3.0) * 4.0)
        reasons.append(f"total_score={total_score}")

    if total_review_num is not None:
        score += min(6.0, math.log10(total_review_num + 1) * 1.5)
        reasons.append(f"total_review_num={total_review_num}")

    score += min(popularity_hits, 10) * 1.5
    reasons.append(f"listing-hits={popularity_hits}")

    penalty, penalty_reasons = synopsis_quality_penalty(title, synopsis)
    score -= penalty
    reasons.extend(f"presentation:{reason}" for reason in penalty_reasons)

    return score, reasons


# ---------------------------------------------------------------------
# Scrape, hard-filter, and score
# ---------------------------------------------------------------------

def scrape_and_score(popularity_hits: dict[str, int]) -> list[Candidate]:
    candidate_urls = list(popularity_hits)

    print(f"\n=== SCRAPING AND CLASSIFYING {len(candidate_urls)} CANDIDATES ===")

    candidates: list[Candidate] = []

    for index, url in enumerate(candidate_urls, start=1):
        print(f"[{index}/{len(candidate_urls)}] {url}")

        try:
            novel = scrape_webnovel(url)
        except Exception as exc:
            print("FAILED:", type(exc).__name__, exc)
            continue

        # ---------------------------------------------------------
        # Hard filter: explicit sexual content.
        # ---------------------------------------------------------
        novel_tags = {
            normalize_text(tag)
            for tag in novel.get("tags", [])
            if normalize_text(tag)
        }

        matched_excluded_tags = novel_tags & EXCLUDED_TAGS
        if matched_excluded_tags:
            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(excluded tags: {sorted(matched_excluded_tags)})"
            )
            time.sleep(REQUEST_DELAY)
            continue

        # ---------------------------------------------------------
        # Popularity floor (review statistics come from the scrape
        # itself -- scrape_webnovel() already calls WebNovel's review
        # endpoint).
        # ---------------------------------------------------------
        total_score = novel.get("total_score")
        total_review_num = novel.get("total_review_num")

        if total_score is not None and total_score < MIN_TOTAL_SCORE:
            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(score={total_score}, required >= {MIN_TOTAL_SCORE})"
            )
            time.sleep(REQUEST_DELAY)
            continue

        if (
            total_review_num is not None
            and total_review_num < MIN_TOTAL_REVIEW_NUM
        ):
            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(reviews={total_review_num}, required >= {MIN_TOTAL_REVIEW_NUM})"
            )
            time.sleep(REQUEST_DELAY)
            continue

        popularity_score, quality_reasons = score_popularity(
            title=novel.get("title"),
            synopsis=novel.get("synopsis"),
            total_score=total_score,
            total_review_num=total_review_num,
            popularity_hits=popularity_hits.get(url, 0),
        )

        candidates.append(
            Candidate(
                url=url,
                story_id=novel.get("story_id"),
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                genres=novel.get("genres", []),
                tags=novel.get("tags", []),
                total_score=total_score,
                total_review_num=total_review_num,
                popularity_hits=popularity_hits.get(url, 0),
                popularity_score=popularity_score,
                quality_reasons=quality_reasons,
            )
        )

        time.sleep(REQUEST_DELAY)

    return candidates


# ---------------------------------------------------------------------
# Popularity-first, genre-diverse selection
# ---------------------------------------------------------------------

def primary_genre(candidate: Candidate) -> str:
    return candidate.genres[0] if candidate.genres else "Unclassified"


def select_popular_diverse(
    candidates: list[Candidate],
    target: int = TARGET,
) -> list[Candidate]:
    """
    Rank by popularity, but cap how much of the final list any single
    genre can take up, backfilling any unfilled seats by raw
    popularity so the target count is still reached. See the Royal
    Road discovery script for the same algorithm with more discussion.
    """
    cap = max(MIN_GENRE_CAP, math.ceil(target * MAX_GENRE_SHARE))

    ranked = sorted(candidates, key=lambda c: c.popularity_score, reverse=True)

    selected: list[Candidate] = []
    overflow: list[Candidate] = []
    genre_counts: Counter[str] = Counter()

    for candidate in ranked:
        genre = primary_genre(candidate)

        if genre_counts[genre] < cap:
            selected.append(candidate)
            genre_counts[genre] += 1
        else:
            overflow.append(candidate)

        if len(selected) >= target:
            break

    if len(selected) < target:
        for candidate in overflow:
            if len(selected) >= target:
                break
            selected.append(candidate)

    return selected


# ---------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------

def write_outputs(selected: list[Candidate], all_candidates: list[Candidate]) -> None:
    urls = [candidate.url for candidate in selected]

    with open("popular_webnovel_urls.txt", "w", encoding="utf-8") as file:
        json.dump(urls, file, indent=2)

    selected_urls = {candidate.url for candidate in selected}

    with open(
        "popular_webnovel_audit.csv", "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "selected",
                "url",
                "story_id",
                "title",
                "popularity_score",
                "total_score",
                "total_review_num",
                "popularity_hits",
                "genres",
                "tags",
                "quality_reasons",
                "synopsis",
            ],
        )
        writer.writeheader()

        for candidate in sorted(
            all_candidates,
            key=lambda item: item.popularity_score,
            reverse=True,
        ):
            writer.writerow({
                "selected": candidate.url in selected_urls,
                "url": candidate.url,
                "story_id": candidate.story_id,
                "title": candidate.title,
                "popularity_score": candidate.popularity_score,
                "total_score": candidate.total_score,
                "total_review_num": candidate.total_review_num,
                "popularity_hits": candidate.popularity_hits,
                "genres": json.dumps(candidate.genres, ensure_ascii=False),
                "tags": json.dumps(candidate.tags, ensure_ascii=False),
                "quality_reasons": json.dumps(
                    candidate.quality_reasons, ensure_ascii=False
                ),
                "synopsis": candidate.synopsis,
            })


def main() -> None:
    popularity_hits = discover_candidates()

    if len(popularity_hits) < MIN_DISCOVERED:
        print(
            f"\nNOTE: only discovered {len(popularity_hits)} candidate URLs "
            f"(target pool: {MIN_DISCOVERED}). Continuing with what was found."
        )

    candidates = scrape_and_score(popularity_hits)

    selected = select_popular_diverse(candidates, target=TARGET)

    write_outputs(selected, candidates)

    genre_counts = Counter(primary_genre(c) for c in selected)

    print(
        f"\n=== SELECTED {len(selected)} WEBNOVEL NOVELS "
        f"(target: {TARGET}, tolerance: +/-{TARGET_TOLERANCE}) ==="
    )

    if len(selected) < MIN_TARGET:
        print(
            "WARNING: Fewer than the minimum acceptable number of novels "
            "passed the sexual-content and popularity filters. The output "
            "is intentionally not padded with weaker candidates."
        )

    print("\nGenre spread of the selection:")
    for genre, count in genre_counts.most_common():
        print(f"  {genre:<20} {count}")

    for rank, candidate in enumerate(selected, start=1):
        print(
            f"{rank:03d} pop={candidate.popularity_score:6.1f} "
            f"score={candidate.total_score} reviews={candidate.total_review_num} "
            f"genres={candidate.genres} {candidate.title}"
        )
        print(candidate.url)

    print("\nWrote:")
    print("  popular_webnovel_urls.txt")
    print("  popular_webnovel_audit.csv")


if __name__ == "__main__":
    main()