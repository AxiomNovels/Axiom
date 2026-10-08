"""Country editor and displays with intercepted APIs; no live database."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect


@pytest.fixture(scope="module")
def frontend():
    root = Path(__file__).resolve().parents[2] / "frontend/public"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def country_api(page):
    state = {"country": "US", "saved": []}
    page.add_init_script("localStorage.setItem('axiomSession', JSON.stringify({access_token:'test'}));")

    def handle(route):
        path = route.request.url.split("/api", 1)[-1].split("?", 1)[0]
        profile = {"id": "reader", "username": "Reader", "country": state["country"],
                   "gender": "Prefer not to say", "created_at": "2026-01-01T00:00:00Z"}
        payload = {}
        if path == "/profile":
            if route.request.method == "PATCH":
                state["saved"].append(route.request.post_data_json)
            payload = profile
        elif path == "/users":
            payload = {"users": [profile]}
        elif path == "/users/reader":
            payload = profile
        elif path == "/search/options":
            payload = {"tags": []}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/api/**", handle)
    return state


def test_search_select_save_clear_and_reject_free_text(page, frontend, country_api):
    page.goto(f"{frontend}/profile.html")
    search = page.get_by_role("combobox", name="Country")
    expect(search).to_have_value("🇺🇸 United States")
    search.click()
    options = page.locator('#country-options [role="option"]')
    assert options.count() == 250
    assert options.nth(1).inner_text() == "🇦🇫 Afghanistan"
    search.fill("can")
    page.get_by_role("option", name="🇨🇦 Canada", exact=True).click()
    expect(search).to_have_value("🇨🇦 Canada")
    page.locator('button[type="submit"]').last.click()
    expect(page.locator("[data-profile-message]")).to_have_text("Profile saved.")
    assert country_api["saved"][-1]["country"] == "Canada"

    search.fill("Atlantis")
    expect(page.get_by_text("No matching countries")).to_be_visible()
    page.locator('button[type="submit"]').last.click()
    assert len(country_api["saved"]) == 1
    assert not search.evaluate("el => el.checkValidity()")

    search.fill("United Kingdom")
    search.press("ArrowDown")  # Not specified
    search.press("ArrowDown")  # United Kingdom
    search.press("Enter")
    expect(search).to_have_value("🇬🇧 United Kingdom")
    search.click()
    search.press("Escape")
    expect(page.get_by_role("listbox")).to_be_hidden()
    search.fill("")
    search.press("Tab")
    page.locator('button[type="submit"]').last.click()
    expect(page.locator("[data-profile-message]")).to_have_text("Profile saved.")
    assert country_api["saved"][-1]["country"] == ""


def test_flag_displays_and_legacy_value(page, frontend, country_api):
    page.goto(f"{frontend}/readers.html")
    expect(page.locator(".reader-directory-location")).to_have_text("🇺🇸 United States")
    page.goto(f"{frontend}/user.html?id=reader")
    expect(page.locator("[data-user-country]")).to_have_text("🇺🇸 United States")
    country_api["country"] = "Atlantis"
    page.goto(f"{frontend}/profile.html")
    expect(page.get_by_role("combobox", name="Country")).to_have_value("Atlantis")
    expect(page.locator("#country-help")).to_contain_text("Previously saved: Atlantis")
    assert not page.get_by_role("combobox", name="Country").evaluate("el => el.checkValidity()")
    page.goto(f"{frontend}/user.html?id=reader")
    expect(page.locator("[data-user-country]")).to_have_text("Atlantis")
