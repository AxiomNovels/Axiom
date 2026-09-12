import re
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser


BASE_URL = "https://www.royalroad.com"

HEADERS = {
    "User-Agent": "Axiom-catalog-research/0.2 (personal project)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

STATUS_MAP = {
    "ONGOING": "ongoing",
    "COMPLETED": "completed",
    "HIATUS": "hiatus",
    "DROPPED": "dropped",
    "STUB": "stub",
}

ROYAL_ROAD_GENRES = (
    "Action",
    "Adventure",
    "Comedy",
    "Contemporary",
    "Drama",
    "Fantasy",
    "Historical",
    "Horror",
    "Mystery",
    "Psychological",
    "Romance",
    "Satire",
    "Sci-fi",
    "Short Story",
    "Tragedy",
    "Thriller",
)

PROMOTIONAL_KEYWORDS = (
    "available on amazon",
    "available on audible",
    "buy the audiobook",
    "buy the book",
    "audiobook",
    "kindle edition",
    "kindle unlimited",
    "kickstarter",
    "patreon",
    "paypal",
    "support the author",
    "support my work",
    "cover by",
)

COMMERCIAL_DOMAINS = (
    "amazon.",
    "audible.",
    "patreon.",
    "kickstarter.",
    "paypal.",
)


def clean_text(node) -> str | None:
    if node is None:
        return None

    text = node.text(
        separator=" ",
        strip=True,
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip() or None


def absolute_url(url: str | None) -> str | None:
    if not url:
        return None

    return urljoin(BASE_URL, url)


def extract_fiction_id(source_url: str) -> int:
    match = re.search(
        r"/fiction/(\d+)",
        source_url,
        re.IGNORECASE,
    )

    if not match:
        raise ValueError(
            f"Could not extract Royal Road fiction ID from: {source_url}"
        )

    return int(match.group(1))


def normalize_url(url: str) -> str:
    value = str(url).strip()

    if not value:
        raise ValueError("Royal Road URL cannot be empty.")

    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Invalid Royal Road URL scheme: {value}")

    if (parsed.hostname or "").lower() not in {
        "royalroad.com",
        "www.royalroad.com",
    }:
        raise ValueError(
            f"URL is not a Royal Road fiction URL: {value}"
        )

    fiction_id = extract_fiction_id(value)

    match = re.search(
        r"/fiction/\d+(?:/([^/?#]+))?",
        parsed.path,
        re.IGNORECASE,
    )

    slug = match.group(1) if match else None

    path = f"/fiction/{fiction_id}"

    if slug:
        path += f"/{slug}"

    return urljoin(BASE_URL, path)


def fetch(url: str) -> str:
    with httpx.Client(
        headers=HEADERS,
        follow_redirects=True,
        timeout=20,
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "text/html" not in content_type.lower():
        raise ValueError(
            f"Expected HTML from Royal Road, got: {content_type}"
        )

    return response.text


def extract_title(tree: HTMLParser) -> str:
    for node in (
        tree.css_first("h1"),
        tree.css_first("meta[property='og:title']"),
        tree.css_first("title"),
    ):
        if node is None:
            continue

        if node.tag == "meta":
            title = node.attributes.get("content")
        else:
            title = clean_text(node)

        if not title:
            continue

        title = re.sub(
            r"\s*\|\s*Royal Road\s*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        if title:
            return title

    raise ValueError(
        "Could not find Royal Road fiction title"
    )


def extract_author(tree: HTMLParser) -> str:
    for selector in (
        "h4 a[href*='/profile/']",
        "h3 a[href*='/profile/']",
        "a[href*='/profile/']",
    ):
        for node in tree.css(selector):
            author = clean_text(node)

            if author:
                return author

    raise ValueError(
        "Could not find Royal Road author"
    )


def extract_cover(
    tree: HTMLParser,
    title: str,
) -> str | None:
    title_casefold = title.casefold()
    partial_match = None

    for image in tree.css("img"):
        alt = image.attributes.get("alt", "").strip()

        src = (
            image.attributes.get("src")
            or image.attributes.get("data-src")
            or image.attributes.get("data-original")
        )

        if not src:
            continue

        url = absolute_url(src)

        if not url:
            continue

        if alt.casefold() == title_casefold:
            return url

        if (
            partial_match is None
            and alt
            and title_casefold in alt.casefold()
        ):
            partial_match = url

    og_image = tree.css_first(
        "meta[property='og:image']"
    )

    if og_image is not None:
        url = absolute_url(
            og_image.attributes.get("content")
        )

        if url:
            return url

    for image in tree.css("img"):
        src = (
            image.attributes.get("src")
            or image.attributes.get("data-src")
            or image.attributes.get("data-original")
        )

        if not src:
            continue

        url = absolute_url(src)

        if (
            url
            and "royalroadcdn.com" in url.lower()
            and "/covers-" in url.lower()
        ):
            return url

    return partial_match


def extract_status(tree: HTMLParser) -> str | None:
    for node in tree.css("span.label, .label"):
        text = clean_text(node)

        if not text:
            continue

        status = STATUS_MAP.get(text.upper())

        if status:
            return status

    for node in tree.css("div, span, p, li"):
        text = clean_text(node)

        if not text or len(text) > 250:
            continue

        match = re.search(
            r"\b(ONGOING|COMPLETED|HIATUS|DROPPED|STUB)\b",
            text,
            re.IGNORECASE,
        )

        if match:
            return STATUS_MAP.get(
                match.group(1).upper()
            )

    return None


def extract_tag_links(tree: HTMLParser) -> list[str]:
    tags = []

    for node in tree.css("a"):
        href = node.attributes.get("href", "")

        if not href:
            continue

        params = parse_qs(urlparse(href).query)

        if not any(
            key.casefold() == "tagsadd"
            for key in params
        ):
            continue

        text = clean_text(node)

        if text and text not in tags:
            tags.append(text)

    return tags


def extract_genres(tree: HTMLParser) -> list[str]:
    genre_lookup = {
        genre.casefold(): genre
        for genre in ROYAL_ROAD_GENRES
    }

    genres = []

    for tag in extract_tag_links(tree):
        genre = genre_lookup.get(tag.casefold())

        if genre and genre not in genres:
            genres.append(genre)

    return genres


def extract_tags(tree: HTMLParser) -> list[str]:
    genre_names = {
        genre.casefold()
        for genre in ROYAL_ROAD_GENRES
    }

    tags = []

    for tag in extract_tag_links(tree):
        if tag.casefold() in genre_names:
            continue

        if tag not in tags:
            tags.append(tag)

    return tags


def extract_description_node(tree: HTMLParser):
    for selector in (
        "div.description",
        ".description",
        "[class*='description']",
    ):
        node = tree.css_first(selector)

        if node is not None:
            return node

    return None


def clean_synopsis_node(node) -> str | None:
    if node is None:
        return None

    paragraphs = node.css("p")

    if paragraphs:
        parts = []

        for paragraph in paragraphs:
            text = clean_text(paragraph)

            if text:
                parts.append(text)

        if parts:
            return "\n\n".join(parts)

    text = node.text(
        separator="\n",
        strip=True,
    )

    if not text:
        return None

    parts = []

    for paragraph in re.split(r"\n+", text):
        paragraph = re.sub(
            r"\s+",
            " ",
            paragraph,
        ).strip()

        if paragraph:
            parts.append(paragraph)

    return "\n\n".join(parts) or None


def is_description_separator(text: str) -> bool:
    text = text.strip()

    return (
        len(text) >= 3
        and set(text) <= {
            "*",
            "-",
            "_",
            "=",
            " ",
        }
    )


def has_commercial_link(paragraph) -> bool:
    for link in paragraph.css("a"):
        href = (
            link.attributes.get("href", "")
            or ""
        ).lower()

        if any(
            domain in href
            for domain in COMMERCIAL_DOMAINS
        ):
            return True

    return False


def is_promotional_text(text: str) -> bool:
    text = text.casefold()

    return any(
        keyword in text
        for keyword in PROMOTIONAL_KEYWORDS
    )


def extract_synopsis(description_node) -> str | None:
    if description_node is None:
        return None

    content_node = (
        description_node.css_first(".hidden-content")
        or description_node
    )

    paragraphs = content_node.css("p")

    if not paragraphs:
        return clean_synopsis_node(content_node)

    synopsis = []

    for paragraph in paragraphs:
        text = clean_synopsis_node(paragraph)

        if not text:
            continue

        if is_description_separator(text):
            break

        if has_commercial_link(paragraph):
            continue

        if is_promotional_text(text):
            continue

        synopsis.append(text)

    return "\n\n".join(synopsis) or None


def parse_royalroad(
    html: str,
    source_url: str,
) -> dict:
    tree = HTMLParser(html)

    title = extract_title(tree)

    return {
        "source": "royalroad",
        "source_url": source_url,
        "fiction_id": extract_fiction_id(source_url),
        "title": title,
        "author": extract_author(tree),
        "status": extract_status(tree),
        "genres": extract_genres(tree),
        "tags": extract_tags(tree),
        "synopsis": extract_synopsis(
            extract_description_node(tree)
        ),
        "cover_image_url": extract_cover(
            tree,
            title,
        ),
        "reading_url": source_url,
    }


def scrape_royalroad(url: str) -> dict:
    source_url = normalize_url(url)

    return parse_royalroad(
        html=fetch(source_url),
        source_url=source_url,
    )


def scrape_royalroads(
    urls: list[str],
) -> list[dict]:
    results = []

    for url in urls:
        print(f"\nROYAL ROAD: {url}")

        try:
            novel = scrape_royalroad(url)
            results.append(novel)

            print(
                f"SUCCESS: {novel['title']} "
                f"| genres={novel['genres']} "
                f"| tags={novel['tags']}"
            )

        except Exception as exc:
            print(
                f"FAILED: {type(exc).__name__}: {exc}"
            )

            results.append(
                {
                    "source": "royalroad",
                    "source_url": str(url),
                    "fiction_id": None,
                    "title": None,
                    "author": None,
                    "status": None,
                    "genres": [],
                    "tags": [],
                    "synopsis": None,
                    "cover_image_url": None,
                    "reading_url": None,
                    "error": str(exc),
                }
            )

    return results


if __name__ == "__main__":
    URLS = [
        "https://www.royalroad.com/fiction/36735/the-perfect-run",
        "https://www.royalroad.com/fiction/21220/mother-of-learning",
        "https://www.royalroad.com/fiction/16344/the-last-philosopher",
    ]

    novels = scrape_royalroads(URLS)

    for novel in novels:
        print()

        for key, value in novel.items():
            print(f"{key}: {value}")