"""
Discover popular philosophical / psychological Wattpad stories.

This script is the Wattpad counterpart to the current WebNovel discovery
pipeline. It deliberately separates:

    discovery / popularity
    quality / popularity thresholds
    philosophical / psychological relevance
    hard banned-tag exclusion

It uses scraper.wattpad.scrape_wattpad() for final story parsing.

Outputs
-------
philosophical_wattpad_urls.txt
philosophical_wattpad_audit.csv
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote, urljoin, urlparse, urlunparse

import httpx
from selectolax.parser import HTMLParser

from scraper.wattpad import (
    BASE_URL,
    HEADERS,
    scrape_wattpad,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

TARGET = 100
MIN_TARGET = 50
MIN_DISCOVERED = 500

REQUEST_DELAY = 0.40
MAX_PAGES_PER_SEED = 40
MAX_SEARCH_PAGES = 20

# Wattpad discovery surfaces. The exact HTML can change, so discovery is
# intentionally link-driven rather than dependent on a single CSS selector.
POPULAR_SEED_URLS = [
    f"{BASE_URL}/stories",
    f"{BASE_URL}/stories/romance",
    f"{BASE_URL}/stories/fantasy",
    f"{BASE_URL}/stories/mystery",
    f"{BASE_URL}/stories/thriller",
    f"{BASE_URL}/stories/horror",
    f"{BASE_URL}/stories/science-fiction",
    f"{BASE_URL}/stories/adventure",
    f"{BASE_URL}/stories/villain",
]

# These are recall-expansion queries, not a popularity ranking by themselves.
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

# Strict lewd-content exclusion requested for the project.
EXCLUDED_TAGS = {
    # General mature or explicit content
    "adultcontent",
    "adultfiction",
    "adultonly",
    "adultromance",
    "adults",
    "explicit",
    "explicitcontent",
    "explicitromance",
    "mature",
    "matureaudience",
    "maturecontent",
    "maturethemes",
    "matureromance",
    "notworkfriendly",
    "nsfw",
    "ratedm",
    "restricted",
    "spicy",
    "spicyromance",

    # Erotica and sexual content
    "erotica",
    "erotic",
    "eroticfiction",
    "eroticromance",
    "eroticstory",
    "hotromance",
    "lemon",
    "lemons",
    "lime",
    "mature scenes",
    "maturescenes",
    "naughtystory",
    "sensual",
    "sexual",
    "sexualcontent",
    "sexualthemes",
    "sexscene",
    "sexscenes",
    "smut",
    "smutfiction",
    "smutty",
    "steamy",
    "steamyromance",

    # Lust-driven characters or plots
    "carnal",
    "desire",
    "horny",
    "lecherous",
    "libido",
    "lust",
    "lustful",
    "lustfulmalelead",
    "lustfulmc",
    "lustfulprotagonist",
    "perverted",
    "pervertedmc",
    "pervertmc",
    "seduction",
    "seductive",
    "sexaddict",
    "sexaddiction",
    "sexdriven",

    # Harems and partner collecting
    "allmaleharem",
    "allfemaleharem",
    "boyharem",
    "femaleharem",
    "girlharem",
    "harem",
    "haremcollection",
    "haremcomedy",
    "haremfantasy",
    "haremking",
    "haremlit",
    "haremromance",
    "haremseeking",
    "haremseekingmc",
    "haremstory",
    "maleharem",
    "multiharem",
    "multipleloveinterests",
    "multiplepartners",
    "polygamy",
    "polyamory",
    "reverseharem",
    "rh",
    "whychoose",
    "whychooseromance",

    # Romance-first or hookup-focused content
    "badboyromance",
    "billionaireromance",
    "hookup",
    "hookups",
    "mafia romance",
    "mafiaromance",

    # Fetish-oriented content
    "agegapromance",
    "bdsm",
    "bondage",
    "breeding",
    "breedingkink",
    "dominance",
    "dominant",
    "dominantmale",
    "domsub",
    "fetish",
    "kink",
    "kinky",
    "masterandslave",
    "omegaverse",
    "possessiveromance",
    "submissive",
    "sugarbaby",
    "sugardaddy",

    # Sexualized supernatural categories
    "alphamate",
    "alpharomance",
    "demonlover",
    "fatedmates",
    "incubus",
    "matebond",
    "mates",
    "monsterromance",
    "paranormalromance",
    "succubus",
    "vampireromance",
    "werewolfromance",

    # Common relationship-category tags
    # Include these only if you want to reject the entire category,
    # including stories that are romantic but not sexually explicit.
    "bl",
    "boylove",
    "boys love",
    "boyxboy",
    "bx b",
    "bxb",
    "femslash",
    "girl love",
    "girls love",
    "girlxgirl",
    "gl",
    "gxg",
    "lesbianromance",
    "lgbtromance",
    "mxm",
    "wlw",
    "yaoi",
    "yuri",

    # Exploitative or abusive sexual themes
    "ageplay",
    "dubcon",
    "forcedmarriage",
    "incest",
    "noncon",
    "nonconsensual",
    "rape",
    "rapefantasy",
    "sexualabuse",
    "sexualassault",
    "stepbrotherromance",
    "stepsiblingromance",
    "teacherstudent",
    "toxicromance",

    # Pregnancy or reproduction-centered romance
    "accidentalpregnancy",
    "babydaddy",
    "mpreg",
    "pregnancy",
    "pregnancyromance",
    "secretbaby",
}


# Quality / popularity thresholds.
#
# Wattpad exposes different metric shapes depending on the current page and
# route loader. A story is rejected only when the metric is actually found and
# known to fail a threshold. Missing metrics are recorded in the audit rather
# than fabricated.
MIN_VOTE_COUNT = 100
MIN_READ_COUNT = 10_000

# A relevance threshold prevents weak one-keyword matches from reaching the
# final list.
MIN_RELEVANCE_SCORE = 5.0


# ---------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------

@dataclass
class Candidate:
    url: str
    story_id: int | None
    title: str | None
    synopsis: str | None
    tags: list[str]

    read_count: int | None
    vote_count: int | None
    comment_count: int | None

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

def canonical_story_url(
    url: str,
) -> str | None:
    absolute = urljoin(
        BASE_URL,
        url,
    )

    parsed = urlparse(
        absolute,
    )

    if parsed.netloc.lower() not in {
        "www.wattpad.com",
        "wattpad.com",
    }:
        return None

    match = re.match(
        r"^/story/(\d+)(?:-[^/?#]+)?/?$",
        parsed.path,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    path = parsed.path.rstrip("/")

    return urlunparse(
        (
            "https",
            "www.wattpad.com",
            path,
            "",
            "",
            "",
        )
    )


def fetch_html(
    client: httpx.Client,
    url: str,
) -> str:
    response = client.get(
        url,
        follow_redirects=True,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        "",
    )

    if "text/html" not in content_type.lower():
        raise ValueError(
            f"Expected HTML from Wattpad, got: {content_type}"
        )

    return response.text


def extract_story_urls(
    html: str,
    page_url: str,
) -> set[str]:
    tree = HTMLParser(
        html,
    )

    urls: set[str] = set()

    for node in tree.css(
        "a[href]",
    ):
        href = node.attributes.get(
            "href",
        )

        if not href:
            continue

        story_url = canonical_story_url(
            urljoin(
                page_url,
                href,
            )
        )

        if story_url:
            urls.add(
                story_url
            )

    return urls


def extract_listing_links(
    html: str,
    page_url: str,
) -> list[str]:
    """
    Find same-family listing/search links.

    Wattpad's pagination has changed historically, so this follows explicit
    links instead of assuming a fixed page query parameter.
    """
    tree = HTMLParser(
        html,
    )

    current = urlparse(
        page_url,
    )

    links: list[str] = []

    for node in tree.css(
        "a[href]",
    ):
        href = node.attributes.get(
            "href",
        )

        if not href:
            continue

        absolute = urljoin(
            page_url,
            href,
        )

        parsed = urlparse(
            absolute,
        )

        if parsed.netloc.lower() not in {
            "www.wattpad.com",
            "wattpad.com",
        }:
            continue

        if parsed.path.startswith(
            "/story/",
        ):
            continue

        # Keep only story/search browsing surfaces.
        if not (
            parsed.path.startswith("/stories")
            or parsed.path.startswith("/search")
        ):
            continue

        # Avoid wandering into unrelated listing families.
        if current.path.startswith("/search"):
            if not parsed.path.startswith("/search"):
                continue

        text = re.sub(
            r"\s+",
            " ",
            node.text(
                separator=" ",
                strip=True,
            ),
        ).strip().lower()

        rel = (
            node.attributes.get("rel")
            or ""
        ).lower()

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
            or "page=" in parsed.query.lower()
        ):
            links.append(
                absolute
            )

    # Preserve order while removing duplicates.
    return list(
        dict.fromkeys(
            links
        )
    )


def crawl_listing(
    client: httpx.Client,
    seed_url: str,
    page_limit: int,
) -> list[set[str]]:
    queue = deque(
        [seed_url]
    )

    seen: set[str] = set()

    pages: list[set[str]] = []

    while (
        queue
        and len(pages) < page_limit
    ):
        url = queue.popleft()

        if url in seen:
            continue

        seen.add(
            url
        )

        try:
            html = fetch_html(
                client,
                url,
            )

        except Exception as exc:
            print(
                "LISTING FAILED:",
                url,
                type(exc).__name__,
                exc,
            )
            continue

        pages.append(
            extract_story_urls(
                html,
                url,
            )
        )

        for next_url in extract_listing_links(
            html,
            url,
        ):
            if next_url not in seen:
                queue.append(
                    next_url
                )

        time.sleep(
            REQUEST_DELAY
        )

    return pages


def wattpad_search_url(
    query: str,
) -> str:
    return (
        f"{BASE_URL}/search/"
        f"{quote(query, safe='')}"
    )


def discover_candidates() -> tuple[
    dict[str, int],
    dict[str, int],
]:
    popularity_hits: dict[str, int] = {}
    search_hits: dict[str, int] = {}

    with httpx.Client(
        headers=HEADERS,
        timeout=30,
    ) as client:

        print(
            "\n=== DISCOVERING POPULAR WATTPAD CANDIDATES ==="
        )

        for seed in POPULAR_SEED_URLS:
            print(
                "POPULAR SEED:",
                seed,
            )

            for stories in crawl_listing(
                client,
                seed,
                MAX_PAGES_PER_SEED,
            ):
                for url in stories:
                    popularity_hits[url] = (
                        popularity_hits.get(
                            url,
                            0,
                        )
                        + 1
                    )

            print(
                "Unique popularity candidates:",
                len(
                    popularity_hits
                ),
            )

        print(
            "\n=== DISCOVERING CONCEPT CANDIDATES ==="
        )

        for query in SEARCH_QUERIES:
            url = wattpad_search_url(
                query,
            )

            print(
                "SEARCH:",
                query,
            )

            for stories in crawl_listing(
                client,
                url,
                MAX_SEARCH_PAGES,
            ):
                for story_url in stories:
                    search_hits[story_url] = (
                        search_hits.get(
                            story_url,
                            0,
                        )
                        + 1
                    )

            time.sleep(
                REQUEST_DELAY
            )

    print(
        "Popularity candidates:",
        len(
            popularity_hits
        ),
    )

    print(
        "Concept-search candidates:",
        len(
            search_hits
        ),
    )

    return (
        popularity_hits,
        search_hits,
    )


# ---------------------------------------------------------------------
# Embedded Wattpad metadata
# ---------------------------------------------------------------------

def normalize_text(
    value: str | None,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").lower(),
    ).strip()


def parse_count(
    value: Any,
) -> int | None:
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return int(
            value
        )

    text = str(
        value
    ).strip().lower().replace(
        ",",
        "",
    )

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*([km])?",
        text,
    )

    if not match:
        return None

    number = float(
        match.group(1)
    )

    suffix = match.group(2)

    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000

    return int(
        number
    )


def find_metric_values(
    value: Any,
    aliases: set[str],
    found: list[int],
) -> None:
    """
    Recursively inspect Wattpad Remix data.

    We only collect values from explicitly named metric keys. Generic keys such
    as "count" are intentionally ignored.
    """
    if isinstance(
        value,
        dict,
    ):
        for key, child in value.items():
            normalized_key = re.sub(
                r"[^a-z0-9]",
                "",
                str(
                    key
                ).lower(),
            )

            if normalized_key in aliases:
                parsed = parse_count(
                    child
                )

                if parsed is not None:
                    found.append(
                        parsed
                    )

            find_metric_values(
                child,
                aliases,
                found,
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            find_metric_values(
                child,
                aliases,
                found,
            )


def extract_remix_context(
    html: str,
) -> Any | None:
    tree = HTMLParser(
        html,
    )

    marker = (
        "window.__remixContext = "
    )

    for script in tree.css(
        "script",
    ):
        text = script.text()

        if not text or marker not in text:
            continue

        start = text.find(
            marker
        )

        json_text = text[
            start + len(marker):
        ].strip()

        if json_text.endswith(
            ";"
        ):
            json_text = json_text[:-1]

        try:
            return json.loads(
                json_text
            )

        except json.JSONDecodeError:
            continue

    return None


def extract_story_metrics(
    html: str,
) -> tuple[
    int | None,
    int | None,
    int | None,
]:
    """
    Best-effort extraction of reads, votes and comments.

    The parser searches embedded Remix metadata first, then falls back to
    explicit visible labels.
    """
    context = extract_remix_context(
        html,
    )

    read_values: list[int] = []
    vote_values: list[int] = []
    comment_values: list[int] = []

    if context is not None:
        find_metric_values(
            context,
            {
                "readcount",
                "reads",
                "numreads",
                "totalreads",
                "readnumber",
            },
            read_values,
        )

        find_metric_values(
            context,
            {
                "votecount",
                "votes",
                "numvotes",
                "totalvotes",
                "voteamount",
            },
            vote_values,
        )

        find_metric_values(
            context,
            {
                "commentcount",
                "comments",
                "numcomments",
                "totalcomments",
            },
            comment_values,
        )

    def visible_metric(
        labels: tuple[str, ...],
    ) -> int | None:
        for label in labels:
            patterns = [
                rf"(\d+(?:\.\d+)?\s*[KkMm]?)\s+{label}\b",
                rf"\b{label}\s*[:\-]?\s*(\d+(?:\.\d+)?\s*[KkMm]?)",
            ]

            for pattern in patterns:
                match = re.search(
                    pattern,
                    html,
                    flags=re.IGNORECASE,
                )

                if match:
                    parsed = parse_count(
                        match.group(1)
                    )

                    if parsed is not None:
                        return parsed

        return None

    read_count = (
        max(read_values)
        if read_values
        else visible_metric(
            (
                "reads",
                "read",
            )
        )
    )

    vote_count = (
        max(vote_values)
        if vote_values
        else visible_metric(
            (
                "votes",
                "vote",
            )
        )
    )

    comment_count = (
        max(comment_values)
        if comment_values
        else visible_metric(
            (
                "comments",
                "comment",
            )
        )
    )

    return (
        read_count,
        vote_count,
        comment_count,
    )


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
    "nature of reality": 8,
    "truth and meaning": 7,
    "nihilism": 9,
    "absurdism": 9,
    "stoic": 7,
    "stoicism": 8,
    "belief system": 5,
    "questioning reality": 7,
    "what it means to be human": 9,
    "what does it mean to be human": 9,
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
    "behavioral": 5,
    "human behavior": 7,
    "cognitive": 7,
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

STRONG_TAGS = {
    "philosophy",
    "philosophical",
    "psychology",
    "psychological",
    "psychological thriller",
    "mental health",
    "psychological horror",
}

INCIDENTAL_PATTERNS = {
    "psychologically painful": 4,
    "psychological threshold": 3,
    "psychological warning": 4,
}


def count_pattern(
    text: str,
    pattern: str,
) -> int:
    return len(
        re.findall(
            re.escape(
                pattern
            ),
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
    title_text = normalize_text(
        title
    )

    synopsis_text = normalize_text(
        synopsis
    )

    combined = (
        f"{title_text} {synopsis_text}"
    ).strip()

    tag_set = {
        normalize_text(
            tag
        )
        for tag in tags
        if normalize_text(
            tag
        )
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
            score += min(
                hits,
                2,
            ) * weight

            reasons.append(
                f"philosophy:{phrase}"
            )

            if phrase in title_text:
                score += weight * 0.20
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
            score += min(
                hits,
                2,
            ) * weight

            reasons.append(
                f"psychology:{phrase}"
            )

            if phrase in title_text:
                score += weight * 0.20
                reasons.append(
                    f"title:{phrase}"
                )

    for tag in tag_set:
        if tag in STRONG_TAGS:
            score += 12
            reasons.append(
                f"strong-tag:{tag}"
            )

    score += min(
        philosophy_hits,
        6,
    ) * 1.5

    score += min(
        psychology_hits,
        6,
    ) * 1.5

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

    if len(
        set(reasons)
    ) >= 4:
        score += 6
        reasons.append(
            "multi-signal"
        )

    return (
        score,
        reasons,
    )


def has_enough_relevance_evidence(
    reasons: list[str],
) -> bool:
    concepts = {
        reason.split(
            ":",
            1,
        )[1]
        for reason in reasons
        if reason.startswith(
            (
                "philosophy:",
                "psychology:",
            )
        )
    }

    domains = {
        reason.split(
            ":",
            1,
        )[0]
        for reason in reasons
        if reason.startswith(
            (
                "philosophy:",
                "psychology:",
            )
        )
    }

    corroboration = any(
        reason.startswith(
            "strong-tag:"
        )
        for reason in reasons
    )

    return (
        len(concepts) >= 2
        or len(domains) >= 2
        or (
            len(concepts) >= 1
            and corroboration
        )
    )


# ---------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------

def synopsis_quality_penalty(
    title: str | None,
    synopsis: str | None,
) -> tuple[
    float,
    list[str],
]:
    title = title or ""
    synopsis = synopsis or ""

    text = (
        f"{title} {synopsis}"
    ).strip()

    if not text:
        return (
            12.0,
            ["missing-synopsis"],
        )

    penalty = 0.0
    reasons: list[str] = []

    letters = [
        char
        for char in text
        if char.isalpha()
    ]

    if letters:
        upper_ratio = (
            sum(
                char.isupper()
                for char in letters
            )
            / len(letters)
        )

        if (
            upper_ratio > 0.45
            and len(letters) > 30
        ):
            penalty += 4
            reasons.append(
                "excessive-capitalization"
            )

    if re.search(
        r"([!?])\1{2,}",
        text,
    ):
        penalty += 2
        reasons.append(
            "excessive-punctuation"
        )

    words = re.findall(
        r"[A-Za-z']+",
        synopsis.lower(),
    )

    if len(words) < 25:
        penalty += 4
        reasons.append(
            "very-short-synopsis"
        )

    if len(words) >= 40:
        unique_ratio = (
            len(
                set(words)
            )
            / len(words)
        )

        if unique_ratio < 0.35:
            penalty += 3
            reasons.append(
                "low-lexical-variety"
            )

    return (
        penalty,
        reasons,
    )


def score_quality(
    *,
    title: str | None,
    synopsis: str | None,
    read_count: int | None,
    vote_count: int | None,
    comment_count: int | None,
    popularity_hits: int,
    search_hits: int,
) -> tuple[
    float,
    list[str],
]:
    score = 0.0
    reasons: list[str] = []

    # Log scaling avoids allowing one enormous story to overwhelm relevance.
    if read_count is not None:
        score += min(
            8.0,
            math.log10(
                read_count + 1
            ) * 1.2,
        )

        reasons.append(
            f"reads={read_count}"
        )

    if vote_count is not None:
        score += min(
            8.0,
            math.log10(
                vote_count + 1
            ) * 1.5,
        )

        reasons.append(
            f"votes={vote_count}"
        )

    if comment_count is not None:
        score += min(
            4.0,
            math.log10(
                comment_count + 1
            ),
        )

        reasons.append(
            f"comments={comment_count}"
        )

    score += min(
        popularity_hits,
        8,
    ) * 1.5

    if popularity_hits:
        reasons.append(
            f"popularity-surfaces={popularity_hits}"
        )

    score += min(
        search_hits,
        5,
    ) * 0.25

    penalty, penalty_reasons = synopsis_quality_penalty(
        title,
        synopsis,
    )

    score -= penalty

    reasons.extend(
        f"presentation:{reason}"
        for reason in penalty_reasons
    )

    return (
        score,
        reasons,
    )


# ---------------------------------------------------------------------
# Scrape, filter and select
# ---------------------------------------------------------------------

def scrape_and_score(
    popularity_hits: dict[str, int],
    search_hits: dict[str, int],
) -> list[Candidate]:
    candidate_urls = list(
        popularity_hits
    )

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

    with httpx.Client(
        headers=HEADERS,
        timeout=30,
    ) as client:

        for index, url in enumerate(
            candidate_urls,
            start=1,
        ):
            print(
                f"[{index}/{len(candidate_urls)}]",
                url,
            )

            try:
                novel = scrape_wattpad(
                    url
                )

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
                normalize_text(
                    tag
                )
                for tag in novel.get(
                    "tags",
                    [],
                )
                if normalize_text(
                    tag
                )
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

            # ---------------------------------------------------------
            # Popularity metrics.
            # ---------------------------------------------------------

            try:
                html = fetch_html(
                    client,
                    url,
                )

                (
                    read_count,
                    vote_count,
                    comment_count,
                ) = extract_story_metrics(
                    html,
                )

            except Exception as exc:
                print(
                    "METADATA FAILED:",
                    type(exc).__name__,
                    exc,
                )

                read_count = None
                vote_count = None
                comment_count = None

            # Hard popularity thresholds only when the metric is available.
            # Missing metrics remain auditable instead of being guessed.
            if (
                read_count is not None
                and read_count < MIN_READ_COUNT
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(reads={read_count:,}, "
                    f"required >= {MIN_READ_COUNT:,})"
                )

                time.sleep(
                    REQUEST_DELAY
                )
                continue

            if (
                vote_count is not None
                and vote_count < MIN_VOTE_COUNT
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(votes={vote_count:,}, "
                    f"required >= {MIN_VOTE_COUNT:,})"
                )

                time.sleep(
                    REQUEST_DELAY
                )
                continue

            relevance_score, reasons = score_novel(
                novel.get(
                    "title"
                ),
                novel.get(
                    "synopsis"
                ),
                novel.get(
                    "tags",
                    [],
                ),
            )

            if (
                relevance_score
                < MIN_RELEVANCE_SCORE
                or not has_enough_relevance_evidence(
                    reasons
                )
            ):
                print(
                    f"SKIPPED: {novel.get('title')!r} "
                    f"(weak relevance={relevance_score:.1f})"
                )

                time.sleep(
                    REQUEST_DELAY
                )
                continue

            quality_score, quality_reasons = score_quality(
                title=novel.get(
                    "title"
                ),
                synopsis=novel.get(
                    "synopsis"
                ),
                read_count=read_count,
                vote_count=vote_count,
                comment_count=comment_count,
                popularity_hits=popularity_hits.get(
                    url,
                    0,
                ),
                search_hits=search_hits.get(
                    url,
                    0,
                ),
            )

            combined_score = (
                relevance_score
                + quality_score
            )

            candidates.append(
                Candidate(
                    url=url,
                    story_id=novel.get(
                        "story_id"
                    ),
                    title=novel.get(
                        "title"
                    ),
                    synopsis=novel.get(
                        "synopsis"
                    ),
                    tags=novel.get(
                        "tags",
                        [],
                    ),
                    read_count=read_count,
                    vote_count=vote_count,
                    comment_count=comment_count,
                    popularity_hits=popularity_hits.get(
                        url,
                        0,
                    ),
                    search_hits=search_hits.get(
                        url,
                        0,
                    ),
                    relevance_score=relevance_score,
                    quality_score=quality_score,
                    combined_score=combined_score,
                    reasons=reasons,
                    quality_reasons=quality_reasons,
                )
            )

            time.sleep(
                REQUEST_DELAY
            )

    return candidates


def select_top_candidates(
    candidates: list[Candidate],
) -> list[Candidate]:
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.combined_score,
            item.relevance_score,
            item.vote_count or 0,
            item.read_count or 0,
            item.comment_count or 0,
            item.popularity_hits,
            item.search_hits,
        ),
        reverse=True,
    )

    return ranked[
        :TARGET
    ]


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
        "philosophical_wattpad_urls.txt",
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
        "philosophical_wattpad_audit.csv",
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
                "relevance_score",
                "quality_score",
                "combined_score",
                "read_count",
                "vote_count",
                "comment_count",
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
            writer.writerow(
                {
                    "selected": (
                        candidate.url
                        in selected_urls
                    ),
                    "url": candidate.url,
                    "story_id": candidate.story_id,
                    "title": candidate.title,
                    "relevance_score": (
                        candidate.relevance_score
                    ),
                    "quality_score": (
                        candidate.quality_score
                    ),
                    "combined_score": (
                        candidate.combined_score
                    ),
                    "read_count": candidate.read_count,
                    "vote_count": candidate.vote_count,
                    "comment_count": candidate.comment_count,
                    "popularity_hits": (
                        candidate.popularity_hits
                    ),
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

    selected = select_top_candidates(
        candidates
    )

    write_outputs(
        selected,
        candidates,
    )

    print(
        f"\n=== SELECTED {len(selected)} WATTPAD STORIES "
        f"(preferred minimum: {MIN_TARGET}, "
        f"maximum: {TARGET}) ==="
    )

    if len(selected) < MIN_TARGET:
        print(
            "WARNING: Fewer than 50 stories passed the current "
            "discovery, banned-tag, popularity, and relevance filters. "
            "The script is intentionally not padding the output."
        )

    for rank, candidate in enumerate(
        selected,
        start=1,
    ):
        print(
            f"{rank:03d} "
            f"combined={candidate.combined_score:6.1f} "
            f"relevance={candidate.relevance_score:6.1f} "
            f"quality={candidate.quality_score:6.1f} "
            f"reads={candidate.read_count} "
            f"votes={candidate.vote_count} "
            f"{candidate.title}"
        )

        print(
            candidate.url
        )

    print(
        "\nWrote:"
    )

    print(
        "  philosophical_wattpad_urls.txt"
    )

    print(
        "  philosophical_wattpad_audit.csv"
    )


if __name__ == "__main__":
    main()
