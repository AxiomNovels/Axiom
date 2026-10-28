"""Quiz journeys with intercepted public catalog responses; no live services."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
KEYS = ["intelligence", "charisma", "courage", "moral_integrity", "kinship_friendship", "romantic_attachment", "arrogance_pride"]


@pytest.fixture(scope="module")
def quiz_frontend():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT / "frontend/public")))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def quiz_api(page, quiz_frontend):
    state = {"fail": False, "empty": False, "events": [], "requests": [], "errors": []}
    page.on("pageerror", lambda error: state["errors"].append(str(error)))
    page.route("**/runtime-config.js", lambda route: route.fulfill(content_type="application/javascript", body=f"window.AXIOM_RUNTIME_CONFIG={{apiBase:{json.dumps(quiz_frontend)},analyticsEnabled:true}};"))

    def handle(route):
        path = route.request.url.split("/api", 1)[1]
        state["requests"].append((route.request.method, path, route.request.post_data))
        if path == "/analytics/events":
            state["events"].append(route.request.post_data_json)
            data = {"accepted": True}
        elif state["fail"]:
            route.fulfill(status=503, content_type="application/json", body='{}')
            return
        elif path == "/search/protagonist-definition":
            data = {"traits": [{"key": key} for key in KEYS]}
        elif path == "/search":
            data = [] if state["empty"] else [{
                "id": index, "title": "<img src=x onerror=alert(1)>" if index == 1 else f"Novel {index}",
                "cover_image_url": f"{quiz_frontend}/assets/axiom-mark.png" if index == 2 else f"{quiz_frontend}/missing-cover.png", "protagonist_profiles": [{
                    "protagonist_name": f"Hero {index}", **dict.fromkeys(KEYS, 50)
                }]
            } for index in range(1, 15)]
        else:
            data = {}
        route.fulfill(content_type="application/json", body=json.dumps(data))

    page.route("**/api/**", handle)
    return state


def complete(page):
    for index in range(18):
        expect(page.locator("#progress-text")).to_have_text(f"Question {index + 1} of 18")
        page.get_by_role("radio").nth(0).check()
        page.locator("#next").click()
    expect(page.locator("#result")).to_be_visible()


def test_full_journey_accessibility_results_matches_and_review(page, quiz_frontend, quiz_api):
    page.set_viewport_size({"width": 1366, "height": 900})
    page.goto(quiz_frontend + "/quiz/index.html")
    expect(page.get_by_role("button", name="Start my story")).to_be_enabled()
    artifacts = ROOT / "test-results"
    artifacts.mkdir(exist_ok=True)
    page.screenshot(path=str(artifacts / "quiz-desktop.png"), full_page=True)
    page.get_by_role("button", name="Start my story").click()
    expect(page.locator("#next")).to_be_disabled()
    expect(page.locator("#question-title")).to_be_focused()
    page.screenshot(path=str(artifacts / "quiz-question.png"), full_page=True)
    page.keyboard.press("Tab")
    expect(page.get_by_role("radio").first).to_be_focused()
    page.keyboard.press("Space")
    page.keyboard.press("ArrowDown")
    expect(page.get_by_role("radio").nth(1)).to_be_checked()
    page.locator("#next").click()
    page.locator("#back").click()
    expect(page.get_by_role("radio").nth(1)).to_be_checked()
    complete(page)
    expect(page.locator("#result-title")).to_be_focused()
    expect(page.locator("#trait-scores output")).to_have_count(7)
    expect(page.locator(".match-card")).to_have_count(10)
    expect(page.locator("#match-basis")).to_contain_text("all seven traits")
    expect(page.locator(".match-card h3").first).to_have_text("<img src=x onerror=alert(1)>")
    expect(page.locator(".match-card h3 img")).to_have_count(0)
    expect(page.locator(".match-card").nth(1).locator(".match-cover img")).to_have_attribute("alt", "Novel 2 cover")
    expect(page.locator(".match-card").first.locator(".match-cover")).to_have_attribute("aria-label", "Cover unavailable")
    expect(page.locator(".match-card a").first).to_have_attribute("href", "/novel.html?id=1")
    expect(page.locator(".match-card").first).to_contain_text("Protagonist: Hero 1")
    expect(page.locator(".match-card").first).to_contain_text("Strongest overlap:")
    expect(page.locator("#result-strength")).to_be_hidden()
    page.get_by_text("Turn the page: your strengths & blind spot").click()
    expect(page.locator("#result-strength")).to_be_visible()
    expect(page.get_by_role("link", name="Explore the Finder", exact=False)).to_have_attribute("href", "/finder.html")
    expect(page.get_by_role("link", name="Browse Popular Novels", exact=False)).to_have_attribute("href", "/popular.html")
    assert page.locator("#result-art").evaluate("img => img.complete && img.naturalWidth > 0")
    page.screenshot(path=str(artifacts / "quiz-result.png"), full_page=True)
    page.get_by_role("button", name="Review my answers").click()
    expect(page.get_by_role("radio").first).to_be_checked()
    complete(page)
    page.get_by_role("button", name="Retake the quiz").click()
    expect(page.get_by_role("radio").first).not_to_be_checked()
    expect(page.locator("#next")).to_be_disabled()
    assert quiz_api["errors"] == []
    assert all(method == "GET" for method, path, _ in quiz_api["requests"] if not path.startswith("/analytics/"))
    assert quiz_api["events"] and all(event["path"] == "/quiz/" for event in quiz_api["events"])
    assert all(set(event) <= {"id", "session_id", "event", "path", "active_seconds"} for event in quiz_api["events"])
    assert page.evaluate("Object.keys(localStorage).filter(k => /quiz/i.test(k))") == []


@pytest.mark.parametrize("width", [320, 390])
def test_mobile_failure_retry_empty_and_no_overflow(page, quiz_frontend, quiz_api, width):
    page.set_viewport_size({"width": width, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    quiz_api["fail"] = True
    page.goto(quiz_frontend + "/quiz/")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    (ROOT / "test-results").mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT / f"test-results/quiz-mobile-{width}.png"), full_page=True)
    page.locator("#start-quiz").click()
    assert page.get_by_role("radio").first.locator("..").bounding_box()["height"] >= 44
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ROOT / f"test-results/quiz-question-mobile-{width}.png"), full_page=True)
    quiz_api["fail"] = True
    complete(page)
    expect(page.locator("#retry-matches")).to_be_visible()
    expect(page.locator("[data-backend-wake-overlay]")).to_have_count(0)
    assert not any(path == "/health" for _, path, _ in quiz_api["requests"])
    expect(page.locator("#trait-scores output")).to_have_count(7)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    quiz_api["fail"] = False
    quiz_api["empty"] = width == 320
    page.locator("#retry-matches").click()
    if width == 320:
        expect(page.locator("#match-status")).to_contain_text("No protagonists")
    else:
        expect(page.locator(".match-card")).to_have_count(10)
    expect(page.locator("#match-list")).to_have_attribute("aria-busy", "false")
    assert quiz_api["errors"] == []


def test_declined_analytics_sends_no_events_or_quiz_answers(page, quiz_frontend, quiz_api):
    page.add_init_script("localStorage.setItem('axiomAnalyticsConsent', 'declined')")
    page.goto(quiz_frontend + "/quiz/")
    page.locator("#start-quiz").click()
    complete(page)
    expect(page.locator(".match-card")).to_have_count(10)
    assert quiz_api["events"] == []
    assert all(method == "GET" and body is None for method, _, body in quiz_api["requests"])
