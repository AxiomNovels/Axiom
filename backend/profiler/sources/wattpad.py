import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

COMMENT_SELECTORS = (
    "[data-testid='comment-body']",
    "[data-testid='comment'] [data-testid='body']",
    ".comment-body",
    ".comment-content",
)


def validate_wattpad_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or hostname not in {"wattpad.com", "www.wattpad.com"}:
        raise ValueError("Expected an HTTPS Wattpad link")
    if not re.search(r"^/story/\d+", parsed.path):
        raise ValueError("Expected a Wattpad /story/ link")


def fetch_wattpad(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", "").casefold():
        raise ValueError("Wattpad did not return HTML")
    return response.text


def extract_part_urls(story_html: str, story_url: str, limit: int = 3) -> list[str]:
    """Find the first public story-part links exposed on a Wattpad story page."""
    soup = BeautifulSoup(story_html, "html.parser")
    urls: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        parsed = urlparse(urljoin(story_url, href))
        if (parsed.hostname or "").casefold() not in {"wattpad.com", "www.wattpad.com"}:
            continue
        if not re.match(r"^/\d+(?:-|$)", parsed.path):
            continue
        clean_url = f"https://www.wattpad.com{parsed.path}"
        if clean_url not in urls:
            urls.append(clean_url)
        if len(urls) >= limit:
            break

    return urls


def parse_wattpad_comments(html: str, limit: int = 40) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    comments: list[str] = []
    seen: set[str] = set()

    for selector in COMMENT_SELECTORS:
        for node in soup.select(selector):
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            key = text.casefold()
            if len(text) < 12 or key in seen:
                continue
            seen.add(key)
            comments.append(text)
            if len(comments) >= limit:
                return comments
        if comments:
            break

    return comments


def collect_wattpad_comments(
    story_url: str,
    limit: int = 40,
    part_limit: int = 3,
) -> list[str]:
    """Collect public inline comments from the first few accessible story parts."""
    validate_wattpad_url(story_url)
    story_html = fetch_wattpad(story_url)
    part_urls = extract_part_urls(story_html, story_url, limit=part_limit)
    if not part_urls:
        raise RuntimeError("Wattpad exposed no public story-part links")

    comments: list[str] = []
    seen: set[str] = set()
    for part_url in part_urls:
        for comment in parse_wattpad_comments(fetch_wattpad(part_url), limit=limit):
            key = comment.casefold()
            if key not in seen:
                seen.add(key)
                comments.append(comment)
            if len(comments) >= limit:
                return comments

    if not comments:
        raise RuntimeError(
            "Wattpad did not expose public inline comments in the accessible part pages"
        )
    return comments
