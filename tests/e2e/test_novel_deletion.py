"""Isolated deletion UI checks. No real accounts or live database mutations."""
import json
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect

from test_protagonist_voting import frontend, login, DEFINITION, USER


@pytest.fixture
def deletion_api(page):
    state = {"admin": True, "deleted": False, "failure": False, "deletes": [], "queries": []}

    def handle(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix("/api")
        payload = []
        code = 200
        if path == "/admin/me":
            code = 200 if state["admin"] else 403
            payload = {"id": USER, "special": True} if state["admin"] else {"detail": "Access denied"}
        elif path == "/admin/users":
            payload = {"users": [], "total": 0}
        elif path == "/admin/novels":
            state["queries"].append(parse_qs(urlparse(request.url).query))
            novels = [] if state["deleted"] else [{"id": 1, "title": "Test novel", "author": "Test author"}]
            payload = {"novels": novels, "total": len(novels)}
        elif path == "/admin/novels/1" and request.method == "DELETE":
            state["deletes"].append(request.headers.get("authorization"))
            if state["failure"]:
                code, payload = 500, {"detail": "The novel could not be deleted. Please try again."}
            else:
                state["deleted"] = True
                payload = {"deleted": True, "notified_readers": 2}
        elif path == "/admin/protagonist-rebuilds":
            payload = {"jobs": []}
        elif path in ("/search/protagonist-definition", "/admin/protagonist-definition"):
            payload = DEFINITION
        elif path == "/novels/1":
            payload = {"id": 1, "title": "Test novel", "author": "Test author", "synopsis": "A story.", "protagonist_profiles": {}}
        elif path.endswith("/reviews"):
            payload = {"reviews": [], "total": 0}
        elif path == "/profile":
            payload = {"id": USER, "username": "Reader"}
        elif path == "/search/options":
            payload = {"tags": [], "genres": [], "statuses": [], "protagonist_definition": DEFINITION}
        route.fulfill(status=code, content_type="application/json", body=json.dumps(payload))

    page.route("http://localhost:8000/**", handle)
    return state


def test_admin_search_cancel_failure_and_delete(page, frontend, deletion_api):
    login(page)
    page.goto(frontend + "/admin.html")
    page.get_by_role("button", name="Remove Novels", exact=True).click()
    host = page.locator("#deletion-panel")
    host.get_by_label("Search by title").fill("Test novel")
    host.get_by_role("button", name="Search", exact=True).click()
    remove = host.get_by_role("button", name="Delete novel: Test novel")
    expect(remove).to_be_visible()
    page.once("dialog", lambda dialog: dialog.dismiss())
    remove.click()
    assert deletion_api["deletes"] == []
    deletion_api["failure"] = True
    page.once("dialog", lambda dialog: dialog.accept())
    remove.click()
    expect(page.locator("#admin-status")).to_contain_text("could not be deleted")
    expect(remove).to_be_enabled()
    deletion_api["failure"] = False
    page.once("dialog", lambda dialog: dialog.accept())
    remove.click()
    expect(page.locator("#admin-status")).to_contain_text("Affected readers have been notified")
    expect(host).to_contain_text("No matches found")
    assert deletion_api["deletes"] == ["Bearer test", "Bearer test"]
    assert any(query.get("q") == ["Test novel"] for query in deletion_api["queries"])
    page.get_by_role("button", name="Accounts", exact=True).click()
    expect(host).to_be_hidden()
    page.get_by_role("button", name="Build Novels", exact=True).click()
    expect(page.locator("#novels-panel")).to_be_visible()


def test_novel_page_admin_can_delete(page, frontend, deletion_api):
    login(page)
    page.goto(frontend + "/novel.html?id=1")
    remove = page.get_by_role("button", name="Delete novel", exact=True)
    expect(remove).to_be_visible()
    page.once("dialog", lambda dialog: dialog.dismiss())
    remove.click()
    assert deletion_api["deletes"] == []
    deletion_api["failure"] = True
    page.once("dialog", lambda dialog: dialog.accept())
    remove.click()
    expect(page.locator("#novel-delete-status")).to_contain_text("could not be deleted")
    expect(page.locator("#novel-title")).to_have_text("Test novel")
    deletion_api["failure"] = False
    page.once("dialog", lambda dialog: dialog.accept())
    remove.click()
    expect(page.get_by_role("heading", name="Novel deleted", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Return to Admin Hub")).to_be_visible()


@pytest.mark.parametrize("signed_in", [False, True])
def test_non_admin_has_no_deletion_controls(page, frontend, deletion_api, signed_in):
    deletion_api["admin"] = False
    if signed_in:
        login(page)
    page.goto(frontend + "/novel.html?id=1")
    expect(page.locator("#novel-title")).to_have_text("Test novel")
    expect(page.locator("#novel-admin-actions")).to_be_hidden()
    assert deletion_api["deletes"] == []
    page.goto(frontend + "/admin.html")
    expect(page.locator("#admin-status")).to_contain_text("Access denied")
    expect(page.locator("#admin-content")).to_be_hidden()
