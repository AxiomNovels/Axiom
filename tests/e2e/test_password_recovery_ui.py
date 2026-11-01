from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect


@pytest.fixture
def recovery_page(page):
    root = Path(__file__).resolve().parents[2] / "frontend" / "public"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Shared analytics must not make an isolated browser test depend on the internet.
    page.route("**/*", lambda route: route.continue_()
               if route.request.url.startswith(("http://127.0.0.1:", "http://localhost:"))
               else route.abort())
    page.route("**/runtime-config.js", lambda route: route.fulfill(
        content_type="application/javascript",
        body='window.AXIOM_RUNTIME_CONFIG={apiBase:"http://localhost:8000",analyticsEnabled:false};',
    ))
    page.route("**/api/**", lambda route: route.fulfill(json={}))
    yield page, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_forgot_password_link_and_email_request(recovery_page):
    page, base = recovery_page
    calls = []
    page.route("**/api/password/forgot", lambda route: (
        calls.append(route.request.post_data_json),
        route.fulfill(json={"message": "If an account exists, check your email."}),
    ))
    page.goto(f"{base}/login.html", wait_until="domcontentloaded")
    page.get_by_role("link", name="Forgot password?").click()
    page.get_by_label("Email address").fill("reader@example.com")
    page.get_by_role("button", name="Send reset link").click()
    expect(page.get_by_role("status")).to_contain_text("check your email")
    assert calls == [{"email": "reader@example.com"}]


def test_reset_validates_confirmation_and_uses_email_credentials(recovery_page):
    page, base = recovery_page
    calls = []
    def reset(route):
        calls.append((route.request.post_data_json, route.request.headers.get("authorization")))
        route.fulfill(json={"message": "Your password has been updated."})
    page.route("**/api/password/reset", reset)
    page.goto(f"{base}/reset-password.html#type=recovery&access_token=test-access&refresh_token=test-refresh", wait_until="domcontentloaded")
    assert "#" not in page.url
    page.get_by_label("New password", exact=True).fill("new-password")
    page.get_by_label("Confirm new password").fill("different-password")
    page.get_by_role("button", name="Reset password").click()
    expect(page.get_by_role("alert")).to_contain_text("don’t match")
    assert not calls
    page.get_by_label("Confirm new password").fill("new-password")
    page.get_by_role("button", name="Reset password").click()
    expect(page.get_by_role("status")).to_contain_text("updated")
    assert calls == [({"password": "new-password", "refresh_token": "test-refresh"}, "Bearer test-access")]
    assert page.evaluate("JSON.stringify(localStorage)").find("test-refresh") == -1


def test_missing_or_expired_recovery_link(recovery_page):
    page, base = recovery_page
    page.goto(f"{base}/reset-password.html#error=access_denied&error_code=otp_expired", wait_until="domcontentloaded")
    expect(page.get_by_role("alert")).to_contain_text("expired")
    expect(page.get_by_role("button", name="Reset password")).to_be_disabled()
    assert "#" not in page.url


def test_reset_failure_allows_retry(recovery_page):
    page, base = recovery_page
    page.route("**/api/password/reset", lambda route: route.fulfill(status=401, json={"detail": "Your link has expired. Please request a new one."}))
    page.goto(f"{base}/reset-password.html#type=recovery&access_token=test-access&refresh_token=test-refresh", wait_until="domcontentloaded")
    page.get_by_label("New password", exact=True).fill("new-password")
    page.get_by_label("Confirm new password").fill("new-password")
    page.get_by_role("button", name="Reset password").click()
    expect(page.get_by_role("alert")).to_contain_text("expired")
    expect(page.get_by_role("button", name="Reset password")).to_be_enabled()
