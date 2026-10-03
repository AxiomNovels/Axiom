"""
Discover ~250 of the most popular Wattpad stories, spread across a
variety of genres, with explicit sexual content hard-filtered out.

This replaces the older philosophy/psychology-focused discovery script.
The selection logic now has three priorities, in this order:

    1. Hard filter: explicit sexual content is excluded outright.
    2. Popularity: reads, votes, and comments.
    3. Genre diversity: no single genre is allowed to dominate the
       final list.

The EXCLUDED_TAGS list below is unchanged from the previous version of
this script -- it was already built specifically to hard-filter
sexual/explicit content on Wattpad, so it is kept as-is here.

Method
------
1. Crawl Wattpad's general "stories" listing plus each of Wattpad's
   own genre/category pages (Romance, Fantasy, Mystery, Thriller,
   Horror, Science Fiction, Adventure, Paranormal, Humor, Teen
   Fiction, Historical Fiction, Werewolf, Short Story, Poetry,
   Classics, Non-Fiction, General Fiction, Chick Lit, Fanfiction --
   see Wattpad's own category navigation), so the candidate pool
   already spans genres rather than being dominated by whatever is
   broadly trending.
2. Deduplicate all discovered story URLs.
3. Scrape every candidate with scraper.wattpad.scrape_wattpad().
4. Hard-exclude any story whose tags indicate explicit sexual content.
5. Require a minimum popularity floor (reads / votes) so obscure
   stories don't dilute the pool.
6. Rank the remaining candidates by a popularity score, then select
   up to TARGET stories using a per-genre cap so that popularity
   dominates the ordering while no single genre can fill the whole
   list. Unfilled seats are backfilled by raw popularity so the
   target count is still reached.

Output
------
popular_wattpad_urls.txt
popular_wattpad_audit.csv
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

from scraper.wattpad import BASE_URL, HEADERS, scrape_wattpad
from scraper.content_policy import EXCLUDED_TAGS_BY_SOURCE


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TARGET = 250
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.40
MAX_PAGES_PER_SEED = 20

# No single genre may take up more than this share of the final list.
MAX_GENRE_SHARE = 0.15
MIN_GENRE_CAP = 8

# Wattpad discovery surfaces, covering the general feed plus Wattpad's
# own genre/category pages so the pool spans genres from the start.
# The exact HTML can change, so discovery is link-driven rather than
# dependent on a single CSS selector. If Wattpad renames a category
# slug, that one seed simply fails to crawl (logged, not fatal) while
# the rest of the discovery still runs.
POPULAR_SEED_URLS = [
    f"{BASE_URL}/stories",
    f"{BASE_URL}/stories/romance",
    f"{BASE_URL}/stories/fantasy",
    f"{BASE_URL}/stories/adventure",
    f"{BASE_URL}/stories/mystery",
    f"{BASE_URL}/stories/thriller",
    f"{BASE_URL}/stories/horror",
    f"{BASE_URL}/stories/science-fiction",
    f"{BASE_URL}/stories/paranormal",
    f"{BASE_URL}/stories/humor",
    f"{BASE_URL}/stories/teenfiction",
    f"{BASE_URL}/stories/historicalfiction",
    f"{BASE_URL}/stories/werewolf",
    f"{BASE_URL}/stories/shortstory",
    f"{BASE_URL}/stories/poetry",
    f"{BASE_URL}/stories/classics",
    f"{BASE_URL}/stories/nonfiction",
    f"{BASE_URL}/stories/generalfiction",
    f"{BASE_URL}/stories/chicklit",
    f"{BASE_URL}/stories/fanfiction",
]

# Strict lewd-content exclusion. Unchanged from the previous version of
# this script -- filtering has already been done for Wattpad.
# Shared with the Upload Novel feature. Edit the list in
# scraper/content_policy.py, not here, so the two never drift apart.
EXCLUDED_TAGS = EXCLUDED_TAGS_BY_SOURCE["wattpad"]


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------

@dataclass
class Candidate:
    url: str
    story_id: int | None
    title: str | None
    synopsis: str | None
    genres: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    read_count: int | None = None
    vote_count: int | None = None
    comment_count: int | None = None

    popularity_hits: int = 0
    popularity_score: float = 0.0

    quality_reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# URL discovery
# ---------------------------------------------------------------------

def canonical_story_url(url: str) -> str | None:
    absolute = urljoin(BASE_URL, url)
    parsed = urlparse(absolute)

    if parsed.netloc.lower() not in {"www.wattpad.com", "wattpad.com"}:
        return None

    match = re.match(
        r"^/story/(\d+)(?:-[^/?#]+)?/?$",
        parsed.path,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    path = parsed.path.rstrip("/")

    return urlunparse(("https", "www.wattpad.com", path, "", "", ""))


def fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url, follow_redirects=True)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        raise ValueError(f"Expected HTML from Wattpad, got: {content_type}")

    return response.text


def extract_story_urls(html: str, page_url: str) -> set[str]:
    tree = HTMLParser(html)
    urls: set[str] = set()

    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue

        story_url = canonical_story_url(urljoin(page_url, href))
        if story_url:
            urls.add(story_url)

    return urls


def extract_listing_links(html: str, page_url: str) -> list[str]:
    """
    Find same-family listing/search links. Wattpad's pagination has
    changed historically, so this follows explicit links instead of
    assuming a fixed page query parameter.
    """
    tree = HTMLParser(html)
    current = urlparse(page_url)
    links: list[str] = []

    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)

        if parsed.netloc.lower() not in {"www.wattpad.com", "wattpad.com"}:
            continue

        if parsed.path.startswith("/story/"):
            continue

        if not (
            parsed.path.startswith("/stories") or parsed.path.startswith("/search")
        ):
            continue

        if current.path.startswith("/search") and not parsed.path.startswith(
            "/search"
        ):
            continue

        text = re.sub(
            r"\s+", " ", node.text(separator=" ", strip=True)
        ).strip().lower()

        rel = (node.attributes.get("rel") or "").lower()

        if (
            "next" in rel
            or text in {"next", "next >", ">", "\u203a", "\u2192"}
            or text.isdigit()
            or "page=" in parsed.query.lower()
        ):
            links.append(absolute)

    return list(dict.fromkeys(links))


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

        pages.append(extract_story_urls(html, url))

        for next_url in extract_listing_links(html, url):
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
        print("\n=== DISCOVERING POPULAR WATTPAD CANDIDATES ===")

        for seed in POPULAR_SEED_URLS:
            print("SEED:", seed)

            for stories in crawl_listing(client, seed, MAX_PAGES_PER_SEED):
                for url in stories:
                    popularity_hits[url] = popularity_hits.get(url, 0) + 1

            print("Unique candidates so far:", len(popularity_hits))

    print("Total discovered candidates:", len(popularity_hits))
    return popularity_hits


# ---------------------------------------------------------------------
# Embedded Wattpad metadata
# ---------------------------------------------------------------------

def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def parse_count(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
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


def find_metric_values(value: Any, aliases: set[str], found: list[int]) -> None:
    """
    Recursively inspect Wattpad Remix data. Only values from explicitly
    named metric keys are collected; generic keys such as "count" are
    intentionally ignored.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())

            if normalized_key in aliases:
                parsed = parse_count(child)
                if parsed is not None:
                    found.append(parsed)

            find_metric_values(child, aliases, found)

    elif isinstance(value, list):
        for child in value:
            find_metric_values(child, aliases, found)


def extract_remix_context(html: str) -> Any | None:
    tree = HTMLParser(html)
    marker = "window.__remixContext = "

    for script in tree.css("script"):
        text = script.text()
        if not text or marker not in text:
            continue

        start = text.find(marker)
        json_text = text[start + len(marker):].strip()

        if json_text.endswith(";"):
            json_text = json_text[:-1]

        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            continue

    return None


def extract_story_metrics(
    html: str,
) -> tuple[int | None, int | None, int | None]:
    """
    Best-effort extraction of reads, votes and comments. Searches
    embedded Remix metadata first, then falls back to visible labels.
    """
    context = extract_remix_context(html)

    read_values: list[int] = []
    vote_values: list[int] = []
    comment_values: list[int] = []

    if context is not None:
        find_metric_values(
            context,
            {"readcount", "reads", "numreads", "totalreads", "readnumber"},
            read_values,
        )
        find_metric_values(
            context,
            {"votecount", "votes", "numvotes", "totalvotes", "voteamount"},
            vote_values,
        )
        find_metric_values(
            context,
            {"commentcount", "comments", "numcomments", "totalcomments"},
            comment_values,
        )

    def visible_metric(labels: tuple[str, ...]) -> int | None:
        for label in labels:
            patterns = [
                rf"(\d+(?:\.\d+)?\s*[KkMm]?)\s+{label}\b",
                rf"\b{label}\s*[:\-]?\s*(\d+(?:\.\d+)?\s*[KkMm]?)",
            ]
            for pattern in patterns:
                match = re.search(pattern, html, flags=re.IGNORECASE)
                if match:
                    parsed = parse_count(match.group(1))
                    if parsed is not None:
                        return parsed
        return None

    read_count = max(read_values) if read_values else visible_metric(("reads", "read"))
    vote_count = max(vote_values) if vote_values else visible_metric(("votes", "vote"))
    comment_count = (
        max(comment_values)
        if comment_values
        else visible_metric(("comments", "comment"))
    )

    return read_count, vote_count, comment_count


# ---------------------------------------------------------------------
# Popularity scoring (no more relevance scoring)
# ---------------------------------------------------------------------

def synopsis_quality_penalty(
    title: str | None,
    synopsis: str | None,
) -> tuple[float, list[str]]:
    title = title or ""
    synopsis = synopsis or ""
    text = f"{title} {synopsis}".strip()

    if not text:
        return 12.0, ["missing-synopsis"]

    penalty = 0.0
    reasons: list[str] = []

    letters = [char for char in text if char.isalpha()]
    if letters:
        upper_ratio = sum(char.isupper() for char in letters) / len(letters)
        if upper_ratio > 0.45 and len(letters) > 30:
            penalty += 4
            reasons.append("excessive-capitalization")

    if re.search(r"([!?])\1{2,}", text):
        penalty += 2
        reasons.append("excessive-punctuation")

    words = re.findall(r"[A-Za-z']+", synopsis.lower())

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
    read_count: int | None,
    vote_count: int | None,
    comment_count: int | None,
    popularity_hits: int,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if read_count is not None:
        score += min(8.0, math.log10(read_count + 1) * 1.2)
        reasons.append(f"reads={read_count}")

    if vote_count is not None:
        score += min(8.0, math.log10(vote_count + 1) * 1.5)
        reasons.append(f"votes={vote_count}")

    if comment_count is not None:
        score += min(4.0, math.log10(comment_count + 1))
        reasons.append(f"comments={comment_count}")

    score += min(popularity_hits, 10) * 1.5
    reasons.append(f"listing-hits={popularity_hits}")

    penalty, penalty_reasons = synopsis_quality_penalty(title, synopsis)
    score -= penalty
    reasons.extend(f"presentation:{reason}" for reason in penalty_reasons)

    return score, reasons


# ---------------------------------------------------------------------
# Scrape, hard-filter, and score
# ---------------------------------------------------------------------

# Minimum popularity floor. Only enforced when the metric is
# successfully extracted -- a missing metric is recorded in the audit
# rather than treated as a failure.
MIN_VOTE_COUNT = 50
MIN_READ_COUNT = 5_000


def scrape_and_score(popularity_hits: dict[str, int]) -> list[Candidate]:
    candidate_urls = list(popularity_hits)

    print(f"\n=== SCRAPING AND CLASSIFYING {len(candidate_urls)} CANDIDATES ===")

    candidates: list[Candidate] = []

    with httpx.Client(headers=HEADERS, timeout=30) as client:
        for index, url in enumerate(candidate_urls, start=1):
            print(f"[{index}/{len(candidate_urls)}]", url)

            try:
                novel = scrape_wattpad(url)
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
                read_count, vote_count, comment_count = extract_story_metrics(html)
            except Exception as exc:
                print("METADATA FAILED:", type(exc).__name__, exc)
                read_count, vote_count, comment_count = None, None, None

            if read_count is not None and read_count < MIN_READ_COUNT:
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(reads={read_count:,}, required >= {MIN_READ_COUNT:,})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            if vote_count is not None and vote_count < MIN_VOTE_COUNT:
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(votes={vote_count:,}, required >= {MIN_VOTE_COUNT:,})"
                )
                time.sleep(REQUEST_DELAY)
                continue

            popularity_score, quality_reasons = score_popularity(
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                read_count=read_count,
                vote_count=vote_count,
                comment_count=comment_count,
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
                    read_count=read_count,
                    vote_count=vote_count,
                    comment_count=comment_count,
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

    with open("popular_wattpad_urls.txt", "w", encoding="utf-8") as file:
        json.dump(urls, file, indent=2)

    selected_urls = {candidate.url for candidate in selected}

    with open(
        "popular_wattpad_audit.csv", "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "selected",
                "url",
                "story_id",
                "title",
                "popularity_score",
                "read_count",
                "vote_count",
                "comment_count",
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
                "read_count": candidate.read_count,
                "vote_count": candidate.vote_count,
                "comment_count": candidate.comment_count,
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
        f"\n=== SELECTED {len(selected)} WATTPAD STORIES "
        f"(target: {TARGET}, tolerance: +/-{TARGET_TOLERANCE}) ==="
    )

    if len(selected) < MIN_TARGET:
        print(
            "WARNING: Fewer than the minimum acceptable number of stories "
            "passed the sexual-content and popularity filters. The output "
            "is intentionally not padded with weaker candidates."
        )

    print("\nGenre spread of the selection:")
    for genre, count in genre_counts.most_common():
        print(f"  {genre:<20} {count}")

    for rank, candidate in enumerate(selected, start=1):
        print(
            f"{rank:03d} pop={candidate.popularity_score:6.1f} "
            f"reads={candidate.read_count} votes={candidate.vote_count} "
            f"genres={candidate.genres} {candidate.title}"
        )
        print(candidate.url)

    print("\nWrote:")
    print("  popular_wattpad_urls.txt")
    print("  popular_wattpad_audit.csv")


if __name__ == "__main__":
    main()