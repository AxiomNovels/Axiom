"""Browser-measured visits from Cloudflare Web Analytics (RUM), excluding bots.

Visits are referral/direct arrivals, not unique people. Never fall back to HTTP
request or unique-IP counts when browser measurement is unavailable.
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone

import requests

from core.config import (
    CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_ANALYTICS_HOSTS,
    CLOUDFLARE_ANALYTICS_TIMEZONE, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID,
)
from core.countries import COUNTRIES

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
CACHE_TTL_SECONDS = 60
_cache: dict[int, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_resolved_account = None

TRAFFIC_QUERY = """
query WebsiteVisits($accountTag: string, $filter: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject) {
  viewer {
    accounts(filter: {accountTag: $accountTag}) {
      daily: rumPageloadEventsAdaptiveGroups(filter: $filter, limit: 100, orderBy: [date_ASC]) {
        dimensions { date }
        count
        sum { visits }
      }
      countries: rumPageloadEventsAdaptiveGroups(filter: $filter, limit: 300, orderBy: [sum_visits_DESC]) {
        dimensions { countryName }
        count
        sum { visits }
      }
    }
  }
}
"""


class AnalyticsConfigurationError(Exception):
    pass


class AnalyticsUpstreamError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _access_error(operation: str) -> AnalyticsUpstreamError:
    if operation == "zone_lookup":
        return AnalyticsUpstreamError(
            "Cloudflare denied the zone lookup used to find the analytics account. "
            "Set CLOUDFLARE_ACCOUNT_ID explicitly, or grant Zone > Zone > Read on the configured zone.", 503
        )
    return AnalyticsUpstreamError(
        "Cloudflare denied Web Analytics data access for the configured account. "
        "An active token can still be denied analytics access. If Account Analytics: Read is already enabled, "
        "check that the backend uses that exact token, its account resources, and the token owner's "
        "Web Analytics access. Restart/redeploy the backend after changing its token.", 503
    )


def _body(response, *, operation: str = "analytics") -> dict:
    if response.status_code == 401:
        raise AnalyticsUpstreamError(
            "Cloudflare rejected the backend API token. Check CLOUDFLARE_API_TOKEN for an invalid, "
            "expired, or revoked token, then restart/redeploy the backend.", 503
        )
    if response.status_code == 403:
        raise _access_error(operation)
    if response.status_code == 429:
        raise AnalyticsUpstreamError("Cloudflare analytics is rate limited. Retry shortly.", 429)
    if response.status_code >= 400:
        raise AnalyticsUpstreamError("Cloudflare analytics could not be loaded. Retry shortly.")
    try:
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError()
    except ValueError as error:
        raise AnalyticsUpstreamError("Cloudflare returned an invalid analytics response.") from error
    errors = body.get("errors") or []
    # GraphQL authorization failures can arrive with HTTP 200. Classify them
    # internally but never return upstream messages (which may contain IDs).
    if any("not authorized" in str(error.get("message", "")).lower() for error in errors if isinstance(error, dict)):
        raise _access_error(operation)
    if errors or body.get("success") is False:
        raise AnalyticsUpstreamError(
            "Cloudflare could not provide Web Analytics for this range. Check Account Analytics: Read permissions, "
            "Web Analytics setup, and the account's available history."
        )
    return body


def _headers() -> dict:
    return {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Accept": "application/json"}


def _account_id() -> str:
    global _resolved_account
    if CLOUDFLARE_ACCOUNT_ID:
        return CLOUDFLARE_ACCOUNT_ID
    if _resolved_account:
        return _resolved_account
    response = requests.get(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}", headers=_headers(), timeout=8
    )
    body = _body(response, operation="zone_lookup")
    account = ((body.get("result") or {}).get("account") or {}).get("id")
    if not account:
        raise AnalyticsConfigurationError("Set CLOUDFLARE_ACCOUNT_ID to the account containing the Web Analytics site.")
    _resolved_account = account
    return account


def _fetch_rows(start: str, end: str) -> dict[str, list[dict]]:
    try:
        response = requests.post(
            GRAPHQL_URL, headers=_headers(),
            json={"query": TRAFFIC_QUERY, "variables": {
                "accountTag": _account_id(),
                "filter": {"datetime_geq": start, "datetime_lt": end,
                           "requestHost_in": list(CLOUDFLARE_ANALYTICS_HOSTS), "bot": 0},
            }}, timeout=10,
        )
    except requests.RequestException as error:
        raise AnalyticsUpstreamError("Cloudflare Web Analytics is temporarily unavailable. Retry shortly.") from error
    body = _body(response)
    accounts = ((body.get("data") or {}).get("viewer") or {}).get("accounts") or []
    if not accounts:
        raise AnalyticsUpstreamError("Cloudflare Web Analytics is unavailable for this account.", 503)
    account = accounts[0]
    if not isinstance(account.get("daily"), list) or not isinstance(account.get("countries"), list):
        raise AnalyticsUpstreamError("Cloudflare returned incomplete Web Analytics data.")
    return {"daily": account["daily"], "countries": account["countries"]}


def _build_response(days: int, today: date | None = None) -> dict:
    if CLOUDFLARE_ANALYTICS_TIMEZONE.upper() not in {"UTC", "ETC/UTC"}:
        raise AnalyticsConfigurationError("Set CLOUDFLARE_ANALYTICS_TIMEZONE=UTC; Cloudflare daily buckets use UTC.")
    now = datetime.now(timezone.utc)
    end_date = today or now.date()
    start_date = end_date - timedelta(days=days - 1)
    start = f"{start_date.isoformat()}T00:00:00Z"
    end = now.isoformat().replace("+00:00", "Z") if today is None else f"{(end_date + timedelta(days=1)).isoformat()}T00:00:00Z"
    source = _fetch_rows(start, end)
    names = {country["code"]: country["name"] for country in COUNTRIES}
    countries = []
    for row in source["countries"]:
        code = str((row.get("dimensions") or {}).get("countryName") or "XX").upper()
        countries.append({"code": code, "name": names.get(code, "Unknown country" if code == "XX" else code),
                          "visits": int(row["sum"]["visits"]), "page_views": int(row["count"])})
    countries.sort(key=lambda country: (-country["visits"], country["name"].casefold()))
    by_date = {row["dimensions"]["date"]: {
        "date": row["dimensions"]["date"], "visits": int(row["sum"]["visits"]), "page_views": int(row["count"]),
    } for row in source["daily"]}
    daily = []
    if by_date:
        for offset in range(days):
            key = (start_date + timedelta(days=offset)).isoformat()
            row = by_date.get(key, {"date": key, "visits": 0, "page_views": 0})
            previous = daily[-1]["visits"] if daily else None
            row["percentage_change"] = round((row["visits"] - previous) / previous * 100, 1) if previous else None
            row["provisional"] = key >= (end_date - timedelta(days=1)).isoformat()
            daily.append(row)
    return {
        "status": "ok" if daily or countries else "empty", "source": "cloudflare_web_analytics",
        "timezone": "UTC", "days": days, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "as_of": end, "daily": daily, "countries": countries,
        "summary": {"visits": sum(row["visits"] for row in daily), "page_views": sum(row["page_views"] for row in daily),
                    "today": by_date.get(end_date.isoformat())},
    }


def daily_traffic(days: int) -> dict:
    if not CLOUDFLARE_API_TOKEN or not (CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_ZONE_ID) or not CLOUDFLARE_ANALYTICS_HOSTS:
        return {"status": "unconfigured", "message":
                "Enable Cloudflare Web Analytics for the website, then configure CLOUDFLARE_API_TOKEN, "
                "CLOUDFLARE_ACCOUNT_ID (or CLOUDFLARE_ZONE_ID), and CLOUDFLARE_ANALYTICS_HOSTS on the backend."}
    with _cache_lock:
        cached = _cache.get(days)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        result = _build_response(days)
        _cache[days] = (time.monotonic() + CACHE_TTL_SECONDS, result)
        return result
