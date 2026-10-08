"""
Find out exactly why a novel URL can't be scraped on this machine.

Run from the backend folder (use the same Python/venv as the API):

    python -m scraper.diagnose_scrape "Royal Road" "https://www.royalroad.com/fiction/21220/mother-of-learning"
    python -m scraper.diagnose_scrape "WebNovel"   "https://www.webnovel.com/book/shadow-slave_22196546206090805"
    python -m scraper.diagnose_scrape "Wattpad"    "https://www.wattpad.com/story/124711439"

It prints library versions, what the site actually returned (status, redirects,
content type, first bytes) and then runs the real scraper and shows the
full traceback if it fails. Paste the output when asking for help.
"""

import platform
import re
import sys
import traceback
from importlib import metadata

import httpx
import requests

from scraper import royalroad, wattpad, webnovel


def version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "NOT INSTALLED"


def describe(status, final_url, history, headers, body: bytes) -> None:
    print(f"  status:           {status}")
    print(f"  final URL:        {final_url}")
    print(f"  redirects:        {history}")
    print(f"  content-type:     {headers.get('content-type')}")
    print(f"  content-encoding: {headers.get('content-encoding')}")
    print(f"  body bytes:       {len(body)}")
    text = body.decode("utf-8", errors="replace")
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    print(f"  <title>:          {' '.join(title.group(1).split())[:120] if title else None}")
    print(f"  first 200 chars:  {' '.join(text[:200].split())!r}")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    source, url = sys.argv[1], sys.argv[2].strip()

    print("ENVIRONMENT")
    print(f"  python {platform.python_version()} on {platform.platform()}")
    for name in ("httpx", "requests", "urllib3", "selectolax", "beautifulsoup4",
                 "certifi", "truststore", "brotli", "brotlicffi", "zstandard"):
        print(f"  {name}: {version(name)}")

    handlers = {
        "royal road": (royalroad, royalroad.scrape_royalroad, royalroad.normalize_url),
        "webnovel": (webnovel, webnovel.scrape_webnovel, webnovel.normalize_url),
        "wattpad": (wattpad, wattpad.scrape_wattpad, lambda value: value),
    }
    module, scrape, normalize = handlers[source.casefold()]

    print("\nRAW REQUEST (same headers the scraper uses)")
    try:
        target = normalize(url)
        if source.casefold() == "webnovel":
            r = requests.get(target, headers=module.HEADERS, timeout=20, allow_redirects=True)
            describe(r.status_code, r.url, [h.status_code for h in r.history], r.headers, r.content)
        else:
            r = httpx.get(target, headers=module.HEADERS, timeout=20, follow_redirects=True)
            describe(r.status_code, str(r.url), [h.status_code for h in r.history], r.headers, r.content)
    except Exception:
        traceback.print_exc()

    print("\nREAL SCRAPE")
    try:
        novel = scrape(url)
        print(f"  OK: {novel.get('title')!r} by {novel.get('author')!r}, "
              f"{len(novel.get('tags') or [])} tags, status={novel.get('status')}")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()