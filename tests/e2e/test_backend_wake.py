"""Keep visitors on Axiom during the experimental Render wake-up flow."""
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

from test_protagonist_voting import frontend


@pytest.mark.parametrize("wake_required", [True, False])
def test_home_recovers_catalogue_reads_without_reload(page, frontend, wake_required):
    original_page = frontend + "/?source=test"
    original_url = original_page + "#popular"
    backend = "https://backend.example.com/"
    attempts = {"/api/home-feature": 0, "/api/novels/featured": 0}
    home_requests = []
    ready = not wake_required
    wake_requests = []
    used_fallback = False

    page.route("**/runtime-config.js", lambda route: route.fulfill(
        content_type="application/javascript",
        body=f'window.AXIOM_RUNTIME_CONFIG = {{apiBase: "{frontend}/backend", backendWakeUrl: "{backend}"}};',
    ))

    def wake_render(route):
        nonlocal ready
        wake_requests.append(route.request)
        assert route.request.url == backend + "api/health"
        assert route.request.method == "GET"
        assert not route.request.is_navigation_request()
        assert route.request.headers.get("sec-fetch-mode") == "no-cors"
        # An opaque response (even an error during startup) is not readiness.
        route.fulfill(status=429 if wake_required else 200, body="Starting up")
        ready = True

    def handle_api(route):
        nonlocal used_fallback
        url = urlparse(route.request.url)
        path = url.path.removeprefix("/backend")
        if not ready:
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

    page.route(backend + "**", wake_render)
    page.route(frontend + "/backend/**", handle_api)
    page.on("request", record_navigation)

    page.goto(original_url)
    expect(page.locator("[data-novel-grid]")).to_contain_text("Test Novel", timeout=45000)
    expect(page.locator("[data-home-feature-inquiry]")).to_have_text("Test Recommendation")
    expect(page).to_have_url(original_url)
    assert attempts == {"/api/home-feature": 3, "/api/novels/featured": 3}
    assert used_fallback
    assert home_requests == [original_page]
    assert wake_requests


def test_persistent_429_never_navigates_to_render(page, frontend):
    backend = "https://backend.example.com/"
    navigations = []
    page.clock.install()
    page.route("**/runtime-config.js", lambda route: route.fulfill(
        content_type="application/javascript",
        body=f'window.AXIOM_RUNTIME_CONFIG = {{apiBase: "{frontend}/backend", backendWakeUrl: "{backend}"}};',
    ))
    page.route(frontend + "/backend/**", lambda route: route.fulfill(status=429, body="Rate limited"))
    page.route(backend + "**", lambda route: route.fulfill(status=429, body="Rate limited"))
    page.on("request", lambda request: navigations.append(request.url) if request.is_navigation_request() else None)
    original_url = frontend + "/?source=test#popular"
    page.goto(original_url)
    page.clock.run_for(2_000)
    expect(page.locator("[data-backend-wake-overlay]")).to_be_visible()
    page.clock.run_for(90_000)
    expect(page.locator("[data-backend-wake-overlay]")).to_have_count(0)
    expect(page).to_have_url(original_url)
    assert len(navigations) == 1
