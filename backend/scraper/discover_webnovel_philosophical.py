"""
Discover the most popular philosophical / psychological WebNovel novels.

Method
------
1. Crawl several WebNovel popularity-oriented ranking pages.
2. Crawl multiple WebNovel search queries as a recall-expansion source.
3. Deduplicate all discovered book URLs.
4. Fetch every candidate with the existing WebNovel scraper/parser.
5. Fetch WebNovel review statistics for each candidate:
      - totalScore
      - totalReviewNum
6. Require:
      - totalScore > 3.0
      - totalReviewNum > 20
7. Score philosophical / psychological relevance using independent evidence:
      - explicit tags: strong positive evidence only
      - synopsis/title semantic concepts
      - psychology-specific concepts
      - philosophy/existential/ethical concepts
      - narrative introspection and human-nature signals
      - negative-context checks to avoid matching books that merely contain
        "psychological" in a warning or incidental sentence
8. Keep the 100 highest-scoring candidates, while writing an audit CSV so
   borderline selections can be inspected.

Tags are NEVER used as a negative filter. A missing philosophical or
psychological tag contributes zero evidence; it does not disqualify a novel.

Review statistics are used as a quality/popularity filter. Collection count
is NOT used.

Usage
-----
Put this file next to your existing webnovel.py, then:

    python discover_webnovel_philosophical.py

Output:
    philosophical_webnovel_urls.txt
    philosophical_webnovel_audit.csv
"""

from __future__ import annotations

import csv
import json
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# Import your existing scraper.
from scraper.webnovel import HEADERS, scrape_webnovel


BASE_URL = "https://www.webnovel.com"


# Several independent popularity surfaces are used. Rankings can change,
# so combining them gives a more stable candidate pool than relying on one.
SEED_URLS = [
    f"{BASE_URL}/ranking/novel/all_time/popular_rank",
    f"{BASE_URL}/ranking/novel/all_time/collection_rank",
    f"{BASE_URL}/ranking/novel/all_time/best_sellers",
    f"{BASE_URL}/ranking/novel/all_time/engagement_rank",
]


# Search is used only for recall expansion. It is deliberately broad.
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


TARGET = 50

MIN_DISCOVERED = 500

REQUEST_DELAY = 0.35

MAX_PAGES_PER_SEED = 60

MAX_SEARCH_PAGES = 20

# WebNovel review filters.
MIN_TOTAL_SCORE = 3.0
MIN_TOTAL_REVIEW_NUM = 20

# Tags that automatically exclude a novel from the candidate pool.
EXCLUDED_TAGS = {
    "harem",
    "smut",
    "pregnancy",
    "yandere",
    "ceo",
}


@dataclass
class Candidate:
    url: str
    title: str | None
    synopsis: str | None
    tags: list[str]

    # WebNovel review statistics.
    total_score: float | None
    total_review_num: int | None

    popularity_hits: int
    search_hits: int

    relevance_score: float
    reasons: list[str]


def canonical_book_url(
    url: str,
) -> str | None:
    """
    Normalize a WebNovel book URL and reject non-book links.
    """

    absolute = urljoin(
        BASE_URL,
        url,
    )

    parsed = urlparse(
        absolute
    )

    if parsed.netloc.lower() not in {
        "www.webnovel.com",
        "webnovel.com",
    }:
        return None

    match = re.search(
        r"/book/[^?#]+",
        parsed.path,
    )

    if not match:
        return None

    path = match.group(0).rstrip("/")

    # A valid WebNovel book URL normally ends in _<numeric-id>, but also
    # accept /book/<numeric-id> because the existing scraper supports both.
    if not (
        re.search(
            r"_\d+$",
            path,
        )
        or re.search(
            r"/book/\d+$",
            path,
        )
    ):
        return None

    return urlunparse(
        (
            "https",
            "www.webnovel.com",
            path,
            "",
            "",
            "",
        )
    )


def fetch_html(
    session: requests.Session,
    url: str,
) -> str:
    response = session.get(
        url,
        timeout=30,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response.text


def extract_book_urls(
    html: str,
    page_url: str,
) -> set[str]:
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    urls: set[str] = set()

    for a in soup.select(
        "a[href]"
    ):
        book = canonical_book_url(
            urljoin(
                page_url,
                a["href"],
            )
        )

        if book:
            urls.add(book)

    return urls


def is_same_listing_family(
    seed_url: str,
    candidate_url: str,
) -> bool:
    """
    Keep pagination traversal on the same ranking/search family.
    """

    seed = urlparse(
        seed_url
    )

    candidate = urlparse(
        candidate_url
    )

    if candidate.netloc.lower() not in {
        "www.webnovel.com",
        "webnovel.com",
    }:
        return False

    if seed.path.startswith(
        "/ranking/"
    ):
        return candidate.path.startswith(
            "/ranking/"
        )

    if seed.path == "/search":
        return candidate.path == "/search"

    return False


def listing_next_links(
    html: str,
    page_url: str,
) -> list[str]:
    """
    Discover pagination without assuming WebNovel's query parameter names.

    This follows explicit NEXT links and numeric pagination links. The
    discovered URL is later constrained to the same listing family.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    found: list[str] = []

    for a in soup.select(
        "a[href]"
    ):
        text = " ".join(
            a.stripped_strings
        ).strip().lower()

        href = urljoin(
            page_url,
            a["href"],
        )

        if not is_same_listing_family(
            page_url,
            href,
        ):
            continue

        rel = {
            str(x).lower()
            for x in (
                a.get("rel")
                or []
            )
        }

        if (
            "next" in rel
            or text in {
                "next",
                "next >",
                ">",
                "›",
                "→",
            }
            or text.isdigit()
        ):
            found.append(
                href
            )

    return found


def crawl_listing(
    session: requests.Session,
    seed_url: str,
    page_limit: int,
) -> list[set[str]]:
    """
    Breadth-first crawl of a ranking/search listing.

    Returns one set per page so popularity/search frequency can be tracked.
    """

    queue = deque(
        [seed_url]
    )

    seen_pages: set[str] = set()

    pages: list[set[str]] = []

    while (
        queue
        and len(pages) < page_limit
    ):
        url = queue.popleft()

        if url in seen_pages:
            continue

        seen_pages.add(
            url
        )

        try:
            html = fetch_html(
                session,
                url,
            )

        except requests.RequestException as exc:
            print(
                "LISTING FAILED:",
                url,
                type(exc).__name__,
                exc,
            )

            continue

        books = extract_book_urls(
            html,
            url,
        )

        pages.append(
            books
        )

        for next_url in listing_next_links(
            html,
            url,
        ):
            if next_url not in seen_pages:
                queue.append(
                    next_url
                )

        time.sleep(
            REQUEST_DELAY
        )

    return pages


def search_url(
    query: str,
    page: int | None = None,
) -> str:
    params = {
        "keywords": query
    }

    # Only add page when requested. If WebNovel changes its pagination
    # convention, explicit pagination links discovered from the HTML still
    # take precedence.
    if page is not None:
        params["page"] = page

    return (
        f"{BASE_URL}/search?"
        f"{urlencode(params)}"
    )


def discover_candidates() -> tuple[
    dict[str, int],
    dict[str, int],
]:
    """
    Return:

        popularity_hits[url] =
            number of ranking pages containing the book

        search_hits[url] =
            number of concept searches containing the book
    """

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    popularity_hits: dict[str, int] = {}

    search_hits: dict[str, int] = {}

    print(
        "\n=== DISCOVERING POPULARITY CANDIDATES ==="
    )

    for seed in SEED_URLS:

        print(
            "RANKING:",
            seed,
        )

        for books in crawl_listing(
            session,
            seed,
            MAX_PAGES_PER_SEED,
        ):

            for url in books:

                popularity_hits[url] = (
                    popularity_hits.get(
                        url,
                        0,
                    )
                    + 1
                )

        print(
            "Unique ranking candidates:",
            len(popularity_hits),
        )

        if (
            len(popularity_hits)
            >= MIN_DISCOVERED
        ):
            # Continue through other ranking families only if desired by
            # removing this break. One family plus pagination is usually
            # enough to reach the requested recall pool.
            pass

    print(
        "\n=== DISCOVERING CONCEPT CANDIDATES ==="
    )

    for query in SEARCH_QUERIES:

        print(
            "SEARCH:",
            query,
        )

        pages = crawl_listing(
            session,
            search_url(query),
            MAX_SEARCH_PAGES,
        )

        for books in pages:

            for url in books:

                search_hits[url] = (
                    search_hits.get(
                        url,
                        0,
                    )
                    + 1
                )

        time.sleep(
            REQUEST_DELAY
        )

    print(
        "Popularity candidates:",
        len(popularity_hits),
    )

    print(
        "Concept-search candidates:",
        len(search_hits),
    )

    return (
        popularity_hits,
        search_hits,
    )


# ---------------------------------------------------------------------
# WebNovel review statistics
# ---------------------------------------------------------------------


def extract_story_id_from_url(
    url: str,
) -> int:
    """
    Extract the numeric WebNovel book ID from a book URL.
    """

    match = re.search(
        r"_(\d+)(?:[/?#]|$)",
        url,
    )

    if not match:
        match = re.search(
            r"/book/(\d+)",
            url,
        )

    if not match:
        raise ValueError(
            f"Could not extract WebNovel book ID from: {url}"
        )

    return int(
        match.group(1)
    )


def fetch_review_statistics(
    session: requests.Session,
    book_id: int,
) -> tuple[
    float | None,
    int | None,
]:
    """
    Fetch WebNovel's book review statistics.

    WebNovel exposes these through:

        /go/pcm/bookReview/get-reviews

    The relevant response object is:

        data.bookStatisticsInfo

    containing:

        totalScore
        totalReviewNum

    The endpoint requires the book ID but does not require us to download
    individual reviews. pageSize=1 keeps the response small while still
    returning bookStatisticsInfo.
    """

    url = (
        f"{BASE_URL}/go/pcm/bookReview/get-reviews"
    )

    params = {
        "bookId": book_id,
        "pageIndex": 1,
        "pageSize": 1,
        "orderBy": 1,
        "novelType": 0,
        "needSummary": 1,
    }

    try:
        response = session.get(
            url,
            params=params,
            timeout=30,
            allow_redirects=True,
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        print(
            "REVIEW REQUEST FAILED:",
            book_id,
            type(exc).__name__,
            exc,
        )

        return (
            None,
            None,
        )

    try:
        payload = response.json()

    except ValueError as exc:
        print(
            "REVIEW JSON FAILED:",
            book_id,
            type(exc).__name__,
            exc,
        )

        return (
            None,
            None,
        )

    if not isinstance(
        payload,
        dict,
    ):
        return (
            None,
            None,
        )

    data = payload.get(
        "data"
    )

    if not isinstance(
        data,
        dict,
    ):
        return (
            None,
            None,
        )

    statistics = data.get(
        "bookStatisticsInfo"
    )

    if not isinstance(
        statistics,
        dict,
    ):
        return (
            None,
            None,
        )

    raw_score = statistics.get(
        "totalScore"
    )

    raw_review_count = statistics.get(
        "totalReviewNum"
    )

    # totalScore is normally a float such as 4.71.
    try:
        total_score = (
            float(raw_score)
            if raw_score is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):
        total_score = None

    # totalReviewNum is normally an integer such as 7133.
    try:
        total_review_num = (
            int(raw_review_count)
            if raw_review_count is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):
        total_review_num = None

    return (
        total_score,
        total_review_num,
    )


# ---------------------------------------------------------------------
# Relevance classification
# ---------------------------------------------------------------------


PHILOSOPHY_PATTERNS = {
    "philosophy": 8,
    "philosophical": 8,
    "existential": 8,
    "existentialism": 10,
    "meaning of life": 8,
    "purpose of life": 8,
    "reason for living": 7,
    "human nature": 7,
    "nature of humanity": 7,
    "free will": 7,
    "determinism": 8,
    "morality": 6,
    "ethical": 6,
    "ethics": 6,
    "moral dilemma": 8,
    "identity": 4,
    "sense of self": 7,
    "selfhood": 8,
    "consciousness": 7,
    "reality itself": 5,
    "nature of reality": 8,
    "truth and meaning": 7,
    "nihilism": 9,
    "absurdism": 9,
    "stoic": 7,
    "stoicism": 8,
    "enlightenment": 4,
    "belief system": 5,
    "questioning reality": 7,
    "what it means to be human": 9,
    "what does it mean to be human": 9,
    "life and death": 5,
    "mortality": 5,
    "existence": 5,
    "meaningless": 5,
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
    "multiple personalities": 9,
    "identity crisis": 8,
    "unreliable narrator": 8,
    "subconscious": 8,
    "unconscious mind": 8,
    "dream interpretation": 8,
    "mind games": 6,
    "manipulation": 3,
    "behavioral": 5,
    "human behavior": 7,
    "cognitive": 7,
    "memory": 2,
    "sanity": 5,
    "insanity": 6,
    "madness": 5,
    "inner demons": 5,
    "mental breakdown": 7,
    "self discovery": 7,
    "self-discovery": 7,
    "introspection": 8,
    "introspective": 8,
    "inner conflict": 6,
    "psychological thriller": 9,
}


# Tags matching these concepts are highly reliable positive evidence, but
# absence of such tags is ignored.
STRONG_TAGS = {
    "philosophy",
    "philosophical",
    "psychology",
    "psychological",
    "psychological thriller",
    "mental health",
    "psychological horror",
}


# Incidental contexts where the mere occurrence of "psychological" should
# not be enough by itself.
INCIDENTAL_PATTERNS = {
    "psychologically painful": 4,
    "psychological threshold": 3,
    "psychological warning": 4,
    "psychological themes": 2,
}


def normalized_text(
    value: str | None,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").lower(),
    ).strip()


def count_pattern(
    text: str,
    pattern: str,
) -> int:
    return len(
        re.findall(
            re.escape(pattern),
            text,
            flags=re.IGNORECASE,
        )
    )


def score_novel(
    title: str | None,
    synopsis: str | None,
    tags: Iterable[str],
) -> tuple[
    float,
    list[str],
]:
    """
    Multi-signal scoring.

    A novel can qualify through:
      * direct philosophical evidence,
      * direct psychological evidence,
      * several weaker introspective signals,
      * or strong tag evidence corroborated by text.

    We intentionally avoid a hard "must have philosophy/psychology tag"
    condition.
    """

    title_text = normalized_text(
        title
    )

    synopsis_text = normalized_text(
        synopsis
    )

    combined = (
        f"{title_text} {synopsis_text}"
    ).strip()

    tag_set = {
        normalized_text(tag)
        for tag in tags
        if normalized_text(tag)
    }

    score = 0.0

    reasons: list[str] = []

    philosophy_hits = 0

    psychology_hits = 0

    for phrase, weight in PHILOSOPHY_PATTERNS.items():

        hits = count_pattern(
            combined,
            phrase,
        )

        if hits:

            philosophy_hits += hits

            score += (
                min(hits, 2)
                * weight
            )

            reasons.append(
                f"philosophy:{phrase}"
            )

            if phrase in title_text:

                score += (
                    weight
                    * 0.75
                )

                reasons.append(
                    f"title:{phrase}"
                )

    for phrase, weight in PSYCHOLOGY_PATTERNS.items():

        hits = count_pattern(
            combined,
            phrase,
        )

        if hits:

            psychology_hits += hits

            score += (
                min(hits, 2)
                * weight
            )

            reasons.append(
                f"psychology:{phrase}"
            )

            if phrase in title_text:

                score += (
                    weight
                    * 0.75
                )

                reasons.append(
                    f"title:{phrase}"
                )

    for tag in tag_set:

        if tag in STRONG_TAGS:

            score += 12

            reasons.append(
                f"strong-tag:{tag}"
            )

    # Diversity of evidence is more valuable than repeating one word.
    score += (
        min(
            philosophy_hits,
            6,
        )
        * 1.5
    )

    score += (
        min(
            psychology_hits,
            6,
        )
        * 1.5
    )

    if (
        philosophy_hits
        and psychology_hits
    ):

        score += 8

        reasons.append(
            "cross-domain-evidence"
        )

    for phrase, penalty in INCIDENTAL_PATTERNS.items():

        if phrase in combined:

            score -= penalty

            reasons.append(
                f"incidental-context:{phrase}"
            )

    # A synopsis with several conceptually distinct signals is more likely
    # genuinely philosophical/psychological than one accidental keyword hit.
    distinct = len(
        set(reasons)
    )

    if distinct >= 4:

        score += 6

        reasons.append(
            "multi-signal"
        )

    return (
        score,
        reasons,
    )


def scrape_and_score(
    popularity_hits: dict[str, int],
    search_hits: dict[str, int],
) -> list[Candidate]:
    """
    Scrape all popularity candidates first. Search-only candidates are added
    only when needed for recall.

    Candidates must satisfy:

        totalScore > MIN_TOTAL_SCORE

    and:

        totalReviewNum > MIN_TOTAL_REVIEW_NUM
    """

    candidate_urls = list(
        popularity_hits
    )

    # If ranking discovery did not reach the desired pool, use concept-search
    # results to fill the candidate pool.
    if (
        len(candidate_urls)
        < MIN_DISCOVERED
    ):

        for url in search_hits:

            if url not in popularity_hits:

                candidate_urls.append(
                    url
                )

            if (
                len(candidate_urls)
                >= MIN_DISCOVERED
            ):
                break

    print(
        "\n=== SCRAPING AND CLASSIFYING",
        len(candidate_urls),
        "CANDIDATES ===",
    )

    candidates: list[Candidate] = []

    # One session is used for review requests so that connection reuse is
    # possible across hundreds of candidates.
    review_session = requests.Session()

    review_session.headers.update(
        HEADERS
    )

    for index, url in enumerate(
        candidate_urls,
        start=1,
    ):

        print(
            f"[{index}/{len(candidate_urls)}]",
            url,
        )

        # -------------------------------------------------------------
        # Existing WebNovel scraper.
        # -------------------------------------------------------------

        try:

            novel = scrape_webnovel(
                url
            )

        except Exception as exc:

            print(
                "FAILED:",
                type(exc).__name__,
                exc,
            )

            continue

        # -------------------------------------------------------------
        # Excluded-tag filter.
        # -------------------------------------------------------------

        novel_tags = {
            normalized_text(tag)
            for tag in novel.get("tags", [])
            if normalized_text(tag)
        }

        matched_excluded_tags = (
            novel_tags
            & EXCLUDED_TAGS
        )

        if matched_excluded_tags:

            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(excluded tags: "
                f"{sorted(matched_excluded_tags)})"
            )

            time.sleep(
                REQUEST_DELAY
            )

            continue

        # -------------------------------------------------------------
        # Review statistics.
        # -------------------------------------------------------------

        try:

            book_id = (
                novel.get("story_id")
                or extract_story_id_from_url(
                    url
                )
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            print(
                "REVIEW FAILED:",
                type(exc).__name__,
                exc,
            )

            continue

        (
            total_score,
            total_review_num,
        ) = fetch_review_statistics(
            review_session,
            int(book_id),
        )

        # Store the values in the local novel dictionary as well. This
        # doesn't modify webnovel.py; it simply makes the current parsed
        # record contain the review information.
        novel["total_score"] = (
            total_score
        )

        novel["total_review_num"] = (
            total_review_num
        )

        # -------------------------------------------------------------
        # Review-score filter.
        # -------------------------------------------------------------

        if (
            total_score is None
            or total_review_num is None
        ):

            print(
                f"SKIPPED: {novel.get('title')!r} "
                "(review statistics unavailable)"
            )

            time.sleep(
                REQUEST_DELAY
            )

            continue

        if (
            total_score
            <= MIN_TOTAL_SCORE
        ):

            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(score={total_score:.2f}, "
                f"required > {MIN_TOTAL_SCORE:.1f})"
            )

            time.sleep(
                REQUEST_DELAY
            )

            continue

        if (
            total_review_num
            <= MIN_TOTAL_REVIEW_NUM
        ):

            print(
                f"SKIPPED: {novel.get('title')!r} "
                f"(reviews={total_review_num:,}, "
                f"required > {MIN_TOTAL_REVIEW_NUM})"
            )

            time.sleep(
                REQUEST_DELAY
            )

            continue

        # -------------------------------------------------------------
        # Philosophical / psychological relevance scoring.
        # -------------------------------------------------------------

        relevance_score, reasons = score_novel(
            novel.get("title"),
            novel.get("synopsis"),
            novel.get("tags", []),
        )

        candidates.append(
            Candidate(
                url=url,
                title=novel.get("title"),
                synopsis=novel.get("synopsis"),
                tags=novel.get("tags", []),
                total_score=total_score,
                total_review_num=total_review_num,
                popularity_hits=popularity_hits.get(
                    url,
                    0,
                ),
                search_hits=search_hits.get(
                    url,
                    0,
                ),
                relevance_score=relevance_score,
                reasons=reasons,
            )
        )

        time.sleep(
            REQUEST_DELAY
        )

    return candidates


def select_top_100(
    candidates: list[Candidate],
) -> list[Candidate]:
    """
    Relevance is primary. Review score/review count, popularity and search
    recurrence break ties.

    We do not require a fixed relevance threshold because the candidate pool
    can contain fewer than 100 obvious matches.

    This guarantees up to 100 results when enough candidates were successfully
    scraped.
    """

    ranked = sorted(
        candidates,
        key=lambda item: (
            item.relevance_score,
            item.total_score or 0,
            item.total_review_num or 0,
            item.popularity_hits,
            item.search_hits,
            len(item.synopsis or ""),
        ),
        reverse=True,
    )

    return ranked[
        :TARGET
    ]


def write_outputs(
    selected: list[Candidate],
    all_candidates: list[Candidate],
) -> None:

    urls = [
        candidate.url
        for candidate in selected
    ]

    with open(
        "philosophical_webnovel_urls.txt",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            urls,
            file,
            indent=2,
        )

    with open(
        "philosophical_webnovel_audit.csv",
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "selected",
                "url",
                "title",
                "relevance_score",
                "total_score",
                "total_review_num",
                "popularity_hits",
                "search_hits",
                "tags",
                "reasons",
                "synopsis",
            ],
        )

        writer.writeheader()

        selected_urls = {
            x.url
            for x in selected
        }

        for candidate in sorted(
            all_candidates,
            key=lambda x: (
                x.relevance_score,
                x.total_score or 0,
                x.total_review_num or 0,
            ),
            reverse=True,
        ):

            writer.writerow(
                {
                    "selected": (
                        candidate.url
                        in selected_urls
                    ),
                    "url": candidate.url,
                    "title": candidate.title,
                    "relevance_score": (
                        candidate.relevance_score
                    ),
                    "total_score": (
                        candidate.total_score
                    ),
                    "total_review_num": (
                        candidate.total_review_num
                    ),
                    "popularity_hits": (
                        candidate.popularity_hits
                    ),
                    "search_hits": (
                        candidate.search_hits
                    ),
                    "tags": json.dumps(
                        candidate.tags
                    ),
                    "reasons": json.dumps(
                        candidate.reasons
                    ),
                    "synopsis": candidate.synopsis,
                }
            )


def main() -> None:

    (
        popularity_hits,
        search_hits,
    ) = discover_candidates()

    candidates = scrape_and_score(
        popularity_hits,
        search_hits,
    )

    if len(candidates) < TARGET:

        raise RuntimeError(
            f"Only {len(candidates)} novels "
            f"passed the review filters; "
            f"need at least {TARGET}."
        )

    selected = select_top_100(
        candidates
    )

    write_outputs(
        selected,
        candidates,
    )

    print(
        "\n=== TOP 100 ==="
    )

    for rank, candidate in enumerate(
        selected,
        start=1,
    ):

        print(
            f"{rank:03d} "
            f"relevance={candidate.relevance_score:6.1f} "
            f"rating={candidate.total_score:.2f} "
            f"reviews={candidate.total_review_num:,} "
            f"{candidate.title}"
        )

        print(
            candidate.url
        )

    print(
        "\nWrote:"
    )

    print(
        "  philosophical_webnovel_urls.txt"
    )

    print(
        "  philosophical_webnovel_audit.csv"
    )


if __name__ == "__main__":
    main()
