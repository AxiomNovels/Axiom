import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Axiom-catalog-research/0.1 (personal project)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def validate_royalroad_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or hostname not in {"royalroad.com", "www.royalroad.com"}:
        raise ValueError("Expected an HTTPS Royal Road fiction link")
    if not re.search(r"^/fiction/\d+", parsed.path):
        raise ValueError("Expected a Royal Road /fiction/ link")


def fetch_royalroad(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", "").casefold():
        raise ValueError("Royal Road did not return HTML")
    return response.text


def parse_royalroad_reviews(html: str, limit: int = 40) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    reviews: list[str] = []
    seen: set[str] = set()

    for container in soup.select(".review-inner"):
        paragraphs = container.find_all("p", recursive=False) or container.find_all("p")
        text = " ".join(node.get_text(" ", strip=True) for node in paragraphs)
        text = re.sub(r"\s+", " ", text).strip()
        key = text.casefold()
        if len(text) < 20 or key in seen:
            continue
        seen.add(key)
        reviews.append(text)
        if len(reviews) >= limit:
            break

    return reviews


def collect_royalroad_reviews(url: str, limit: int = 40) -> list[str]:
    validate_royalroad_url(url)
    reviews = parse_royalroad_reviews(fetch_royalroad(url), limit=limit)
    if not reviews:
        raise RuntimeError("No public Royal Road reviews were found on the fiction page")
    return reviews
