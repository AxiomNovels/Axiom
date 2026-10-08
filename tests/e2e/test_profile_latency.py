"""Profile/avatar request reuse with isolated browser API responses."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect


@pytest.fixture(scope="module")
def profile_frontend():
    root = Path(__file__).resolve().parents[2] / "frontend" / "public"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def profile_api(page):
    state = {"reads": 0, "writes": 0, "status": 200}
    page.add_init_script("""
      localStorage.setItem('axiomSession', JSON.stringify({access_token: 'test'}));
      localStorage.setItem('axiomUser', JSON.stringify({id: 'reader', user_metadata: {username: 'Reader'}}));
    """)
    page.route("**/runtime-config.js", lambda route: route.fulfill(
        content_type="text/javascript", body="window.AXIOM_RUNTIME_CONFIG = {apiBase: 'http://localhost:8000'};"))

    def handle(route):
        path = route.request.url.split("/api/", 1)[-1]
        payload, status = {}, 200
        if path == "profile":
            state["reads"] += 1
            status = state["status"]
            payload = {"username": "Reader", "avatar_url": "/assets/axiom-mark.png"}
        elif path == "profile/avatar":
            state["writes"] += 1
            payload = {"username": "Reader", "avatar_url": "/assets/axiom-logo.png?updated=1"}
        elif path == "admin/me":
            status = 403
        elif path == "search/options":
            payload = {"tags": []}
        elif path == "novels/featured":
            payload = []
        route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))

    page.route("http://localhost:8000/**", handle)
    return state


def test_profile_load_and_avatar_save_reuse_returned_data(page, profile_frontend, profile_api):
    page.goto(profile_frontend + "/profile.html")
    avatar = page.locator("[data-account-trigger-content] img")
    expect(avatar).to_have_attribute("src", "/assets/axiom-mark.png")
    expect(page.locator("[data-profile-username]")).to_have_text("Reader")
    assert profile_api["reads"] == 1
    # Cropping is unrelated to request reuse; supply its normal output shape.
    page.evaluate("""async () => {
      exportAvatarImage = () => 'data:image/png;base64,aGVsbG8=';
      await applyAvatarEdit();
    }""")
    expect(avatar).to_have_attribute("src", "/assets/axiom-logo.png?updated=1")
    assert profile_api["writes"] == 1
    assert profile_api["reads"] == 1


def test_other_pages_still_load_header_avatar(page, profile_frontend, profile_api):
    page.goto(profile_frontend + "/index.html")
    expect(page.locator("[data-account-trigger-content] img")).to_have_attribute(
        "src", "/assets/axiom-mark.png")
    assert profile_api["reads"] == 1


def test_profile_failure_keeps_header_fallback(page, profile_frontend, profile_api):
    profile_api["status"] = 500
    page.goto(profile_frontend + "/profile.html")
    expect(page.locator("[data-profile-username]")).to_have_text("Couldn't load")
    expect(page.locator("[data-account-trigger-content] img")).to_have_count(0)
    assert profile_api["reads"] == 1
