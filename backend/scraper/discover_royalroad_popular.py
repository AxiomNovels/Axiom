"""
Discover ~250 of the most popular Royal Road fictions, spread across a
variety of genres, with explicit sexual content hard-filtered out.

This replaces the older philosophy/psychology-focused discovery script.
The selection logic now has three priorities, in this order:

    1. Hard filter: explicit sexual content is excluded outright.
    2. Popularity: followers, rating, and rating count.
    3. Genre diversity: no single genre is allowed to dominate the
       final list, so the output spans Fantasy, Sci-fi, Romance,
       Mystery, Horror, Action, Comedy, Drama, and so on.

Method
------
1. Crawl several cross-genre Royal Road listing pages (Best Rated,
   Trending, Active Popular, Popular This Week) as well as each of
   Royal Road's official genres via the `?genre=` filter on the
   Best Rated / Trending pages, so the candidate pool already spans
   many genres rather than being dominated by whatever is broadly
   trending (on Royal Road that tends to be LitRPG/progression
   fantasy).
2. Deduplicate all discovered fiction URLs.
3. Scrape every candidate with scraper.royalroad.scrape_royalroad().
4. Hard-exclude any fiction whose tags indicate explicit sexual
   content (see EXCLUDED_TAGS below).
5. Require a minimum popularity floor (followers / rating / rating
   count) so obscure or abandoned fictions don't dilute the pool.
6. Rank the remaining candidates by a popularity score, then select
   up to TARGET fictions using a per-genre cap so that popularity
   dominates the ordering while no single genre can fill the whole
   list. If the cap leaves seats unfilled, they are backfilled by
   raw popularity regardless of genre, so the target count is still
   reached.

Banned-tag research
--------------------
Royal Road's tag/content-warning vocabulary was confirmed against
Royal Road's own knowledge base and tag-description threads (the
"Sexual Content" content warning; the former "Harem" tag, which was
split into "Multiple Love Interests" / "Competing Love Interest" /
"Royal Harem" in late 2025; and the newer "Smut" tag). Only tags that
signal explicit sexual content are banned -- unrelated content
warnings such as Gore or Profanity are left alone, since the request
here is specifically to filter sexual content, not violence or
language.

Output
------
popular_royalroad_urls.txt
popular_royalroad_audit.csv
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

from scraper.royalroad import (
    BASE_URL,
    HEADERS,
    ROYAL_ROAD_GENRES,
    scrape_royalroad,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TARGET = 250
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.4
MAX_PAGES_PER_SEED = 15

# No single genre may take up more than this share of the final list.
MAX_GENRE_SHARE = 0.15
MIN_GENRE_CAP = 8

# Cross-genre listings. These surface whatever is broadly popular right
# now, regardless of genre.
BROAD_SEED_URLS = [
    f"{BASE_URL}/fictions/best-rated",
    f"{BASE_URL}/fictions/trending",
    f"{BASE_URL}/fictions/active-popular",
    f"{BASE_URL}/fictions/weekly-popular",
]

# Genre-scoped listings. Royal Road's Best Rated / Trending pages accept
# a `?genre=<slug>` filter (confirmed via Royal Road's own "Trending is
# currently limited to 50 fictions per genre" documentation), so every
# official genre gets its own popularity-ranked seed instead of relying
# on whatever genre happens to dominate the unfiltered lists.
def _genre_slug(genre: str) -> str:
    return genre.lower().replace(" ", "-")


GENRE_SEED_URLS = [
    f"{BASE_URL}/fictions/{listing}?genre={_genre_slug(genre)}"
    for listing in ("best-rated", "trending")
    for genre in ROYAL_ROAD_GENRES
]

POPULAR_SEED_URLS = BROAD_SEED_URLS + GENRE_SEED_URLS

# Tags that indicate explicit sexual content. This is a hard filter:
# any match excludes the fiction regardless of popularity or genre.
EXCLUDED_TAGS = {
    "sexual content",
    "harem",
    "multiple love interests",
    "competing love interest",
    "competing love interests",
    "royal harem",
    "multiple lovers",
    "reverse harem",
    "smut",
    "erotica",
    "erotic",
}

# Hard popularity floor. Only enforced when the metric is successfully
# extracted -- a missing metric is recorded in the audit rather than
# treated as a failure.
MIN_FOLLOWERS = 50
MIN_RATING = 3.0
MIN_RATING_COUNT = 10


@dataclass
class Candidate:
    url: str
    fiction_id: int | None
    title: str | None
    synopsis: str | None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    followers: int | None = None
    rating: float | None = None
    rating_count: int | None = None

    popularity_hits: int = 0
    popularity_score: float = 0.0

    quality_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# URL discovery
# ---------------------------------------------------------------------

def canonical_fiction_url(url: str) -> str | None:
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)

    if parsed.netloc.lower() not in {"www.royalroad.com", "royalroad.com"}:
        return None

    match = re.match(
        r"^/fiction/(\d+)(?:/[^/?#]+)?/?$",
        parsed.path,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return urlunparse((
        "https",
        "www.royalroad.com",
        parsed.path.rstrip("/"),
        "",
        "",
        "",
    ))


def fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url, follow_redirects=True)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        raise ValueError(f"Expected HTML, got: {content_type}")

    return response.text


def extract_fiction_urls(html: str, page_url: str) -> set[str]:
    tree = HTMLParser(html)
    urls: set[str] = set()

    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue

        fiction_url = canonical_fiction_url(urljoin(page_url, href))
        if fiction_url:
            urls.add(fiction_url)

    return urls


def extract_next_listing_urls(html: str, page_url: str) -> list[str]:
    """
    Follow explicit pagination links rather than assuming one fixed
    Royal Road pagination format. The genre filter (if present in the
    seed URL's query string) is preserved automatically because it is
    only the page number that changes on Royal Road's own "next" links.
    """
    tree = HTMLParser(html)
    current = urlparse(page_url)
    results: list[str] = []

    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)

        if parsed.netloc.lower() not in {"www.royalroad.com", "royalroad.com"}:
            continue

        if parsed.path.startswith("/fiction/"):
            continue

        if not (
            parsed.path.startswith("/fictions")
            or parsed.path.startswith("/search")
        ):
            continue

        if (
            current.path.startswith("/search")
            and not parsed.path.startswith("/search")
        ):
            continue

        text = re.sub(
            r"\s+", " ", node.text(separator=" ", strip=True)
        ).strip().lower()

        rel = (node.attributes.get("rel") or "").lower()

        if (
            "next" in rel
            or text in {"next", ">", "\u203a", "\u2192"}
            or text.isdigit()
            or "page=" in parsed.query.lower()
        ):
            results.append(absolute)

    return list(dict.fromkeys(results))


def crawl_listing(
    client: httpx.Client,
    seed_url: str,
    page_limit: int,
) -> list[set[str]]:
    queue = deque([seed_url])
    seen: set[str] = set()
    pages: list[set[str]] = []

    while queue and len(pages) < page_limit:
        url = queue.popleft()

        if url in seen:
            continue
        seen.add(url)

        try:
            html = fetch_html(client, url)
        except Exception as exc:
            print("LISTING FAILED:", url, type(exc).__name__, exc)
            continue

        pages.append(extract_fiction_urls(html, url))

        for next_url in extract_next_listing_urls(html, url):
            if next_url not in seen:
                queue.append(next_url)

        time.sleep(REQUEST_DELAY)

    return pages


def discover_candidates() -> dict[str, int]:
    """
    Return {url: number_of_listing_pages_it_appeared_on}.
    """
    popularity_hits: dict[str, int] = {}

    with httpx.Client(headers=HEADERS, timeout=30) as client:
        print("\n=== DISCOVERING POPULAR ROYAL ROAD FICTIONS ===")

        for seed in POPULAR_SEED_URLS:
            print("SEED:", seed)

            for fictions in crawl_listing(client, seed, MAX_PAGES_PER_SEED):
                for url in fictions:
                    popularity_hits[url] = popularity_hits.get(url, 0) + 1

            print("Unique candidates so far:", len(popularity_hits))

    print("Total discovered candidates:", len(popularity_hits))
    return popularity_hits


# ---------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def parse_count(value: str | int | float | None) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().lower().replace(",", "")

    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([km])?", text)
    if not match:
        return None

    number = float(match.group(1))
    suffix = match.group(2)

    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000

    return int(number)


def extract_metric_after_label(
    html: str,
    labels: tuple[str, ...],
) -> int | None:
    tree = HTMLParser(html)
    page_text = tree.text(separator=" ", strip=True)

    for label in labels:
        patterns = [
            rf"(\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KkMm]?)\s+{re.escape(label)}\b",
            rf"\b{re.escape(label)}\s*[:\-]?\s*(\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KkMm]?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                count = parse_count(match.group(1))
                if count is not None:
                    return count

    return None


def extract_rating_metrics(html: str) -> tuple[float | None, int | None]:
    patterns = [
        r"(\d(?:\.\d+)?)\s*/\s*5\s*(?:from\s*)?(\d[\d,]*)\s*ratings?",
        r"(\d(?:\.\d+)?)\s+stars?\s+from\s+(\d[\d,]*)",
    ]

    text = HTMLParser(html).text(separator=" ", strip=True)

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1)), parse_count(match.group(2))

    rating_match = re.search(
        r'["\'](?:rating|averageRating)["\']\s*:\s*["\']?(\d(?:\.\d+)?)',
        html,
        flags=re.IGNORECASE,
    )
    count_match = re.search(
        r'["\'](?:ratingCount|ratings)["\']\s*:\s*["\']?(\d+)',
        html,
        flags=re.IGNORECASE,
    )

    rating = float(rating_match.group(1)) if rating_match else None
    count = parse_count(count_match.group(1)) if count_match else None

    return rating, count


def extract_fiction_metrics(
    html: str,
) -> tuple[int | None, float | None, int | None]:
    followers = extract_metric_after_label(html, ("followers", "follows", "follow"))
    rating, rating_count = extract_rating_metrics(html)
    return followers, rating, rating_count


# ---------------------------------------------------------------------
# Popularity scoring (no more relevance scoring)
# ---------------------------------------------------------------------

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

    if re.search(r"([!?])\1{2,}", text):
        penalty += 2
        reasons.append("excessive-punctuation")

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
    followers: int | None,
    rating: float | None,
    rating_count: int | None,
    popularity_hits: int,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if followers is not None:
        score += min(10.0, math.log10(followers + 1) * 2.0)
        reasons.append(f"followers={followers}")

    if rating is not None:
        confidence = (
            min(rating_count or 0, 500) / 500
            if rating_count is not None
            else 0.35
        )
        adjusted_rating = confidence * rating + (1 - confidence) * 3.8
        score += max(-2.0, (adjusted_rating - 3.0) * 4.0)
        reasons.append(f"rating={rating}")

    if rating_count is not None:
        score += min(4.0, math.log10(rating_count + 1))
        reasons.append(f"rating_count={rating_count}")

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

    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for index, url in enumerate(candidate_urls, start=1):
            print(f"[{index}/{len(candidate_urls)}] {url}")

            try:
                novel = scrape_royalroad(url)
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

            try:
                html = fetch_html(client, url)
                followers, rating, rating_count = extract_fiction_metrics(html)
            except Exception as exc:
                print("METADATA FAILED:", type(exc).__name__, exc)
                followers, rating, rating_count = None, None, None

            if followers is not None and followers < MIN_FOLLOWERS:
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(followers={followers}, required >= {MIN_FOLLOWERS})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            if rating is not None and rating < MIN_RATING:
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(rating={rating}, required >= {MIN_RATING})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            if rating_count is not None and rating_count < MIN_RATING_COUNT:
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(rating_count={rating_count}, required >= {MIN_RATING_COUNT})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            popularity_score, quality_reasons = score_popularity(
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                followers=followers,
                rating=rating,
                rating_count=rating_count,
                popularity_hits=popularity_hits.get(url, 0),
            )

            candidates.append(
                Candidate(
                    url=url,
                    fiction_id=novel.get("fiction_id"),
                    title=novel.get("title"),
                    synopsis=novel.get("synopsis"),
                    genres=novel.get("genres", []),
                    tags=novel.get("tags", []),
                    followers=followers,
                    rating=rating,
                    rating_count=rating_count,
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
    genre can take up. If the cap leaves seats unfilled -- because
    there simply aren't enough qualifying fictions in other genres --
    the remaining seats are backfilled by raw popularity so the target
    count is still reached. This keeps popularity as the dominant
    factor while still guaranteeing genre variety whenever the pool
    supports it.
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

    with open("popular_royalroad_urls.txt", "w", encoding="utf-8") as file:
        json.dump(urls, file, indent=2)

    selected_urls = {candidate.url for candidate in selected}

    with open(
        "popular_royalroad_audit.csv", "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "selected",
                "url",
                "fiction_id",
                "title",
                "popularity_score",
                "followers",
                "rating",
                "rating_count",
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
                "fiction_id": candidate.fiction_id,
                "title": candidate.title,
                "popularity_score": candidate.popularity_score,
                "followers": candidate.followers,
                "rating": candidate.rating,
                "rating_count": candidate.rating_count,
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
        f"\n=== SELECTED {len(selected)} ROYAL ROAD FICTIONS "
        f"(target: {TARGET}, tolerance: +/-{TARGET_TOLERANCE}) ==="
    )

    if len(selected) < MIN_TARGET:
        print(
            "WARNING: Fewer than the minimum acceptable number of fictions "
            "passed the sexual-content and popularity filters. The output "
            "is intentionally not padded with weaker candidates."
        )

    print("\nGenre spread of the selection:")
    for genre, count in genre_counts.most_common():
        print(f"  {genre:<20} {count}")

    for rank, candidate in enumerate(selected, start=1):
        print(
            f"{rank:03d} pop={candidate.popularity_score:6.1f} "
            f"followers={candidate.followers} rating={candidate.rating} "
            f"genres={candidate.genres} {candidate.title}"
        )
        print(candidate.url)

    print("\nWrote:")
    print("  popular_royalroad_urls.txt")
    print("  popular_royalroad_audit.csv")


if __name__ == "__main__":
    main()