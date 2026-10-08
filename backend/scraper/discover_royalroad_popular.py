"""Discover popular Royal Road novels with conservative sexual-content filtering.

Follower-ranked searches (overall and per genre) build the candidate pool.
Each fiction is fetched once using Royal Road's shared transport and parser.
Warnings, normalized policy labels, and explicit disclosures in the full
untrimmed description are checked before popularity floors and ranking.

80% of seats go to the most-followed eligible novels. The remaining 20%
prefer underrepresented genres, with a popularity floor relative to the
ordinary top-N cutoff. All genre labels count, regardless of tag order.
Outputs retain the existing JSON URL list and CSV audit formats. Page
metadata cannot certify the contents of chapters an author has not flagged.
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

from scraper.royalroad import (
    BASE_URL,
    ROYAL_ROAD_GENRES,
    RoyalRoadChallengeError,
    RoyalRoadClient,
    extract_description_node,
    extract_statistics,
    fetch,
    parse_royalroad,
)
from scraper.content_policy import EXCLUDED_TAGS_BY_SOURCE, find_policy_violations


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TARGET = 500
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.4
MAX_PAGES_PER_SEED = 15

# Popularity takes most seats; diversity only draws from established novels.
DIVERSITY_SHARE = 0.20
DIVERSITY_POPULARITY_RATIO = 0.25

# Verified against the current advanced-search form. Display labels do not
# always match the parameter values (e.g. Romance and Short Story).
GENRE_SEARCH_TAGS = {
    genre: {
        "Romance": "romance_main",
        "Sci-fi": "sci_fi",
        "Short Story": "one_shot",
    }.get(genre, genre.lower())
    for genre in ROYAL_ROAD_GENRES
}


def search_seed(order: str, genre: str | None = None) -> str:
    params = [
        ("orderBy", order), ("dir", "desc"),
        ("tagsRemove", "sexuality"), ("tagsRemove", "harem"),
        ("tagsRemove", "competing_love"),
    ]
    if genre is not None:
        params.append(("tagsAdd", GENRE_SEARCH_TAGS[genre]))
    return f"{BASE_URL}/fictions/search?{urlencode(params)}"


BROAD_SEED_URLS = [search_seed("followers"), search_seed("popularity")]
GENRE_SEED_URLS = [search_seed("followers", genre) for genre in ROYAL_ROAD_GENRES]

POPULAR_SEED_URLS = BROAD_SEED_URLS + GENRE_SEED_URLS

# Tags that indicate explicit sexual content. This is a hard filter:
# any match excludes the fiction regardless of popularity or genre.
# Shared with the Upload Novel feature. Edit the list in
# scraper/content_policy.py, not here, so the two never drift apart.
EXCLUDED_TAGS = EXCLUDED_TAGS_BY_SOURCE["royalroad"]

# Missing followers cannot establish popularity and are rejected. Optional
# rating metrics enforce their floors whenever available.
MIN_FOLLOWERS = 250
MIN_RATING = 3.5
MIN_RATING_COUNT = 25


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
        f"/fiction/{int(match.group(1))}",
        "",
        "",
        "",
    ))


def fetch_html(client: RoyalRoadClient, url: str) -> str:
    return fetch(url, client=client)


def stop_if_blocked(error: Exception) -> None:
    """Stop the run on access failures rather than repeatedly hitting the site."""
    if isinstance(error, RoyalRoadChallengeError):
        raise error
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in {401, 403, 429} or status >= 500:
            raise error


def extract_fiction_urls(html: str, page_url: str) -> set[str]:
    tree = HTMLParser(html)
    urls: set[str] = set()

    for node in tree.css(".fiction-list-item h2 a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue

        fiction_url = canonical_fiction_url(urljoin(page_url, href))
        if fiction_url:
            urls.add(fiction_url)

    return urls


def extract_next_listing_urls(html: str, page_url: str) -> list[str]:
    """Follow only the next page of this listing, keeping every seed filter."""
    tree = HTMLParser(html)
    current = urlparse(page_url)
    filters = parse_qs(current.query)
    current_page = int(filters.get("page", ["1"])[0])
    for node in tree.css(".pagination a[href], a[rel='next'][href]"):
        parsed = urlparse(urljoin(page_url, node.attributes["href"]))
        if parsed.netloc.lower() not in {"www.royalroad.com", "royalroad.com"}:
            continue
        if parsed.path != current.path:
            continue
        params = parse_qs(parsed.query)
        page = params.get("page", [""])[0]
        if not page.isdigit() or int(page) != current_page + 1:
            continue
        if any(key != "page" and key in filters and sorted(values) != sorted(filters[key])
               for key, values in params.items()):
            continue
        merged = {**filters, **params}
        return [urlunparse(current._replace(query=urlencode(merged, doseq=True), fragment=""))]
    return []


def crawl_listing(
    client: RoyalRoadClient,
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
            stop_if_blocked(exc)
            print("LISTING FAILED:", url, type(exc).__name__, exc)
            time.sleep(REQUEST_DELAY)
            continue

        fictions = extract_fiction_urls(html, url)
        if not fictions:
            break
        pages.append(fictions)

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

    with RoyalRoadClient() as client:
        print("\n=== DISCOVERING POPULAR ROYAL ROAD FICTIONS ===")

        for seed in POPULAR_SEED_URLS:
            print("SEED:", seed)

            seed_fictions = set().union(*crawl_listing(client, seed, MAX_PAGES_PER_SEED))
            for url in sorted(seed_fictions):
                popularity_hits[url] = popularity_hits.get(url, 0) + 1

            print("Unique candidates so far:", len(popularity_hits))

    print("Total discovered candidates:", len(popularity_hits))
    return popularity_hits


# ---------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------

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
    stats = tree.css_first(".fiction-stats")
    page_text = (stats or tree).text(separator=" ", strip=True)

    for label in labels:
        patterns = [
            rf"\b{re.escape(label)}\s*[:\-]?\s*(\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KkMm]?)",
            rf"(\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KkMm]?)\s+{re.escape(label)}\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, flags=re.IGNORECASE)
            if match:
                count = parse_count(match.group(1))
                if count is not None:
                    return count

    return None


def extract_rating_metrics(html: str) -> tuple[float | None, int | None]:
    count, score = extract_statistics(HTMLParser(html))
    if count is not None or score is not None:
        return score, count

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
        score += math.log10(followers + 1) * 10.0
        reasons.append(f"followers={followers}")

    if rating is not None:
        count = rating_count or 0
        confidence = count / (count + 100)
        adjusted_rating = confidence * rating + (1 - confidence) * 3.8
        score += max(-2.0, adjusted_rating - 3.8)
        reasons.append(f"rating={rating}")

    if rating_count is not None:
        score += min(4.0, math.log10(rating_count + 1)) * 0.25
        reasons.append(f"rating_count={rating_count}")

    score += min(popularity_hits, 10) * 0.05
    reasons.append(f"listing-hits={popularity_hits}")

    _, penalty_reasons = synopsis_quality_penalty(title, synopsis)
    reasons.extend(f"presentation:{reason}" for reason in penalty_reasons)

    return score, reasons


# ---------------------------------------------------------------------
# Scrape, hard-filter, and score
# ---------------------------------------------------------------------

# Check untrimmed story descriptions, including disclosures after a separator
# that synopsis cleanup deliberately drops. Do not inspect reviews or ads.
SEXUAL_DISCLOSURE = re.compile(
    r"\b(?:sex(?:ual)? (?:content|scenes?|themes|acts)|sexually explicit|"
    r"explicit sexual content|smut(?:ty)?|erotica?|nsfw|porn(?:ography|ographic)?|"
    r"hentai|ecchi|harem|bdsm|incest|sexual (?:assault|violence)|rape|"
    r"(?:spicy|steamy|erotic) romance)\b",
    re.IGNORECASE,
)
NEGATED_DISCLOSURE = re.compile(
    r"\b(?:no|not|without|free of|does not contain|doesn't contain|will not contain)"
    r"\s+(?:(?:any|explicit|sexual|graphic)\s+)*$",
    re.IGNORECASE,
)


def sexual_content_reasons(html: str, novel: dict) -> list[str]:
    reasons = find_policy_violations("royalroad", novel)
    tree = HTMLParser(html)
    description = extract_description_node(tree)
    texts = [novel.get("title") or ""]
    if description is not None:
        texts.append(description.text(separator=" ", strip=True))
    for text in texts:
        for match in SEXUAL_DISCLOSURE.finditer(text):
            prefix = text[max(0, match.start() - 70):match.start()]
            suffix = text[match.end():match.end() + 6]
            if NEGATED_DISCLOSURE.search(prefix) or re.match(r"[- ]free\b", suffix, re.I):
                continue
            label = f"description:{match.group(0).casefold()}"
            if label not in reasons:
                reasons.append(label)
    return reasons


def scrape_and_score(popularity_hits: dict[str, int]) -> list[Candidate]:
    # Defensively combine slug aliases even when called with an external pool.
    unique_hits: dict[str, int] = {}
    for url, hits in popularity_hits.items():
        canonical = canonical_fiction_url(url)
        if canonical:
            unique_hits[canonical] = max(hits, unique_hits.get(canonical, 0))
    candidates: list[Candidate] = []
    consecutive_server_errors = 0
    print(f"\n=== SCRAPING AND CLASSIFYING {len(unique_hits)} CANDIDATES ===")

    with RoyalRoadClient() as client:
        for index, (url, hits) in enumerate(unique_hits.items(), start=1):
            print(f"[{index}/{len(unique_hits)}] {url}")
            try:
                html = fetch_html(client, url)
                consecutive_server_errors = 0
                novel = parse_royalroad(html, url)
                violations = sexual_content_reasons(html, novel)
                if violations:
                    print(f"SKIPPED: {novel['title']!r} (content policy: {violations})")
                    continue

                followers, rating, rating_count = extract_fiction_metrics(html)
                if followers is None or followers < MIN_FOLLOWERS:
                    print(f"SKIPPED: {novel['title']!r} (followers={followers})")
                    continue
                if rating is not None and rating < MIN_RATING:
                    print(f"SKIPPED: {novel['title']!r} (rating={rating})")
                    continue
                if rating_count is not None and rating_count < MIN_RATING_COUNT:
                    print(f"SKIPPED: {novel['title']!r} (rating_count={rating_count})")
                    continue

                score, reasons = score_popularity(
                    title=novel.get("title"), synopsis=novel.get("synopsis"),
                    followers=followers, rating=rating, rating_count=rating_count,
                    popularity_hits=hits,
                )
                candidates.append(Candidate(
                    url=url, fiction_id=novel["fiction_id"], title=novel["title"],
                    synopsis=novel.get("synopsis"), genres=novel["genres"],
                    tags=novel["tags"], followers=followers, rating=rating,
                    rating_count=rating_count, popularity_hits=hits,
                    popularity_score=score, quality_reasons=reasons,
                ))
            except Exception as exc:
                if isinstance(exc, httpx.HTTPStatusError) and 500 <= exc.response.status_code < 600:
                    # An individual broken novel must not discard the batch.
                    # Repeated failures indicate a source outage; stop normally.
                    consecutive_server_errors += 1
                    if consecutive_server_errors >= 3:
                        stop_if_blocked(exc)
                else:
                    consecutive_server_errors = 0
                    stop_if_blocked(exc)
                print("FAILED:", type(exc).__name__, exc)
            finally:
                time.sleep(REQUEST_DELAY)
    return candidates


# ---------------------------------------------------------------------
# Popularity-first, genre-diverse selection
# ---------------------------------------------------------------------


def popularity_rank(candidate: Candidate) -> tuple:
    # Followers dominate; quality and listing frequency only break ties.
    return (candidate.followers or 0, candidate.popularity_score,
            candidate.rating_count or 0, -(candidate.fiction_id or 0))


def candidate_genres(candidate: Candidate) -> set[str]:
    return set(candidate.genres)


def select_popular_diverse(
    candidates: list[Candidate], target: int = TARGET,
) -> list[Candidate]:
    """Keep a popular core and use a bounded share of seats for genre coverage."""
    if target <= 0:
        return []
    ranked = sorted(candidates, key=popularity_rank, reverse=True)
    unique: dict[str, Candidate] = {}
    for candidate in ranked:
        key = str(candidate.fiction_id) if candidate.fiction_id is not None else (
            canonical_fiction_url(candidate.url) or candidate.url
        )
        unique.setdefault(key, candidate)
    ranked = list(unique.values())
    if len(ranked) <= target:
        return ranked

    diversity_seats = min(target - 1, math.floor(target * DIVERSITY_SHARE))
    selected = ranked[:target - diversity_seats]
    selected_urls = {c.url for c in selected}
    counts = Counter(genre for c in selected for genre in candidate_genres(c))
    cutoff = max(MIN_FOLLOWERS, (ranked[target - 1].followers or 0)
                 * DIVERSITY_POPULARITY_RATIO)
    pools: dict[str, list[Candidate]] = {}
    for candidate in ranked[len(selected):]:
        if (candidate.followers or 0) < cutoff:
            continue
        for genre in sorted(candidate_genres(candidate)):
            pools.setdefault(genre, []).append(candidate)

    while len(selected) < target:
        options = []
        for genre, pool in pools.items():
            while pool and pool[0].url in selected_urls:
                pool.pop(0)
            if pool:
                options.append((genre, pool[0]))
        if not options:
            break
        _, candidate = min(options, key=lambda item: (
            counts[item[0]], tuple(-value for value in popularity_rank(item[1])), item[0],
        ))
        selected.append(candidate)
        selected_urls.add(candidate.url)
        counts.update(candidate_genres(candidate))

    for candidate in ranked:
        if len(selected) >= target:
            break
        if candidate.url not in selected_urls:
            selected.append(candidate)
            selected_urls.add(candidate.url)
    return sorted(selected, key=popularity_rank, reverse=True)


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
            key=popularity_rank,
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

    if not selected:
        raise RuntimeError("No eligible Royal Road novels found; existing outputs were preserved.")
    write_outputs(selected, candidates)

    genre_counts = Counter(genre for c in selected for genre in candidate_genres(c))

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

    print("\nGenre coverage (novels can count in multiple genres):")
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
