import re
from urllib.parse import urljoin
import json

import httpx
from selectolax.parser import HTMLParser


BASE_URL = "https://www.wattpad.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch(url: str) -> str:
    """
    Fetch a public Wattpad story page and return its HTML.
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

    if "text/html" not in content_type.lower():
        raise ValueError(
            f"Expected HTML from Wattpad, got: {content_type}"
        )

    return response.text


def clean_text(node) -> str | None:
    """
    Normalize whitespace in a Selectolax node.
    """

    if node is None:
        return None

    text = node.text(
        separator=" ",
        strip=True,
    )

    # Add a space between text that was separated by
    # HTML structure but got joined together.
    text = re.sub(
        r"(?<=[a-z])(?=[A-Z])",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip() or None

def extract_remix_context(
    tree: HTMLParser,
) -> dict | None:
    """
    Extract Wattpad's embedded Remix loader data.

    Wattpad embeds story information in a script containing:

        window.__remixContext = {...}

    The story data is located under the route loader data.
    """

    scripts = tree.css("script")

    for script in scripts:
        text = script.text()

        if not text:
            continue

        marker = "window.__remixContext = "

        if marker not in text:
            continue

        start = text.find(marker)

        if start == -1:
            continue

        json_text = text[
            start + len(marker):
        ].strip()

        # Remove a trailing semicolon if present.
        if json_text.endswith(";"):
            json_text = json_text[:-1]

        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            continue

    return None

def find_story_data(
    value,
) -> dict | None:
    """
    Recursively search the Remix context for a dictionary
    containing Wattpad story metadata.
    """

    if isinstance(value, dict):

        # This is the shape we want.
        if (
            "story_id" in value
            and "title" in value
            and "author" in value
        ):
            return value

        for child in value.values():
            result = find_story_data(child)

            if result is not None:
                return result

    elif isinstance(value, list):

        for child in value:
            result = find_story_data(child)

            if result is not None:
                return result

    return None

def extract_remix_story_data(
    tree: HTMLParser,
) -> dict | None:
    """
    Extract normalized story data from Wattpad's embedded
    Remix context.
    """

    context = extract_remix_context(tree)

    if not context:
        return None

    story = find_story_data(context)

    if not story:
        return None

    return story


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


def extract_story_id(
    source_url: str,
) -> int:
    """
    Extract the numeric Wattpad story ID.
    """

    match = re.search(
        r"/story/(\d+)",
        source_url,
    )

    if not match:
        raise ValueError(
            f"Could not extract Wattpad story ID from: {source_url}"
        )

    return int(match.group(1))


def extract_title(
    tree: HTMLParser,
) -> str:
    """
    Extract the Wattpad story title.

    Prefer the h1[data-testid='title'] element.
    """

    title_node = tree.css_first(
        "h1[data-testid='title']"
    )

    if not title_node:
        title_node = tree.css_first("h1")

    title = clean_text(title_node)

    if not title:
        raise ValueError(
            "Could not find Wattpad story title"
        )

    return title


def extract_author(
    tree: HTMLParser,
) -> str | None:
    """
    Extract the Wattpad author's username.

    Wattpad exposes the author as a link such as:

        /user/Sheolle
    """

    author_node = tree.css_first(
        "a[href*='/user/']"
    )

    author = clean_text(author_node)

    return author

def debug_cover_candidates(
    tree: HTMLParser,
    title: str,
) -> None:
    print()
    print("=" * 70)
    print("COVER IMAGE CANDIDATES")
    print("=" * 70)

    print("\nALL IMAGES:")

    images = tree.css("img")

    print("Found:", len(images))

    for index, image in enumerate(images):
        src = image.attributes.get("src")
        srcset = image.attributes.get("srcset")
        alt = image.attributes.get("alt")
        width = image.attributes.get("width")
        height = image.attributes.get("height")

        print()
        print(f"IMAGE #{index}")
        print("ALT:", alt)
        print("SRC:", src)
        print("SRCSET:", srcset)
        print("WIDTH:", width)
        print("HEIGHT:", height)
        print("ATTRIBUTES:", image.attributes)

def debug_synopsis_candidates(
    tree: HTMLParser,
) -> None:
    print()
    print("=" * 70)
    print("SYNOPSIS CANDIDATES")
    print("=" * 70)

    # Look for elements containing the description meta text.
    meta = tree.css_first(
        "meta[name='description']"
    )

    meta_text = None

    if meta:
        meta_text = (
            meta.attributes.get("content") or ""
        ).strip()

    print("\nMETA DESCRIPTION:")
    print(meta_text)

    print("\nELEMENTS CONTAINING META DESCRIPTION TEXT:")

    if meta_text:
        # Use a reasonably distinctive portion of the
        # description to search the DOM.
        search_text = meta_text[:80]

        for index, node in enumerate(tree.css("*")):
            text = clean_text(node)

            if not text:
                continue

            if search_text.lower() in text.lower():
                print()
                print(f"CANDIDATE #{index}")
                print("TAG:", node.tag)
                print("TEXT:", text[:3000])
                print("ATTRIBUTES:", node.attributes)
                print("HTML:", node.html[:3000])

def extract_synopsis(
    tree: HTMLParser,
) -> str | None:
    """
    Extract the full Wattpad story synopsis.

    Wattpad visually truncates the description with CSS,
    but the full text is still present in the HTML.
    """

    # Find the description container by looking for
    # the "Read more" button that belongs to it.
    for button in tree.css("button"):
        button_text = clean_text(button)

        if button_text != "Read more":
            continue

        parent = button.parent

        if parent is None:
            continue

        description_node = parent.css_first(
            "div._66soR.waz33"
        )

        if description_node is None:
            continue

        description = clean_text(
            description_node
        )

        description = description.split("HIGHEST RANK", 1)[0]
        description = description.split("All Rights Reserved", 1)[0]

        if description:
            return description

    # Fallback to the meta description if the full
    # description cannot be found.
    meta = tree.css_first(
        "meta[name='description']"
    )

    if meta:
        description = (
            meta.attributes.get("content") or ""
        ).strip()

        if description:
            return re.sub(
                r"\s+",
                " ",
                description,
            )

    return None


def extract_tags(
    tree: HTMLParser,
) -> list[str]:
    """
    Extract Wattpad keywords from the meta keywords tag.

    Wattpad's tested page exposes values such as:

        action, adventure, fantasy, reincarnation, romance...

    The final value may contain a duplicate/broad category such
    as 'Fantasy', so duplicates are removed while preserving order.
    """

    keywords_node = tree.css_first(
        "meta[name='keywords']"
    )

    if not keywords_node:
        return []

    content = keywords_node.attributes.get(
        "content"
    )

    if not content:
        return []

    tags = []

    for value in content.split(","):
        tag = value.strip()

        if not tag:
            continue

        if tag not in tags:
            tags.append(tag)

    return tags


def extract_cover(images, story_id=None, title=None):
    """
    Extract the primary Wattpad story cover.
    """

    candidates = []

    for img in images:
        src = img.attributes.get("src", "")
        alt = (img.attributes.get("alt") or "").strip()

        if "/cover/" not in src:
            continue

        score = 0

        # Exact story ID match is extremely strong
        if story_id and f"/cover/{story_id}-" in src:
            score += 1000

        # Exact title match is also strong
        if title and alt.lower() == title.lower():
            score += 100

        # Any non-empty alt text is useful
        if alt:
            score += 10

        candidates.append((score, src))

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    return candidates[0][1]


def extract_status(
    tree: HTMLParser,
) -> str | None:
    """
    Extract the status of the current Wattpad story.

    The status is located inside the story-specific metadata
    container:

        div[data-testid='story-meta']

    The status itself has:

        data-testid='story-status-with-first-published-tooltip'
    """

    status_node = tree.css_first(
        "[data-testid='story-status-with-first-published-tooltip']"
    )

    status = clean_text(status_node)

    if not status:
        return None

    return status


def extract_reading_url(
    tree: HTMLParser,
    source_url: str,
) -> str:
    """
    Return the Wattpad story URL.

    Unlike Royal Road, the tested Wattpad story page did not
    expose a reliable first-chapter URL in the inspected DOM.
    The story URL is therefore used as the reading destination.
    """

    return source_url


def parse_wattpad(
    html: str,
    source_url: str,
) -> dict:
    """
    Parse a Wattpad story page into normalized source data.

    Wattpad embeds structured story metadata in its Remix
    context. That data is preferred over DOM scraping because
    it provides the actual story record rather than text from
    related/recommended stories.
    """

    tree = HTMLParser(html)

    story_id = extract_story_id(
        source_url
    )

    # ---------------------------------------------------------
    # Primary extraction: embedded Remix story data
    # ---------------------------------------------------------

    remix_story = extract_remix_story_data(tree)

    if remix_story:

        title = remix_story.get("title")
        author = remix_story.get("author")
        status = remix_story.get("status")
        tags = remix_story.get("tags") or []
        synopsis = remix_story.get("synopsis")
        cover_image_url = remix_story.get(
            "cover_image_url"
        )
        reading_url = remix_story.get(
            "reading_url"
        )

        # Make sure story_id is an integer when possible.
        remix_story_id = remix_story.get("story_id")

        if remix_story_id:
            try:
                story_id = int(remix_story_id)
            except (TypeError, ValueError):
                pass

        return {
            "source": "wattpad",
            "source_url": source_url,
            "story_id": story_id,
            "title": title,
            "author": author,
            "status": status,
            "tags": tags,
            "synopsis": synopsis,
            "cover_image_url": cover_image_url,
            "reading_url": reading_url,
        }

    # ---------------------------------------------------------
    # Fallback: existing DOM extraction
    # ---------------------------------------------------------

    images = tree.css("img")

    title = extract_title(tree)
    author = extract_author(tree)
    status = extract_status(tree)
    tags = extract_tags(tree)
    synopsis = extract_synopsis(tree)

    cover_image_url = extract_cover(
        images,
        story_id=story_id,
        title=title,
    )

    reading_url = extract_reading_url(
        tree,
        source_url,
    )

    return {
        "source": "wattpad",
        "source_url": source_url,
        "story_id": story_id,
        "title": title,
        "author": author,
        "status": status,
        "tags": tags,
        "synopsis": synopsis,
        "cover_image_url": cover_image_url,
        "reading_url": reading_url,
    }


def scrape_wattpad(
    url: str,
) -> dict:
    """
    Fetch and parse a Wattpad story page.
    """

    html = fetch(url)

    return parse_wattpad(
        html=html,
        source_url=url,
    )


def scrape_wattpad_many(
    urls: list[str],
) -> list[dict]:
    """
    Fetch and parse multiple Wattpad story pages.

    Each URL is processed independently. If one URL fails,
    the error is printed and scraping continues with the
    remaining URLs.

    Returns a list containing the successfully scraped novels.
    """

    novels = []

    for index, url in enumerate(urls, start=1):
        print()
        print("=" * 70)
        print(f"WATTPAD NOVEL {index} OF {len(urls)}")
        print("=" * 70)
        print(f"URL: {url}")

        try:
            novel = scrape_wattpad(url)

            novels.append(novel)

            print()
            print("Successfully scraped:")
            print(f"  title:  {novel['title']}")
            print(f"  author: {novel['author']}")
            print(f"  status: {novel['status']}")

        except Exception as exc:
            print()
            print("FAILED:")
            print(f"  {type(exc).__name__}: {exc}")

    return novels


if __name__ == "__main__":
    urls = [
        "https://www.wattpad.com/story/"
        "150854149-reincarnated-as-a-demon%27s-wife",
        "https://www.wattpad.com/story/"
        "399857198-saanvi-daughter-of-vaikuntha",
        "https://www.wattpad.com/story/"
        "414644283-the-villainess-who-only-wished-for-her-cat%27s",

    ]

    novels = scrape_wattpad_many(urls)

    print()
    print("=" * 70)
    print("SCRAPING COMPLETE")
    print("=" * 70)
    print(f"Successfully scraped: {len(novels)}")
    print(f"Failed:               {len(urls) - len(novels)}")

    for novel in novels:
        print()
        print("-" * 70)
        print(f"Title:  {novel['title']}")
        print(f"Author: {novel['author']}")
        print(f"ID:     {novel['story_id']}")