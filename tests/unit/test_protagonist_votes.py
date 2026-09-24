from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from main import app
from core.auth import get_current_user, get_optional_current_user
from routes.admin import require_special
from routes import protagonist_votes as votes
from profiler.prompt import MEASURES


USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def api(monkeypatch):
    service = MagicMock()
    monkeypatch.setattr(votes, "create_service_client", lambda: service)
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": 1}]
    service.rpc.return_value.execute.return_value.data = {"eligible": True, "my_votes": {"selflessness": 0}}
    app.dependency_overrides[get_current_user] = lambda: (USER, MagicMock())
    app.dependency_overrides[get_optional_current_user] = lambda: (USER, MagicMock())
    try:
        yield TestClient(app), service
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("score", [0, 50, 100])
def test_vote_uses_verified_identity_and_returns_recalibrated_summary(api, score):
    client, service = api
    result = client.put("/api/novels/1/protagonist-votes/selflessness", json={"score": score})
    assert result.status_code == 200
    assert result.json()["eligible"] is True
    service.rpc.assert_any_call("cast_protagonist_vote", {
        "p_novel_id": 1, "p_user_id": USER, "p_trait": "selflessness", "p_score": score,
    })


@pytest.mark.parametrize("payload", [{"score": -1}, {"score": 101}, {"score": True},
    {"score": "50"}, {"score": 2.5}, {}, {"score": 50, "user_id": "someone-else"}])
def test_vote_rejects_invalid_scores_and_identity_spoofing(api, payload):
    client, service = api
    assert client.put("/api/novels/1/protagonist-votes/selflessness", json=payload).status_code == 422
    service.rpc.assert_not_called()


def test_unknown_trait_rejected(api):
    client, service = api
    assert client.put("/api/novels/1/protagonist-votes/fake", json={"score": 10}).status_code == 422
    service.rpc.assert_not_called()


def test_missing_gemini_baseline_rejected(api):
    client, service = api
    service.rpc.return_value.execute.side_effect = APIError({"code": "P0001", "message": "No baseline"})
    assert client.put("/api/novels/1/protagonist-votes/selflessness", json={"score": 10}).status_code == 409


def test_missing_novel_rejected(api):
    client, service = api
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    assert client.get("/api/novels/999/protagonist-votes").status_code == 404
    service.rpc.assert_not_called()


def test_withdraw_scoped_to_authenticated_user(api):
    client, service = api
    assert client.delete("/api/novels/1/protagonist-votes/selflessness").status_code == 200
    query = service.table.return_value.delete.return_value
    query.eq.assert_called_once_with("novel_id", 1)
    query.eq.return_value.eq.assert_called_once_with("user_id", USER)
    query.eq.return_value.eq.return_value.eq.assert_called_once_with("trait", "selflessness")


def test_anonymous_summary_never_requests_another_users_votes(api):
    client, service = api
    app.dependency_overrides[get_optional_current_user] = lambda: (None, None)
    assert client.get("/api/novels/1/protagonist-votes").status_code == 200
    service.rpc.assert_called_once_with("protagonist_vote_summary", {"p_novel_id": 1, "p_user_id": None})


@pytest.mark.parametrize("method,path", [
    ("PUT", "/novels/1/protagonist-votes/selflessness"),
    ("DELETE", "/novels/1/protagonist-votes/selflessness"),
    ("GET", "/admin/novels/1/protagonist-votes"),
    ("GET", f"/admin/users/{USER}/protagonist-votes"),
    ("DELETE", "/admin/protagonist-votes/1"),
    ("DELETE", f"/admin/users/{USER}/protagonist-votes"),
])
def test_private_routes_require_login(method, path):
    assert TestClient(app).request(method, "/api" + path, json={"score": 50}).status_code == 401


def test_ordinary_user_cannot_read_or_delete_admin_votes(api, monkeypatch):
    client, service = api
    from routes import admin
    monkeypatch.setattr(admin, "create_service_client", lambda: service)
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={})
    for method, path in [("GET", "/novels/1/protagonist-votes"),
                         ("GET", f"/users/{USER}/protagonist-votes"),
                         ("DELETE", "/protagonist-votes/1"),
                         ("DELETE", f"/users/{USER}/protagonist-votes")]:
        assert client.request(method, "/api/admin" + path).status_code == 403
    service.table.assert_not_called()


def test_admin_bulk_delete_is_all_novels_and_not_paginated(api):
    client, service = api
    app.dependency_overrides[require_special] = lambda: ("admin", service)
    assert client.delete(f"/api/admin/users/{USER}/protagonist-votes").status_code == 200
    query = service.table.return_value.delete.return_value
    query.eq.assert_called_once_with("user_id", USER)
    query.eq.return_value.execute.assert_called_once()


def test_admin_individual_delete_handles_missing_vote(api):
    client, service = api
    app.dependency_overrides[require_special] = lambda: ("admin", service)
    service.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
    assert client.delete("/api/admin/protagonist-votes/123").status_code == 404


def test_gemini_save_registers_complete_baseline_atomically(monkeypatch):
    from profiler import profile_novel
    service = MagicMock()
    monkeypatch.setattr(profile_novel, "database_client", lambda **kwargs: service)
    scores = dict.fromkeys(MEASURES, 0)
    profile_novel.save_profile(1, "Hero", {"scores": scores})
    service.rpc.assert_called_once_with("save_gemini_protagonist", {
        "p_novel_id": 1, "p_name": "Hero", "p_scores": scores,
    })
    service.table.assert_not_called()


@pytest.mark.parametrize("locked", [True, False])
def test_admin_can_toggle_score_lock(api, locked):
    client, service = api
    app.dependency_overrides[require_special] = lambda: ("admin", service)
    result = client.patch("/api/admin/novels/1/protagonist-score-lock", json={"locked": locked})
    assert result.status_code == 200
    service.rpc.assert_any_call("set_protagonist_score_lock", {"p_novel_id": 1, "p_locked": locked})


@pytest.mark.parametrize("locked", ["true", 1, None])
def test_lock_rejects_invalid_values(api, locked):
    client, service = api
    app.dependency_overrides[require_special] = lambda: ("admin", service)
    assert client.patch("/api/admin/novels/1/protagonist-score-lock", json={"locked": locked}).status_code == 422
    service.rpc.assert_not_called()


def test_lock_requires_admin(api, monkeypatch):
    client, service = api
    from routes import admin
    monkeypatch.setattr(admin, "create_service_client", lambda: service)
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={})
    assert client.patch("/api/admin/novels/1/protagonist-score-lock", json={"locked": True}).status_code == 403
    service.rpc.assert_not_called()


def test_lock_requires_login():
    assert TestClient(app).patch("/api/admin/novels/1/protagonist-score-lock", json={"locked": True}).status_code == 401


def test_lock_without_profile_reports_conflict(api):
    client, service = api
    app.dependency_overrides[require_special] = lambda: ("admin", service)
    service.rpc.return_value.execute.side_effect = APIError({"code": "P0001", "message": "No profile"})
    assert client.patch("/api/admin/novels/1/protagonist-score-lock", json={"locked": True}).status_code == 409
