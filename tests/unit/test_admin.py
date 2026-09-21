from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from core import auth
from routes import admin


@pytest.fixture
def service(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(admin, "create_service_client", lambda: client)
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
    table, measures = admin.PROFILES[kind]
    service.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": 1}]
    scores = dict.fromkeys(measures, 50)
    payload = admin.ProfileScores(scores=scores, protagonist_name="Hero" if kind == "protagonist" else None)
    assert admin.save_scores(1, kind, payload, ("owner", service)) == {"saved": True}
    service.table.assert_any_call(table)
    saved = service.table.return_value.upsert.call_args.args[0]
    assert saved["novel_id"] == 1
    assert all(saved[key] == 50 for key in measures)
    for invalid in [{}, {**scores, "unknown": 1}, {**scores, measures[0]: 101}, {**scores, measures[0]: -1}]:
        with pytest.raises(HTTPException) as error:
            admin.save_scores(1, kind, admin.ProfileScores(scores=invalid), ("owner", service))
        assert error.value.status_code == 422


@pytest.mark.parametrize("value", [True, 1.5, "50", float("nan")])
def test_scores_reject_non_integers(value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        admin.ProfileScores(scores={"action": value})
