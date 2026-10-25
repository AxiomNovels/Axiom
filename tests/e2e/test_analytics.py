"""Isolated Stage 1 browser checks. All API requests use controlled fixtures."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect


@pytest.fixture(scope="module")
def analytics_frontend():
    root = Path(__file__).resolve().parents[2] / "frontend" / "public"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown(); server.server_close(); thread.join()


@pytest.fixture
def analytics_api(page, analytics_frontend):
    state = {"events": [], "reports": [], "fail": False}
    daily = [{"date": "2026-10-22", "page_views": 25, "visits": 8, "frontend_requests": 80,
              "backend_requests": 40, "active_seconds": 600, "signups": 2}]
    data = {"totals": {**daily[0], "anonymous_visits": 5, "signed_in_accounts": 3, "engaged_sessions": 8},
            "daily": daily, "previous": {"page_views": 10, "requests": 50, "active_seconds": 300},
            "hourly": [{"hour": 12, "requests": 120, "page_views": 25}],
            "countries": [{"country": "CA", "page_views": 25, "requests": 120, "engaged_sessions": 8, "active_seconds": 600}],
            "pages": [{"path": "/novel.html", "page_views": 25, "entrances": 8, "last_pages": 8}],
            "accounts": [{"username": "<script>unsafe</script>", "sessions": 1, "page_views": 3, "active_seconds": 60}],
            "request_types": [{"source": "frontend", "kind": "page", "requests": 80}],
            "latest_event": "2026-10-22T12:00:00Z"}
    page.route("**/runtime-config.js", lambda route: route.fulfill(content_type="application/javascript", body=f"window.AXIOM_RUNTIME_CONFIG={{apiBase:{json.dumps(analytics_frontend)},analyticsEnabled:true,analyticsEndpoint:{json.dumps(analytics_frontend+'/api/analytics/events')}}};"))

    def handle(route):
        path = route.request.url.split("/api", 1)[-1].split("?", 1)[0]
        result = {}
        if path == "/analytics/events":
            state["events"].append(route.request.post_data_json); result = {"accepted": True}
        elif path == "/admin/analytics":
            state["reports"].append(route.request.url)
            if state["fail"]:
                route.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": "Analytics is not ready. Apply database/analytics.sql."})); return
            result = {"report": data, "collection": {"enabled": True, "edge_configured": True, "ip_logging": False, "queued": 0, "dropped": 0, "write_failures": 0}}
        elif path == "/admin/analytics/export":
            route.fulfill(content_type="text/csv", body="date_utc,page_views\n2026-10-22,25\n"); return
        elif path == "/admin/analytics/ip-logs":
            result = {"rows": [{"occurred_at": "2026-10-22", "ip": "192.0.2.1"}]}
        elif path == "/admin/me": result = {"id": "admin", "special": True}
        elif path == "/admin/users": result = {"users": [], "total": 0}
        elif path == "/admin/novels": result = {"novels": [], "total": 0}
        elif path in ("/novels/featured", "/friends/requests", "/reading-lists"): result = []
        elif path == "/profile": result = {"id": "admin", "username": "Admin"}
        route.fulfill(content_type="application/json", body=json.dumps(result))
    page.route("**/api/**", handle)
    return state


def test_dashboard_filters_exports_tabs_and_mobile(page, analytics_frontend, analytics_api):
    page.add_init_script("localStorage.setItem('axiomAnalyticsConsent','declined')")
    page.goto(analytics_frontend+"/admin.html")
    page.get_by_role("button", name="Analytics", exact=True).click()
    expect(page.locator("#analytics-cards")).to_contain_text("25")
    expect(page.locator("#analytics-map path[role='button']")).to_have_count(1)
    page.locator("#analytics-map-metric").select_option("active_seconds")
    expect(page.locator("#analytics-map path[role='button']")).to_have_attribute("aria-label", "Canada: 10 min. Filter by this country.")
    expect(page.locator("#analytics-accounts")).to_contain_text("<script>unsafe</script>")
    assert page.locator("#analytics-accounts script").count() == 0
    page.locator("#analytics-country").select_option("CA")
    page.get_by_role("button", name="Update report").click()
    expect(page.locator("#analytics-results")).to_be_visible()
    assert "country=CA" in analytics_api["reports"][-1]
    page.locator("#analytics-metric").select_option("active_seconds")
    expect(page.locator("#analytics-daily-chart svg")).to_have_attribute("aria-label", "Active seconds; exact values are available in the data table below.")
    with page.expect_download() as download:
        page.get_by_role("button", name="Export daily CSV").click()
    assert download.value.suggested_filename == "axiom-analytics.csv"
    page.screenshot(path="test-results/analytics-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.locator("#analytics-panel").evaluate("el => el.scrollWidth <= el.clientWidth")
    page.screenshot(path="test-results/analytics-mobile.png", full_page=True)
    page.get_by_role("button", name="Accounts", exact=True).click()
    expect(page.locator("#analytics-panel")).to_be_hidden()
    expect(page.locator("#users-panel")).to_be_visible()
    page.get_by_role("button", name="Remove Novels", exact=True).click()
    expect(page.locator("#deletion-panel")).to_be_visible()
    expect(page.locator("#analytics-panel")).to_be_hidden()
    page.get_by_role("button", name="Analytics", exact=True).click()
    expect(page.locator("#analytics-results")).to_be_visible()
    expect(page.locator("#deletion-panel")).to_be_hidden()


def test_default_tracking_then_heartbeat_and_opt_out(page, analytics_frontend, analytics_api):
    page.clock.install()
    page.goto(analytics_frontend+"/mission.html")
    expect(page.locator("#analytics-consent")).to_have_count(0)
    page.wait_for_function("localStorage.getItem('axiomAnalyticsVisit') !== null")
    page.clock.run_for(31000)
    page.wait_for_timeout(20)
    assert any(event["event"] == "page_view" for event in analytics_api["events"])
    assert any(event["event"] == "heartbeat" and 0 < event["active_seconds"] <= 30 for event in analytics_api["events"])
    page.get_by_role("button", name="Analytics preferences", exact=True).click()
    page.get_by_role("button", name="Turn analytics off").click()
    count = len(analytics_api["events"])
    page.clock.run_for(60000)
    assert len(analytics_api["events"]) == count
    assert page.evaluate("localStorage.getItem('axiomAnalyticsVisit')") is None


def test_existing_opt_out_preserved_and_can_be_reenabled(page, analytics_frontend, analytics_api):
    page.add_init_script("localStorage.setItem('axiomAnalyticsConsent','declined')")
    page.goto(analytics_frontend+"/mission.html")
    expect(page.get_by_role("button", name="Analytics preferences", exact=True)).to_be_visible()
    assert analytics_api["events"] == []
    page.get_by_role("button", name="Analytics preferences", exact=True).click()
    page.get_by_role("button", name="Turn analytics on").click()
    page.wait_for_function("localStorage.getItem('axiomAnalyticsVisit') !== null")
    page.wait_for_timeout(20)
    assert any(event["event"] == "page_view" for event in analytics_api["events"])


def test_report_failure_visible_and_retry_works(page, analytics_frontend, analytics_api):
    page.add_init_script("localStorage.setItem('axiomAnalyticsConsent','declined')")
    analytics_api["fail"] = True
    page.goto(analytics_frontend+"/admin.html")
    page.get_by_role("button", name="Analytics", exact=True).click()
    expect(page.locator("#analytics-status")).to_contain_text("Apply database/analytics.sql")
    expect(page.locator("#analytics-export")).to_be_disabled()
    analytics_api["fail"] = False
    page.get_by_role("button", name="Update report").click()
    expect(page.locator("#analytics-results")).to_be_visible()


def test_privacy_signal_disables_optional_tracking(page, analytics_frontend, analytics_api):
    page.add_init_script("localStorage.setItem('axiomAnalyticsConsent','accepted');Object.defineProperty(navigator,'globalPrivacyControl',{value:true})")
    page.goto(analytics_frontend+"/mission.html")
    page.wait_for_timeout(100)
    assert analytics_api["events"] == []
