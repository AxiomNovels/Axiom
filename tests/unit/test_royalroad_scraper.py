"""Royal Road regressions using compact fixtures, never live source requests."""
from unittest.mock import Mock

import httpx
import pytest
from curl_cffi import requests as browser_requests

from scraper import royalroad
from scraper.content_policy import find_policy_violations


URL = "https://www.royalroad.com/fiction/123/test-story"
CHALLENGE = "<html><title>Just a moment...</title></html>"
BOOK = """<html><head><meta property="og:image" content="/cover.jpg"></head>
<body><h1>Test Story</h1><h4><a href="/profile/42">Test Author</a></h4>
<div class="fiction-info"><span class="label">COMPLETED</span><span class="tags">
<a href="/fictions/search?tagsAdd=fantasy">Fantasy</a>
<a href="/fictions/search?tagsAdd=magic">Magic</a></span>
<div class="description"><div class="hidden-content"><p>A story synopsis.</p>
<p>***</p><p>Available on Amazon</p></div></div>
<div class="fiction-stats"><span title="Overall Score" data-content="4.83 / 5">
<style>.star-123-overall-test:after{width:97%}</style></span>
<ul><li>Average Views :</li><li>99,000</li><li>Followers :</li><li>1,234</li>
<li>Ratings :</li><li>456</li><li>100 Chapters</li></ul></div></div>
</body></html>"""


def response(status=200, body=BOOK, **headers):
    return httpx.Response(status, text=body, request=httpx.Request("GET", URL),
                          headers={"content-type": "text/html; charset=utf-8", **headers})


@pytest.fixture
def transports(monkeypatch):
    direct = Mock(return_value=response())
    browser = Mock(return_value=response())
    monkeypatch.setattr(httpx.Client, "get", direct)
    monkeypatch.setattr(browser_requests.Session, "get", browser)
    return direct, browser


def test_plain_success_preserves_transport_and_payload(transports):
    direct, browser = transports
    novel = royalroad.scrape_royalroad(URL)
    assert novel == {
        "source": "royalroad", "source_url": URL, "fiction_id": 123,
        "title": "Test Story", "author": "Test Author", "status": "completed",
        "chapter_count": 100, "overall_score": 4.83, "rating_count": 456,
        "genres": ["Fantasy"], "tags": ["MAGIC"], "synopsis": "A story synopsis.",
        "cover_image_url": "https://www.royalroad.com/cover.jpg", "reading_url": URL,
    }
    direct.assert_called_once()
    browser.assert_not_called()


@pytest.mark.parametrize("status,body,headers", [
    (403, "Forbidden", {}), (403, CHALLENGE, {}), (200, CHALLENGE, {}),
    (200, "Verify your browser", {"cf-mitigated": "challenge"}),
])
def test_challenge_falls_back_to_browser_transport(transports, status, body, headers):
    direct, browser = transports
    direct.return_value = response(status, body, **headers)
    assert royalroad.scrape_royalroad(URL)["title"] == "Test Story"
    assert direct.call_count == browser.call_count == 1


def test_browser_session_is_reused_after_first_challenge(transports, monkeypatch):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    session_factory = Mock(wraps=browser_requests.Session)
    monkeypatch.setattr(browser_requests, "Session", session_factory)
    with royalroad.RoyalRoadClient() as client:
        assert client.fetch(URL) == client.fetch(URL) == BOOK
    assert direct.call_count == 1
    assert browser.call_count == 2
    session_factory.assert_called_once()
    options = session_factory.call_args.kwargs
    assert options["impersonate"] == "chrome"
    assert "User-Agent" not in options["headers"]
    assert "verify" not in options


@pytest.mark.parametrize("status", [200, 403, 503])
def test_persistent_challenge_never_reaches_parser(transports, monkeypatch, status):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    browser.return_value = response(status, CHALLENGE)
    parser = Mock()
    monkeypatch.setattr(royalroad, "parse_royalroad", parser)
    with pytest.raises(royalroad.RoyalRoadChallengeError, match="blocking"):
        royalroad.scrape_royalroad(URL)
    parser.assert_not_called()
    assert direct.call_count == browser.call_count == 1


@pytest.mark.parametrize("status", [404, 429, 500, 503])
def test_non_challenge_errors_are_not_retried(transports, status):
    direct, browser = transports
    direct.return_value = response(status, "Source error")
    with pytest.raises(httpx.HTTPStatusError) as caught:
        royalroad.fetch(URL)
    assert caught.value.response.status_code == status
    browser.assert_not_called()


@pytest.mark.parametrize("status", [403, 404, 429, 503])
def test_browser_http_error_keeps_status(transports, status):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    browser.return_value = response(status, "Source error")
    with pytest.raises(httpx.HTTPStatusError) as caught:
        royalroad.fetch(URL)
    assert caught.value.response.status_code == status


def test_browser_timeout_keeps_api_error_contract(transports):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    browser.side_effect = browser_requests.exceptions.Timeout("Connection failed")
    with pytest.raises(httpx.RequestError, match="Timeout"):
        royalroad.fetch(URL)


def test_non_html_is_rejected(transports):
    direct, browser = transports
    direct.return_value = response(body='{}', **{"content-type": "application/json"})
    with pytest.raises(ValueError, match="Expected HTML"):
        royalroad.fetch(URL)
    browser.assert_not_called()


def test_normal_cloudflare_script_does_not_trigger_fallback(transports):
    direct, browser = transports
    html = BOOK + "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script>"
    direct.return_value = response(body=html)
    assert royalroad.fetch(URL) == html
    browser.assert_not_called()


def test_plain_list_warnings_are_tags_and_rejected_by_shared_policy():
    warning = """<div class="font-red-sunglo"><strong>Warning</strong>
    <span>This fiction contains:</span><ul class="list-inline">
    <li>Graphic Violence</li><li>Sexual Content</li></ul></div>"""
    html = BOOK.replace('<span class="label">', warning + '<span class="label">')
    novel = royalroad.parse_royalroad(html, URL)
    assert novel["tags"] == ["MAGIC", "GRAPHIC VIOLENCE", "SEXUAL CONTENT"]
    assert find_policy_violations("Royal Road", novel) == ["SEXUAL CONTENT"]


@pytest.mark.parametrize("label", ["NSFW", "sexual-content", "SEX_SCENES", "Adult Content",
                                   "Multiple Lovers", "EROTIC FICTION", "Reverse-Harem"])
def test_expanded_labels_use_shared_normalization(label):
    assert find_policy_violations("royalroad", {"tags": [label]}) == [label]
    assert find_policy_violations("royalroad", {"genres": [label]}) == [label]


def test_unrelated_labels_remain_eligible():
    assert find_policy_violations("royalroad", {"tags": [
        "Profanity", "Graphic Violence", "Romance Subplot", "Female Lead",
    ]}) == []
