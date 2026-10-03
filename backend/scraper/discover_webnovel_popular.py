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
from scraper.content_policy import EXCLUDED_TAGS_BY_SOURCE


BASE_URL = "https://www.webnovel.com"


# ---------------------------------------------------------------------
# ORIGINAL SOURCES
# ---------------------------------------------------------------------

# Cross-genre "all time" rankings. Several independent surfaces are
# combined since rankings can change and one family alone can be
# unstable.
RANKING_SEED_URLS = [
    f"{BASE_URL}/ranking/novel/all_time/popular_rank",
    f"{BASE_URL}/ranking/novel/all_time/collection_rank",
    f"{BASE_URL}/ranking/novel/all_time/best_sellers",
    f"{BASE_URL}/ranking/novel/all_time/engagement_rank",
    f"{BASE_URL}/ranking/novel/all_time/power_rank",
    f"{BASE_URL}/ranking/novel/all_time/fandom_rank",
]


# WebNovel's own top-level genre categories.
#
# These remain in place as keyword searches because they are already
# part of the original discovery strategy.
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


# ---------------------------------------------------------------------
# ADDITIONAL WEBNOVEL SOURCES
# ---------------------------------------------------------------------
#
# WebNovel currently exposes additional novel discovery surfaces
# outside the ranking URLs above:
#
#   /category
#       Category browser with Popular / Recommended / Most Collections /
#       Rating / Time Updated sorting.
#
#   /stories/novel
#       Dedicated novel catalog with genre, lead, status and sorting
#       controls.
#
#   /
#       WebNovel homepage, which exposes additional Power Ranking and
#       Collection Ranking sections.
#
# We deliberately add these sources rather than replacing the existing
# ranking/search sources.
#
# See:
#   https://en.webnovel.com/category
#   https://www.webnovel.com/stories/novel
#   https://www.webnovel.com/
#
ADDITIONAL_SEED_URLS = [
    f"{BASE_URL}/category",
    f"{BASE_URL}/stories/novel",
]


# How many pages to crawl from each additional source.
#
# Category pages are especially useful because they expose books that
# may not appear in the global ranking pages.
MAX_ADDITIONAL_PAGES_PER_SEED = 40

# Category links discovered from /category are themselves added as
# additional sources. This gives each top-level genre its own crawl.
MAX_DISCOVERED_CATEGORY_SEEDS = 100


TARGET = 250
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

# This is now a discovery diagnostic rather than a hard stop.
# We intentionally allow the script to continue if fewer URLs are
# found, because the additional category/catalog sources can still
# produce useful results.
MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.35
MAX_PAGES_PER_SEED = 40


# No single genre may take up more than this share of the final list.
MAX_GENRE_SHARE = 0.15
MIN_GENRE_CAP = 8


# WebNovel review-statistics floor. Only enforced when the statistics
# were actually retrieved.
MIN_TOTAL_SCORE = 3.0
MIN_TOTAL_REVIEW_NUM = 5


# Tags that indicate explicit sexual content on WebNovel. This is a
# hard filter: any match excludes the novel regardless of popularity
# or genre.
# Shared with the Upload Novel feature. Edit the list in
# scraper/content_policy.py, not here, so the two never drift apart.
EXCLUDED_TAGS = EXCLUDED_TAGS_BY_SOURCE["webnovel"]


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
# URL DISCOVERY
# ---------------------------------------------------------------------

def canonical_book_url(url: str) -> str | None:
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)

    if parsed.netloc.lower() not in {
        "www.webnovel.com",
        "webnovel.com",
        "en.webnovel.com",
    }:
        return None

    match = re.search(r"/book/[^?#]+", parsed.path)
    if not match:
        return None

    path = match.group(0).rstrip("/")

    # WebNovel book URLs normally look like:
    #   /book/title_123456
    #
    # Keep the existing validation logic, but accept numeric book IDs
    # as well.
    if not (
        re.search(r"_\d+$", path)
        or re.search(r"/book/\d+$", path)
    ):
        return None

    return urlunparse((
        "https",
        "www.webnovel.com",
        path,
        "",
        "",
        "",
    ))


def canonical_listing_url(url: str) -> str | None:
    """
    Normalize listing URLs so that the same page isn't crawled through
    different hostnames or harmless fragments.
    """
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)

    if parsed.netloc.lower() not in {
        "www.webnovel.com",
        "webnovel.com",
        "en.webnovel.com",
    }:
        return None

    if not (
        parsed.path.startswith("/ranking/")
        or parsed.path.startswith("/search")
        or parsed.path.startswith("/category")
        or parsed.path.startswith("/stories/novel")
    ):
        return None

    return urlunparse((
        "https",
        "www.webnovel.com",
        parsed.path,
        "",
        parsed.query,
        "",
    ))


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(
        url,
        timeout=30,
        allow_redirects=True,
    )
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


def is_same_listing_family(
    seed_url: str,
    candidate_url: str,
) -> bool:
    seed = urlparse(seed_url)
    candidate = urlparse(candidate_url)

    if candidate.netloc.lower() not in {
        "www.webnovel.com",
        "webnovel.com",
        "en.webnovel.com",
    }:
        return False

    # Existing ranking family.
    if seed.path.startswith("/ranking/"):
        return candidate.path.startswith("/ranking/")

    # Existing search family.
    if seed.path.startswith("/search"):
        return candidate.path.startswith("/search")

    # NEW: WebNovel category browser.
    #
    # Category pagination and category filter links remain underneath
    # /category.
    if seed.path.startswith("/category"):
        return candidate.path.startswith("/category")

    # NEW: dedicated novel catalog.
    if seed.path.startswith("/stories/novel"):
        return candidate.path.startswith("/stories/novel")

    return False


def listing_next_links(
    html: str,
    page_url: str,
) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []

    for a in soup.select("a[href]"):
        text = " ".join(a.stripped_strings).strip().lower()
        href = urljoin(page_url, a["href"])

        if not is_same_listing_family(page_url, href):
            continue

        normalized = canonical_listing_url(href)
        if not normalized:
            continue

        rel = {
            str(x).lower()
            for x in (a.get("rel") or [])
        }

        if (
            "next" in rel
            or text in {
                "next",
                "next >",
                ">",
                "\u203a",
                "\u2192",
            }
            or text.isdigit()
        ):
            found.append(normalized)

    return list(dict.fromkeys(found))


def extract_category_seed_urls(
    html: str,
    page_url: str,
) -> set[str]:
    """
    Extract WebNovel's own /category/... pages.

    This is intentionally discovery-based rather than hard-coding
    WebNovel's internal numeric category IDs.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()

    for a in soup.select("a[href]"):
        href = urljoin(page_url, a["href"])
        parsed = urlparse(href)

        if parsed.netloc.lower() not in {
            "www.webnovel.com",
            "webnovel.com",
            "en.webnovel.com",
        }:
            continue

        if not parsed.path.startswith("/category"):
            continue

        normalized = canonical_listing_url(href)
        if normalized:
            found.add(normalized)

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

        normalized_seed = canonical_listing_url(url)
        if not normalized_seed:
            continue

        url = normalized_seed

        if url in seen_pages:
            continue

        seen_pages.add(url)

        try:
            html = fetch_html(session, url)
        except requests.RequestException as exc:
            print(
                "LISTING FAILED:",
                url,
                type(exc).__name__,
                exc,
            )
            continue

        pages.append(
            extract_book_urls(html, url)
        )

        for next_url in listing_next_links(html, url):
            if next_url not in seen_pages:
                queue.append(next_url)

        time.sleep(REQUEST_DELAY)

    return pages


def search_url(query: str) -> str:
    return (
        f"{BASE_URL}/search?"
        f"{urlencode({'keywords': query})}"
    )


# ---------------------------------------------------------------------
# NEW DISCOVERY SOURCES
# ---------------------------------------------------------------------

def discover_additional_category_seeds(
    session: requests.Session,
) -> list[str]:
    """
    Fetch WebNovel's category index and discover the site's actual
    category URLs.

    This avoids guessing WebNovel's internal category IDs.
    """
    category_index = f"{BASE_URL}/category"

    print("\n=== DISCOVERING WEBNOVEL CATEGORY SOURCES ===")
    print("CATEGORY INDEX:", category_index)

    try:
        html = fetch_html(session, category_index)
    except requests.RequestException as exc:
        print(
            "CATEGORY INDEX FAILED:",
            type(exc).__name__,
            exc,
        )
        return []

    category_urls = extract_category_seed_urls(
        html,
        category_index,
    )

    # Don't allow an accidental explosion in the number of sources.
    category_urls = sorted(category_urls)[
        :MAX_DISCOVERED_CATEGORY_SEEDS
    ]

    print(
        "Discovered category listing sources:",
        len(category_urls),
    )

    for url in category_urls:
        print("  CATEGORY SOURCE:", url)

    return category_urls


def discover_candidates() -> dict[str, int]:
    """
    Return:
        {book_url: number_of_listing_pages_it_appeared_on}

    Existing ranking/search sources are preserved. Additional
    WebNovel catalog/category/homepage sources are layered on top.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    popularity_hits: dict[str, int] = {}

    def record_books(books: set[str]) -> None:
        for url in books:
            popularity_hits[url] = (
                popularity_hits.get(url, 0) + 1
            )

    # -------------------------------------------------------------
    # ORIGINAL CROSS-GENRE RANKINGS
    # -------------------------------------------------------------
    print(
        "\n=== DISCOVERING CROSS-GENRE RANKING "
        "CANDIDATES ==="
    )

    for seed in RANKING_SEED_URLS:
        print("RANKING:", seed)

        for books in crawl_listing(
            session,
            seed,
            MAX_PAGES_PER_SEED,
        ):
            record_books(books)

        print(
            "Unique candidates so far:",
            len(popularity_hits),
        )

    # -------------------------------------------------------------
    # ORIGINAL PER-GENRE SEARCHES
    # -------------------------------------------------------------
    print("\n=== DISCOVERING PER-GENRE SEARCH CANDIDATES ===")

    for genre in GENRE_QUERIES:
        print("GENRE:", genre)

        for books in crawl_listing(
            session,
            search_url(genre),
            MAX_PAGES_PER_SEED,
        ):
            record_books(books)

        print(
            "Unique candidates so far:",
            len(popularity_hits),
        )

        time.sleep(REQUEST_DELAY)

    # -------------------------------------------------------------
    # NEW: WEBNOVEL CATEGORY INDEX
    # -------------------------------------------------------------
    #
    # First scrape /category itself.
    #
    # This page contains popular novels and links into WebNovel's
    # genre/category catalog.
    # -------------------------------------------------------------
    print("\n=== DISCOVERING WEBNOVEL CATEGORY CATALOG ===")

    category_index = f"{BASE_URL}/category"

    try:
        category_html = fetch_html(
            session,
            category_index,
        )

        record_books(
            extract_book_urls(
                category_html,
                category_index,
            )
        )

        print(
            "Category index candidates:",
            len(popularity_hits),
        )

    except requests.RequestException as exc:
        print(
            "CATEGORY INDEX FAILED:",
            type(exc).__name__,
            exc,
        )

    time.sleep(REQUEST_DELAY)

    # -------------------------------------------------------------
    # NEW: DISCOVER ACTUAL CATEGORY URLS
    # -------------------------------------------------------------
    category_seeds = discover_additional_category_seeds(
        session
    )

    for seed in category_seeds:
        print("CATEGORY:", seed)

        for books in crawl_listing(
            session,
            seed,
            MAX_ADDITIONAL_PAGES_PER_SEED,
        ):
            record_books(books)

        print(
            "Unique candidates so far:",
            len(popularity_hits),
        )

        time.sleep(REQUEST_DELAY)

    # -------------------------------------------------------------
    # NEW: DEDICATED NOVEL CATALOG
    # -------------------------------------------------------------
    #
    # /stories/novel is a separate catalog surface from the ranking
    # URLs. It exposes genre and sorting controls and therefore tends
    # to surface books that are not captured by the global rankings.
    # -------------------------------------------------------------
    print("\n=== DISCOVERING DEDICATED NOVEL CATALOG ===")

    novel_catalog = f"{BASE_URL}/stories/novel"

    for books in crawl_listing(
        session,
        novel_catalog,
        MAX_ADDITIONAL_PAGES_PER_SEED,
    ):
        record_books(books)

    print(
        "Unique candidates so far:",
        len(popularity_hits),
    )

    # -------------------------------------------------------------
    # NEW: WEBNOVEL HOMEPAGE RANKING SECTIONS
    # -------------------------------------------------------------
    #
    # The homepage currently exposes additional Power Ranking and
    # Collection Ranking book lists. We scrape the homepage itself
    # rather than trying to guess the underlying internal API.
    # -------------------------------------------------------------
    print("\n=== DISCOVERING HOMEPAGE RANKINGS ===")

    homepage = BASE_URL

    try:
        homepage_html = fetch_html(
            session,
            homepage,
        )

        homepage_books = extract_book_urls(
            homepage_html,
            homepage,
        )

        record_books(homepage_books)

        print(
            "Homepage book candidates:",
            len(homepage_books),
        )
        print(
            "Unique candidates so far:",
            len(popularity_hits),
        )

    except requests.RequestException as exc:
        print(
            "HOMEPAGE FAILED:",
            type(exc).__name__,
            exc,
        )

    time.sleep(REQUEST_DELAY)

    print(
        "\nTotal discovered candidates:",
        len(popularity_hits),
    )

    return popularity_hits


# ---------------------------------------------------------------------
# POPULARITY SCORING
# ---------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").lower(),
    ).strip()


def synopsis_quality_penalty(
    title: str | None,
    synopsis: str | None,
) -> tuple[float, list[str]]:
    text = f"{title or ''} {synopsis or ''}".strip()

    if not text:
        return 12.0, ["missing-synopsis"]

    penalty = 0.0
    reasons: list[str] = []

    letters = [
        char
        for char in text
        if char.isalpha()
    ]

    if letters and len(letters) > 30:
        upper_ratio = (
            sum(
                char.isupper()
                for char in letters
            )
            / len(letters)
        )

        if upper_ratio > 0.45:
            penalty += 4
            reasons.append(
                "excessive-capitalization"
            )

    words = re.findall(
        r"[A-Za-z']+",
        (synopsis or "").lower(),
    )

    if len(words) < 20:
        penalty += 4
        reasons.append(
            "very-short-synopsis"
        )

    if len(words) >= 40:
        unique_ratio = (
            len(set(words))
            / len(words)
        )

        if unique_ratio < 0.35:
            penalty += 3
            reasons.append(
                "low-lexical-variety"
            )

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
            min(
                total_review_num or 0,
                500,
            )
            / 500
            if total_review_num is not None
            else 0.35
        )

        adjusted_score = (
            confidence * total_score
            + (1 - confidence) * 3.8
        )

        score += max(
            -2.0,
            (adjusted_score - 3.0) * 4.0,
        )

        reasons.append(
            f"total_score={total_score}"
        )

    if total_review_num is not None:
        score += min(
            6.0,
            math.log10(
                total_review_num + 1
            ) * 1.5,
        )

        reasons.append(
            f"total_review_num={total_review_num}"
        )

    # Appearance across independent WebNovel discovery surfaces is
    # useful evidence of popularity. This is intentionally retained
    # from the original script.
    score += min(
        popularity_hits,
        10,
    ) * 1.5

    reasons.append(
        f"listing-hits={popularity_hits}"
    )

    penalty, penalty_reasons = (
        synopsis_quality_penalty(
            title,
            synopsis,
        )
    )

    score -= penalty

    reasons.extend(
        f"presentation:{reason}"
        for reason in penalty_reasons
    )

    return score, reasons


# ---------------------------------------------------------------------
# SCRAPE, HARD-FILTER, AND SCORE
# ---------------------------------------------------------------------

def scrape_and_score(
    popularity_hits: dict[str, int],
) -> list[Candidate]:
    candidate_urls = list(popularity_hits)

    print(
        f"\n=== SCRAPING AND CLASSIFYING "
        f"{len(candidate_urls)} CANDIDATES ==="
    )

    candidates: list[Candidate] = []

    for index, url in enumerate(
        candidate_urls,
        start=1,
    ):
        print(
            f"[{index}/{len(candidate_urls)}] {url}"
        )

        try:
            novel = scrape_webnovel(url)
        except Exception as exc:
            print(
                "FAILED:",
                type(exc).__name__,
                exc,
            )
            continue

        # ---------------------------------------------------------
        # HARD FILTER: EXPLICIT SEXUAL CONTENT
        # ---------------------------------------------------------
        novel_tags = {
            normalize_text(tag)
            for tag in novel.get("tags", [])
            if normalize_text(tag)
        }

        matched_excluded_tags = (
            novel_tags & EXCLUDED_TAGS
        )

        if matched_excluded_tags:
            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(excluded tags: "
                f"{sorted(matched_excluded_tags)})"
            )

            time.sleep(REQUEST_DELAY)
            continue

        # ---------------------------------------------------------
        # POPULARITY FLOOR
        # ---------------------------------------------------------
        total_score = novel.get(
            "total_score"
        )

        total_review_num = novel.get(
            "total_review_num"
        )

        if (
            total_score is not None
            and total_score < MIN_TOTAL_SCORE
        ):
            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(score={total_score}, "
                f"required >= {MIN_TOTAL_SCORE})"
            )

            time.sleep(REQUEST_DELAY)
            continue

        if (
            total_review_num is not None
            and total_review_num
            < MIN_TOTAL_REVIEW_NUM
        ):
            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(reviews={total_review_num}, "
                f"required >= {MIN_TOTAL_REVIEW_NUM})"
            )

            time.sleep(REQUEST_DELAY)
            continue

        popularity_score, quality_reasons = (
            score_popularity(
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                total_score=total_score,
                total_review_num=total_review_num,
                popularity_hits=popularity_hits.get(
                    url,
                    0,
                ),
            )
        )

        candidates.append(
            Candidate(
                url=url,
                story_id=novel.get("story_id"),
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                genres=novel.get(
                    "genres",
                    [],
                ),
                tags=novel.get(
                    "tags",
                    [],
                ),
                total_score=total_score,
                total_review_num=total_review_num,
                popularity_hits=popularity_hits.get(
                    url,
                    0,
                ),
                popularity_score=popularity_score,
                quality_reasons=quality_reasons,
            )
        )

        time.sleep(REQUEST_DELAY)

    return candidates


# ---------------------------------------------------------------------
# POPULARITY-FIRST, GENRE-DIVERSE SELECTION
# ---------------------------------------------------------------------

def primary_genre(
    candidate: Candidate,
) -> str:
    return (
        candidate.genres[0]
        if candidate.genres
        else "Unclassified"
    )


def select_popular_diverse(
    candidates: list[Candidate],
    target: int = TARGET,
) -> list[Candidate]:
    """
    Rank by popularity, but cap how much of the final list any single
    genre can take up.

    IMPORTANT:
    The original implementation stopped after filling the target
    during the capped pass. That is fine when the candidate pool is
    large, but this version explicitly performs a second backfill pass
    whenever genre caps prevent the target from being filled.

    Popularity remains the primary ordering signal.
    """
    cap = max(
        MIN_GENRE_CAP,
        math.ceil(
            target * MAX_GENRE_SHARE
        ),
    )

    ranked = sorted(
        candidates,
        key=lambda c: c.popularity_score,
        reverse=True,
    )

    selected: list[Candidate] = []
    overflow: list[Candidate] = []
    genre_counts: Counter[str] = Counter()

    # -------------------------------------------------------------
    # PASS 1: popularity-first subject to genre caps
    # -------------------------------------------------------------
    for candidate in ranked:
        genre = primary_genre(candidate)

        if genre_counts[genre] < cap:
            selected.append(candidate)
            genre_counts[genre] += 1
        else:
            overflow.append(candidate)

        if len(selected) >= target:
            break

    # -------------------------------------------------------------
    # PASS 2: backfill from overflow by popularity.
    #
    # This is deliberately unchanged in spirit from the original
    # selection algorithm.
    # -------------------------------------------------------------
    if len(selected) < target:
        for candidate in overflow:
            if len(selected) >= target:
                break

            selected.append(candidate)

    return selected[:target]


# ---------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------

def write_outputs(
    selected: list[Candidate],
    all_candidates: list[Candidate],
) -> None:
    urls = [
        candidate.url
        for candidate in selected
    ]

    with open(
        "popular_webnovel_urls.txt",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            urls,
            file,
            indent=2,
        )

    selected_urls = {
        candidate.url
        for candidate in selected
    }

    with open(
        "popular_webnovel_audit.csv",
        "w",
        newline="",
        encoding="utf-8",
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
            key=lambda item:
                item.popularity_score,
            reverse=True,
        ):
            writer.writerow({
                "selected":
                    candidate.url
                    in selected_urls,

                "url":
                    candidate.url,

                "story_id":
                    candidate.story_id,

                "title":
                    candidate.title,

                "popularity_score":
                    candidate.popularity_score,

                "total_score":
                    candidate.total_score,

                "total_review_num":
                    candidate.total_review_num,

                "popularity_hits":
                    candidate.popularity_hits,

                "genres":
                    json.dumps(
                        candidate.genres,
                        ensure_ascii=False,
                    ),

                "tags":
                    json.dumps(
                        candidate.tags,
                        ensure_ascii=False,
                    ),

                "quality_reasons":
                    json.dumps(
                        candidate.quality_reasons,
                        ensure_ascii=False,
                    ),

                "synopsis":
                    candidate.synopsis,
            })


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:
    popularity_hits = discover_candidates()

    if len(popularity_hits) < MIN_DISCOVERED:
        print(
            f"\nNOTE: only discovered "
            f"{len(popularity_hits)} candidate URLs "
            f"(target pool: {MIN_DISCOVERED}). "
            f"Continuing with what was found."
        )

    candidates = scrape_and_score(
        popularity_hits
    )

    print(
        "\nCandidates remaining after "
        "sexual-content and popularity filters:",
        len(candidates),
    )

    selected = select_popular_diverse(
        candidates,
        target=TARGET,
    )

    write_outputs(
        selected,
        candidates,
    )

    genre_counts = Counter(
        primary_genre(candidate)
        for candidate in selected
    )

    print(
        f"\n=== SELECTED {len(selected)} "
        f"WEBNOVEL NOVELS "
        f"(target: {TARGET}, "
        f"tolerance: +/-{TARGET_TOLERANCE}) ==="
    )

    if len(selected) < MIN_TARGET:
        print(
            "WARNING: Fewer than the minimum acceptable "
            "number of novels passed the sexual-content "
            "and popularity filters. The output is "
            "intentionally not padded with weaker "
            "candidates."
        )

    print("\nGenre spread of the selection:")

    for genre, count in genre_counts.most_common():
        print(
            f"  {genre:<20} {count}"
        )

    for rank, candidate in enumerate(
        selected,
        start=1,
    ):
        print(
            f"{rank:03d} "
            f"pop={candidate.popularity_score:6.1f} "
            f"score={candidate.total_score} "
            f"reviews={candidate.total_review_num} "
            f"genres={candidate.genres} "
            f"{candidate.title}"
        )

        print(candidate.url)

    print("\nWrote:")
    print("  popular_webnovel_urls.txt")
    print("  popular_webnovel_audit.csv")


if __name__ == "__main__":
    main()
