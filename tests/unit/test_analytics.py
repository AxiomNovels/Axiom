from datetime import date, datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from core.auth import get_optional_current_user
from routes.admin import require_special
from services import analytics_service as service


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(service, "ENABLED", True)
    monkeypatch.setattr(service, "EDGE_SECRET", "test-edge-secret")
    service._limits.clear()
    app.dependency_overrides[get_optional_current_user] = lambda: (None, None)
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def payload(**kwargs):
    return {"id": str(uuid4()), "session_id": str(uuid4()), "event": "page_view", "path": "/novel.html", **kwargs}


def test_public_config_shares_only_collection_flag(client, monkeypatch):
    response = client.get("/api/analytics/config")
    assert response.status_code == 200
    assert response.json() == {"enabled": True}
    assert response.headers["cache-control"] == "no-store"
    monkeypatch.setattr(service, "ENABLED", False)
    assert client.get("/api/analytics/config").json() == {"enabled": False}


def test_browser_cannot_choose_identity_or_location(client):
    for field in ("user_id", "country", "ip", "source"):
        assert client.post("/api/analytics/events", json=payload(**{field: "spoofed"})).status_code == 422


def test_forged_country_headers_ignored(client, monkeypatch):
    submit = MagicMock(return_value=True)
    monkeypatch.setattr(service, "submit", submit)
    response = client.post("/api/analytics/events", json=payload(), headers={"X-Axiom-Country": "CA", "X-Axiom-Edge-Secret": "wrong"})
    assert response.status_code == 202
    assert submit.call_args.args[0]["country"] == "XX"
    assert submit.call_args.args[0]["user_id"] is None


def test_verified_edge_location_and_backend_identity(client, monkeypatch):
    submit = MagicMock(return_value=True)
    monkeypatch.setattr(service, "submit", submit)
    app.dependency_overrides[get_optional_current_user] = lambda: ("verified-user", None)
    response = client.post("/api/analytics/events", json=payload(), headers={"X-Axiom-Country": "CA", "X-Axiom-Edge-Secret": "test-edge-secret"})
    assert response.status_code == 202
    assert submit.call_args.args[0]["country"] == "CA"
    assert submit.call_args.args[0]["user_id"] == "verified-user"


@pytest.mark.parametrize("event", [payload(path="/profile.html?token=secret"), payload(active_seconds=31), payload(active_seconds=True), payload(event="signup")])
def test_invalid_events_rejected(client, event):
    assert client.post("/api/analytics/events", json=event).status_code == 422


def test_body_size_and_cross_site_protection(client):
    assert client.post("/api/analytics/events", content=b"x"*5000).status_code == 413
    assert client.post("/api/analytics/events", json=payload(), headers={"Origin": "https://attacker.invalid"}).status_code == 403


def test_collection_rate_limit(client, monkeypatch):
    monkeypatch.setattr(service, "submit", lambda record: True)
    for _ in range(120):
        assert client.post("/api/analytics/events", json=payload()).status_code == 202
    assert client.post("/api/analytics/events", json=payload()).status_code == 429


def test_edge_intake_requires_secret(client, monkeypatch):
    monkeypatch.setattr(service, "submit", lambda record: True)
    event = {"path": "/", "country": "CA", "kind": "page", "status": 200, "ip": "192.0.2.1"}
    assert client.post("/api/analytics/edge", json=event).status_code == 403
    assert client.post("/api/analytics/edge", json=event, headers={"X-Axiom-Edge-Secret": "test-edge-secret"}).status_code == 202


def test_reports_exports_and_ip_logs_require_authentication(client):
    for path in ("/admin/analytics?start=2026-01-01&end=2026-01-02", "/admin/analytics/export?start=2026-01-01&end=2026-01-02", "/admin/analytics/ip-logs"):
        response = client.get("/api"+path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"


def test_report_aggregates_and_export(client):
    db = MagicMock()
    today = datetime.now(timezone.utc).date().isoformat()
    db.rpc.return_value.execute.return_value.data = {"daily": [{"date": today, "page_views": 5, "visits": 2, "active_seconds": 60}]}
    app.dependency_overrides[require_special] = lambda: ("admin", db)
    response = client.get(f"/api/admin/analytics?start={today}&end={today}&country=CA")
    assert response.status_code == 200
    db.rpc.assert_called_with("analytics_report", {"p_start": today, "p_end": today, "p_country": "CA"})
    response = client.get(f"/api/admin/analytics/export?start={today}&end={today}")
    assert response.status_code == 200
    assert "ip" not in response.text and "user_id" not in response.text
    assert "page_views" in response.text
    assert client.get("/api/admin/analytics?start=2026-01-01&end=2026-12-31").status_code == 422


def test_api_count_uses_route_templates_and_ignores_forged_location(client, monkeypatch):
    submit = MagicMock(return_value=True)
    monkeypatch.setattr(service, "submit", submit)
    client.get("/api/admin/me", headers={"X-Axiom-Country": "CA"})
    record = submit.call_args.args[0]
    assert record["source"] == "backend" and "country" not in record
    submit.reset_mock()
    client.get("/api/admin/me", headers={"X-Axiom-Country": "CA", "X-Axiom-Edge-Secret": "test-edge-secret"})
    assert submit.call_args.args[0]["country"] == "CA"


def test_path_sanitization_and_disabled_collection(monkeypatch):
    assert service.clean_path("/novel.html?token=secret#anything") == "/novel.html"
    assert service.clean_path("/popular.html?page=2&seed=random") == "/popular.html"
    assert service.clean_path("/api/users/private-user-id") == "/api/other"
    assert service.clean_path("/api/novels/{novel_id}") == "/api/novels/{novel_id}"
    assert service.clean_path("/assets/private-cover.png") == "/assets/*"
    assert service.clean_path("/some-private-name") == "/other"
    monkeypatch.setattr(service, "ENABLED", False)
    assert service.submit({}) is False


def test_ip_logging_disabled_drops_addresses(monkeypatch):
    import queue
    test_queue = queue.Queue()
    monkeypatch.setattr(service, "pending", test_queue)
    monkeypatch.setattr(service, "_started", True)
    monkeypatch.setattr(service, "ENABLED", True)
    monkeypatch.setattr(service, "LOG_IPS", False)
    service.submit({"event": "request", "path": "/", "source": "frontend", "ip": "192.0.2.1"})
    assert "ip" not in test_queue.get_nowait()
