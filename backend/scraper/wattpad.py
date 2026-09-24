import re
from urllib.parse import urljoin
import json

import httpx
from selectolax.parser import HTMLParser

from .genres import IN_HOUSE_GENRES


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


def clean_synopsis(
    node: HTMLParser,
) -> str | None:
    """
    Clean synopsis text while preserving paragraph breaks.

    Whitespace inside each paragraph is normalized, while
    separate paragraphs remain separated by a blank line.
    """

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


def extract_jsonld_data(
    tree: HTMLParser,
) -> list:
    """
    Extract JSON-LD objects from the page.

    Wattpad may expose structured story metadata through
    application/ld+json scripts.
    """

    results = []

    for script in tree.css(
        "script[type='application/ld+json']"
    ):
        text = script.text()

        if not text:
            continue

        text = text.strip()

        if not text:
            continue

        try:
            data = json.loads(text)

        except json.JSONDecodeError:
            # Some sites contain malformed JSON-LD.
            # Ignore it and continue searching other scripts.
            continue

        if isinstance(data, list):
            results.extend(data)

        else:
            results.append(data)

    return results


def find_genre_values(
    value,
) -> list[str]:
    """
    Recursively find genre/category values inside structured data.
    """

    genres = []

    if isinstance(value, dict):

        for key, child in value.items():

            key_lower = key.lower()

            if key_lower in {
                "genre",
                "genres",
            }:

                if isinstance(child, str):

                    child = child.strip()

                    if child:
                        genres.append(child)

                elif isinstance(child, list):

                    for item in child:

                        if isinstance(item, str):

                            item = item.strip()

                            if item:
                                genres.append(item)

            # Continue recursively through nested data.
            genres.extend(
                find_genre_values(child)
            )

    elif isinstance(value, list):

        for child in value:

            genres.extend(
                find_genre_values(child)
            )

    return genres


def normalize_genre_value(
    value: str,
) -> str | None:
    """
    Normalize a single Wattpad genre value.

    Wattpad JSON-LD may expose genres as URLs such as:

        https://www.wattpad.com/stories/fantasy

    Convert those URLs into human-readable genre names:

        Fantasy

    Plain genre strings are preserved.
    """

    if not value:
        return None

    value = str(value).strip()

    if not value:
        return None

    # ---------------------------------------------------------
    # Wattpad genre URL
    # ---------------------------------------------------------

    match = re.match(
        r"^https?://(?:www\.)?wattpad\.com/stories/([^/?#]+)/?$",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        slug = match.group(1)

        # Convert:
        #
        # dark-fantasy -> Dark Fantasy
        # science-fiction -> Science Fiction
        # young-adult -> Young Adult
        #
        # Preserve normal capitalization through title().
        genre = re.sub(
            r"[-_]+",
            " ",
            slug,
        )

        genre = genre.strip()

        if not genre:
            return None

        return genre.title()

    # ---------------------------------------------------------
    # Plain genre value
    # ---------------------------------------------------------

    value = value.replace(
        "&amp;",
        "&",
    )

    value = value.replace(
        "&#39;",
        "'",
    )

    value = value.replace(
        "&quot;",
        '"',
    )

    return value.strip() or None


def normalize_genres(
    genres,
) -> list[str]:
    """
    Normalize and deduplicate Wattpad genre values while
    preserving their original order.
    """

    normalized = []

    for genre in genres:

        if genre is None:
            continue

        genre = normalize_genre_value(
            str(genre)
        )

        if not genre:
            continue

        # Case-insensitive duplicate detection.
        if any(
            existing.lower() == genre.lower()
            for existing in normalized
        ):
            continue

        normalized.append(genre)

    return normalized


def extract_genres_from_jsonld(
    tree: HTMLParser,
) -> list[str]:
    """
    Extract genres from Wattpad's JSON-LD structured data.
    """

    jsonld_objects = extract_jsonld_data(tree)

    genres = []

    for obj in jsonld_objects:
        genres.extend(
            find_genre_values(obj)
        )

    return normalize_genres(genres)


def extract_genres(
    tree: HTMLParser,
    remix_story: dict | None = None,
) -> list[str]:
    """
    Extract Wattpad story genres/categories.

    Extraction sources:

        1. JSON-LD structured data
        2. Remix story data
        3. Story metadata section
        4. Explicit genre meta tag
        5. Article section
        6. Generic genre/category metadata

    All discovered values are combined and deduplicated.

    Tags are intentionally NOT treated as genres here.
    They are classified later against IN_HOUSE_GENRES.
    """

    genres = []

    # ---------------------------------------------------------
    # 1. JSON-LD
    # ---------------------------------------------------------

    genres.extend(
        extract_genres_from_jsonld(tree)
    )

    # ---------------------------------------------------------
    # 2. Remix story data
    # ---------------------------------------------------------

    if remix_story:

        for key in (
            "genre",
            "genres",
            "category",
            "categories",
        ):

            value = remix_story.get(key)

            if isinstance(value, str):

                value = value.strip()

                if value:
                    genres.append(value)

            elif isinstance(value, list):

                for item in value:

                    if isinstance(item, str):

                        item = item.strip()

                        if item:
                            genres.append(item)

    # ---------------------------------------------------------
    # 3. Story metadata section
    #
    # This is where Wattpad may expose values such as:
    #
    #     Complete
    #     Fiction
    #     Romance
    #
    # These must be collected before classification.
    # ---------------------------------------------------------

    genres.extend(
        extract_taxonomy_genres(tree)
    )

    # ---------------------------------------------------------
    # 4. Explicit genre meta tag
    # ---------------------------------------------------------

    meta = tree.css_first(
        "meta[name='genre']"
    )

    if meta:

        content = (
            meta.attributes.get("content")
            or ""
        ).strip()

        if content:
            genres.extend(
                re.split(
                    r"\s*,\s*",
                    content,
                )
            )

    # ---------------------------------------------------------
    # 5. Article section
    # ---------------------------------------------------------

    meta = tree.css_first(
        "meta[property='article:section']"
    )

    if meta:

        content = (
            meta.attributes.get("content")
            or ""
        ).strip()

        if content:
            genres.append(content)

    # ---------------------------------------------------------
    # 6. Generic genre/category attributes
    # ---------------------------------------------------------

    selectors = [
        "[data-testid*='genre']",
        "[data-testid*='category']",
        "[class*='genre']",
        "[class*='Genre']",
        "[class*='category']",
        "[class*='Category']",
    ]

    for selector in selectors:

        for node in tree.css(selector):

            text = clean_text(node)

            if text:
                genres.append(text)

    return normalize_genres(
        genres
    )


def extract_synopsis(
    tree: HTMLParser,
) -> str | None:
    """
    Extract the full Wattpad story synopsis while preserving
    paragraph breaks.

    Wattpad visually truncates the description with CSS,
    but the full text is still present in the HTML.
    """

    # Find the description container by looking for
    # the "Read more" button that belongs to it.
    for button in tree.css("button"):

        button_text = clean_text(
            button
        )

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

        description = clean_synopsis(
            description_node
        )

        if not description:
            continue

        # Remove text that appears after the actual synopsis.
        description = description.split(
            "HIGHEST RANK",
            1,
        )[0]

        description = description.split(
            "All Rights Reserved",
            1,
        )[0]

        description = description.strip()

        if description:
            return description

    # ---------------------------------------------------------
    # Fallback to the meta description.
    #
    # Meta descriptions usually do not preserve paragraph
    # structure, but preserve newlines if they happen to exist.
    # ---------------------------------------------------------

    meta = tree.css_first(
        "meta[name='description']"
    )

    if meta:

        description = (
            meta.attributes.get("content")
            or ""
        ).strip()

        if description:

            paragraphs = []

            for paragraph in re.split(
                r"\n+",
                description,
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

    return None

def normalize_tags(
    tags: list[str],
) -> list[str]:
    """
    Normalize Wattpad tags so that the first character is
    uppercase and all subsequent characters are lowercase.
    """

    normalized = []

    for tag in tags:

        if not tag:
            continue

        tag = tag.strip()

        if not tag:
            continue

        tag = tag.upper()

        if tag not in normalized:
            normalized.append(tag)

    return normalized

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

    tags = normalize_tags(tags)
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

def extract_taxonomy_genres(
    tree: HTMLParser,
) -> list[str]:
    """
    Extract Wattpad genres/categories from the taxonomy row.

    Wattpad may render the taxonomy separator inside the
    preceding label, e.g. "Fiction •". Remove the separator
    before returning the genre value.
    """

    genres = []

    taxonomy_row = tree.css_first(
        "[data-testid='taxonomy-row']"
    )

    if taxonomy_row is None:
        return []

    for node in taxonomy_row.css(
        "[data-testid='label']"
    ):
        text = clean_text(node)

        if not text:
            continue

        # Wattpad may include the taxonomy separator in the
        # first label, e.g. "Fiction •".
        text = re.sub(
            r"\s*[•·]\s*$",
            "",
            text,
        ).strip()

        if not text:
            continue

        if not any(
            existing.casefold() == text.casefold()
            for existing in genres
        ):
            genres.append(text)

    return normalize_genres(
        genres
    )

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

def extract_part_count(
    tree: HTMLParser,
    remix_story: dict | None = None,
) -> int | None:
    """
    Extract the total number of Wattpad story parts.

    Wattpad calls chapters "parts".

    Extraction order:

        1. Embedded Remix story data
        2. Visible page text such as "42 Parts"

    Different Wattpad versions may use different field names
    for the count, so several common names are checked.
    """

    # ---------------------------------------------------------
    # 1. Check the embedded Remix story data.
    #
    # Wattpad's exact field name can vary between versions,
    # so check several possible names.
    # ---------------------------------------------------------

    if remix_story:

        possible_keys = [
            "part_count",
            "partCount",
            "parts_count",
            "partsCount",
            "chapter_count",
            "chapterCount",
            "total_parts",
            "totalParts",
            "total_chapters",
            "totalChapters",
        ]

        for key in possible_keys:

            value = remix_story.get(key)

            if value is None:
                continue

            # Already numeric.
            if isinstance(
                value,
                int,
            ):
                if value >= 0:
                    return value

            # Numeric string.
            if isinstance(
                value,
                str,
            ):
                value = value.strip()

                if re.fullmatch(
                    r"\d[\d,]*",
                    value,
                ):
                    try:
                        count = int(
                            value.replace(
                                ",",
                                "",
                            )
                        )

                        if count >= 0:
                            return count

                    except ValueError:
                        pass

    # ---------------------------------------------------------
    # 2. Search the visible Wattpad page.
    #
    # Wattpad displays the count as something like:
    #
    #     42 Parts
    #
    # or:
    #
    #     1,234 Parts
    # ---------------------------------------------------------

    text = tree.text(
        separator=" ",
        strip=True,
    )

    if text:

        match = re.search(
            r"\b([\d,]+)\s+Parts?\b",
            text,
            flags=re.IGNORECASE,
        )

        if match:

            try:
                return int(
                    match.group(1).replace(
                        ",",
                        "",
                    )
                )

            except ValueError:
                pass

    return None

def classify_genres_and_tags(
    genres: list[str],
    tags: list[str],
) -> tuple[list[str], list[str]]:
    """
    Classify every extracted genre and tag against the shared
    in-house genre list.

    Values that match an in-house genre are placed in genres.
    Everything else is placed in tags. Matching is case-insensitive,
    while recognized genres use the exact capitalization from
    IN_HOUSE_GENRES.
    """

    genre_lookup = {
        genre.casefold(): genre
        for genre in IN_HOUSE_GENRES
    }

    classified_genres = []
    classified_tags = []

    for value in list(genres) + list(tags):
        if not isinstance(value, str):
            continue

        value = value.strip()
        if not value:
            continue

        genre = genre_lookup.get(value.casefold())

        if genre is not None:
            if genre not in classified_genres:
                classified_genres.append(genre)
        else:
            if not any(
                existing.casefold() == value.casefold()
                for existing in classified_tags
            ):
                classified_tags.append(value)

    return classified_genres, classified_tags

def debug_story_metadata_context(
    tree: HTMLParser,
) -> None:
    """
    Print the DOM surrounding Wattpad's story-meta element.
    """

    metadata = tree.css_first(
        "[data-testid='story-meta']"
    )

    if metadata is None:
        print("story-meta NOT FOUND")
        return

    print("\n--- STORY META PARENT ---")

    parent = metadata.parent

    if parent:
        print(parent.html)

    print("\n--- STORY META GRANDPARENT ---")

    if parent and parent.parent:
        print(parent.parent.html)

    print("\n--- ELEMENTS AROUND STORY META ---")

    if parent:
        for child in parent.iter():
            text = clean_text(child)

            if text:
                print(
                    f"{child.tag} "
                    f"class={child.attributes.get('class')} "
                    f"testid={child.attributes.get('data-testid')} "
                    f"text={text!r}"
                )

    print("--- END STORY META CONTEXT ---\n")


def parse_wattpad(
    html: str,
    source_url: str,
) -> dict:
    """
    Parse a Wattpad story page into normalized source data.

    Wattpad embeds structured story metadata in its Remix
    context. That data is preferred over DOM scraping.

    Genre extraction is performed independently because genre
    information may exist in JSON-LD or page metadata even when
    the Remix story record does not contain it.
    """

    tree = HTMLParser(html)

    story_id = extract_story_id(
        source_url
    )

    # ---------------------------------------------------------
    # Primary extraction: embedded Remix story data
    # ---------------------------------------------------------

    remix_story = extract_remix_story_data(
        tree
    )

    part_count = extract_part_count(
        tree,
        remix_story=remix_story,
    )

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

        remix_story_id = remix_story.get(
            "story_id"
        )

        if remix_story_id:

            try:
                story_id = int(
                    remix_story_id
                )

            except (
                TypeError,
                ValueError,
            ):
                pass

    else:

        # -----------------------------------------------------
        # DOM fallback
        # -----------------------------------------------------

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

    # ---------------------------------------------------------
    # Classify all extracted genres and tags against the shared
    # in-house genre list.
    # ---------------------------------------------------------

    genres = extract_genres(
        tree,
        remix_story=remix_story,
    )

    genres, tags = classify_genres_and_tags(
        genres,
        tags,
    )
    tags = normalize_tags(tags)

    return {
        "source": "wattpad",
        "source_url": source_url,
        "story_id": story_id,
        "title": title,
        "author": author,
        "status": status,
        "chapter_count": part_count,
        "genres": genres,
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
            print(f"  title:    {novel['title']}")
            print(f"  author:   {novel['author']}")
            print(f"  status:   {novel['status']}")
            print(f"  chapters: {novel['chapter_count']}")

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
        "248229220-bound-to-earth",

        "https://www.wattpad.com/story/246002648",
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
        print(f"Title:    {novel['title']}")
        print(f"Author:   {novel['author']}")
        print(f"ID:       {novel.get('story_id')}")
        print(f"Status:   {novel.get('status')}")
        print(f"Chapters: {novel.get('chapter_count')}")
        print(f"Genres:   {novel.get('genres')}")
        print(f"Tags:     {novel.get('tags')}")
        print(f"Synopsis: {novel.get('synopsis')}")