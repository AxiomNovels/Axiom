"""Popular browsing with intercepted API responses; no live services."""
import json
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect

from test_protagonist_voting import frontend


@pytest.fixture
def popular_api(page):
    state = {"total": 41, "failure": False, "requests": []}
    page.route("**/runtime-config.js", lambda route: route.fulfill(
        content_type="application/javascript",
        body='window.AXIOM_RUNTIME_CONFIG = {apiBase:"http://localhost:8000",analyticsEnabled:false};',
    ))

    def handle(route):
        url = urlparse(route.request.url)
        payload = []
        if url.path == "/api/novels/popular":
            query = parse_qs(url.query)
            state["requests"].append(query)
            if state["failure"]:
                route.fulfill(status=503, body="Unavailable")
                return
            total = state["total"]
            total_pages = (total + 19) // 20
            current = min(int(query["page"][0]), max(1, total_pages))
            start = (current - 1) * 20
            payload = {
                "novels": [{"id": i, "title": f"Novel {i}", "author": "Test author",
                            "synopsis": "A story.", "tags": ["Fantasy"],
                            "average_rating": 4.5 if i == 1 else None,
                            "review_count": 2 if i == 1 else 0}
                           for i in range(start + 1, min(start + 20, total) + 1)],
                "total": total, "page": current, "page_size": 20, "total_pages": total_pages,
            }
        route.fulfill(content_type="application/json", body=json.dumps(payload))

    page.route("http://localhost:8000/**", handle)
    return state


def test_popular_navigation_pages_and_back(page, frontend, popular_api):
    page.goto(frontend + "/search.html")
    page.locator('.reader-nav a[href="/popular.html"]').click()
    expect(page.locator(".series-result")).to_have_count(20)
    expect(page.locator("[data-popular-summary]")).to_contain_text("1–20 of 41 novels")
    expect(page.locator(".result-rating").first).to_have_text("★ 4.50 / 5 · 2 reviews")
    expect(page.locator(".result-rating").nth(1)).to_have_text("Not yet rated")
    seed = popular_api["requests"][0]["seed"]
    page.get_by_role("link", name="Next", exact=True).click()
    expect(page.locator("[data-popular-summary]")).to_contain_text("21–40 of 41 novels")
    expect(page.locator(".series-result")).to_have_count(20)
    assert popular_api["requests"][-1]["seed"] == seed
    page.get_by_role("link", name="Next", exact=True).click()
    expect(page.locator(".series-result")).to_have_count(1)
    expect(page.locator(".series-result")).to_have_attribute("href", "/novel.html?id=41")
    expect(page.get_by_role("link", name="Next", exact=True)).to_have_count(0)
    page.go_back()
    expect(page.locator("[data-popular-summary]")).to_contain_text("21–40 of 41 novels")
    assert popular_api["requests"][-1]["seed"] == seed


def test_popular_empty_error_retry_and_out_of_range(page, frontend, popular_api):
    popular_api["failure"] = True
    page.goto(frontend + "/popular.html?page=999&seed=test")
    expect(page.locator("[data-popular-summary]")).to_contain_text("temporarily unavailable")
    popular_api["failure"] = False
    page.get_by_role("button", name="Try again").click()
    expect(page.locator("[data-popular-summary]")).to_contain_text("Page 3 of 3")
    assert "page=3" in page.url
    popular_api["total"] = 0
    page.reload()
    expect(page.locator("[data-popular-summary]")).to_contain_text("No novels")
    expect(page.locator("[data-popular-pagination]")).to_be_hidden()


def test_popular_mobile_layout_and_invalid_page(page, frontend, popular_api):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(frontend + "/popular.html?page=invalid")
    expect(page.locator(".series-result")).to_have_count(20)
    assert popular_api["requests"][-1]["page"] == ["1"]
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.get_by_role("navigation", name="Novel pages")).to_be_visible()
