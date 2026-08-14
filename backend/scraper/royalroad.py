import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser


BASE_URL = "https://www.royalroad.com"

HEADERS = {
    "User-Agent": "Axiom-catalog-research/0.1 (personal project)",
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

def debug_description(tree: HTMLParser) -> None:
    description_node = tree.css_first("div.description")

    if not description_node:
        print("NO DESCRIPTION NODE")
        return

    print("\n" + "=" * 70)
    print("DESCRIPTION HTML STRUCTURE")
    print("=" * 70)

    for index, child in enumerate(description_node.iter()):
        print(f"\nCHILD {index}")
        print("TAG:", child.tag)
        print("TEXT:", clean_text(child))
        print("ATTRIBUTES:", child.attributes)

        html = child.html
        if html:
            print("HTML:", html[:1000])

def fetch(url: str) -> str:
    """
    Fetch a public Royal Road page and return its HTML.
    """

    response = httpx.get(
        url,
        headers=HEADERS,
        follow_redirects=True,
        timeout=20,
    )

    response.raise_for_status()

    content_type = response.headers.get("content-type", "")

    if "text/html" not in content_type.lower():
        raise ValueError(
            f"Expected HTML from Royal Road, got: {content_type}"
        )

    return response.text


def clean_text(node) -> str | None:
    """
    Normalize whitespace in a Selectolax node.
    """

    if node is None:
        return None

    text = node.text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return text.strip() or None


def absolute_url(url: str | None) -> str | None:
    """
    Convert a relative URL into an absolute URL.
    """

    if not url:
        return None

    return urljoin(BASE_URL, url)


def extract_fiction_id(source_url: str) -> int:
    """
    Extract the numeric Royal Road fiction ID.
    """

    match = re.search(r"/fiction/(\d+)", source_url)

    if not match:
        raise ValueError(
            f"Could not extract Royal Road fiction ID from: {source_url}"
        )

    return int(match.group(1))


def extract_title(tree: HTMLParser) -> str:
    """
    Extract the fiction title.
    """

    title_node = tree.css_first("h1")
    title = clean_text(title_node)

    if not title:
        raise ValueError(
            "Could not find Royal Road fiction title"
        )

    return title


def extract_author(tree: HTMLParser) -> str:
    """
    Extract the author's Royal Road username.
    """

    author_node = tree.css_first(
        "h4 a[href*='/profile/']"
    )

    author = clean_text(author_node)

    if not author:
        raise ValueError(
            "Could not find Royal Road author"
        )

    return author


def extract_cover(
    tree: HTMLParser,
    title: str,
) -> str | None:
    """
    Extract the fiction cover URL.

    Prefer an image whose alt text exactly matches the
    fiction title.
    """

    for image in tree.css("img"):
        alt = image.attributes.get("alt", "").strip()

        if alt.lower() == title.lower():
            src = image.attributes.get("src")

            if src:
                return absolute_url(src)

    # Fallback: partial title match.
    for image in tree.css("img"):
        alt = image.attributes.get("alt", "").strip()

        if title.lower() in alt.lower():
            src = image.attributes.get("src")

            if src:
                return absolute_url(src)

    return None


def extract_status(tree: HTMLParser) -> str:
    """
    Extract the actual Royal Road fiction status.

    Royal Road may show multiple labels near the fiction
    metadata, e.g.:

        Original COMPLETED

    Therefore we inspect all candidate label elements and
    select the one whose text is a known status.
    """

    for node in tree.css(
        "span.label.label-default.label-sm.bg-blue-hoki"
    ):
        text = clean_text(node)

        if not text:
            continue

        normalized = text.upper()

        if normalized in STATUS_MAP:
            return STATUS_MAP[normalized]

    # Fallback: inspect all small label elements.
    for node in tree.css("span.label"):
        text = clean_text(node)

        if not text:
            continue

        normalized = text.upper()

        if normalized in STATUS_MAP:
            return STATUS_MAP[normalized]

    raise ValueError(
        "Could not find Royal Road fiction status"
    )


def extract_tags(tree: HTMLParser) -> list[str]:
    """
    Extract Royal Road's fiction tags.

    We intentionally preserve all source tags here.

    A later transformation step can decide which tags should
    become Axiom genres versus more specific tags.
    """

    tags = []

    for node in tree.css("a"):
        href = node.attributes.get("href", "")
        text = clean_text(node)

        if not text:
            continue

        if "tagsAdd=" in href:
            if text not in tags:
                tags.append(text)

    return tags


def is_description_separator(text: str) -> bool:
    """
    Detect the common divider Royal Road authors use to
    separate the synopsis from additional author notes.
    """

    if not text:
        return False

    normalized = text.strip()

    # Examples:
    #
    # **********************************
    # ------------------------------
    # ==============================
    #
    if len(normalized) >= 5:
        if set(normalized) <= {"*", "-", "_", "=", " "}:
            return True

    return False


PROMOTIONAL_KEYWORDS = (
    "available on amazon",
    "available on audible",
    "buy the audiobook",
    "buy the book",
    "audiobook",
    "kindle edition",
    "kickstarter",
    "patreon",
    "paypal",
    "support the author",
    "support my work",
    "cover by",
)


def extract_synopsis(description_node) -> str | None:
    """
    Extract the actual synopsis from a Royal Road description.

    Royal Road may place author announcements, advertisements, or
    commercial links before/after the actual synopsis.

    We operate at paragraph level so we don't accidentally merge
    promotional material into the synopsis.
    """

    if not description_node:
        return None

    hidden_content = description_node.css_first(".hidden-content")

    if not hidden_content:
        return clean_text(description_node)

    paragraphs = hidden_content.css("p")

    if not paragraphs:
        return clean_text(hidden_content)

    synopsis_parts = []

    for paragraph in paragraphs:
        text = clean_text(paragraph)

        if not text:
            continue

        normalized = text.lower()

        # ---------------------------------
        # External/commercial links
        # ---------------------------------

        links = paragraph.css("a")

        hrefs = []

        for link in links:
            href = link.attributes.get("href", "")

            if href:
                hrefs.append(href.lower())

        commercial_domains = (
            "amazon.",
            "audible.",
            "patreon.",
            "kickstarter.",
            "paypal.",
        )

        has_commercial_link = any(
            domain in href
            for href in hrefs
            for domain in commercial_domains
        )

        if has_commercial_link:
            continue

        # ---------------------------------
        # Promotional language
        # ---------------------------------

        if any(
            keyword in normalized
            for keyword in PROMOTIONAL_KEYWORDS
        ):
            continue

        synopsis_parts.append(text)

    if not synopsis_parts:
        return None

    return " ".join(synopsis_parts)


def extract_reading_url(
    tree: HTMLParser,
    source_url: str,
) -> str:
    """
    Extract the first chapter URL.

    Fall back to the fiction URL if no chapter link is found.
    """

    # Keep the first chapter separately as useful scraped metadata.
    first_chapter_url = None

    start_reading = tree.css_first(
        "a[href*='/fiction/'][href*='/chapter/']"
    )

    if start_reading:
        href = start_reading.attributes.get("href", "")

        if href:
            first_chapter_url = urljoin(
                BASE_URL,
                href,
            )

    return source_url


def parse_royalroad(
    html: str,
    source_url: str,
) -> dict:
    """
    Parse a Royal Road fiction page into normalized source data.
    """

    tree = HTMLParser(html)

    fiction_id = extract_fiction_id(source_url)
    title = extract_title(tree)
    author = extract_author(tree)
    status = extract_status(tree)
    tags = extract_tags(tree)
    synopsis = extract_synopsis(tree)
    cover_image_url = extract_cover(tree, title)
    reading_url = extract_reading_url(
        tree,
        source_url,
    )

    debug_description(tree)
    

    return {
        "source": "royalroad",
        "source_url": source_url,
        "fiction_id": fiction_id,
        "title": title,
        "author": author,
        "status": status,
        "tags": tags,
        "synopsis": synopsis,
        "cover_image_url": cover_image_url,
        "reading_url": reading_url,
    }

    

def scrape_royalroad(url: str) -> dict:
    """
    Fetch and parse a Royal Road fiction page.
    """

    html = fetch(url)

    return parse_royalroad(
        html=html,
        source_url=url,
    )


if __name__ == "__main__":
    url = (
        "https://www.royalroad.com/fiction/"
        "36735/the-perfect-run"
    )

    novel = scrape_royalroad(url)

    for key, value in novel.items():
        print(f"{key}: {value}")