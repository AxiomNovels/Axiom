import httpx


URL = "https://www.webnovel.com/book/reverend-insanity_7996858406002505"


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
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def main():
    print("=" * 70)
    print("WEBNOVEL REQUEST DIAGNOSTIC")
    print("=" * 70)

    print()
    print("URL:")
    print(URL)

    print()
    print("Sending request...")

    try:
        with httpx.Client(
            headers=HEADERS,
            follow_redirects=True,
            timeout=20,
        ) as client:

            response = client.get(URL)

            print()
            print("STATUS:", response.status_code)
            print("FINAL URL:", response.url)
            print(
                "CONTENT TYPE:",
                response.headers.get("content-type"),
            )
            print(
                "CONTENT LENGTH:",
                len(response.content),
            )

            print()
            print("=" * 70)
            print("RESPONSE HEADERS")
            print("=" * 70)

            for key, value in response.headers.items():
                print(f"{key}: {value}")

            print()
            print("=" * 70)
            print("FIRST 2000 CHARACTERS OF RESPONSE")
            print("=" * 70)

            print(response.text[:2000])

    except Exception as exc:
        print()
        print("=" * 70)
        print("REQUEST FAILED")
        print("=" * 70)
        print(type(exc).__name__)
        print(str(exc))


if __name__ == "__main__":
    main()