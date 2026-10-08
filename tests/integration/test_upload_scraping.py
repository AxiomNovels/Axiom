"""Upload API regressions with no live source, Supabase, or profiling calls."""
from unittest.mock import Mock

import pytest
import requests
from curl_cffi import requests as browser_requests
from fastapi.testclient import TestClient

from core.auth import get_current_user
from main import app
from routes import novels
from scraper import webnovel

URL = "https://www.webnovel.com/book/shadow-slave_22196546206090805"
CHALLENGE = "<html><title>Just a moment...</title></html>"
BOOK = """<html><head><title>Shadow Slave - Guiltythree - WebNovel</title></head>
<body><h1>Shadow Slave</h1><script>g_data.book = {
"bookName":"Shadow Slave","authorName":"Guiltythree","chapterCount":123,
"tagInfos":[{"tagName":"ACTION","enTagName":"ACTION"}]};</script></body></html>"""


def response(status, body):
    result = requests.Response()
    result.status_code = status
    result.url = URL
    result.headers["Content-Type"] = "text/html; charset=utf-8"
    result._content = body.encode()
    result.encoding = "utf-8"
    return result


@pytest.fixture
def upload(monkeypatch):
    monkeypatch.delenv("WEBNOVEL_PROXY_URL", raising=False)
    direct = Mock(return_value=response(403, CHALLENGE))
    browser = Mock(return_value=response(200, BOOK))
    monkeypatch.setattr(webnovel.requests, "get", direct)
    monkeypatch.setattr(webnovel.browser_requests, "get", browser)
    monkeypatch.setattr(novels, "_find_existing_novel", lambda novel: None)
    profiler = Mock(return_value={"profiles": []})
    monkeypatch.setattr(novels.novel_profiling, "build_preview", profiler)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: ("test-user", None)
    try:
        with TestClient(app) as client:
            yield client, direct, browser, profiler
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_preview_recovers_from_plain_request_challenge(upload):
    client, direct, browser, profiler = upload
    result = client.post("/api/novels/scrape", json={"url": URL, "source": "WebNovel"})
    assert result.status_code == 200, result.text
    novel = result.json()
    assert novel["title"] == "Shadow Slave"
    assert novel["author"] == "Guiltythree"
    assert novel["chapter_count"] == 123
    assert novel["reading_links"][0]["url"] == URL
    assert direct.call_count == browser.call_count == 1
    profiler.assert_called_once()


@pytest.mark.parametrize("path", ["/api/novels/scrape", "/api/novels"])
@pytest.mark.parametrize("status", [200, 403, 503])
def test_challenge_is_source_failure_for_preview_and_add(upload, path, status):
    client, direct, browser, profiler = upload
    browser.return_value = response(status, CHALLENGE)
    result = client.post(path, json={"url": URL, "source": "WebNovel"})
    assert result.status_code == 502
    assert "blocking" in result.json()["detail"]
    assert "invalid" not in result.json()["detail"]
    assert "WebNovelChallengeError" in result.headers["X-Scrape-Debug"]
    profiler.assert_not_called()


@pytest.mark.parametrize("status,expected", [(403, 502), (404, 422), (429, 502), (503, 502)])
def test_plain_http_errors_keep_existing_api_classification(upload, status, expected):
    client, direct, browser, profiler = upload
    direct.return_value = response(status, "Source error")
    browser.return_value = response(status, "Source error")
    result = client.post("/api/novels/scrape", json={"url": URL, "source": "WebNovel"})
    assert result.status_code == expected
    profiler.assert_not_called()


def test_browser_timeout_is_source_failure(upload):
    client, direct, browser, profiler = upload
    browser.side_effect = browser_requests.exceptions.Timeout("Timed out")
    result = client.post("/api/novels/scrape", json={"url": URL, "source": "WebNovel"})
    assert result.status_code == 502
    profiler.assert_not_called()
