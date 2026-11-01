from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.auth import get_current_user
from main import app
import routes.auth as auth_routes


@pytest.fixture
def recovery(monkeypatch):
    provider = MagicMock()
    monkeypatch.setattr(auth_routes, "create_public_client", lambda: provider)
    monkeypatch.setattr(auth_routes, "FRONTEND_ORIGINS", ("https://axiomnovels.com", "http://localhost:3000"))
    with TestClient(app) as client:
        yield client, provider
    app.dependency_overrides.pop(get_current_user, None)


def test_request_sends_recovery_to_allowed_frontend(recovery):
    client, provider = recovery
    response = client.post("/api/password/forgot", json={"email": "reader@example.com"}, headers={"origin": "http://localhost:3000"})
    assert response.status_code == 200
    provider.auth.reset_password_for_email.assert_called_once_with(
        "reader@example.com", {"redirect_to": "http://localhost:3000/reset-password.html"}
    )


def test_request_cannot_override_callback_or_disclose_missing_account(recovery):
    client, provider = recovery
    success = client.post("/api/password/forgot", json={"email": "reader@example.com"})
    error = RuntimeError("No such user")
    error.code = "user_not_found"
    provider.auth.reset_password_for_email.side_effect = error
    missing = client.post("/api/password/forgot", json={"email": "missing@example.com"}, headers={"origin": "https://evil.example"})
    assert missing.status_code == 200
    assert missing.json() == success.json()
    assert provider.auth.reset_password_for_email.call_args.args[1] == {"redirect_to": "https://axiomnovels.com/reset-password.html"}


def test_request_reports_delivery_failure(recovery):
    client, provider = recovery
    provider.auth.reset_password_for_email.side_effect = RuntimeError("SMTP unavailable")
    assert client.post("/api/password/forgot", json={"email": "reader@example.com"}).status_code == 503


def test_request_validates_email_and_reports_rate_limit(recovery):
    client, provider = recovery
    assert client.post("/api/password/forgot", json={"email": "invalid"}).status_code == 422
    provider.auth.reset_password_for_email.assert_not_called()
    error = RuntimeError("rate limited")
    error.status = 429
    provider.auth.reset_password_for_email.side_effect = error
    assert client.post("/api/password/forgot", json={"email": "reader@example.com"}).status_code == 429


def test_reset_requires_authentication(recovery):
    client, provider = recovery
    response = client.post("/api/password/reset", json={"password": "new-password", "refresh_token": "refresh"})
    assert response.status_code == 401
    provider.auth.update_user.assert_not_called()


def test_reset_preserves_banned_account_check(recovery, monkeypatch):
    import core.auth as shared_auth

    client, provider = recovery
    monkeypatch.setattr(shared_auth.supabase.auth, "get_user", lambda token: SimpleNamespace(
        user=SimpleNamespace(id="reader-id", app_metadata={"axiom_banned": True})
    ))
    response = client.post("/api/password/reset", json={"password": "new-password", "refresh_token": "refresh"}, headers={"authorization": "Bearer recovery-token"})
    assert response.status_code == 403
    provider.auth.update_user.assert_not_called()


def test_reset_updates_only_authenticated_user(recovery):
    client, provider = recovery
    app.dependency_overrides[get_current_user] = lambda: ("reader-id", MagicMock())
    provider.auth.set_session.return_value = SimpleNamespace(user=SimpleNamespace(id="reader-id"))
    response = client.post("/api/password/reset", json={"password": "new-password", "refresh_token": "refresh"}, headers={"authorization": "Bearer recovery-token"})
    assert response.status_code == 200
    provider.auth.set_session.assert_called_once_with("recovery-token", "refresh")
    provider.auth.update_user.assert_called_once_with({"password": "new-password"})


def test_reset_rejects_invalid_session_and_short_password(recovery):
    client, provider = recovery
    app.dependency_overrides[get_current_user] = lambda: ("reader-id", MagicMock())
    provider.auth.set_session.return_value = SimpleNamespace(user=SimpleNamespace(id="different-user"))
    headers = {"authorization": "Bearer recovery-token"}
    assert client.post("/api/password/reset", json={"password": "new-password", "refresh_token": "refresh"}, headers=headers).status_code == 401
    assert client.post("/api/password/reset", json={"password": "short", "refresh_token": "refresh"}, headers=headers).status_code == 422
    provider.auth.update_user.assert_not_called()
