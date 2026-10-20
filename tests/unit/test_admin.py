from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from core import auth
from routes import admin
from profiler.prompt import DEFAULT_DEFINITION, MEASURES


@pytest.fixture
def service(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(admin, "create_service_client", lambda: client)
    monkeypatch.setattr(admin, "load_definition", lambda client=None: DEFAULT_DEFINITION)
    return client


@pytest.mark.parametrize("metadata", [{}, {"axiom_special": "true"}, {"axiom_special": True, "axiom_banned": True}])
def test_special_permission_is_strict_and_server_owned(service, metadata):
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata=metadata)
    with pytest.raises(HTTPException) as error:
        admin.require_special(("owner", None))
    assert error.value.status_code == 403


def test_special_allowed(service):
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={"axiom_special": True})
    assert admin.require_special(("owner", None)) == ("owner", service)


def test_users_include_last_online_and_support_name_sort(service):
    service.table.return_value.select.return_value.order.return_value.order.return_value.range.return_value.execute.return_value.data = [
        {"id": "one", "username": "Alice", "created_at": "2026-01-01T00:00:00Z"},
    ]
    service.table.return_value.select.return_value.order.return_value.order.return_value.range.return_value.execute.return_value.count = 1
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(
        app_metadata={}, last_sign_in_at="2026-10-18T12:00:00Z"
    )

    result = admin.users(q="", page=1, sort="name", admin=("owner", service))

    assert result["users"][0]["last_online"] == "2026-10-18T12:00:00Z"
    assert result["sort"] == "name"
    service.table.return_value.select.return_value.order.return_value.order.return_value.range.assert_called_once_with(0, 24)


def test_users_sort_last_online_before_paginating(service):
    query = service.table.return_value.select.return_value
    query.order.return_value.order.return_value.execute.return_value.data = [
        {"id": "old", "username": "Old", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "new", "username": "New", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "never", "username": "Never", "created_at": "2026-01-01T00:00:00Z"},
    ]
    query.order.return_value.order.return_value.execute.return_value.count = 3

    def user_by_id(user_id):
        return SimpleNamespace(user=SimpleNamespace(
            app_metadata={},
            last_sign_in_at={"old": "2026-01-01T00:00:00Z", "new": "2026-10-18T12:00:00Z", "never": None}[user_id],
        ))

    service.auth.admin.get_user_by_id.side_effect = user_by_id
    result = admin.users(q="", page=1, sort="last_online", admin=("owner", service))

    assert [user["id"] for user in result["users"]] == ["new", "old", "never"]
    query.order.return_value.order.return_value.range.assert_not_called()


def test_ordinary_account_cannot_call_admin_routes(service):
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={})
    app.dependency_overrides[auth.get_current_user] = lambda: ("ordinary", None)
    try:
        client = TestClient(app)
        for path in ("/me", "/users", "/novels", "/novels/1/profiles"):
            assert client.get("/api/admin" + path).status_code == 403
        assert client.patch("/api/admin/users/00000000-0000-0000-0000-000000000001/ban", json={"banned": True}).status_code == 403
        assert client.put("/api/admin/novels/1/profiles/philosophy", json={"scores": {}}).status_code == 403
        service.table.assert_not_called()
        service.auth.admin.update_user_by_id.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_banned_existing_session_rejected(monkeypatch):
    fake = MagicMock()
    fake.auth.get_user.return_value.user = SimpleNamespace(id="user", app_metadata={"axiom_banned": True})
    monkeypatch.setattr(auth, "supabase", fake)
    for resolver in (auth.get_current_user, auth.get_optional_current_user):
        with pytest.raises(HTTPException) as error:
            resolver("Bearer existing-session")
        assert error.value.status_code == 403


def test_all_admin_routes_require_login():
    client = TestClient(app)
    for method, path, body in [
        ("GET", "/me", None), ("GET", "/users", None), ("GET", "/novels", None),
        ("GET", "/novels/1/profiles", None),
        ("PATCH", "/users/00000000-0000-0000-0000-000000000001/ban", {"banned": True}),
        ("PUT", "/novels/1/profiles/philosophy", {"scores": {}}),
    ]:
        assert client.request(method, "/api/admin" + path, json=body).status_code == 401


def test_ban_self_and_special_protected(service):
    from uuid import UUID
    target = UUID("00000000-0000-0000-0000-000000000001")
    with pytest.raises(HTTPException):
        admin.ban_user(target, admin.BanUpdate(banned=True), (str(target), service))
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={"axiom_special": True})
    with pytest.raises(HTTPException):
        admin.ban_user(target, admin.BanUpdate(banned=True), ("other", service))
    service.auth.admin.update_user_by_id.assert_not_called()


@pytest.mark.parametrize("banned", [True, False])
def test_ban_preserves_metadata_and_controls_auth(service, banned):
    from uuid import UUID
    target = UUID("00000000-0000-0000-0000-000000000001")
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={"provider": "email"})
    admin.ban_user(target, admin.BanUpdate(banned=banned), ("owner", service))
    payload = service.auth.admin.update_user_by_id.call_args.args[1]
    assert payload["app_metadata"] == {"provider": "email", "axiom_banned": banned}
    assert payload["ban_duration"] == ("876000h" if banned else "none")


@pytest.mark.parametrize("kind", list(admin.PROFILES))
def test_score_save_whitelists_fields(service, kind):
    measures = MEASURES
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": 1}]
    scores = dict.fromkeys(measures, 50)
    payload = admin.ProfileScores(scores=scores, protagonist_name="Hero", revision=1)
    assert admin.save_scores(1, kind, payload, ("owner", service)) == {"saved": True}
    service.rpc.assert_called_once_with("save_protagonist_profile", {
        "p_novel_id": 1, "p_name": "Hero", "p_scores": scores, "p_revision": 1, "p_generated": False,
    })
    service.table.return_value.upsert.assert_not_called()
    for invalid in [{}, {**scores, "unknown": 1}, {**scores, measures[0]: 101}, {**scores, measures[0]: -1}]:
        with pytest.raises(HTTPException) as error:
            admin.save_scores(1, kind, admin.ProfileScores(scores=invalid, revision=1), ("owner", service))
        assert error.value.status_code == 422


@pytest.mark.parametrize("value", [True, 1.5, "50", float("nan")])
def test_scores_reject_non_integers(value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        admin.ProfileScores(scores={"action": value}, revision=1)


def test_generation_requires_login_and_special_access(service):
    client = TestClient(app)
    path = "/api/admin/novels/1/profiles/protagonist/generate"
    assert client.post(path).status_code == 401
    service.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata={})
    app.dependency_overrides[auth.get_current_user] = lambda: ("ordinary", None)
    try:
        assert client.post(path).status_code == 403
        service.table.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_generation_returns_draft_without_saving(service, monkeypatch):
    novel = {"id": 1, "title": "Example", "synopsis": "A story"}
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [novel]
    draft = {"status": "ready", "protagonist_name": "Hero", "scores": dict.fromkeys(MEASURES, 40), "revision": 1}
    generate = MagicMock(return_value=draft)
    monkeypatch.setattr(admin, "generate_protagonist_preview", generate)
    assert admin.generate_scores(1, None, ("owner", service)) == draft
    generate.assert_called_once_with(novel, None)
    service.table.return_value.upsert.assert_not_called()
    service.rpc.assert_not_called()


@pytest.mark.parametrize("status,code", [("skipped", 422), ("failed", 502)])
def test_generation_failure_keeps_existing_scores(service, monkeypatch, status, code):
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": 1}]
    monkeypatch.setattr(admin, "generate_protagonist_preview", lambda novel, protagonist_name=None: {"status": status, "message": "Unable to generate"})
    with pytest.raises(HTTPException) as error:
        admin.generate_scores(1, None, ("owner", service))
    assert error.value.status_code == code
    service.table.return_value.upsert.assert_not_called()


def test_generation_uses_admin_supplied_protagonist_name(service, monkeypatch):
    novel = {"id": 1, "title": "Example"}
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [novel]
    generate = MagicMock(return_value={"status": "ready"})
    monkeypatch.setattr(admin, "generate_protagonist_preview", generate)
    payload = admin.ProfileGenerationRequest(protagonist_name="  Issei Hyoudou  ")
    assert admin.generate_scores(1, payload, ("owner", service))["status"] == "ready"
    generate.assert_called_once_with(novel, "Issei Hyoudou")


def test_generation_missing_novel_does_not_call_gemini(service, monkeypatch):
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    generate = MagicMock()
    monkeypatch.setattr(admin, "generate_protagonist_preview", generate)
    with pytest.raises(HTTPException) as error:
        admin.generate_scores(1, None, ("owner", service))
    assert error.value.status_code == 404
    generate.assert_not_called()
