"""Behavior and work-count regressions for latency-sensitive request paths."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from routes import search, users
from services import search_service
from services.recommendation_service import recommend_novels


@pytest.mark.parametrize("sort, expected", [
    ("relevance", [2, 1]), ("title_asc", [1, 2]),
    ("title_desc", [2, 1]), ("unknown", [1, 2]),
])
def test_search_preserves_sort_filtering_and_scores_once(monkeypatch, sort, expected):
    rows = [
        {"id": 1, "title": "A magic story", "tags": ["Keep"]},
        {"id": 2, "title": "Magic", "tags": ["Keep"]},
        {"id": 3, "title": "Magic", "tags": ["Exclude"]},
        {"id": 4, "title": "Unrelated", "tags": ["Keep"]},
    ]
    monkeypatch.setattr(search, "_fetch_catalogue", lambda: deepcopy(rows))
    scored = []
    original = search_service.novel_relevance

    def score(novel, query):
        scored.append(novel["id"])
        return original(novel, query)

    monkeypatch.setattr(search_service, "novel_relevance", score)
    response = TestClient(app).get("/api/search", params={
        "q": "magic", "sort": sort, "include_tags": "Keep",
    })
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == expected
    assert scored == [1, 2, 3, 4]
    assert all(row["review_count"] == 0 for row in response.json())


class DirectoryQuery:
    def __init__(self, rows):
        self.rows = deepcopy(rows)

    def select(self, *_args):
        return self

    def order(self, key):
        self.rows.sort(key=lambda row: row[key])
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


@pytest.mark.parametrize("sort, expected", [
    ("last_online", ["b", "a"]), ("alphabetical", ["a", "b"]),
])
def test_directory_only_enriches_returned_accounts(monkeypatch, sort, expected):
    profiles = [
        {"id": "a", "username": "Alice", "online_status_visibility": "public"},
        {"id": "b", "username": "Bob", "online_status_visibility": "public"},
        {"id": "c", "username": "Carol", "online_status_visibility": "private"},
    ]
    client = SimpleNamespace(table=lambda _name: DirectoryQuery(profiles))
    monkeypatch.setattr(users, "create_service_client", lambda: client)
    monkeypatch.setattr(users, "_online_user_ids", lambda *_: {"b", "c"})
    monkeypatch.setattr(users, "_presence_by_user_id", lambda *_: {
        "a": "2026-01-01", "b": "2026-01-02", "c": "2026-01-03",
    })
    calls = []

    def special(_client, identity):
        calls.append(identity)
        return identity == "b"

    monkeypatch.setattr(users, "_is_special_account", special)
    result = users.list_public_users(sort=sort, limit=2)
    assert [row["id"] for row in result["users"]] == expected
    assert calls == expected
    assert {row["id"]: row["special"] for row in result["users"]} == {"a": False, "b": True}
    assert all("_public_presence" not in row and "online_status_visibility" not in row
               for row in result["users"])
    # Private presence is never returned, even when the result includes it.
    result = users.list_public_users(sort=sort, limit=3)
    assert next(row for row in result["users"] if row["id"] == "c")["online"] is False


def test_badge_failures_and_banned_accounts_remain_non_special():
    def failure(_identity):
        raise RuntimeError("Auth unavailable")

    client = SimpleNamespace(auth=SimpleNamespace(admin=SimpleNamespace(get_user_by_id=failure)))
    assert users._is_special_account(client, "a") is False
    client.auth.admin.get_user_by_id = lambda _: SimpleNamespace(user=SimpleNamespace(
        app_metadata={"axiom_special": True, "axiom_banned": True},
    ))
    assert users._is_special_account(client, "a") is False


def test_recommendation_cards_preserve_current_traits_tags_ties_and_inputs():
    source = {"id": 1, "tags": [" magic ", "Academy"],
              "protagonist_profiles": {"intellectual_drive": 100}}
    rows = [
        {"id": 2, "title": "B", "tags": ["MAGIC", " Academy ", "magic"],
         "protagonist_profiles": [{"intellectual_drive": 100}]},
        {"id": 3, "title": "A", "tags": ["magic", "Academy"],
         "protagonist_profiles": {"intellectual_drive": 100}},
        {"id": 4, "title": "Z", "tags": ["magic"],
         "protagonist_profiles": {"intellectual_drive": 0}},
        {"id": 5, "title": None, "tags": [], "protagonist_profiles": {}},
    ]
    original = deepcopy(rows)
    result = recommend_novels(source, [source, *rows, rows[0]], limit=2)
    assert [row["id"] for row in result] == [3, 2]
    assert set(result[1]["shared_tags"]) == {"Academy", "MAGIC", "magic"}
    assert all(set(row) == {"id", "title", "author", "cover_image_url", "shared_tags"}
               for row in result)
    assert rows == original
    assert recommend_novels(source, rows, limit=0) == []
    assert len(recommend_novels(source, rows, limit=-1)) == 3
    assert len(recommend_novels(source, rows, limit=20)) == 4
