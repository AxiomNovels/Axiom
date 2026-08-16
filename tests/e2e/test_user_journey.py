import os
import uuid

import pytest
from playwright.sync_api import expect
import truststore

truststore.inject_into_ssl()

from supabase import create_client


FRONTEND_URL = os.getenv("TEST_FRONTEND_URL", "http://localhost:3100")
BACKEND_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8100")


def required_test_setting(name):
    value = os.getenv(name, "").strip()
    if not value:
        pytest.fail(f"Missing {name} in tests/.env.test")
    return value


def test_complete_reader_journey(page):
    supabase_url = required_test_setting("SUPABASE_URL")
    secret_key = required_test_setting("SUPABASE_SECRET_KEY")
    admin = create_client(supabase_url, secret_key)

    email = f"axiom.test.{uuid.uuid4().hex}@gmail.com"
    password = f"Axiom-Test-{uuid.uuid4().hex}!"
    user_id = None

    def accept_dialog(dialog):
        dialog.accept()

    page.on("dialog", accept_dialog)

    # The application normally calls port 8000. During tests, keep the app
    # untouched and transparently direct those browser requests to port 8100.
    def route_test_api(route):
        test_url = route.request.url.replace(
            "http://localhost:8000",
            BACKEND_URL,
            1,
        )
        route.continue_(url=test_url)

    page.route("http://localhost:8000/**", route_test_api)

    try:
        created = admin.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
            }
        )
        user_id = created.user.id

        page.goto(f"{FRONTEND_URL}/signup.html")
        expect(page.get_by_role("heading", name="Sign up for Axiom")).to_be_visible()

        page.goto(f"{FRONTEND_URL}/login.html")
        page.locator("#email").fill(email)
        page.locator("#password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_url(f"{FRONTEND_URL}/")

        stored_user = page.evaluate("JSON.parse(localStorage.getItem('axiomUser'))")
        assert stored_user and stored_user.get("id")
        assert stored_user["id"] == user_id
        expect(page.locator("[data-user-actions]")).to_be_visible()

        novels_response = page.request.get(f"{BACKEND_URL}/api/novels")
        assert novels_response.ok
        novels = novels_response.json()
        assert novels, "The test database must contain at least one novel"
        target = novels[0]

        search = page.locator("#novel-search")
        search.fill(target["title"])
        search.press("Enter")
        page.wait_for_url(f"{FRONTEND_URL}/search.html**")
        expect(page.locator("[data-search-results] h3").first).to_have_text(target["title"])

        page.locator("[data-search-results] .book-card-link").first.click()
        page.wait_for_url(f"{FRONTEND_URL}/novel.html?id={target['id']}")
        expect(page.locator("#novel-title")).to_have_text(target["title"])

        page.locator("[data-logout-button]").click()
        page.wait_for_url(f"{FRONTEND_URL}/")
        expect(page.locator("[data-guest-actions]")).to_be_visible()

        page.goto(f"{FRONTEND_URL}/login.html")
        page.locator("#email").fill(email)
        page.locator("#password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_url(f"{FRONTEND_URL}/")
        expect(page.locator("[data-user-actions]")).to_be_visible()
    finally:
        if user_id:
            admin.auth.admin.delete_user(user_id)
