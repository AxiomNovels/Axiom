import httpx
from selectolax.parser import HTMLParser


URL = "https://www.wattpad.com/story/150854149-reincarnated-as-a-demon%27s-wife"


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


def clean_text(node):
    if node is None:
        return None

    return node.text(
        separator=" ",
        strip=True,
    )


def main():
    print("=" * 70)
    print("WATTPAD DOM TEST")
    print("=" * 70)

    print()
    print("URL:")
    print(URL)

    print()
    print("Fetching...")

    response = httpx.get(
        URL,
        headers=HEADERS,
        follow_redirects=True,
        timeout=20,
    )

    print("STATUS:", response.status_code)
    print("FINAL URL:", response.url)
    print("CONTENT TYPE:", response.headers.get("content-type"))
    print("HTML LENGTH:", len(response.text))

    response.raise_for_status()

    tree = HTMLParser(response.text)

    print()
    print("=" * 70)
    print("TITLE")
    print("=" * 70)

    title = tree.css_first("title")

    if title:
        print(clean_text(title))
    else:
        print("NO TITLE FOUND")

    print()
    print("=" * 70)
    print("H1 ELEMENTS")
    print("=" * 70)

    h1s = tree.css("h1")

    print("Found:", len(h1s))

    for index, node in enumerate(h1s):
        print()
        print(f"H1 #{index}")
        print("TEXT:", clean_text(node))
        print("HTML:", node.html[:1000])

    print()
    print("=" * 70)
    print("META TAGS")
    print("=" * 70)

    for node in tree.css("meta"):
        name = node.attributes.get("name")
        prop = node.attributes.get("property")
        content = node.attributes.get("content")

        if name or prop:
            print(
                f"name={name!r} "
                f"property={prop!r} "
                f"content={content!r}"
            )

    print()
    print("=" * 70)
    print("LINKS CONTAINING STORY / AUTHOR / USER")
    print("=" * 70)

    for node in tree.css("a"):
        href = node.attributes.get("href", "")
        text = clean_text(node)

        combined = f"{href} {text or ''}".lower()

        if any(
            keyword in combined
            for keyword in (
                "story",
                "author",
                "user",
                "profile",
            )
        ):
            print()
            print("TEXT:", text)
            print("HREF:", href)


if __name__ == "__main__":
    main()