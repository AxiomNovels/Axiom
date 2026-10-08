"""Discover popular Wattpad stories with strict metadata content filtering.

Each story page is fetched once. Story-scoped reads drive ranking; votes and
comments break ties. Keep a popular 80% core and use 20% of seats to improve
genre coverage, subject to an established-popularity floor.
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
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx
from curl_cffi import requests as browser_requests
from selectolax.parser import HTMLParser

from scraper.wattpad import BASE_URL, HEADERS, parse_wattpad
from scraper.content_policy import EXCLUDED_TAGS_BY_SOURCE, find_policy_violations


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TARGET = 250
TARGET_TOLERANCE = 10
MIN_TARGET = TARGET - TARGET_TOLERANCE

MIN_DISCOVERED = 1500

REQUEST_DELAY = 0.40
MAX_PAGES_PER_SEED = 20

# Most seats follow popularity; a bounded share improves genre coverage.
DIVERSITY_SHARE = 0.20
DIVERSITY_POPULARITY_RATIO = 0.25

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

# Source-specific banned labels are matched using the shared policy normalizer.
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

    path = f"/story/{int(match.group(1))}"

    return urlunparse(("https", "www.wattpad.com", path, "", "", ""))


PROXY_URL = None


class DiscoveryChallengeError(httpx.RequestError):
    """Wattpad served a browser challenge instead of the requested page."""


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
                f"Wattpad browser request failed ({type(error).__name__}).",
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
            response = self.direct.get(url)
            if response.status_code == 403 or is_challenge(response):
                response = self._browser_get(url)

        if is_challenge(response):
            raise DiscoveryChallengeError(
                "Wattpad is blocking access with a browser challenge.",
                request=response.request,
            )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            raise ValueError(f"Expected HTML from Wattpad, got: {content_type}")
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


def extract_listing_links(html: str, page_url: str) -> list[str]:
    return next_listing_page(html, page_url)


def crawl_listing(
    client: DiscoveryClient,
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
            time.sleep(REQUEST_DELAY)
            print("LISTING FAILED:", url, type(exc).__name__, exc)
            continue

        stories = extract_story_urls(html, url)
        if not stories:
            break
        pages.append(stories)

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

    with DiscoveryClient() as client:
        print("\n=== DISCOVERING POPULAR WATTPAD CANDIDATES ===")

        for seed in POPULAR_SEED_URLS:
            print("SEED:", seed)

            stories = set().union(*crawl_listing(client, seed, MAX_PAGES_PER_SEED))
            for url in sorted(stories):
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


def story_records(value: Any, story_id: int) -> list[dict]:
    """Find only this story's records, excluding users and recommendations."""
    found = []
    if isinstance(value, dict):
        identity = value.get("story_id", value.get("storyId", value.get("id")))
        if str(identity) == str(story_id) and "title" in value:
            found.append(value)
        for child in value.values():
            found.extend(story_records(child, story_id))
    elif isinstance(value, list):
        for child in value:
            found.extend(story_records(child, story_id))
    return found


def extract_story_metrics(
    html: str, story_id: int | None = None,
) -> tuple[int | None, int | None, int | None]:
    """Read story-scoped Remix counts, then fall back to visible story labels."""
    context = extract_remix_context(html)
    records = story_records(context, story_id) if story_id is not None else []
    aliases = (
        {"readcount", "reads", "numreads", "totalreads", "readnumber"},
        {"votecount", "votes", "numvotes", "totalvotes", "voteamount"},
        {"commentcount", "comments", "numcomments", "totalcomments"},
    )
    metrics: list[int | None] = []
    tree = HTMLParser(html)
    scope = tree.css_first("[data-testid='story-stats'], .story-stats, .story-info")
    # Unscoped recommendations cannot supply a missing metric.
    text = (scope or tree).text(separator=" ", strip=True) if context is None or scope else ""
    for names, label in zip(aliases, ("reads?", "votes?", "comments?")):
        values = []
        for record in records:
            for key, child in record.items():
                if re.sub(r"[^a-z0-9]", "", str(key).casefold()) in names:
                    number = parse_count(child)
                    if number is not None and number >= 0:
                        values.append(number)
        if values:
            metrics.append(max(values))
            continue
        value = None
        for pattern in (
            rf"\b{label}\s*[:\-]?\s*(\d[\d,]*(?:\.\d+)?\s*[KkMm]?)",
            rf"(\d[\d,]*(?:\.\d+)?\s*[KkMm]?)\s+{label}\b",
        ):
            match = re.search(pattern, text, re.I)
            if match:
                value = parse_count(match.group(1))
                break
        metrics.append(value)
    return tuple(metrics)


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
        score += math.log10(read_count + 1) * 10.0
        reasons.append(f"reads={read_count}")

    if vote_count is not None:
        score += min(4.0, math.log10(vote_count + 1)) * 0.25
        reasons.append(f"votes={vote_count}")

    if comment_count is not None:
        score += min(4.0, math.log10(comment_count + 1)) * 0.10
        reasons.append(f"comments={comment_count}")

    score += min(popularity_hits, 10) * 0.05
    reasons.append(f"listing-hits={popularity_hits}")

    _, penalty_reasons = synopsis_quality_penalty(title, synopsis)
    reasons.extend(f"presentation:{reason}" for reason in penalty_reasons)

    return score, reasons


# ---------------------------------------------------------------------
# Scrape, hard-filter, and score
# ---------------------------------------------------------------------

# Reads are required to establish popularity. Votes enforce their floor when
# available; missing reads cannot be replaced by listing appearances.
MIN_VOTE_COUNT = 50
MIN_READ_COUNT = 5_000


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


def sexual_content_reasons(html: str, novel: dict) -> list[str]:
    reasons = find_policy_violations("wattpad", novel)
    tree = HTMLParser(html)
    texts = [novel.get("title") or "", novel.get("synopsis") or ""]
    if tree.css_first("[data-testid='mature-badge'], [aria-label='Mature']") is not None:
        reasons.append("metadata:mature")
    for node in tree.css(".story-description, [data-testid='story-description'], div._66soR.waz33"):
        texts.append(node.text(separator=" ", strip=True))
    for record in story_records(extract_remix_context(html), novel["story_id"]):
        # Mature is a conservative discovery exclusion, even if no tags say so.
        for key in ("mature", "isMature", "is_mature"):
            if record.get(key) is True or str(record.get(key)).casefold() in {"1", "true"}:
                reasons.append("metadata:mature")
                break
        for key in ("description", "synopsis"):
            if isinstance(record.get(key), str):
                texts.append(HTMLParser(record[key]).text(separator=" ", strip=True))
    reasons.extend(description_disclosures(*texts))
    return list(dict.fromkeys(reasons))


def scrape_and_score(popularity_hits: dict[str, int]) -> list[Candidate]:
    unique_hits: dict[str, int] = {}
    for url, hits in popularity_hits.items():
        canonical = canonical_story_url(url)
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
                novel = parse_wattpad(html, url)
                if not novel.get("title") or not novel.get("author"):
                    print("SKIPPED: incomplete story metadata")
                    continue
                violations = sexual_content_reasons(html, novel)
                if violations:
                    print(f"SKIPPED: {novel['title']!r} (content policy: {violations})")
                    continue
                reads, votes, comments = extract_story_metrics(html, novel["story_id"])
                if reads is None or reads < MIN_READ_COUNT:
                    print(f"SKIPPED: {novel['title']!r} (reads={reads})")
                    continue
                if votes is not None and votes < MIN_VOTE_COUNT:
                    print(f"SKIPPED: {novel['title']!r} (votes={votes})")
                    continue
                score, reasons = score_popularity(
                    title=novel["title"], synopsis=novel.get("synopsis"),
                    read_count=reads, vote_count=votes, comment_count=comments,
                    popularity_hits=hits,
                )
                candidates.append(Candidate(
                    url=url, story_id=novel["story_id"], title=novel["title"],
                    synopsis=novel.get("synopsis"), genres=novel["genres"],
                    tags=novel["tags"], read_count=reads, vote_count=votes,
                    comment_count=comments, popularity_hits=hits,
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
    return (candidate.read_count or 0, candidate.vote_count or 0, candidate.comment_count or 0, candidate.popularity_score, -(candidate.story_id or 0))


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
            canonical_story_url(candidate.url) or candidate.url
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
            key=popularity_rank,
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

    if not selected:
        raise RuntimeError("No eligible novels found; existing outputs were preserved.")
    write_outputs(selected, candidates)

    genre_counts = Counter(genre for c in selected for genre in candidate_genres(c))

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

    print("\nGenre coverage (novels can count in multiple genres):")
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
