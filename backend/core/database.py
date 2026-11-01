import atexit
import os
from urllib.request import getproxies, proxy_bypass

import httpx
from supabase import create_client, ClientOptions

from core.config import SUPABASE_KEY, SUPABASE_URL


# Only the transport (TLS context and connection pool) is shared. Headers,
# cookies, auth storage and sessions belong to each individual client.
_transport = httpx.HTTPTransport(http2=True)
atexit.register(_transport.close)
# Preserve outbound HTTP(S)_PROXY / ALL_PROXY and NO_PROXY configuration.
_proxy_transports = {
    scheme: httpx.HTTPTransport(proxy=url, http2=True)
    for scheme, url in getproxies().items()
    if scheme in {"http", "https", "all"}
}
for _proxy_transport in _proxy_transports.values():
    atexit.register(_proxy_transport.close)


class _BorrowedTransport(httpx.BaseTransport):
    def handle_request(self, request):
        transport = _transport
        if _proxy_transports and not proxy_bypass(request.url.host):
            transport = _proxy_transports.get(
                request.url.scheme, _proxy_transports.get("all", _transport)
            )
        return transport.handle_request(request)

    def close(self):
        # Closing a short-lived SDK client must not close other users' pool.
        pass


def _create_client(key):
    http_client = httpx.Client(
        transport=_BorrowedTransport(), follow_redirects=True, timeout=120,
    )
    return create_client(SUPABASE_URL, key, options=ClientOptions(
        httpx_client=http_client, auto_refresh_token=False,
    ))


supabase = _create_client(SUPABASE_KEY)


def create_public_client():
    """Create an isolated client for public auth operations.

    Auth refreshes update the client's in-memory session, so they must never
    share the application-wide client across concurrent users.
    """
    return _create_client(SUPABASE_KEY)


def create_authenticated_client(access_token: str):
    """Create an isolated PostgREST client whose requests satisfy user RLS."""
    client = _create_client(SUPABASE_KEY)
    client.options.headers["Authorization"] = f"Bearer {access_token}"
    return client


def create_service_client():
    """Create a Supabase client authorized with the service-role secret key.

    Used for privileged writes (e.g. publishing a novel a user has
    submitted) that should not depend on end-user RLS policies. Mirrors
    the secret-key clients already used by scraper/staging.py,
    scraper/publish.py, and profiler/profile_novel.py.
    """
    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Missing SUPABASE_SECRET_KEY in backend/.env")
    return _create_client(secret_key)
