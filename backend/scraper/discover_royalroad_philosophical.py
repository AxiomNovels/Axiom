"""
Discover popular philosophical / psychological Royal Road fictions.

Uses scraper.royalroad.scrape_royalroad() as the story-level parser.

Outputs
-------
philosophical_royalroad_urls.txt
philosophical_royalroad_audit.csv
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

from scraper.royalroad import (
    BASE_URL,
    HEADERS,
    scrape_royalroad,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TARGET = 100
MIN_TARGET = 50
MIN_DISCOVERED = 500

REQUEST_DELAY = 0.5
MAX_PAGES_PER_SEED = 40
MAX_SEARCH_PAGES = 15

# Popularity-first discovery surfaces. Multiple lists reduce dependence on
# one ranking and reward fictions that remain visible across surfaces.
POPULAR_SEED_URLS = [
    # f"{BASE_URL}/fictions/weekly-popular",
    f"{BASE_URL}/fictions/best-rated",
    f"{BASE_URL}/fictions/trending",
    f"{BASE_URL}/fictions/active-popular",
]

SEARCH_QUERIES = [
    "philosophy",
    "philosophical",
    "existential",
    "existentialism",
    "meaning of life",
    "human nature",
    "morality",
    "ethics",
    "free will",
    "identity",
    "consciousness",
    "psychology",
    "psychological",
    "psychological thriller",
    "mental health",
    "trauma",
    "sanity",
    "mind games",
    "self discovery",
    "introspection",
]

# Strict exclusion requested for all source pipelines.
EXCLUDED_TAGS = {
    "harem",
    "smut",
}

# Hard popularity floor. Followers are the closest Royal Road equivalent to
# the collection requirement used for WebNovel.
MIN_FOLLOWERS = 80

# Only enforce these when the value is successfully extracted.
MIN_RATING = 3.0
MIN_RATING_COUNT = 20

MIN_RELEVANCE_SCORE = 10.0


@dataclass
class Candidate:
    url: str
    fiction_id: int | None
    title: str | None
    synopsis: str | None
    tags: list[str]

    followers: int | None
    rating: float | None
    rating_count: int | None

    popularity_hits: int
    search_hits: int

    relevance_score: float
    quality_score: float
    combined_score: float

    reasons: list[str]
    quality_reasons: list[str]


# ---------------------------------------------------------------------
# URL discovery
# ---------------------------------------------------------------------

def canonical_fiction_url(url: str) -> str | None:
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)

    if parsed.netloc.lower() not in {
        "www.royalroad.com",
        "royalroad.com",
    }:
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
        raise ValueError(
            f"Expected HTML, got: {content_type}"
        )

    return response.text


def extract_fiction_urls(html: str, page_url: str) -> set[str]:
    tree = HTMLParser(html)
    urls: set[str] = set()

    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue

        fiction_url = canonical_fiction_url(
            urljoin(page_url, href)
        )

        if fiction_url:
            urls.add(fiction_url)

    return urls


def extract_next_listing_urls(
    html: str,
    page_url: str,
) -> list[str]:
    """
    Follow explicit pagination/search links instead of assuming one fixed
    Royal Road pagination format.
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

        if parsed.netloc.lower() not in {
            "www.royalroad.com",
            "royalroad.com",
        }:
            continue

        if parsed.path.startswith("/fiction/"):
            continue

        if not (
            parsed.path.startswith("/fictions")
            or parsed.path.startswith("/search")
        ):
            continue

        # Do not let a search crawl wander into unrelated browsing routes.
        if (
            current.path.startswith("/search")
            and not parsed.path.startswith("/search")
        ):
            continue

        text = re.sub(
            r"\s+",
            " ",
            node.text(separator=" ", strip=True),
        ).strip().lower()

        rel = (node.attributes.get("rel") or "").lower()

        if (
            "next" in rel
            or text in {"next", ">", "›", "→"}
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
            print(
                "LISTING FAILED:",
                url,
                type(exc).__name__,
                exc,
            )
            continue

        pages.append(
            extract_fiction_urls(html, url)
        )

        for next_url in extract_next_listing_urls(
            html,
            url,
        ):
            if next_url not in seen:
                queue.append(next_url)

        time.sleep(REQUEST_DELAY)

    return pages


def royalroad_search_url(query: str) -> str:
    # Search routes can vary, so this remains easy to modify in one place.
    from urllib.parse import quote
    return (
        f"{BASE_URL}/fictions/search"
        f"?title={quote(query, safe='')}"
    )


def discover_candidates() -> tuple[dict[str, int], dict[str, int]]:
    popularity_hits: dict[str, int] = {}
    search_hits: dict[str, int] = {}

    with httpx.Client(
        headers=HEADERS,
        timeout=30,
    ) as client:

        print("\n=== DISCOVERING POPULAR ROYAL ROAD FICTIONS ===")

        for seed in POPULAR_SEED_URLS:
            print("POPULAR SEED:", seed)

            for fictions in crawl_listing(
                client,
                seed,
                MAX_PAGES_PER_SEED,
            ):
                for url in fictions:
                    popularity_hits[url] = (
                        popularity_hits.get(url, 0) + 1
                    )

            print(
                "Unique popularity candidates:",
                len(popularity_hits),
            )

        print("\n=== DISCOVERING CONCEPT CANDIDATES ===")

        for query in SEARCH_QUERIES:
            print("SEARCH:", query)

            for fictions in crawl_listing(
                client,
                royalroad_search_url(query),
                MAX_SEARCH_PAGES,
            ):
                for url in fictions:
                    search_hits[url] = (
                        search_hits.get(url, 0) + 1
                    )

            time.sleep(REQUEST_DELAY)

    print("Popularity candidates:", len(popularity_hits))
    print("Concept-search candidates:", len(search_hits))

    return popularity_hits, search_hits


# ---------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").lower(),
    ).strip()


def parse_count(value: str | int | float | None) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().lower().replace(",", "")

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*([km])?",
        text,
    )

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

    # Text-node approach works across small markup changes.
    page_text = tree.text(
        separator=" ",
        strip=True,
    )

    for label in labels:
        patterns = [
            rf"(\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KkMm]?)\s+{re.escape(label)}\b",
            rf"\b{re.escape(label)}\s*[:\-]?\s*(\d+(?:,\d{{3}})*(?:\.\d+)?\s*[KkMm]?)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                page_text,
                flags=re.IGNORECASE,
            )

            if match:
                count = parse_count(match.group(1))
                if count is not None:
                    return count

    return None


def extract_rating_metrics(
    html: str,
) -> tuple[float | None, int | None]:
    """
    Best-effort extraction of average rating and rating count.

    Avoid treating unrelated values such as chapter counts as ratings.
    """
    patterns = [
        r"(\d(?:\.\d+)?)\s*/\s*5\s*(?:from\s*)?(\d[\d,]*)\s*ratings?",
        r"(\d(?:\.\d+)?)\s+stars?\s+from\s+(\d[\d,]*)",
    ]

    text = HTMLParser(html).text(
        separator=" ",
        strip=True,
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            rating = float(match.group(1))
            count = parse_count(match.group(2))
            return rating, count

    # Embedded metadata fallback.
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

    rating = (
        float(rating_match.group(1))
        if rating_match
        else None
    )

    count = (
        parse_count(count_match.group(1))
        if count_match
        else None
    )

    return rating, count


def extract_fiction_metrics(
    html: str,
) -> tuple[int | None, float | None, int | None]:
    followers = extract_metric_after_label(
        html,
        (
            "followers",
            "follows",
            "follow",
        ),
    )

    rating, rating_count = extract_rating_metrics(html)

    return followers, rating, rating_count


# ---------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------

PHILOSOPHY_PATTERNS = {
    "philosophy": 8,
    "philosophical": 8,
    "existential": 8,
    "existentialism": 10,
    "meaning of life": 8,
    "purpose of life": 8,
    "human nature": 7,
    "free will": 7,
    "determinism": 8,
    "morality": 6,
    "ethical": 6,
    "ethics": 6,
    "moral dilemma": 8,
    "identity": 4,
    "sense of self": 7,
    "consciousness": 7,
    "nature of reality": 8,
    "nihilism": 9,
    "absurdism": 9,
    "stoicism": 8,
    "mortality": 5,
    "existence": 5,
}

PSYCHOLOGY_PATTERNS = {
    "psychology": 8,
    "psychological": 7,
    "psychologist": 7,
    "psychiatrist": 7,
    "therapy": 6,
    "therapist": 6,
    "mental illness": 7,
    "mental health": 7,
    "personality disorder": 9,
    "depression": 6,
    "ptsd": 8,
    "trauma": 5,
    "psychosis": 8,
    "schizophrenia": 9,
    "dissociation": 9,
    "split personality": 9,
    "identity crisis": 8,
    "unreliable narrator": 8,
    "subconscious": 8,
    "mind games": 6,
    "human behavior": 7,
    "cognitive": 7,
    "sanity": 5,
    "insanity": 6,
    "madness": 5,
    "mental breakdown": 7,
    "self discovery": 7,
    "self-discovery": 7,
    "introspection": 8,
    "introspective": 8,
    "inner conflict": 6,
    "psychological thriller": 9,
}

STRONG_TAGS = {
    "psychological",
    "psychological horror",
    "psychological thriller",
    "psychology",
    "philosophy",
    "philosophical",
}


def score_novel(
    title: str | None,
    synopsis: str | None,
    tags: Iterable[str],
) -> tuple[float, list[str]]:
    title_text = normalize_text(title)
    synopsis_text = normalize_text(synopsis)
    combined = f"{title_text} {synopsis_text}".strip()

    tag_set = {
        normalize_text(tag)
        for tag in tags
        if normalize_text(tag)
    }

    score = 0.0
    reasons: list[str] = []
    philosophy_concepts: set[str] = set()
    psychology_concepts: set[str] = set()

    for phrase, weight in PHILOSOPHY_PATTERNS.items():
        hits = len(re.findall(
            re.escape(phrase),
            combined,
            flags=re.IGNORECASE,
        ))

        if hits:
            philosophy_concepts.add(phrase)
            score += min(hits, 2) * weight
            reasons.append(f"philosophy:{phrase}")

            if phrase in title_text:
                score += weight * 0.20
                reasons.append(f"title:{phrase}")

    for phrase, weight in PSYCHOLOGY_PATTERNS.items():
        hits = len(re.findall(
            re.escape(phrase),
            combined,
            flags=re.IGNORECASE,
        ))

        if hits:
            psychology_concepts.add(phrase)
            score += min(hits, 2) * weight
            reasons.append(f"psychology:{phrase}")

            if phrase in title_text:
                score += weight * 0.20
                reasons.append(f"title:{phrase}")

    for tag in tag_set:
        if tag in STRONG_TAGS:
            score += 12
            reasons.append(f"strong-tag:{tag}")

    score += min(len(philosophy_concepts), 6) * 1.5
    score += min(len(psychology_concepts), 6) * 1.5

    if philosophy_concepts and psychology_concepts:
        score += 8
        reasons.append("cross-domain-evidence")

    if len(philosophy_concepts | psychology_concepts) >= 3:
        score += 6
        reasons.append("multi-concept-evidence")

    return score, reasons


def has_enough_relevance_evidence(
    reasons: list[str],
) -> bool:
    concepts = {
        reason.split(":", 1)[1]
        for reason in reasons
        if reason.startswith((
            "philosophy:",
            "psychology:",
        ))
    }

    domains = {
        reason.split(":", 1)[0]
        for reason in reasons
        if reason.startswith((
            "philosophy:",
            "psychology:",
        ))
    }

    strong_tag = any(
        reason.startswith("strong-tag:")
        for reason in reasons
    )

    return (
        len(concepts) >= 2
        or len(domains) >= 2
        or (len(concepts) >= 1 and strong_tag)
    )


# ---------------------------------------------------------------------
# Quality scoring
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
        upper_ratio = sum(
            char.isupper()
            for char in letters
        ) / len(letters)

        if upper_ratio > 0.45:
            penalty += 4
            reasons.append("excessive-capitalization")

    if re.search(r"([!?])\1{2,}", text):
        penalty += 2
        reasons.append("excessive-punctuation")

    words = re.findall(
        r"[A-Za-z']+",
        (synopsis or "").lower(),
    )

    if len(words) < 25:
        penalty += 4
        reasons.append("very-short-synopsis")

    if len(words) >= 40:
        unique_ratio = len(set(words)) / len(words)

        if unique_ratio < 0.35:
            penalty += 3
            reasons.append("low-lexical-variety")

    return penalty, reasons


def score_quality(
    *,
    title: str | None,
    synopsis: str | None,
    followers: int | None,
    rating: float | None,
    rating_count: int | None,
    popularity_hits: int,
    search_hits: int,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if followers is not None:
        score += min(
            10.0,
            math.log10(followers + 1) * 2.0,
        )
        reasons.append(f"followers={followers}")

    # Bayesian-style adjustment: low rating counts have less influence.
    if rating is not None:
        confidence = (
            min(rating_count or 0, 500) / 500
            if rating_count is not None
            else 0.35
        )

        adjusted_rating = (
            confidence * rating
            + (1 - confidence) * 3.8
        )

        score += max(
            -2.0,
            (adjusted_rating - 3.0) * 4.0,
        )

        reasons.append(
            f"rating={rating}"
        )

    if rating_count is not None:
        score += min(
            4.0,
            math.log10(rating_count + 1),
        )
        reasons.append(
            f"rating_count={rating_count}"
        )

    score += min(popularity_hits, 8) * 1.5
    score += min(search_hits, 5) * 0.25

    penalty, penalty_reasons = synopsis_quality_penalty(
        title,
        synopsis,
    )

    score -= penalty

    reasons.extend(
        f"presentation:{reason}"
        for reason in penalty_reasons
    )

    return score, reasons


# ---------------------------------------------------------------------
# Scrape and filter
# ---------------------------------------------------------------------

def scrape_and_score(
    popularity_hits: dict[str, int],
    search_hits: dict[str, int],
) -> list[Candidate]:
    candidate_urls = list(popularity_hits)

    if len(candidate_urls) < MIN_DISCOVERED:
        for url in search_hits:
            if url not in popularity_hits:
                candidate_urls.append(url)

            if len(candidate_urls) >= MIN_DISCOVERED:
                break

    print(
        f"\n=== SCRAPING AND CLASSIFYING "
        f"{len(candidate_urls)} CANDIDATES ==="
    )

    candidates: list[Candidate] = []

    with httpx.Client(
        headers=HEADERS,
        timeout=30,
    ) as client:

        for index, url in enumerate(candidate_urls, start=1):
            print(f"[{index}/{len(candidate_urls)}] {url}")

            try:
                novel = scrape_royalroad(url)

            except Exception as exc:
                print(
                    "FAILED:",
                    type(exc).__name__,
                    exc,
                )
                continue

            # ---------------------------------------------------------
            # Strict banned-tag filter.
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

            try:
                html = fetch_html(client, url)
                followers, rating, rating_count = (
                    extract_fiction_metrics(html)
                )

            except Exception as exc:
                print(
                    "METADATA FAILED:",
                    type(exc).__name__,
                    exc,
                )
                followers = None
                rating = None
                rating_count = None

            # Followers are a hard popularity requirement. If the current
            # page structure prevents extraction, keep the story auditable
            # rather than inventing a number.
            if (
                followers is not None
                and followers < MIN_FOLLOWERS
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(followers={followers:,}, "
                    f"required >= {MIN_FOLLOWERS:,})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            if (
                rating is not None
                and rating < MIN_RATING
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(rating={rating}, "
                    f"required >= {MIN_RATING})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            if (
                rating_count is not None
                and rating_count < MIN_RATING_COUNT
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(rating_count={rating_count}, "
                    f"required >= {MIN_RATING_COUNT})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            relevance_score, reasons = score_novel(
                novel.get("title"),
                novel.get("synopsis"),
                novel.get("tags", []),
            )

            if (
                relevance_score < MIN_RELEVANCE_SCORE
                or not has_enough_relevance_evidence(reasons)
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(weak relevance={relevance_score:.1f})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            quality_score, quality_reasons = score_quality(
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                followers=followers,
                rating=rating,
                rating_count=rating_count,
                popularity_hits=popularity_hits.get(url, 0),
                search_hits=search_hits.get(url, 0),
            )

            candidates.append(
                Candidate(
                    url=url,
                    fiction_id=novel.get("fiction_id"),
                    title=novel.get("title"),
                    synopsis=novel.get("synopsis"),
                    tags=novel.get("tags", []),
                    followers=followers,
                    rating=rating,
                    rating_count=rating_count,
                    popularity_hits=popularity_hits.get(url, 0),
                    search_hits=search_hits.get(url, 0),
                    relevance_score=relevance_score,
                    quality_score=quality_score,
                    combined_score=(
                        relevance_score + quality_score
                    ),
                    reasons=reasons,
                    quality_reasons=quality_reasons,
                )
            )

            time.sleep(REQUEST_DELAY)

    return candidates


def select_top_candidates(
    candidates: list[Candidate],
) -> list[Candidate]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.combined_score,
            item.relevance_score,
            item.rating or 0,
            item.rating_count or 0,
            item.followers or 0,
            item.popularity_hits,
            item.search_hits,
        ),
        reverse=True,
    )

    return ranked[:TARGET]


# ---------------------------------------------------------------------
# Output
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
        "philosophical_royalroad_urls.txt",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(urls, file, indent=2)

    selected_urls = {
        candidate.url
        for candidate in selected
    }

    with open(
        "philosophical_royalroad_audit.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "selected",
                "url",
                "fiction_id",
                "title",
                "relevance_score",
                "quality_score",
                "combined_score",
                "followers",
                "rating",
                "rating_count",
                "popularity_hits",
                "search_hits",
                "tags",
                "reasons",
                "quality_reasons",
                "synopsis",
            ],
        )

        writer.writeheader()

        for candidate in sorted(
            all_candidates,
            key=lambda item: (
                item.combined_score,
                item.relevance_score,
            ),
            reverse=True,
        ):
            writer.writerow({
                "selected": (
                    candidate.url in selected_urls
                ),
                "url": candidate.url,
                "fiction_id": candidate.fiction_id,
                "title": candidate.title,
                "relevance_score": candidate.relevance_score,
                "quality_score": candidate.quality_score,
                "combined_score": candidate.combined_score,
                "followers": candidate.followers,
                "rating": candidate.rating,
                "rating_count": candidate.rating_count,
                "popularity_hits": candidate.popularity_hits,
                "search_hits": candidate.search_hits,
                "tags": json.dumps(
                    candidate.tags,
                    ensure_ascii=False,
                ),
                "reasons": json.dumps(
                    candidate.reasons,
                    ensure_ascii=False,
                ),
                "quality_reasons": json.dumps(
                    candidate.quality_reasons,
                    ensure_ascii=False,
                ),
                "synopsis": candidate.synopsis,
            })


def main() -> None:
    popularity_hits, search_hits = discover_candidates()

    candidates = scrape_and_score(
        popularity_hits,
        search_hits,
    )

    selected = select_top_candidates(candidates)

    write_outputs(selected, candidates)

    print(
        f"\n=== SELECTED {len(selected)} ROYAL ROAD FICTIONS "
        f"(preferred minimum: {MIN_TARGET}, "
        f"maximum: {TARGET}) ==="
    )

    if len(selected) < MIN_TARGET:
        print(
            "WARNING: Fewer than 50 fictions passed the current "
            "banned-tag, popularity, quality, and relevance filters. "
            "The output is intentionally not padded."
        )

    for rank, candidate in enumerate(selected, start=1):
        print(
            f"{rank:03d} "
            f"combined={candidate.combined_score:6.1f} "
            f"relevance={candidate.relevance_score:6.1f} "
            f"quality={candidate.quality_score:6.1f} "
            f"followers={candidate.followers} "
            f"rating={candidate.rating} "
            f"{candidate.title}"
        )
        print(candidate.url)

    print("\nWrote:")
    print("  philosophical_royalroad_urls.txt")
    print("  philosophical_royalroad_audit.csv")


if __name__ == "__main__":
    main()
