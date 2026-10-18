from pathlib import Path
from urllib.parse import urlparse
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"
ORIGIN = "https://axiomnovels.com"


def head(path):
    html = (PUBLIC / path).read_text(encoding="utf-8")
    return re.search(r"<head.*?</head>", html, re.IGNORECASE | re.DOTALL).group(0)


def test_static_sitemap_is_valid_and_contains_only_known_public_pages():
    root = ET.parse(PUBLIC / "sitemap.xml").getroot()
    urls = [element.text for element in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert len(urls) == len(set(urls))
    assert urls
    assert all(url.startswith(ORIGIN) for url in urls)
    assert all(urlparse(url).query == "" for url in urls)
    assert not any(path in url for url in urls for path in ("login.html", "search.html", "profile.html", "admin.html"))


def test_indexable_landing_pages_have_unique_metadata_and_canonical_urls():
    pages = ["index.html", "finder.html", "readers.html"]
    titles = []
    canonicals = []
    for page in pages:
        document_head = head(page)
        titles.append(re.search(r"<title>(.*?)</title>", document_head, re.IGNORECASE | re.DOTALL).group(1).strip())
        canonicals.append(re.search(r'<link rel="canonical" href="([^"]+)"', document_head).group(1))
        description = re.search(r'<meta name="description" content="([^"]+)"', document_head)
        assert description and 50 <= len(description.group(1)) <= 170
        assert 'property="og:title"' in document_head
        assert 'property="og:description"' in document_head
    assert len(titles) == len(set(titles))
    assert canonicals == [f"{ORIGIN}/" if page == "index.html" else f"{ORIGIN}/{page}" for page in pages]


def test_non_indexable_pages_are_marked_by_runtime_headers():
    source = (ROOT / "frontend" / "server.js").read_text(encoding="utf-8")
    for page in ("search.html", "login.html", "profile.html", "admin.html", "user.html", "list.html", "mission.html", "team.html", "protagonist-profile-info.html"):
        assert f'"/{page}"' in source
    assert 'headers["X-Robots-Tag"] = "noindex, nofollow"' in source


def test_robots_references_production_sitemap_without_blocking_assets():
    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *\nAllow: /" in robots
    assert "Sitemap: https://axiomnovels.com/sitemap.xml" in robots
    assert "Disallow: /styles.css" not in robots
    assert "Disallow: /script.js" not in robots
