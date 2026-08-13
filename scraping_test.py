import httpx
from selectolax.parser import HTMLParser

URL = "https://www.royalroad.com/fiction/21220/mother-of-learning"

resp = httpx.get(
    URL,
    headers={
        "User-Agent": "Axiom-catalog-research/0.1 (personal project)"
    },
    follow_redirects=True,
    timeout=20,
)

print("status:", resp.status_code)
print("url:", resp.url)
print("length:", len(resp.text))

tree = HTMLParser(resp.text)

print("title:", tree.css_first("h1").text(strip=True))