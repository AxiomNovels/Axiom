"""Exercise real SDK requests against a fake transport, never Supabase."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import httpx

from core import database
from routes import users


def test_pooled_connections_keep_tokens_cookies_and_sessions_isolated(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[], headers={"set-cookie": "private=one; Path=/"})

    monkeypatch.setattr(database, "_transport", httpx.MockTransport(respond))
    monkeypatch.setattr(database, "_proxy_transports", {})
    first = database.create_authenticated_client("first-token")
    second = database.create_authenticated_client("second-token")
    public = database.create_public_client()
    service = database.create_service_client()
    clients = [first, second, public, service]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda c: c.table("profiles").select("id").execute(), clients))
    assert {r.headers["authorization"] for r in requests} == {
        "Bearer first-token", "Bearer second-token",
        "Bearer test-publishable-key", "Bearer test-secret-key",
    }
    assert all("cookie" not in r.headers for r in requests)
    assert first.auth._storage is not second.auth._storage
    first.auth._storage.set_item("isolation-test", "private")
    assert second.auth._storage.get_item("isolation-test") is None
    first.options.httpx_client.close()
    second.table("profiles").select("id").execute()
    assert requests[-1].headers["authorization"] == "Bearer second-token"


def test_pool_preserves_proxy_routing_and_bypass(monkeypatch):
    direct, proxy = Mock(), Mock()
    monkeypatch.setattr(database, "_transport", direct)
    monkeypatch.setattr(database, "_proxy_transports", {"https": proxy})
    monkeypatch.setattr(database, "proxy_bypass", lambda host: host == "internal.example")
    transport = database._BorrowedTransport()
    external = httpx.Request("GET", "https://external.example")
    internal = httpx.Request("GET", "https://internal.example")
    transport.handle_request(external)
    transport.handle_request(internal)
    proxy.handle_request.assert_called_once_with(external)
    direct.handle_request.assert_called_once_with(internal)


def test_badges_use_one_batch_and_fail_closed():
    client = Mock()
    client.rpc.return_value.execute.return_value.data = [{"id": "a"}]
    assert users._special_account_ids(client, ["a", "b"]) == {"a"}
    client.rpc.assert_called_once_with("reader_special_badges", {"user_ids": ["a", "b"]})
    client.auth.admin.get_user_by_id.assert_not_called()
    client.rpc.side_effect = RuntimeError("unavailable")
    assert users._special_account_ids(client, ["a"]) == set()


def test_badges_preserve_rolling_deployment_fallback():
    from postgrest.exceptions import APIError
    client = Mock()
    client.rpc.side_effect = APIError({"code": "PGRST202", "message": "missing", "details": "", "hint": ""})
    client.auth.admin.get_user_by_id.return_value.user.app_metadata = {"axiom_special": True}
    assert users._special_account_ids(client, ["a"]) == {"a"}
