"""Recover homepage data after the Render startup handoff."""
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

from test_protagonist_voting import frontend


@pytest.mark.parametrize("handoff", [True, False])
def test_home_recovers_catalogue_reads_without_reload(page, frontend, handoff):
    original_page = frontend + "/?source=test"
    original_url = original_page + "#popular"
    callback_url = frontend + "/?__axiom_woke=1"
    backend = "https://backend.example.com/"
    attempts = {"/api/home-feature": 0, "/api/novels/featured": 0}
    home_requests = []
    returned = not handoff
    used_fallback = False

    page.route("**/runtime-config.js", lambda route: route.fulfill(
        content_type="application/javascript",
        body=f'window.AXIOM_RUNTIME_CONFIG = {{apiBase: "{frontend}/backend", backendWakeUrl: "{backend}"}};',
    ))

    def return_from_render(route):
        nonlocal returned
        returned = True
        route.fulfill(status=303, headers={"Location": callback_url})

    def handle_api(route):
        nonlocal used_fallback
        url = urlparse(route.request.url)
        path = url.path.removeprefix("/backend")
        if not returned:
            route.fulfill(status=503, body="Starting up")
            return
        if path == "/api/health":
            route.fulfill(json={"status": "ok"})
            return
        if path == "/api/novels/featured" and url.query == "refresh=true":
            used_fallback = True
            route.fulfill(json=[{"id": 1, "title": "Test Novel"}])
            return
        if path in attempts:
            attempts[path] += 1
            if attempts[path] == 1:
                route.fulfill(status=503, body="Starting up")
                return
            if attempts[path] == 2:
                route.fulfill(content_type="text/html", body="<p>Starting up</p>")
                return
        novel = {"id": 1, "title": "Test Novel"}
        payload = {"inquiry": "Test Recommendation", "description": "A story", "novel": novel}
        route.fulfill(json=payload if path == "/api/home-feature" else [])

    def record_navigation(request):
        if request.is_navigation_request() and request.url.startswith(frontend):
            home_requests.append(request.url.split("#", 1)[0])

    page.route(backend + "**", return_from_render)
    page.route(frontend + "/backend/**", handle_api)
    page.on("request", record_navigation)

    page.goto(original_url)
    expect(page.locator("[data-novel-grid]")).to_contain_text("Test Novel", timeout=45000)
    expect(page.locator("[data-home-feature-inquiry]")).to_have_text("Test Recommendation")
    expect(page).to_have_url(original_url)
    assert attempts == {"/api/home-feature": 3, "/api/novels/featured": 3}
    assert used_fallback
    assert home_requests == ([original_page, callback_url] if handoff else [original_page])
