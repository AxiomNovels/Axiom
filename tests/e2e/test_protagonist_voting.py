"""Browser UI checks with an isolated API fixture; no live accounts or database."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect


KEYS = ['intelligence', 'charisma', 'moral_integrity', 'kinship_friendship', 'romantic_attachment', 'erotic_desire', 'arrogance_pride']
# Exercise the seven defaults here; custom definitions are tested separately below.
DEFINITION = {"revision": 1, "instructions": "Score using evidence.", "traits": [
    {"key": key, "name": key.replace("_", " ").title(), "prompt": f"Score {key} from 0 to 100."}
    for key in KEYS
]}
USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def frontend():
    root = Path(__file__).resolve().parents[2] / "frontend" / "public"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def voting_api(page):
    state = {"eligible": True, "locked": False, "votes": {}, "requests": [],
             "definition": json.loads(json.dumps(DEFINITION)), "definition_writes": []}

    def summary():
        return {"revision": state["definition"]["revision"], "traits": state["definition"]["traits"],
                "eligible": state["eligible"], "scores_locked": state["locked"], "baseline": dict.fromkeys(KEYS, 20),
                "profile": {key: round((20 + state["votes"][key]) / 2) if key in state["votes"] and not state["locked"] else 20 for key in KEYS},
                "my_votes": state["votes"], "vote_count": len(state["votes"]), "voter_count": int(bool(state["votes"])),
                "distribution": {key: [{"score": value, "count": 1}] for key, value in state["votes"].items()}}

    def handle(route):
        path = route.request.url.split("/api", 1)[-1].split("?", 1)[0]
        method = route.request.method
        state["requests"].append((method, path))
        payload = []
        if path == "/admin/me":
            payload = {"id": USER, "special": True}
        elif path in ("/admin/protagonist-definition", "/search/protagonist-definition"):
            if method == "PUT":
                draft = route.request.post_data_json
                state["definition_writes"].append(draft)
                if state.get("conflict"):
                    route.fulfill(status=409, content_type="application/json", body=json.dumps({"detail":"Protagonist definitions changed. Reload and review your changes before saving."}))
                    return
                state["definition"] = {**draft,"revision":draft["revision"]+1}
            payload = state["definition"]
        elif path == "/search/options":
            payload = {"tags":[],"genres":[],"statuses":[],"protagonist_definition":state["definition"]}
        elif path == "/admin/protagonist-rebuilds":
            payload = {"jobs":[]}
        elif path == "/profile":
            payload = {"id": USER, "username": "Reader"}
        elif path == "/admin/users":
            users = state.get("users", [{"id": USER, "username": "Reader", "special": True}])
            payload = {"users": users, "total": len(users)}
        elif path == "/admin/novels":
            payload = {"novels": [{"id": 1, "title": "Test novel"}], "total": 1}
        elif path == "/admin/novels/1/profiles":
            payload = {"novel":{"id":1,"title":"Test novel"},"definition":state["definition"],
                       "profiles":{"protagonist":{"protagonist_name":"Hero","scores":{
                           t["key"]:20 for t in state["definition"]["traits"]}}}}
        elif path == "/admin/novels/1/profiles/protagonist":
            state["saved_scores"] = route.request.post_data_json
            payload = {"saved":True}
        elif path == "/admin/novels/1/protagonist-score-lock":
            state["locked"] = route.request.post_data_json["locked"]
            payload = summary()
        elif path == "/admin/protagonist-votes/1":
            state["votes"].clear()
            payload = {"deleted": 1}
        elif path.startswith("/admin/") and path.endswith("/protagonist-votes"):
            if method == "DELETE":
                state["votes"].clear()
                payload = {"deleted": True}
            else:
                records = [{"id": 1, "novel_id": 1, "user_id": USER, "trait": key, "score": value,
                            "profiles": {"username": "Reader"}, "novels": {"novels": {"title": "Test novel"}},
                            "updated_at": "2026-01-01T12:00:00Z"} for key, value in state["votes"].items()]
                payload = {"novel": {"id": 1, "title": "Test novel"}, "summary": summary(), "votes": records, "total": len(records)}
        elif "/protagonist-votes" in path:
            trait = path.rsplit("/", 1)[-1]
            if method == "PUT":
                state["votes"][trait] = route.request.post_data_json["score"]
            elif method == "DELETE":
                state["votes"].pop(trait, None)
            payload = summary()
        elif path == "/novels/1":
            payload = {"id": 1, "title": "Test novel", "author": "Author", "status": "ongoing", "synopsis": "A novel.",
                       "protagonist_profiles": dict.fromkeys(KEYS, 20)}
        elif path.endswith("/reviews"):
            payload = {"reviews": [], "total": 0}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("http://localhost:8000/**", handle)
    return state


def login(page):
    page.add_init_script(f"localStorage.setItem('axiomSession', JSON.stringify({{access_token:'test'}})); localStorage.setItem('axiomUser', JSON.stringify({{id:'{USER}',user_metadata:{{username:'Reader'}}}}));")


def test_reader_votes_updates_and_withdraws(page, frontend, voting_api):
    login(page)
    page.goto(frontend + "/vote.html?id=1")
    host = page.locator("#protagonist-votes")
    row = host.locator("form").filter(has=page.get_by_label("Moral Integrity", exact=True))
    row.get_by_label("Moral Integrity", exact=True).fill("100")
    row.get_by_role("button", name="Vote", exact=True).click()
    expect(host.get_by_role("status")).to_have_text("Vote saved. Profile recalculated.")
    expect(row.locator(".vote-current")).to_have_text("60")
    row.get_by_label("Moral Integrity", exact=True).fill("0")
    row.get_by_role("button", name="Update vote").click()
    expect(row.locator(".vote-trait-description small")).to_contain_text("Your vote: 0")
    expect(row.locator(".vote-current")).to_have_text("10")
    row.get_by_role("button", name="Remove").click()
    expect(host.get_by_role("status")).to_have_text("Vote removed. Profile recalculated.")
    expect(row.locator(".vote-current")).to_have_text("20")
    page.set_viewport_size({"width": 390, "height": 844})
    assert host.evaluate("el => el.scrollWidth <= el.clientWidth")
    page.screenshot(path="test-results/voting-mobile.png", full_page=True)


def test_guest_and_unestablished_profiles(page, frontend, voting_api):
    page.goto(frontend + "/vote.html?id=1")
    expect(page.get_by_role("link", name="Log in to vote")).to_be_visible()
    voting_api["eligible"] = False
    page.reload()
    expect(page.locator("#protagonist-votes")).to_contain_text("Voting opens when all current")
    expect(page.locator("#protagonist-votes input")).to_have_count(0)


def test_admin_distribution_individual_and_user_wide_deletion(page, frontend, voting_api):
    login(page)
    voting_api["votes"]["moral_integrity"] = 100
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(frontend + "/admin.html")
    page.get_by_role("button", name="Build Novels", exact=True).click()
    page.get_by_role("button", name="Vote distribution").click()
    host = page.locator("#vote-workspace")
    expect(host).to_contain_text("Reader · Moral Integrity: 100")
    expect(host.locator("meter")).to_have_attribute("value", "1")
    page.screenshot(path="test-results/voting-admin.png", full_page=True)
    host.get_by_role("button", name="Delete vote", exact=True).click()
    expect(host).to_contain_text("0 trait votes")
    voting_api["votes"]["intelligence"] = 0
    page.get_by_role("button", name="Accounts", exact=True).click()
    page.get_by_role("button", name="View votes").click()
    expect(host).to_contain_text("Test novel · Intelligence: 0")
    host.get_by_role("button", name="Delete all votes by this user").click()
    expect(host).to_contain_text("No votes found.")
    assert ("DELETE", f"/admin/users/{USER}/protagonist-votes") in voting_api["requests"]


def test_locked_reader_votes_still_saved(page, frontend, voting_api):
    login(page)
    voting_api["locked"] = True
    page.goto(frontend + "/vote.html?id=1")
    host = page.locator("#protagonist-votes")
    expect(host).to_contain_text("Scores locked by a moderator")
    row = host.locator("form").filter(has=page.get_by_label("Moral Integrity", exact=True))
    row.get_by_label("Moral Integrity", exact=True).fill("100")
    row.get_by_role("button", name="Vote", exact=True).click()
    expect(host.get_by_role("status")).to_have_text("Vote saved. Locked scores unchanged.")
    expect(row.locator(".vote-current")).to_have_text("20")
    assert voting_api["votes"] == {"moral_integrity": 100}


def test_admin_locks_and_unlocks_scores(page, frontend, voting_api):
    login(page)
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(frontend + "/admin.html")
    page.get_by_role("button", name="Build Novels", exact=True).click()
    page.get_by_role("button", name="Vote distribution").click()
    host = page.locator("#vote-workspace")
    host.get_by_role("button", name="Lock scores", exact=True).click()
    expect(host).to_contain_text("Scores locked. Votes are collected")
    assert voting_api["locked"] is True
    host.get_by_role("button", name="Unlock scores", exact=True).click()
    expect(host).to_contain_text("Scores unlocked. Reader votes can change")
    assert voting_api["locked"] is False


def test_novel_only_shows_voting_link(page, frontend, voting_api):
    login(page)
    page.goto(frontend + "/novel.html?id=1")
    link = page.get_by_role("link", name="Vote on traits")
    expect(link).to_have_attribute("href", "/vote.html?id=1")
    expect(page.locator(".trait-vote-form")).to_have_count(0)
    assert not any("protagonist-votes" in path for method, path in voting_api["requests"])
    link.click()
    expect(page.get_by_role("heading", name="Test novel", exact=True)).to_be_visible()
    expect(page.locator(".trait-vote-form")).to_have_count(7)
    page.screenshot(path="test-results/voting-desktop.png", full_page=True)
    page.get_by_role("link", name="Back to novel").click()
    expect(page.locator("#novel-title")).to_have_text("Test novel")


def test_admin_account_actions_menu_and_layout(page, frontend, voting_api):
    login(page)
    voting_api["users"] = [
        {"id": "reader-two", "username": "NightReader", "special": False, "banned": False},
        {"id": "moderator", "username": "Shadowfax", "special": True, "banned": False},
        {"id": USER, "username": "wafflehunter", "special": True, "banned": False},
    ]
    page.goto(frontend + "/admin.html")
    expect(page.locator(".admin-catalog-row")).to_have_count(3)
    expect(page.get_by_role("button", name="Ban account", exact=True)).not_to_be_visible()
    page.get_by_label("More actions for NightReader", exact=True).click()
    expect(page.get_by_role("button", name="Ban account", exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("button", name="Ban account", exact=True)).not_to_be_visible()
    page.screenshot(path="test-results/admin-accounts-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_label("More actions for Shadowfax", exact=True).click()
    expect(page.locator(".admin-action-menu[open]").get_by_role("button", name="Delete all votes")).to_be_visible()
    expect(page.locator(".admin-action-menu[open]").get_by_role("button", name="Ban account")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path="test-results/admin-accounts-mobile.png", full_page=True)


def test_manage_definition_stages_changes_and_confirms_impact(page, frontend, voting_api):
    login(page)
    page.goto(frontend + "/admin.html")
    page.get_by_role("button", name="Build Protagonist Traits", exact=True).click()
    panel = page.locator("#definition-panel")
    expect(panel.locator(".definition-trait")).to_have_count(1)
    expect(panel.get_by_role("button", name="Save definition")).to_be_disabled()
    card = panel.locator(".definition-trait").first
    card.get_by_label("Trait name: Intelligence", exact=True).fill("Determination")
    card.get_by_label("Scoring prompt", exact=True).fill("0 gives up; 100 perseveres.")
    expect(panel.locator("#definition-impact")).to_contain_text("including locked profiles")
    expect(panel.locator("#definition-impact")).to_contain_text("Intelligence")
    assert voting_api["definition_writes"] == []
    page.once("dialog", lambda dialog: dialog.dismiss())
    panel.get_by_role("button", name="Save definition").click()
    assert voting_api["definition_writes"] == []
    page.once("dialog", lambda dialog: dialog.accept())
    panel.get_by_role("button", name="Save definition").click()
    expect(panel.locator("#definition-status")).to_contain_text("Saved revision 2")
    saved = voting_api["definition_writes"][0]
    assert saved["revision"] == 1
    assert saved["traits"][0] == {"key":"intelligence","name":"Determination","prompt":"0 gives up; 100 perseveres."}
    assert saved["traits"][1:] == DEFINITION["traits"][1:]
    page.set_viewport_size({"width":390,"height":844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path="test-results/manage-protagonist-mobile.png", full_page=True)


def test_manage_definition_add_delete_and_conflict_keep_draft(page, frontend, voting_api):
    login(page)
    page.goto(frontend + "/admin.html")
    page.get_by_role("button", name="Build Protagonist Traits", exact=True).click()
    panel = page.locator("#definition-panel")
    expect(panel.locator(".definition-trait")).to_have_count(1)
    panel.get_by_role("button", name="Add trait", exact=True).click()
    card = panel.locator(".definition-trait")
    card.get_by_label("Trait name: New trait", exact=True).fill("Resilience")
    card.get_by_label("Trait key", exact=False).fill("resilience")
    card.get_by_label("Scoring prompt", exact=True).fill("Perseverance, from 0 to 100.")
    panel.get_by_role("button", name="Edit trait 1: Intelligence", exact=True).click()
    panel.locator(".definition-trait").get_by_role("button", name="Delete this trait").click()
    page.once("dialog", lambda dialog: dialog.accept())
    voting_api["conflict"] = True
    panel.get_by_role("button", name="Save definition").click()
    expect(panel.locator("#definition-status")).to_contain_text("Reload and review")
    panel.get_by_role("button", name="Edit trait 7: Resilience", exact=True).click()
    expect(panel.locator(".definition-trait").get_by_label("Trait name: Resilience", exact=True)).to_have_value("Resilience")
    assert voting_api["definition_writes"][0]["traits"][-1]["key"] == "resilience"
    assert "intelligence" not in [t["key"] for t in voting_api["definition_writes"][0]["traits"]]
    # Other tabs remain visible independently of the novels panel.
    page.get_by_role("button", name="Accounts", exact=True).click()
    expect(page.locator("#users-panel")).to_be_visible()
    expect(panel).not_to_be_visible()
    page.get_by_role("button", name="Build Protagonist Traits", exact=True).click()
    panel.get_by_role("button", name="Edit trait 7: Resilience", exact=True).click()
    expect(panel.locator(".definition-trait").get_by_label("Trait name: Resilience", exact=True)).to_have_value("Resilience")


def test_finder_and_guide_use_custom_names_as_text(page, frontend, voting_api):
    voting_api["definition"]["traits"] = [{"key":"resilience","name":'<img src=x onerror="window.injected=true">',"prompt":"A new rubric"}]
    page.goto(frontend + "/finder.html")
    filters = page.locator('[data-profile-filters="protagonist"]')
    expect(filters.locator(".profile-filter")).to_have_count(1)
    expect(filters.locator("strong")).to_have_text('<img src=x onerror="window.injected=true">')
    expect(filters.locator("img")).to_have_count(0)
    expect(filters.locator('[name="resilience_min"]')).to_have_count(1)
    page.goto(frontend + "/protagonist-profile-info.html")
    expect(page.locator(".trait-guide")).to_have_count(1)
    expect(page.locator(".trait-guide-body")).to_have_text("A new rubric")
    assert page.evaluate("window.injected === undefined")


def test_manual_profile_editor_uses_custom_traits_and_revision(page, frontend, voting_api):
    voting_api["definition"] = {"revision":9,"instructions":"Use evidence.","traits":[
        {"key":"resilience","name":"Resilience","prompt":"0 gives up; 100 perseveres."}]}
    login(page)
    page.goto(frontend + "/admin.html")
    page.get_by_role("button", name="Build Novels", exact=True).click()
    page.get_by_role("button", name="Edit profiles", exact=True).click()
    editor = page.locator("#profile-editor")
    expect(editor.locator('input[type="range"]')).to_have_count(1)
    editor.get_by_label("Resilience", exact=True).evaluate("el => { el.value = '70'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
    editor.get_by_role("button", name="Save changes", exact=True).click()
    expect(editor.locator('p[role="status"]')).to_have_text("Changes saved.")
    assert voting_api["saved_scores"] == {"scores":{"resilience":70},"protagonist_name":"Hero","revision":9}
