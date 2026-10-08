"""Discover popular WebNovel books with conservative content filtering.

Fetch each book once and reuse that HTML for the unchanged source parser,
content checks, and book-scoped views/rating/review statistics. Retain an 80%
popular core and reserve 20% of seats for established novels in other genres.
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

import os
import httpx
from curl_cffi import requests as browser_requests
from selectolax.parser import HTMLParser
from bs4 import BeautifulSoup

from scraper.webnovel import HEADERS, parse_webnovel
from scraper.content_policy import EXCLUDED_TAGS_BY_SOURCE, find_policy_violations


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
    "romance",
    "mystery",
    "comedy",
    "slice of life",
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
MAX_ADDITIONAL_PAGES_PER_SEED = 15

# Category links discovered from /category are themselves added as
# additional sources. This gives each top-level genre its own crawl.
MAX_DISCOVERED_CATEGORY_SEEDS = 100


TARGET = 300
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

# A smaller discovered pool is diagnostic; the eligibility floors still apply.
MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.35
MAX_PAGES_PER_SEED = 15


# Most seats follow popularity; a bounded share improves genre coverage.
DIVERSITY_SHARE = 0.20
DIVERSITY_POPULARITY_RATIO = 0.25


# Views are required to establish popularity. Optional rating/review metrics
# enforce their quality floors whenever the book page exposes them.
MIN_TOTAL_SCORE = 3.5
MIN_READ_COUNT = 5_000
MIN_TOTAL_REVIEW_NUM = 25


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

    read_count: int | None = None
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

    match = re.fullmatch(r"/book/(?:[^/?#]+_)?(\d+)/?", parsed.path)
    if not match:
        return None
    return f"{BASE_URL}/book/{int(match.group(1))}"


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


PROXY_URL = os.getenv("WEBNOVEL_PROXY_URL", "").strip() or None


class DiscoveryChallengeError(httpx.RequestError):
    """WebNovel served a browser challenge instead of the requested page."""


def is_challenge(response) -> bool:
    return (
        response.headers.get("cf-mitigated", "").casefold() == "challenge"
        or bool(re.search(
            r"<title[^>]*>\s*Just a moment(?:\.\.\.|\u2026)?\s*</title>",
            response.text,
            re.IGNORECASE,
        ))
        or "window._cf_chl_opt" in response.text
    )


class DiscoveryClient:
    """Reuse connections/cookies and switch transport once if HTTP is refused."""

    def __init__(self):
        self.direct = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20)
        self.browser = None
        self.proxy = PROXY_URL

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.direct.close()
        if self.browser is not None:
            self.browser.close()

    def _browser_get(self, url: str) -> httpx.Response:
        if self.browser is None:
            # Let curl_cffi supply matching browser headers, TLS and HTTP/2.
            # The old User-Agent must not override the Chrome profile.
            self.browser = browser_requests.Session(
                impersonate="chrome",
                headers={"Accept-Language": "en-US,en;q=0.9"},
                timeout=20,
                allow_redirects=True,
            )
        request = httpx.Request("GET", url)
        try:
            response = self.browser.get(url, proxy=self.proxy)
        except browser_requests.exceptions.RequestException as error:
            raise httpx.RequestError(
                f"WebNovel browser request failed ({type(error).__name__}).",
                request=request,
            ) from None
        # Preserve the existing httpx exception contract for API callers.
        return httpx.Response(
            response.status_code,
            # curl_cffi already decompressed the body; do not ask httpx to
            # decode it again using the original wire encoding/length.
            headers={key: value for key, value in response.headers.items()
                     if key.casefold() not in {"content-encoding", "content-length"}},
            text=response.text,
            request=httpx.Request("GET", response.url),
        )

    def fetch(self, url: str) -> str:
        if self.browser is not None or self.proxy:
            response = self._browser_get(url)
        else:
            try:
                response = self.direct.get(url)
            except httpx.DecodingError:
                # Some WebNovel responses fail HTTPX's content decoder before
                # status/challenge checks run. Recover through the browser
                # transport once, then reuse that session for subsequent pages.
                response = self._browser_get(url)
            else:
                if response.status_code == 403 or is_challenge(response):
                    response = self._browser_get(url)

        if is_challenge(response):
            raise DiscoveryChallengeError(
                "WebNovel is blocking access with a browser challenge.",
                request=response.request,
            )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            raise ValueError(f"Expected HTML from WebNovel, got: {content_type}")
        return response.text



def stop_if_blocked(error: Exception) -> None:
    """Stop the run on access failures rather than repeatedly hitting the site."""
    if isinstance(error, DiscoveryChallengeError):
        raise error
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in {401, 403, 429} or status >= 500:
            raise error


def fetch_html(client: DiscoveryClient, url: str) -> str:
    return client.fetch(url)


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


def next_listing_page(html: str, page_url: str) -> list[str]:
    """Follow one next page in the same listing, preserving its filters."""
    tree = HTMLParser(html)
    current = urlparse(page_url)
    filters = parse_qs(current.query)
    page_keys = {"page", "pageIndex", "p", "offset"}
    for node in tree.css("a[href]"):
        parsed = urlparse(urljoin(page_url, node.attributes["href"]))
        if parsed.netloc.lower() != current.netloc.lower() or parsed.path != current.path:
            continue
        params = parse_qs(parsed.query)
        changed = [key for key in page_keys if key in params and params[key] != filters.get(key)]
        if len(changed) != 1:
            continue
        key = changed[0]
        value = params[key][0]
        old = filters.get(key, ["0" if key == "offset" else "1"])[0]
        if not value.isdigit() or not old.isdigit():
            continue
        text = node.text(separator=" ", strip=True).casefold()
        explicit_next = "next" in node.attributes.get("rel", "").split() or text in {
            "next", "next >", ">", "\u203a", "\u2192",
        }
        if int(value) <= int(old):
            continue
        if key == "offset" and not explicit_next:
            continue
        if key != "offset" and int(value) != int(old) + 1:
            continue
        if any(k not in page_keys and k in filters and sorted(v) != sorted(filters[k])
               for k, v in params.items()):
            continue
        merged = {**filters, **params}
        return [urlunparse(current._replace(query=urlencode(merged, doseq=True), fragment=""))]
    return []


def listing_next_links(html: str, page_url: str) -> list[str]:
    return next_listing_page(html, page_url)


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

        if not (parsed.path.startswith("/category/")
                or parsed.path.startswith("/stories/novel-")):
            continue
        if any(key in parse_qs(parsed.query) for key in ("page", "pageIndex", "offset")):
            continue

        normalized = canonical_listing_url(href)
        if normalized:
            found.add(normalized)

    return found


def crawl_listing(
    session: DiscoveryClient,
    seed_url: str,
    page_limit: int,
    first_html: str | None = None,
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
            html = first_html if url == seed_url and first_html is not None else fetch_html(session, url)
        except Exception as exc:
            stop_if_blocked(exc)
            time.sleep(REQUEST_DELAY)
            print(
                "LISTING FAILED:",
                url,
                type(exc).__name__,
                exc,
            )
            continue

        books = extract_book_urls(html, url)
        if not books:
            break
        pages.append(books)

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

def discover_additional_category_seeds(session: DiscoveryClient) -> list[str]:
    found = set()
    for index in ADDITIONAL_SEED_URLS:
        try:
            found.update(extract_category_seed_urls(fetch_html(session, index), index))
        except Exception as exc:
            stop_if_blocked(exc)
            print("CATEGORY INDEX FAILED:", type(exc).__name__, exc)
        finally:
            time.sleep(REQUEST_DELAY)
    return sorted(found)[:MAX_DISCOVERED_CATEGORY_SEEDS]


def discover_candidates() -> dict[str, int]:
    """Count appearances once per independent ranking/genre seed."""
    popularity_hits: dict[str, int] = {}
    with DiscoveryClient() as client:
        preloaded: dict[str, str] = {}
        categories: set[str] = set()
        for index in ADDITIONAL_SEED_URLS:
            try:
                html = fetch_html(client, index)
                preloaded[index] = html
                categories.update(extract_category_seed_urls(html, index))
            except Exception as exc:
                stop_if_blocked(exc)
                print("CATEGORY INDEX FAILED:", index, type(exc).__name__, exc)
            finally:
                time.sleep(REQUEST_DELAY)
        # Actual genre catalogs come before keyword searches, which can contain
        # books merely mentioning a genre in their title or description.
        seeds = list(dict.fromkeys(
            RANKING_SEED_URLS + ADDITIONAL_SEED_URLS
            + sorted(categories)[:MAX_DISCOVERED_CATEGORY_SEEDS]
            + [search_url(genre) for genre in GENRE_QUERIES]
        ))
        print("\n=== DISCOVERING POPULAR WEBNOVEL CANDIDATES ===")
        for seed in seeds:
            print("SEED:", seed)
            books = set().union(*crawl_listing(
                client, seed,
                MAX_ADDITIONAL_PAGES_PER_SEED if seed in categories or seed in ADDITIONAL_SEED_URLS
                else MAX_PAGES_PER_SEED,
                first_html=preloaded.get(seed),
            ))
            for url in sorted(books):
                popularity_hits[url] = popularity_hits.get(url, 0) + 1
            print("Unique candidates so far:", len(popularity_hits))
        try:
            for url in sorted(extract_book_urls(fetch_html(client, BASE_URL), BASE_URL)):
                popularity_hits[url] = popularity_hits.get(url, 0) + 1
        except Exception as exc:
            stop_if_blocked(exc)
            print("HOMEPAGE FAILED:", type(exc).__name__, exc)
        finally:
            time.sleep(REQUEST_DELAY)
    print("Total discovered candidates:", len(popularity_hits))
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
    *, title: str | None, synopsis: str | None, total_score: float | None,
    total_review_num: int | None, popularity_hits: int, read_count: int | None = None,
) -> tuple[float, list[str]]:
    score = math.log10((read_count or 0) + 1) * 10.0
    reasons = [f"reads={read_count}", f"listing-hits={popularity_hits}"]
    if total_score is not None:
        count = total_review_num or 0
        confidence = count / (count + 100)
        adjusted = confidence * total_score + (1 - confidence) * 3.8
        score += max(-2.0, adjusted - 3.8)
        reasons.append(f"total_score={total_score}")
    if total_review_num is not None:
        score += min(4.0, math.log10(total_review_num + 1)) * 0.25
        reasons.append(f"total_review_num={total_review_num}")
    score += min(popularity_hits, 10) * 0.05
    _, notes = synopsis_quality_penalty(title, synopsis)
    reasons.extend(f"presentation:{reason}" for reason in notes)
    return score, reasons


# ---------------------------------------------------------------------
# SCRAPE, HARD-FILTER, AND SCORE
# ---------------------------------------------------------------------

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



def description_disclosures(*texts: str) -> list[str]:
    reasons = []
    for text in texts:
        text = re.sub(r"\s+", " ", text or "")
        for match in SEXUAL_DISCLOSURE.finditer(text):
            prefix = text[max(0, match.start() - 70):match.start()]
            suffix = text[match.end():match.end() + 6]
            if NEGATED_DISCLOSURE.search(prefix) or re.match(r"[- ]free\b", suffix, re.I):
                continue
            label = f"description:{match.group(0).casefold()}"
            if label not in reasons:
                reasons.append(label)
    return reasons


def extract_book_info(html: str, story_id: int) -> dict:
    """Read only g_data.book.bookInfo; reviews contain unrelated scores/counts."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script"):
        text = node.get_text()
        marker = re.search(r"g_data\.book\s*=\s*", text)
        if not marker:
            continue
        raw = text[marker.end():]
        # WebNovel JS strings escape spaces/apostrophes, unlike valid JSON.
        raw = re.sub(
            r'\\(?:u[0-9a-fA-F]{4}|.)',
            lambda match: match.group(0) if match.group(0)[1] in '"\\/bfnrtu'
            else match.group(0)[1:],
            raw,
        )
        try:
            data, _ = json.JSONDecoder().raw_decode(raw.lstrip())
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        info = data.get("bookInfo", data)
        if isinstance(info, dict) and str(info.get("bookId")) == str(story_id):
            return info
    return {}


def parse_count(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().casefold().replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([km])?", text)
    if not match:
        return None
    count = float(match.group(1)) * {None: 1, "k": 1000, "m": 1000000}[match.group(2)]
    return int(count) if math.isfinite(count) else None


def extract_book_metrics(html: str, story_id: int) -> tuple:
    info = extract_book_info(html, story_id)
    reads = parse_count(info.get("pvNum"))
    reviews = parse_count(info.get("totalReviewNum"))
    score = info.get("totalScore")
    try:
        score = float(score)
        if not 0 <= score <= 5:
            score = None
    except (ValueError, TypeError):
        score = None
    soup = BeautifulSoup(html, "html.parser")
    if reviews is None:
        node = soup.select_one(".j_total_book_review")
        if node is not None:
            reviews = parse_count(node.get_text(strip=True))
    if reads is None:
        # Match compact leaf labels instead of page text containing reviews.
        for node in soup.select("span"):
            text = node.get_text(" ", strip=True)
            match = re.fullmatch(r"(\d[\d,.]*\s*[KkMm]?)\s+Views", text, re.I)
            if match:
                reads = parse_count(match.group(1))
                break
    return reads, score, reviews


def sexual_content_reasons(html: str, novel: dict) -> list[str]:
    reasons = find_policy_violations("webnovel", novel)
    info = extract_book_info(html, novel["story_id"])
    texts = [novel.get("title") or "", novel.get("synopsis") or ""]
    if isinstance(info.get("description"), str):
        texts.append(BeautifulSoup(info["description"], "html.parser").get_text(" ", strip=True))
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select(".book-desc, .bookDesc, .book-description, .synopsis"):
        texts.append(node.get_text(" ", strip=True))
    # Preserve the source policy's conservative mature/adult exclusions.
    rating = info.get("ageGroup")
    if rating:
        reasons.extend(find_policy_violations("webnovel", {"tags": [rating]}))
    for key in ("mature", "isMature", "is_mature"):
        if info.get(key) is True or str(info.get(key)).casefold() in {"1", "true"}:
            reasons.append("metadata:mature")
            break
    reasons.extend(description_disclosures(*texts))
    return list(dict.fromkeys(reasons))


def scrape_and_score(popularity_hits: dict[str, int]) -> list[Candidate]:
    unique_hits: dict[str, int] = {}
    for url, hits in popularity_hits.items():
        canonical = canonical_book_url(url)
        if canonical:
            unique_hits[canonical] = max(hits, unique_hits.get(canonical, 0))
    candidates: list[Candidate] = []
    consecutive_server_errors = 0
    print(f"\n=== SCRAPING AND CLASSIFYING {len(unique_hits)} CANDIDATES ===")
    with DiscoveryClient() as client:
        for index, (url, hits) in enumerate(unique_hits.items(), start=1):
            print(f"[{index}/{len(unique_hits)}] {url}")
            try:
                html = fetch_html(client, url)
                consecutive_server_errors = 0
                # Avoid the extra review API request. This page already exposes
                # the counts needed to rank and validate the book.
                novel = parse_webnovel(html, url, include_statistics=False)
                violations = sexual_content_reasons(html, novel)
                if violations:
                    print(f"SKIPPED: {novel['title']!r} (content policy: {violations})")
                    continue
                reads, rating, reviews = extract_book_metrics(html, novel["story_id"])
                if reads is None or reads < MIN_READ_COUNT:
                    print(f"SKIPPED: {novel['title']!r} (reads={reads})")
                    continue
                if rating is not None and rating < MIN_TOTAL_SCORE:
                    print(f"SKIPPED: {novel['title']!r} (rating={rating})")
                    continue
                if reviews is not None and reviews < MIN_TOTAL_REVIEW_NUM:
                    print(f"SKIPPED: {novel['title']!r} (reviews={reviews})")
                    continue
                score, reasons = score_popularity(
                    title=novel["title"], synopsis=novel.get("synopsis"),
                    read_count=reads, total_score=rating, total_review_num=reviews,
                    popularity_hits=hits,
                )
                candidates.append(Candidate(
                    url=url, story_id=novel["story_id"], title=novel["title"],
                    synopsis=novel.get("synopsis"), genres=novel["genres"],
                    tags=novel["tags"], read_count=reads, total_score=rating,
                    total_review_num=reviews, popularity_hits=hits,
                    popularity_score=score, quality_reasons=reasons,
                ))
                print(f"PARSED: {novel['title']!r} (reads={reads}, rating={rating}, reviews={reviews})")
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
# POPULARITY-FIRST, GENRE-DIVERSE SELECTION
# ---------------------------------------------------------------------

def popularity_rank(candidate: Candidate) -> tuple:
    return (candidate.read_count or 0, candidate.popularity_score, candidate.total_review_num or 0, -(candidate.story_id or 0))


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
        key = str(candidate.story_id) if candidate.story_id is not None else (
            canonical_book_url(candidate.url) or candidate.url
        )
        unique.setdefault(key, candidate)
    ranked = list(unique.values())
    if len(ranked) <= target:
        return ranked

    diversity_seats = min(target - 1, math.floor(target * DIVERSITY_SHARE))
    selected = ranked[:target - diversity_seats]
    selected_urls = {c.url for c in selected}
    counts = Counter(genre for c in selected for genre in candidate_genres(c))
    cutoff = max(MIN_READ_COUNT, (ranked[target - 1].read_count or 0)
                 * DIVERSITY_POPULARITY_RATIO)
    pools: dict[str, list[Candidate]] = {}
    for candidate in ranked[len(selected):]:
        if (candidate.read_count or 0) < cutoff:
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
            key=popularity_rank,
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

    if not selected:
        raise RuntimeError("No eligible novels found; existing outputs were preserved.")
    write_outputs(selected, candidates)

    genre_counts = Counter(genre for c in selected for genre in candidate_genres(c))

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

    print("\nGenre coverage (novels can count in multiple genres):")

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
            f"reads={candidate.read_count} score={candidate.total_score} "
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
