"""Network-isolated regressions for WebNovel transport and challenge handling."""
from unittest.mock import Mock

import pytest
import requests
from curl_cffi import requests as browser_requests

from scraper import webnovel

URL = "https://www.webnovel.com/book/shadow-slave_22196546206090805"
BOOK = "<html><title>Shadow Slave - WebNovel</title><h1>Shadow Slave</h1></html>"
CHALLENGE = "<html><title>Just a moment...</title><script>window._cf_chl_opt = {};</script></html>"


def response(status=200, body=BOOK, **headers):
    result = requests.Response()
    result.status_code = status
    result.url = URL
    result.headers.update({"Content-Type": "text/html; charset=utf-8", **headers})
    result._content = body.encode("utf-8")
    result.encoding = "utf-8"
    return result


@pytest.fixture
def transports(monkeypatch):
    monkeypatch.delenv("WEBNOVEL_PROXY_URL", raising=False)
    direct = Mock(return_value=response())
    browser = Mock(return_value=response())
    monkeypatch.setattr(webnovel.requests, "get", direct)
    monkeypatch.setattr(webnovel.browser_requests, "get", browser)
    return direct, browser


def test_success_preserves_existing_transport(transports):
    direct, browser = transports
    assert webnovel.fetch(URL) == BOOK
    direct.assert_called_once()
    browser.assert_not_called()


@pytest.mark.parametrize("status,body,headers", [
    (403, CHALLENGE, {}),
    (403, "Forbidden", {}),
    (200, CHALLENGE, {}),
    (200, "<html>Verification required</html>", {"cf-mitigated": "challenge"}),
])
def test_refused_request_retries_with_consistent_browser_transport(transports, status, body, headers):
    direct, browser = transports
    direct.return_value = response(status, body, **headers)
    assert webnovel.fetch(URL) == BOOK
    browser.assert_called_once()
    options = browser.call_args.kwargs
    assert options["impersonate"] == "chrome"
    assert "User-Agent" not in options["headers"]
    assert "verify" not in options
    assert options["timeout"] == 20


@pytest.mark.parametrize("status", [200, 403, 503])
def test_repeated_challenge_never_reaches_parser(transports, status):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    browser.return_value = response(status, CHALLENGE)
    with pytest.raises(webnovel.WebNovelChallengeError) as caught:
        webnovel.scrape_webnovel(URL, include_statistics=False)
    assert caught.value.response.status_code == status
    assert direct.call_count == browser.call_count == 1


@pytest.mark.parametrize("status", [404, 429, 500, 503])
def test_non_challenge_http_errors_are_not_retried(transports, status):
    direct, browser = transports
    direct.return_value = response(status, "Source error")
    with pytest.raises(requests.HTTPError) as caught:
        webnovel.fetch(URL)
    assert caught.value.response.status_code == status
    browser.assert_not_called()


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_browser_http_errors_preserve_status(transports, status):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    browser.return_value = response(status, "Source error")
    with pytest.raises(requests.HTTPError) as caught:
        webnovel.fetch(URL)
    assert caught.value.response.status_code == status


def test_browser_timeout_is_normalized_without_proxy_secrets(transports):
    direct, browser = transports
    direct.return_value = response(403, CHALLENGE)
    browser.side_effect = browser_requests.exceptions.Timeout("http://user:secret@proxy")
    with pytest.raises(requests.RequestException) as caught:
        webnovel.fetch(URL)
    assert "secret" not in str(caught.value)
    assert caught.value.__suppress_context__ is True


def test_configured_proxy_uses_browser_transport_without_direct_request(transports, monkeypatch):
    direct, browser = transports
    monkeypatch.setenv("WEBNOVEL_PROXY_URL", " http://user:secret@proxy.example:8080 ")
    assert webnovel.fetch(URL) == BOOK
    direct.assert_not_called()
    assert browser.call_args.kwargs["proxy"] == "http://user:secret@proxy.example:8080"


def test_non_html_is_rejected(transports):
    direct, browser = transports
    direct.return_value = response(body='{"error": "no book"}', **{"Content-Type": "application/json"})
    with pytest.raises(ValueError, match="Expected HTML"):
        webnovel.fetch(URL)
    browser.assert_not_called()

def test_normal_cloudflare_javascript_does_not_make_a_book_a_challenge(transports):
    direct, browser = transports
    html = BOOK + "<script src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'></script>"
    direct.return_value = response(body=html)
    assert webnovel.fetch(URL) == html
    browser.assert_not_called()
