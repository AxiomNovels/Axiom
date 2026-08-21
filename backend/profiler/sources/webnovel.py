import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from scraper.webnovel import fetch


REVIEW_SELECTORS = (
    ".j_book_review_content",
    "p.m-comment-bd",
)


def validate_webnovel_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or hostname not in {"webnovel.com", "www.webnovel.com"}:
        raise ValueError("Expected an HTTPS WebNovel reading link")


def parse_webnovel_reviews(html: str, limit: int = 40) -> list[str]:
    """Extract the public book reviews included in WebNovel's book-page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    reviews: list[str] = []
    seen: set[str] = set()

    for selector in REVIEW_SELECTORS:
        for node in soup.select(selector):
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            key = text.casefold()
            if len(text) < 20 or key in seen:
                continue
            seen.add(key)
            reviews.append(text)
            if len(reviews) >= limit:
                return reviews

        if reviews:
            break

    return reviews


def collect_webnovel_reviews(url: str, limit: int = 40) -> list[str]:
    validate_webnovel_url(url)
    reviews = parse_webnovel_reviews(fetch(url), limit=limit)
    if not reviews:
        raise RuntimeError("No public WebNovel reviews were found on the book page")
    return reviews
