import json
import re

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.webnovel.com"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def normalize_url(
    url_or_id: str,
) -> str:
    """
    Convert a WebNovel URL or numeric book ID into a
    standard WebNovel book URL.

    Examples:

        7996858406002505

    becomes:

        https://www.webnovel.com/book/7996858406002505

    A full WebNovel URL is returned unchanged.
    """

    value = str(url_or_id).strip()

    if not value:
        raise ValueError(
            "WebNovel URL or ID cannot be empty."
        )

    # Already a WebNovel URL.
    if "webnovel.com" in value.lower():
        return value

    # Numeric ID.
    if value.isdigit():
        return (
            f"{BASE_URL}/book/{value}"
        )

    raise ValueError(
        f"Could not understand WebNovel URL or ID: {value}"
    )


def extract_story_id(
    source_url: str,
) -> int:
    """
    Extract the numeric WebNovel book ID.

    WebNovel URLs normally look like:

        /book/reverend-insanity_7996858406002505
    """

    match = re.search(
        r"_(\d+)(?:[/?#]|$)",
        source_url,
    )

    if not match:
        # Also support URLs where the ID appears directly
        # after /book/.
        match = re.search(
            r"/book/(\d+)",
            source_url,
        )

    if not match:
        raise ValueError(
            f"Could not extract WebNovel book ID from: "
            f"{source_url}"
        )

    return int(match.group(1))


def clean_text(
    text: str | None,
) -> str | None:
    """
    Normalize whitespace in extracted text.
    """

    if not text:
        return None

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip() or None

def clean_synopsis(
    text: str | None,
) -> str | None:
    """
    Clean synopsis text while preserving paragraph breaks.

    Each non-empty line is treated as a paragraph.
    Whitespace inside a paragraph is normalized, but paragraphs
    remain separated by a blank line.
    """

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


def fetch(
    url: str,
) -> str:
    """
    Fetch a public WebNovel book page.

    WebNovel can return unusual responses depending on the
    requested URL, so this function keeps the request simple
    and uses the same working approach as our diagnostic.
    """

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20,
        allow_redirects=True,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "",
    )

    if (
        "text/html" not in
        content_type.lower()
    ):
        raise ValueError(
            "Expected HTML from WebNovel, got: "
            f"{content_type}"
        )

    return response.text

def fetch_review_statistics(
    story_id: int,
) -> dict:
    """
    Fetch WebNovel review statistics for a book.

    Returns:
        {
            "total_score": float | None,
            "total_review_num": int | None,
        }

    This uses WebNovel's public book-review endpoint rather than
    attempting to extract review statistics from the book HTML.
    """

    url = (
        f"{BASE_URL}/go/pcm/bookReview/get-reviews"
    )

    params = {
        "bookId": story_id,
        "pageIndex": 1,
        "pageSize": 20,
        "orderBy": 1,
        "novelType": 0,
        "needSummary": 1,
    }

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=20,
        allow_redirects=True,
    )

    response.raise_for_status()

    data = response.json()

    statistics = (
        data
        .get("data", {})
        .get("bookStatisticsInfo", {})
    )

    total_score = statistics.get(
        "totalScore"
    )

    total_review_num = statistics.get(
        "totalReviewNum"
    )

    try:
        if total_score is not None:
            total_score = float(
                total_score
            )
    except (
        TypeError,
        ValueError,
    ):
        total_score = None

    try:
        if total_review_num is not None:
            total_review_num = int(
                total_review_num
            )
    except (
        TypeError,
        ValueError,
    ):
        total_review_num = None

    return {
        "total_score": total_score,
        "total_review_num": total_review_num,
    }


def extract_js_string(
    text: str,
    key: str,
) -> str | None:
    """
    Extract a simple quoted JavaScript string value.

    Handles WebNovel's unusual escaping such as:

        "authorName":"Gu\ Zhen\ Ren"

    The backslash before a space is removed.
    """

    pattern = (
        rf'"{re.escape(key)}"\s*:\s*"'
    )

    match = re.search(
        pattern,
        text,
    )

    if not match:
        return None

    start = match.end()

    chars = []
    escaped = False

    for index in range(
        start,
        len(text),
    ):
        char = text[index]

        if escaped:
            # WebNovel sometimes uses invalid escapes such as
            # \  and \'
            if char == " ":
                chars.append(" ")
            elif char == "'":
                chars.append("'")
            else:
                # Preserve normal escaped characters.
                chars.append(char)

            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            break

        chars.append(char)

    value = "".join(chars)

    return clean_text(value)


def extract_author_from_gdata(
    soup: BeautifulSoup,
) -> str | None:
    """
    Extract authorName directly from WebNovel's g_data.book
    without requiring the entire object to be valid JSON.
    """

    for script in soup.find_all("script"):

        text = script.get_text()

        if not text:
            continue

        if "g_data.book" not in text:
            continue

        author = extract_js_string(
            text,
            "authorName",
        )

        if author:
            return author

    return None

def extract_tags_from_gdata(
    soup: BeautifulSoup,
) -> list[str]:
    """
    Extract WebNovel tags directly from g_data.book.bookInfo.

    This deliberately avoids json.loads() because the massive
    WebNovel object may contain invalid JavaScript escapes elsewhere.
    """

    for script in soup.find_all("script"):

        text = script.get_text()

        if not text:
            continue

        if "g_data.book" not in text:
            continue

        # Find tagInfos.
        match = re.search(
            r'"tagInfos"\s*:\s*\[',
            text,
        )

        if not match:
            continue

        start = match.end()

        # Find the closing ] for tagInfos.
        depth = 1
        in_string = False
        escaped = False
        end = None

        for index in range(
            start,
            len(text),
        ):

            char = text[index]

            if in_string:

                if escaped:
                    escaped = False
                    continue

                if char == "\\":
                    escaped = True
                    continue

                if char == '"':
                    in_string = False

                continue

            if char == '"':
                in_string = True

            elif char == "[":
                depth += 1

            elif char == "]":
                depth -= 1

                if depth == 0:
                    end = index
                    break

        if end is None:
            continue

        tag_text = text[
            start:end
        ]

        # Extract enTagName first.
        tags = re.findall(
            r'"enTagName"\s*:\s*"((?:\\.|[^"\\])*)"',
            tag_text,
        )

        cleaned_tags = []

        for tag in tags:

            # WebNovel's unusual escapes.
            tag = re.sub(
                r"\\(?=\s)",
                "",
                tag,
            )

            tag = tag.replace(
                "\\'",
                "'",
            )

            tag = tag.replace(
                '\\"',
                '"',
            )

            tag = clean_text(
                tag
            )

            if tag and tag not in cleaned_tags:
                cleaned_tags.append(tag)

        if cleaned_tags:
            return cleaned_tags

    return []


def extract_title(
    soup: BeautifulSoup,
) -> str | None:
    """
    Extract the WebNovel book title.

    Try several common locations because WebNovel's HTML
    structure can vary.
    """

    # ---------------------------------------------------------
    # 1. Open Graph title
    # ---------------------------------------------------------

    node = soup.find(
        "meta",
        attrs={
            "property": "og:title"
        },
    )

    if node:
        title = clean_text(
            node.get("content")
        )

        if title:
            return title

    # ---------------------------------------------------------
    # 2. Twitter title
    # ---------------------------------------------------------

    node = soup.find(
        "meta",
        attrs={
            "name": "twitter:title"
        },
    )

    if node:
        title = clean_text(
            node.get("content")
        )

        if title:
            return title

    # ---------------------------------------------------------
    # 3. JSON-LD
    # ---------------------------------------------------------

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        },
    ):
        try:
            data = json.loads(
                script.string or
                script.get_text()
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        if isinstance(data, dict):
            title = clean_text(
                data.get("name")
            )

            if title:
                return title

    # ---------------------------------------------------------
    # 4. Common title elements
    # ---------------------------------------------------------

    selectors = [
        "h1.book-name",
        "h1.bookName",
        "h1.title",
        "h1",
    ]

    for selector in selectors:
        node = soup.select_one(selector)

        if node:
            title = clean_text(
                node.get_text(" ", strip=True)
            )

            if title:
                return title

    # ---------------------------------------------------------
    # 5. HTML <title>
    # ---------------------------------------------------------

    if soup.title:
        title = clean_text(
            soup.title.get_text()
        )

        if title:
            # WebNovel titles may be followed by
            # " - WebNovel" or similar site text.
            title = re.sub(
                r"\s*[-|]\s*WebNovel.*$",
                "",
                title,
                flags=re.IGNORECASE,
            )

            return title.strip() or None

    return None


def extract_author(
    soup: BeautifulSoup,
) -> str | None:
    """
    Extract the actual WebNovel author.

    Prefer the authorName stored in g_data.book.bookInfo.
    """

    return extract_author_from_gdata(
        soup
    )


def extract_status(
    soup: BeautifulSoup,
) -> str | None:
    """
    Extract the WebNovel book status.

    The working HTML approach has shown that the page
    contains the word 'Completed' for completed books.

    We therefore look for explicit completion markers
    before falling back to Ongoing.
    """

    text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    if not text:
        return None

    # Explicit completed markers.
    completed_patterns = [
        r"\bCompleted\b",
        r"\bComplete\b",
    ]

    for pattern in completed_patterns:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return "Completed"

    # Explicit ongoing markers.
    ongoing_patterns = [
        r"\bOngoing\b",
        r"\bUpdating\b",
        r"\bIn Progress\b",
    ]

    for pattern in ongoing_patterns:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return "Ongoing"

    return None


def extract_synopsis(
    soup: BeautifulSoup,
) -> str | None:
    """
    Extract the full WebNovel synopsis from the page while
    preserving paragraph breaks.

    WebNovel's meta description can be truncated, so it should
    NOT be our primary source.

    Instead, look for the actual Synopsis section in the page
    HTML and extract the text belonging to that section.

    Fall back to metadata only if the full synopsis cannot be
    located.
    """

    # ---------------------------------------------------------
    # 1. Look for an element explicitly representing the
    #    synopsis/description.
    # ---------------------------------------------------------

    selectors = [
        ".book-desc",
        ".bookDesc",
        ".book-description",
        ".bookDescription",
        ".synopsis",
        ".description",
        "[class*='book-desc']",
        "[class*='bookDesc']",
        "[class*='synopsis']",
        "[class*='description']",
    ]

    candidates = []

    for selector in selectors:

        nodes = soup.select(
            selector
        )

        for node in nodes:

            text = clean_synopsis(
                node.get_text(
                    "\n",
                    strip=True,
                )
            )

            if not text:
                continue

            # Ignore extremely short elements.
            if len(text) < 40:
                continue

            candidates.append(
                text
            )

    # Prefer the longest candidate.
    if candidates:

        candidates.sort(
            key=len,
            reverse=True,
        )

        return candidates[0]

    # ---------------------------------------------------------
    # 2. Search for the visible "Synopsis" heading and use
    #    the surrounding HTML structure.
    # ---------------------------------------------------------

    for node in soup.find_all(
        string=re.compile(
            r"^\s*Synopsis\s*$",
            re.IGNORECASE,
        )
    ):

        heading = node.parent

        if heading is None:
            continue

        # Try the parent container first.
        parent = heading.parent

        if parent is not None:

            text = clean_synopsis(
                parent.get_text(
                    "\n",
                    strip=True,
                )
            )

            if text:

                # Remove the Synopsis heading.
                text = re.sub(
                    r"^\s*Synopsis\s*\n*",
                    "",
                    text,
                    flags=re.IGNORECASE,
                ).strip()

                if len(text) >= 40:
                    return text

        # Try the next sibling.
        sibling = heading.find_next_sibling()

        if sibling is not None:

            text = clean_synopsis(
                sibling.get_text(
                    "\n",
                    strip=True,
                )
            )

            if text and len(text) >= 40:
                return text

    # ---------------------------------------------------------
    # 3. Look for JSON-LD description.
    #
    # JSON-LD may contain embedded newlines, so use
    # clean_synopsis rather than clean_text.
    # ---------------------------------------------------------

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        },
    ):

        try:

            data = json.loads(
                script.string
                or script.get_text()
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        if not isinstance(
            data,
            dict,
        ):
            continue

        description = clean_synopsis(
            data.get("description")
        )

        if (
            description
            and len(description) >= 40
        ):
            return description

    # ---------------------------------------------------------
    # 4. Open Graph description.
    #
    # This may be truncated, so it is deliberately a fallback.
    # ---------------------------------------------------------

    node = soup.find(
        "meta",
        attrs={
            "property": "og:description"
        },
    )

    if node:

        description = clean_synopsis(
            node.get("content")
        )

        if description:
            return description

    # ---------------------------------------------------------
    # 5. Standard meta description.
    #
    # Last resort only.
    # ---------------------------------------------------------

    node = soup.find(
        "meta",
        attrs={
            "name": "description"
        },
    )

    if node:

        description = clean_synopsis(
            node.get("content")
        )

        if description:
            return description

    return None


def extract_tags(
    soup: BeautifulSoup,
) -> list[str]:
    """
    Extract WebNovel tags from g_data.book.bookInfo.tagInfos.
    """

    return extract_tags_from_gdata(
        soup
    )


def extract_cover(
    soup: BeautifulSoup,
    story_id: int,
) -> str | None:
    """
    Extract the actual WebNovel cover URL.

    Do NOT construct the URL from the book ID. WebNovel's
    image URLs can contain additional path information.

    Try Open Graph, Twitter, JSON-LD, then image elements.
    """

    # ---------------------------------------------------------
    # 1. Open Graph image
    # ---------------------------------------------------------

    node = soup.find(
        "meta",
        attrs={
            "property": "og:image"
        },
    )

    if node:
        image_url = node.get("content")

        if image_url:
            return image_url.strip()

    # ---------------------------------------------------------
    # 2. Twitter image
    # ---------------------------------------------------------

    node = soup.find(
        "meta",
        attrs={
            "name": "twitter:image"
        },
    )

    if node:
        image_url = node.get("content")

        if image_url:
            return image_url.strip()

    # ---------------------------------------------------------
    # 3. JSON-LD image
    # ---------------------------------------------------------

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        },
    ):
        try:
            data = json.loads(
                script.string or
                script.get_text()
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        if not isinstance(data, dict):
            continue

        image = data.get("image")

        if isinstance(image, str):
            return image

        if isinstance(image, list):
            for item in image:
                if isinstance(item, str):
                    return item

        if isinstance(image, dict):
            image_url = image.get("url")

            if image_url:
                return image_url

    # ---------------------------------------------------------
    # 4. Image elements
    # ---------------------------------------------------------

    candidates = []

    for image in soup.find_all("img"):
        src = (
            image.get("src")
            or image.get("data-src")
            or image.get("data-original")
        )

        if not src:
            continue

        src = src.strip()

        alt = clean_text(
            image.get("alt")
        ) or ""

        score = 0

        # Book ID appearing in the image URL is useful.
        if str(story_id) in src:
            score += 100

        # Cover-related URLs are useful.
        if "cover" in src.lower():
            score += 50

        # Alt text containing book-related language.
        if "cover" in alt.lower():
            score += 20

        candidates.append(
            (score, src)
        )

    if candidates:
        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return candidates[0][1]

    return None


def extract_reading_url(
    source_url: str,
) -> str:
    """
    Return the WebNovel book page as the reading URL.
    """

    return source_url

def debug_author_and_tags(
    soup: BeautifulSoup,
) -> None:
    """
    Diagnose how WebNovel exposes the author and tags
    in the HTML returned to our scraper.
    """

    print()
    print("=" * 70)
    print("WEBNOVEL AUTHOR / TAG DIAGNOSTIC")
    print("=" * 70)

    # ---------------------------------------------------------
    # AUTHOR
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("AUTHOR CANDIDATES")
    print("=" * 70)

    found_author = False

    for index, text_node in enumerate(
        soup.find_all(
            string=re.compile(
                r"Author",
                re.IGNORECASE,
            )
        )
    ):
        text = clean_text(str(text_node))

        if not text:
            continue

        found_author = True

        print()
        print(f"CANDIDATE #{index}")
        print("TEXT:", text)

        parent = text_node.parent

        if parent:
            print("PARENT TAG:", parent.name)
            print(
                "PARENT ATTRIBUTES:",
                parent.attrs,
            )
            print(
                "PARENT TEXT:",
                clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                ),
            )
            print(
                "PARENT HTML:",
                str(parent)[:3000],
            )

            # Look at the parent and nearby elements.
            grandparent = parent.parent

            if grandparent:
                print()
                print("GRANDPARENT TAG:", grandparent.name)
                print(
                    "GRANDPARENT ATTRIBUTES:",
                    grandparent.attrs,
                )
                print(
                    "GRANDPARENT TEXT:",
                    clean_text(
                        grandparent.get_text(
                            " ",
                            strip=True,
                        )
                    ),
                )
                print(
                    "GRANDPARENT HTML:",
                    str(grandparent)[:5000],
                )

    if not found_author:
        print("NO AUTHOR TEXT FOUND")

    # ---------------------------------------------------------
    # TITLE FALLBACK INVESTIGATION
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("TITLE ELEMENT")
    print("=" * 70)

    if soup.title:
        print(
            "TITLE:",
            clean_text(
                soup.title.get_text()
            ),
        )

    # ---------------------------------------------------------
    # TAG SECTION
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("TAG CANDIDATES")
    print("=" * 70)

    found_tags = False

    for index, node in enumerate(
        soup.find_all(
            string=re.compile(
                r"REINCARNATION|VILLAIN|CULTIVATION|TRANSMIGRATION",
                re.IGNORECASE,
            )
        )
    ):
        text = clean_text(str(node))

        if not text:
            continue

        found_tags = True

        print()
        print(f"CANDIDATE #{index}")
        print("TEXT:", text)

        parent = node.parent

        if parent:
            print("PARENT TAG:", parent.name)
            print(
                "PARENT ATTRIBUTES:",
                parent.attrs,
            )
            print(
                "PARENT TEXT:",
                clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                ),
            )
            print(
                "PARENT HTML:",
                str(parent)[:3000],
            )

            grandparent = parent.parent

            if grandparent:
                print()
                print(
                    "GRANDPARENT TAG:",
                    grandparent.name,
                )
                print(
                    "GRANDPARENT ATTRIBUTES:",
                    grandparent.attrs,
                )
                print(
                    "GRANDPARENT TEXT:",
                    clean_text(
                        grandparent.get_text(
                            " ",
                            strip=True,
                        )
                    ),
                )
                print(
                    "GRANDPARENT HTML:",
                    str(grandparent)[:5000],
                )

    if not found_tags:
        print("NO TAG TEXT FOUND")

    # ---------------------------------------------------------
    # [Input] INVESTIGATION
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("[INPUT] CANDIDATES")
    print("=" * 70)

    found_input = False

    for index, node in enumerate(
        soup.find_all(
            string=re.compile(
                r"\[Input\]",
                re.IGNORECASE,
            )
        )
    ):
        text = clean_text(str(node))

        if not text:
            continue

        found_input = True

        print()
        print(f"CANDIDATE #{index}")
        print("TEXT:", text)

        parent = node.parent

        if parent:
            print("PARENT TAG:", parent.name)
            print(
                "PARENT ATTRIBUTES:",
                parent.attrs,
            )
            print(
                "PARENT TEXT:",
                clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                ),
            )
            print(
                "PARENT HTML:",
                str(parent)[:3000],
            )

    if not found_input:
        print("NO [Input] TEXT FOUND")


def parse_webnovel(
    html: str,
    source_url: str,
) -> dict:
    """
    Parse a WebNovel book page into normalized source data.
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )


    story_id = extract_story_id(
        source_url
    )

    review_statistics = fetch_review_statistics(
        story_id
    )

    total_score = review_statistics.get(
        "total_score"
    )

    total_review_num = review_statistics.get(
        "total_review_num"
    )


    title = extract_title(soup)
    author = extract_author(soup)
    status = extract_status(soup)
    tags = extract_tags(soup)
    synopsis = extract_synopsis(soup)
    cover_image_url = extract_cover(
        soup,
        story_id,
    )
    reading_url = extract_reading_url(
        source_url
    )

    return {
        "source": "webnovel",
        "source_url": source_url,
        "story_id": story_id,
        "total_score": total_score,
        "total_review_num": total_review_num,
        "title": title,
        "author": author,
        "status": status,
        "tags": tags,
        "synopsis": synopsis,
        "cover_image_url": cover_image_url,
        "reading_url": reading_url,
    }


def scrape_webnovel(
    url_or_id: str,
) -> dict:
    """
    Fetch and parse one WebNovel book.

    Accepts either a complete WebNovel URL or a numeric
    book ID.
    """

    source_url = normalize_url(
        url_or_id
    )

    html = fetch(
        source_url
    )

    return parse_webnovel(
        html=html,
        source_url=source_url,
    )


def scrape_webnovels(
    urls_or_ids: list[str],
) -> list[dict]:
    """
    Fetch and parse multiple WebNovel books.

    A failure on one book does not stop the remaining books.

    Each failed book receives a small error record so that
    the caller can see which input failed.
    """

    results = []

    for value in urls_or_ids:
        print()
        print("=" * 70)
        print("WEBNOVEL")
        print("=" * 70)
        print("INPUT:", value)

        try:
            novel = scrape_webnovel(
                value
            )

            results.append(
                novel
            )

            print(
                "SUCCESS:",
                novel.get("title")
                or novel.get("story_id"),
            )

        except Exception as exc:
            print(
                "FAILED:",
                type(exc).__name__,
                str(exc),
            )

            results.append(
                {
                    "source": "webnovel",
                    "source_url": str(value),
                    "story_id": None,
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
        "https://www.webnovel.com/book/reverend-insanity_7996858406002505",
        "https://www.webnovel.com/book/radiant-blade-of-the-wilderness_35970900108664305",
        "https://www.webnovel.com/book/walker-of-the-worlds_17307252205313105",
        "https://www.webnovel.com/book/shadow-slave_22196546206090805",
    ]

    novels = scrape_webnovels(
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