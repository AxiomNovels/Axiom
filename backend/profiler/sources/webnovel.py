import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from requests import RequestException

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
    urls_to_try = [url]
    book_id_match = re.search(r"(?:_|/book/)(\d+)(?:[/?#]|$)", url)
    if book_id_match:
        canonical_url = f"https://www.webnovel.com/book/{book_id_match.group(1)}"
        if canonical_url not in urls_to_try:
            urls_to_try.append(canonical_url)

    last_error = None
    reviews = []
    for candidate_url in urls_to_try:
        try:
            reviews = parse_webnovel_reviews(fetch(candidate_url), limit=limit)
        except RequestException as error:
            last_error = error
            continue
        if reviews:
            return reviews

    if last_error is not None:
        status = getattr(last_error.response, "status_code", None)
        detail = f"HTTP {status}" if status else type(last_error).__name__
        raise RuntimeError(f"WebNovel blocked or failed the public review request ({detail})") from last_error
    if not reviews:
        raise RuntimeError("No public WebNovel reviews were found on the book page")
    return reviews
