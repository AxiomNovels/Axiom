"""Royal Road upload preview and policy enforcement without live services."""
from unittest.mock import Mock

import httpx
import pytest
from curl_cffi import requests as browser_requests
from fastapi.testclient import TestClient

from core.auth import get_current_user
from main import app
from routes import novels


URL = "https://www.royalroad.com/fiction/123/story"
CHALLENGE = "<html><title>Just a moment...</title></html>"
BOOK = """<html><h1>Story</h1><h4><a href='/profile/1'>Author</a></h4>
<div class='fiction-info'><span class='tags'>
<a href='/fictions/search?tagsAdd=fantasy'>Fantasy</a></span>
<div class='description'><p>A story synopsis.</p></div></div></html>"""


def response(status=200, body=BOOK):
    return httpx.Response(status, text=body, request=httpx.Request("GET", URL),
                          headers={"content-type": "text/html"})


@pytest.fixture
def upload(monkeypatch):
    direct = Mock(return_value=response(403, CHALLENGE))
    browser = Mock(return_value=response())
    monkeypatch.setattr(httpx.Client, "get", direct)
    monkeypatch.setattr(browser_requests.Session, "get", browser)
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


def test_upload_preview_recovers_from_403_and_preserves_fields(upload):
    client, direct, browser, profiler = upload
    result = client.post("/api/novels/scrape", json={"url": URL, "source": "Royal Road"})
    assert result.status_code == 200, result.text
    novel = result.json()
    assert novel["title"] == "Story"
    assert novel["author"] == "Author"
    assert novel["genres"] == ["Fantasy"]
    assert novel["reading_links"][0]["url"] == URL
    assert direct.call_count == browser.call_count == 1
    profiler.assert_called_once()


@pytest.mark.parametrize("path", ["/api/novels/scrape", "/api/novels"])
def test_http_200_challenge_is_source_failure_for_upload(upload, path):
    client, direct, browser, profiler = upload
    browser.return_value = response(200, CHALLENGE)
    result = client.post(path, json={"url": URL, "source": "Royal Road"})
    assert result.status_code == 502
    assert "RoyalRoadChallengeError" in result.headers["X-Scrape-Debug"]
    profiler.assert_not_called()


@pytest.mark.parametrize("path", ["/api/novels/scrape", "/api/novels"])
def test_separate_sexual_content_warning_blocks_upload_before_profiling(upload, path):
    client, direct, browser, profiler = upload
    browser.return_value = response(body=BOOK.replace(
        "<span class='tags'>", """<div><strong>Warning</strong><ul class='list-inline'>
        <li>Sexual Content</li></ul></div><span class='tags'>""",
    ))
    result = client.post(path, json={"url": URL, "source": "Royal Road"})
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "content_policy_violation"
    profiler.assert_not_called()
