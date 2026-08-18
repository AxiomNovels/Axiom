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


def normalize_url(
    url: str,
) -> str:
    """
    Normalize a Royal Road fiction URL.

    Removes surrounding whitespace and ensures the URL
    points to Royal Road.
    """

    value = str(url).strip()

    if not value:
        raise ValueError(
            "Royal Road URL cannot be empty."
        )

    if "royalroad.com" not in value.lower():
        raise ValueError(
            f"Could not understand Royal Road URL: {value}"
        )

    return value


def fetch(
    url: str,
) -> str:
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

    content_type = response.headers.get(
        "content-type",
        "",
    )

    if (
        "text/html"
        not in content_type.lower()
    ):
        raise ValueError(
            "Expected HTML from Royal Road, got: "
            f"{content_type}"
        )

    return response.text


def clean_text(
    node,
) -> str | None:
    """
    Normalize whitespace in a Selectolax node.

    This is intended for short fields such as titles,
    authors, tags, and status labels.
    """

    if node is None:
        return None

    text = node.text(
        separator=" ",
        strip=True,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip() or None


def clean_synopsis_node(
    node,
) -> str | None:
    """
    Extract text from a Selectolax node while preserving
    paragraph boundaries.

    Whitespace inside each paragraph is normalized, while
    separate paragraphs remain separated by a blank line.
    """

    if node is None:
        return None

    text = node.text(
        separator="\n",
        strip=True,
    )

    if not text:
        return None

    paragraphs = []

    for paragraph in re.split(
        r"\n+",
        text,
    ):
        paragraph = re.sub(
            r"\s+",
            " ",
            paragraph,
        ).strip()

        if paragraph:
            paragraphs.append(
                paragraph
            )

    return "\n\n".join(
        paragraphs
    ) or None


def absolute_url(
    url: str | None,
) -> str | None:
    """
    Convert a relative URL into an absolute URL.
    """

    if not url:
        return None

    return urljoin(
        BASE_URL,
        url,
    )


def extract_fiction_id(
    source_url: str,
) -> int:
    """
    Extract the numeric Royal Road fiction ID.
    """

    match = re.search(
        r"/fiction/(\d+)",
        source_url,
    )

    if not match:
        raise ValueError(
            "Could not extract Royal Road fiction ID "
            f"from: {source_url}"
        )

    return int(
        match.group(1)
    )


def extract_title(
    tree: HTMLParser,
) -> str:
    """
    Extract the fiction title.
    """

    title_node = tree.css_first(
        "h1"
    )

    title = clean_text(
        title_node
    )

    if not title:
        raise ValueError(
            "Could not find Royal Road fiction title"
        )

    return title


def extract_author(
    tree: HTMLParser,
) -> str:
    """
    Extract the author's Royal Road username.
    """

    author_node = tree.css_first(
        "h4 a[href*='/profile/']"
    )

    author = clean_text(
        author_node
    )

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

    Prefer an image whose alt text exactly matches
    the fiction title.
    """

    for image in tree.css(
        "img"
    ):
        alt = (
            image.attributes.get(
                "alt",
                "",
            ).strip()
        )

        if alt.lower() == title.lower():

            src = image.attributes.get(
                "src"
            )

            if src:
                return absolute_url(
                    src
                )

    # Fallback: partial title match.
    for image in tree.css(
        "img"
    ):
        alt = (
            image.attributes.get(
                "alt",
                "",
            ).strip()
        )

        if title.lower() in alt.lower():

            src = image.attributes.get(
                "src"
            )

            if src:
                return absolute_url(
                    src
                )

    return None


def extract_status(
    tree: HTMLParser,
) -> str:
    """
    Extract the Royal Road fiction status.
    """

    for node in tree.css(
        "span.label.label-default."
        "label-sm.bg-blue-hoki"
    ):

        text = clean_text(
            node
        )

        if not text:
            continue

        normalized = text.upper()

        if normalized in STATUS_MAP:
            return STATUS_MAP[
                normalized
            ]

    # Fallback: inspect all labels.
    for node in tree.css(
        "span.label"
    ):

        text = clean_text(
            node
        )

        if not text:
            continue

        normalized = text.upper()

        if normalized in STATUS_MAP:
            return STATUS_MAP[
                normalized
            ]

    raise ValueError(
        "Could not find Royal Road fiction status"
    )


def extract_tags(
    tree: HTMLParser,
) -> list[str]:
    """
    Extract Royal Road fiction tags.

    All source tags are preserved.
    """

    tags = []

    for node in tree.css(
        "a"
    ):

        href = node.attributes.get(
            "href",
            "",
        )

        text = clean_text(
            node
        )

        if not text:
            continue

        if "tagsAdd=" not in href:
            continue

        if text not in tags:
            tags.append(
                text
            )

    return tags


def is_description_separator(
    text: str,
) -> bool:
    """
    Detect common divider lines used to separate a synopsis
    from author notes or promotional content.
    """

    if not text:
        return False

    normalized = text.strip()

    if len(normalized) >= 5:

        if set(normalized) <= {
            "*",
            "-",
            "_",
            "=",
            " ",
        }:
            return True

    return False


def has_commercial_link(
    paragraph,
) -> bool:
    """
    Determine whether a paragraph contains a known
    commercial or promotional link.
    """

    commercial_domains = (
        "amazon.",
        "audible.",
        "patreon.",
        "kickstarter.",
        "paypal.",
    )

    for link in paragraph.css(
        "a"
    ):

        href = link.attributes.get(
            "href",
            "",
        ).lower()

        if any(
            domain in href
            for domain in commercial_domains
        ):
            return True

    return False


def extract_synopsis(
    description_node,
) -> str | None:
    """
    Extract the actual synopsis from a Royal Road description
    while preserving paragraph breaks.

    Royal Road may place author announcements,
    advertisements, or commercial links before or after the
    actual synopsis.

    The synopsis is processed paragraph by paragraph.
    """

    if description_node is None:
        return None

    hidden_content = description_node.css_first(
        ".hidden-content"
    )

    # Use hidden-content if it exists because Royal Road
    # commonly stores the full description there.
    content_node = (
        hidden_content
        or description_node
    )

    paragraphs = content_node.css(
        "p"
    )

    # ---------------------------------------------------------
    # No paragraph elements.
    #
    # Still preserve any line breaks that exist in the source.
    # ---------------------------------------------------------

    if not paragraphs:
        return clean_synopsis_node(
            content_node
        )

    synopsis_parts = []

    for paragraph in paragraphs:

        text = clean_synopsis_node(
            paragraph
        )

        if not text:
            continue

        normalized = text.lower()

        # ---------------------------------------------
        # Separator lines often indicate that author
        # notes or promotional material follow.
        # ---------------------------------------------

        if is_description_separator(
            text
        ):
            break

        # ---------------------------------------------
        # Commercial links
        # ---------------------------------------------

        if has_commercial_link(
            paragraph
        ):
            continue

        # ---------------------------------------------
        # Promotional language
        # ---------------------------------------------

        if any(
            keyword in normalized
            for keyword in PROMOTIONAL_KEYWORDS
        ):
            continue

        synopsis_parts.append(
            text
        )

    if not synopsis_parts:
        return None

    # Preserve paragraph boundaries.
    return "\n\n".join(
        synopsis_parts
    )


def extract_reading_url(
    source_url: str,
) -> str:
    """
    Return the Royal Road fiction page as the reading URL.

    The fiction page is a stable canonical reading entry point.
    """

    return source_url


def parse_royalroad(
    html: str,
    source_url: str,
) -> dict:
    """
    Parse a Royal Road fiction page into normalized source data.
    """

    tree = HTMLParser(
        html
    )

    fiction_id = extract_fiction_id(
        source_url
    )

    title = extract_title(
        tree
    )

    author = extract_author(
        tree
    )

    status = extract_status(
        tree
    )

    tags = extract_tags(
        tree
    )

    # ---------------------------------------------------------
    # Extract the actual description node before passing it
    # into extract_synopsis().
    # ---------------------------------------------------------

    description_node = tree.css_first(
        "div.description"
    )

    synopsis = extract_synopsis(
        description_node
    )

    cover_image_url = extract_cover(
        tree,
        title,
    )

    reading_url = extract_reading_url(
        source_url
    )

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


def scrape_royalroad(
    url: str,
) -> dict:
    """
    Fetch and parse one Royal Road fiction.
    """

    source_url = normalize_url(
        url
    )

    html = fetch(
        source_url
    )

    return parse_royalroad(
        html=html,
        source_url=source_url,
    )


def scrape_royalroads(
    urls: list[str],
) -> list[dict]:
    """
    Fetch and parse multiple Royal Road fictions.

    A failure on one fiction does not stop the remaining
    fictions.

    Each failed fiction receives an error record.
    """

    results = []

    for value in urls:

        print()
        print("=" * 70)
        print("ROYAL ROAD")
        print("=" * 70)
        print("INPUT:", value)

        try:

            novel = scrape_royalroad(
                value
            )

            results.append(
                novel
            )

            print(
                "SUCCESS:",
                novel.get("title")
                or novel.get("fiction_id"),
            )

        except Exception as exc:

            print(
                "FAILED:",
                type(exc).__name__,
                str(exc),
            )

            results.append(
                {
                    "source": "royalroad",
                    "source_url": str(value),
                    "fiction_id": None,
                    "title": None,
                    "author": None,
                    "status": None,
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
        (
            "https://www.royalroad.com/fiction/"
            "36735/the-perfect-run"
        ),
        (
            "https://www.royalroad.com/fiction/"
            "21220/mother-of-learning"
        ),
        (
            "https://www.royalroad.com/fiction/16344/the-last-philosopher"
        ),
    ]

    novels = scrape_royalroads(
        URLS
    )

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    for novel in novels:

        print()

        for key, value in novel.items():

            print(
                f"{key}: {value}"
            )