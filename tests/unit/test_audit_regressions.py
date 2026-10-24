"""Security and reliability regressions; every service is replaced locally."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from core.source_http import source_get, source_url
from models.auth import LoginRequest, SignupRequest, RefreshSessionRequest
from routes import auth, search, novels, users, admin
from scraper import wattpad, webnovel


@pytest.mark.parametrize("value", [
    "http://127.0.0.1/?webnovel.com", "https://webnovel.com.attacker.test/book/1",
    "https://user:secret@www.webnovel.com/book/1", "https://webnovel.com:8443/book/1",
    "file:///webnovel.com/book/1", "https://webnovel.com\\@127.0.0.1/book/1",
])
def test_upload_rejects_untrusted_webnovel_urls_before_network(value, monkeypatch):
    get = Mock(side_effect=AssertionError("Network must not be reached"))
    monkeypatch.setattr(webnovel.requests, "get", get)
    with pytest.raises(ValueError):
        webnovel.scrape_webnovel(value, include_statistics=False)
    get.assert_not_called()


def test_wattpad_rejects_internal_target(monkeypatch):
    get = Mock()
    monkeypatch.setattr(wattpad.httpx, "get", get)
    with pytest.raises(ValueError):
        wattpad.scrape_wattpad("http://127.0.0.1/story/123")
    get.assert_not_called()


@pytest.mark.parametrize("domain", ["wattpad.com", "royalroad.com", "webnovel.com"])
def test_redirect_checks_destination_before_request(domain):
    get = Mock(return_value=SimpleNamespace(status_code=302, headers={"Location": "http://127.0.0.1/private"}))
    with pytest.raises(ValueError):
        source_get(get, f"https://www.{domain}/story/1", domain)
    assert get.call_count == 1
    assert get.call_args.kwargs["allow_redirects"] is False


def test_relative_redirect_and_bounded_loop():
    ok = SimpleNamespace(status_code=200, headers={})
    get = Mock(side_effect=[SimpleNamespace(status_code=302, headers={"Location": "/book/2"}), ok])
    assert source_get(get, "https://webnovel.com/book/1", "webnovel.com") is ok
    assert get.call_args.args[0] == "https://webnovel.com/book/2"
    get = Mock(return_value=SimpleNamespace(status_code=302, headers={"Location": "/loop"}))
    with pytest.raises(ValueError, match="too many"):
        source_get(get, "https://webnovel.com/book/1", "webnovel.com")
    assert get.call_count == 6


def test_auth_operations_use_isolated_clients(monkeypatch):
    shared, isolated, service = Mock(), Mock(), Mock()
    response = SimpleNamespace(user=None, session=None)
    isolated.auth.sign_up.return_value = response
    isolated.auth.sign_in_with_password.return_value = response
    monkeypatch.setattr(auth, "supabase", shared)
    monkeypatch.setattr(auth, "create_public_client", lambda: isolated)
    monkeypatch.setattr(auth, "find_profile_id_by_username", lambda _: None)
    auth.signup(SignupRequest(email="a@example.com", username="reader", password="password"))
    auth.login(LoginRequest(identifier="a@example.com", password="password"))
    shared.auth.sign_up.assert_not_called()
    shared.auth.sign_in_with_password.assert_not_called()
    isolated.auth.sign_up.assert_called_once()
    isolated.auth.sign_in_with_password.assert_called_once()


def test_failed_signup_profile_write_never_deletes_an_account(monkeypatch):
    isolated, service = Mock(), Mock()
    isolated.auth.sign_up.return_value = SimpleNamespace(user=SimpleNamespace(id="existing"), session=None)
    service.table.return_value.insert.return_value.execute.side_effect = RuntimeError("Database unavailable")
    monkeypatch.setattr(auth, "create_public_client", lambda: isolated)
    monkeypatch.setattr(auth, "create_service_client", lambda: service)
    monkeypatch.setattr(auth, "find_profile_id_by_username", lambda _: None)
    with pytest.raises(HTTPException) as caught:
        auth.signup(SignupRequest(email="a@example.com", username="reader", password="password"))
    assert caught.value.status_code == 503
    service.auth.admin.delete_user.assert_not_called()


def test_username_wildcards_are_literal(monkeypatch):
    client = Mock()
    client.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value.data = []
    monkeypatch.setattr(auth, "supabase", client)
    auth.find_profile_id_by_username("reader_one%")
    client.table.return_value.select.return_value.ilike.assert_called_once_with("username", r"reader\_one\%")


@pytest.mark.parametrize("status,expected", [(400, 401), (401, 401), (429, 503), (500, 503), (None, 503)])
def test_refresh_separates_invalid_tokens_from_outages(monkeypatch, status, expected):
    error = RuntimeError("provider message")
    error.status = status
    client = Mock()
    client.auth.refresh_session.side_effect = error
    monkeypatch.setattr(auth, "create_public_client", lambda: client)
    with pytest.raises(HTTPException) as caught:
        auth.refresh_session(RefreshSessionRequest(refresh_token="test"))
    assert caught.value.status_code == expected
    assert "provider message" not in caught.value.detail


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.orders = []
        self.start, self.end = 0, 999
    def select(self, *args, **kwargs): return self
    def order(self, column):
        self.orders.append(column)
        return self
    def range(self, start, end):
        self.start, self.end = start, end
        return self
    def limit(self, count): return self.range(0, count - 1)
    def execute(self):
        rows = list(self.rows)
        for key in reversed(self.orders):
            rows.sort(key=lambda row: row[key])
        return SimpleNamespace(data=rows[self.start:self.end + 1], count=len(rows))


def test_catalogue_and_options_include_rows_after_server_cap(monkeypatch):
    rows = [{"id": i, "title": f"Novel {i:04}", "tags": [f"Tag {i}"], "genres": [], "status": "ongoing"} for i in range(1101)]
    client = SimpleNamespace(table=lambda _: Query(rows))
    monkeypatch.setattr(search, "supabase", client)
    monkeypatch.setattr(search, "load_definition", lambda: {"traits": []})
    monkeypatch.setattr(search, "measures_for", lambda _: [])
    monkeypatch.setattr(novels, "supabase", client)
    assert len(search._fetch_catalogue()) == 1101
    assert "Tag 1100" in search.search_options()["tags"]
    assert len(novels.list_novels()) == 1101


def test_private_presence_never_changes_directory_order(monkeypatch):
    rows = [{"id": str(i), "username": f"Reader {i:03}", "online_status_visibility": "private"} for i in range(105)]
    rows[-1]["online_status_visibility"] = "public"
    monkeypatch.setattr(users, "create_service_client", lambda: SimpleNamespace(table=lambda _: Query(rows)))
    monkeypatch.setattr(users, "_online_user_ids", lambda *_: {"104"})
    monkeypatch.setattr(users, "_presence_by_user_id", lambda *_: {"104": "2026-01-01", "1": "2026-10-01"})
    monkeypatch.setattr(users, "_is_special_account", lambda *_: False)
    result = users.list_public_users(sort="last_online", limit=3)["users"]
    assert [row["id"] for row in result] == ["104", "0", "1"]
    assert result[1]["online"] is False


def test_admin_sorts_real_auth_datetimes_and_missing_signins(monkeypatch):
    client = SimpleNamespace(table=lambda _: Query([{"id": "a", "username": "A"}, {"id": "b", "username": "B"}]), auth=SimpleNamespace(admin=SimpleNamespace(
        get_user_by_id=lambda identity: SimpleNamespace(user=SimpleNamespace(app_metadata={}, last_sign_in_at=datetime(2026, 1, 1, tzinfo=timezone.utc) if identity == "b" else None)))))
    assert [r["id"] for r in admin.users(q="", page=1, sort="last_online", admin=("owner", client))["users"]] == ["b", "a"]


def test_rebuild_worker_losing_claim_does_not_generate(monkeypatch):
    from services import protagonist_rebuild_service as rebuilds
    client = Mock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"status": "queued"}]
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    generate = Mock()
    monkeypatch.setattr(rebuilds, 'create_service_client', lambda: client)
    monkeypatch.setattr(rebuilds, 'regenerate', generate)
    rebuilds.run_job('job')
    generate.assert_not_called()


def test_profile_patch_preserves_omitted_private_fields():
    from routes.profile import update_my_profile
    from models.profile import ProfileUpdate
    client = Mock()
    client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "reader"}]
    update_my_profile(ProfileUpdate(gender="Prefer not to say", city="Toronto"), ("reader", client))
    client.table.return_value.update.assert_called_once_with({"gender": "Prefer not to say", "city": "Toronto"})


def test_unread_count_uses_database_count_beyond_row_cap():
    from routes.inbox import get_unread_count
    client = Mock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = SimpleNamespace(count=1500, data=[])
    assert get_unread_count(("reader", client)) == {"unread_count": 1500}
    client.table.return_value.select.assert_called_once_with("id", count="exact", head=True)
