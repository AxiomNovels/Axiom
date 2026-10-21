from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from services import cloudflare_analytics as analytics


@pytest.fixture(autouse=True)
def analytics_config(monkeypatch):
    analytics._cache.clear()
    monkeypatch.setattr(analytics, "CLOUDFLARE_API_TOKEN", "secret-server-only")
    monkeypatch.setattr(analytics, "CLOUDFLARE_ACCOUNT_ID", "account-id")
    monkeypatch.setattr(analytics, "CLOUDFLARE_ZONE_ID", None)
    monkeypatch.setattr(analytics, "CLOUDFLARE_ANALYTICS_TIMEZONE", "UTC")
    monkeypatch.setattr(analytics, "CLOUDFLARE_ANALYTICS_HOSTS", ("axiomnovels.com", "www.axiomnovels.com"))
    monkeypatch.setattr(analytics, "_resolved_account", None)
    yield
    analytics._cache.clear()


def response_for(daily=None, countries=None):
    return SimpleNamespace(status_code=200, json=lambda: {
        "data": {"viewer": {"accounts": [{"daily": daily or [], "countries": countries or []}]}}, "errors": None,
    })


def test_unconfigured_analytics_is_explicit(monkeypatch):
    monkeypatch.setattr(analytics, "CLOUDFLARE_API_TOKEN", None)
    assert analytics.daily_traffic(7)["status"] == "unconfigured"


def test_browser_visits_and_countries_use_identical_bot_and_host_filters(monkeypatch):
    post = MagicMock(return_value=response_for(
        daily=[{"dimensions": {"date": "2026-10-17"}, "sum": {"visits": 4}, "count": 10},
               {"dimensions": {"date": "2026-10-19"}, "sum": {"visits": 7}, "count": 12}],
        countries=[{"dimensions": {"countryName": "US"}, "sum": {"visits": 9}, "count": 19},
                   {"dimensions": {"countryName": "XX"}, "sum": {"visits": 2}, "count": 3}],
    ))
    monkeypatch.setattr(analytics.requests, "post", post)
    result = analytics._build_response(3, date(2026, 10, 19))
    assert [(row["date"], row["visits"], row["page_views"]) for row in result["daily"]] == [
        ("2026-10-17", 4, 10), ("2026-10-18", 0, 0), ("2026-10-19", 7, 12),
    ]
    assert result["source"] == "cloudflare_web_analytics"
    assert result["summary"]["visits"] == sum(c["visits"] for c in result["countries"]) == 11
    assert result["summary"]["page_views"] == sum(c["page_views"] for c in result["countries"]) == 22
    assert result["summary"]["today"]["visits"] == 7
    assert result["daily"][1]["percentage_change"] == -100
    assert result["daily"][2]["percentage_change"] is None
    assert result["countries"][1]["name"] == "Unknown country"
    payload = post.call_args.kwargs["json"]
    assert payload["variables"]["filter"] == {
        "datetime_geq": "2026-10-17T00:00:00Z", "datetime_lt": "2026-10-20T00:00:00Z",
        "requestHost_in": ["axiomnovels.com", "www.axiomnovels.com"], "bot": 0,
    }
    assert payload["query"].count("filter: $filter") == 2
    assert "httpRequests" not in payload["query"]
    assert "secret-server-only" not in str(result) and "account-id" not in str(result)


def test_empty_browser_data_does_not_fall_back_to_zone_requests(monkeypatch):
    post = MagicMock(return_value=response_for())
    monkeypatch.setattr(analytics.requests, "post", post)
    result = analytics.daily_traffic(7)
    assert result["status"] == "empty" and result["daily"] == [] and result["countries"] == []
    assert result["summary"]["today"] is None
    analytics.daily_traffic(7)
    post.assert_called_once()


@pytest.mark.parametrize("status, expected", [(403, 503), (401, 503), (429, 429), (500, 502)])
def test_upstream_errors_are_sanitized(monkeypatch, status, expected):
    monkeypatch.setattr(analytics.requests, "post", lambda *args, **kwargs: SimpleNamespace(status_code=status, text="token=secret"))
    with pytest.raises(analytics.AnalyticsUpstreamError) as error:
        analytics.daily_traffic(7)
    assert error.value.status_code == expected
    assert "secret" not in str(error.value)


def test_graphql_permission_error_does_not_return_empty_traffic(monkeypatch):
    response = SimpleNamespace(status_code=200, json=lambda: {"errors": [{"message": "not authorized for account secret-account"}]})
    monkeypatch.setattr(analytics.requests, "post", lambda *args, **kwargs: response)
    with pytest.raises(analytics.AnalyticsUpstreamError) as error:
        analytics.daily_traffic(7)
    assert error.value.status_code == 503
    assert "An active token can still be denied" in str(error.value)
    assert "exact token" in str(error.value)
    assert "secret-account" not in str(error.value)
    assert analytics._cache == {}


def test_invalid_token_is_not_reported_as_missing_analytics_permission(monkeypatch):
    monkeypatch.setattr(analytics.requests, "post", lambda *args, **kwargs: SimpleNamespace(status_code=401))
    with pytest.raises(analytics.AnalyticsUpstreamError, match="invalid, expired, or revoked"):
        analytics.daily_traffic(7)


def test_zone_lookup_denial_explains_zone_permission_or_explicit_account(monkeypatch):
    monkeypatch.setattr(analytics, "CLOUDFLARE_ACCOUNT_ID", None)
    monkeypatch.setattr(analytics, "CLOUDFLARE_ZONE_ID", "configured-zone")
    monkeypatch.setattr(analytics.requests, "get", lambda *args, **kwargs: SimpleNamespace(status_code=403))
    post = MagicMock()
    monkeypatch.setattr(analytics.requests, "post", post)
    with pytest.raises(analytics.AnalyticsUpstreamError) as error:
        analytics.daily_traffic(7)
    assert error.value.status_code == 503
    assert "CLOUDFLARE_ACCOUNT_ID" in str(error.value)
    assert "Zone > Zone > Read" in str(error.value)
    assert "Account Analytics: Read" not in str(error.value)
    post.assert_not_called()


def test_explicit_account_does_not_need_zone_lookup_permission(monkeypatch):
    get = MagicMock(side_effect=AssertionError("Zone lookup must not be called"))
    monkeypatch.setattr(analytics.requests, "get", get)
    monkeypatch.setattr(analytics.requests, "post", lambda *args, **kwargs: response_for())
    assert analytics.daily_traffic(7)["status"] == "empty"
    get.assert_not_called()


def test_timeout_is_retryable_and_not_cached(monkeypatch):
    post = MagicMock(side_effect=requests.Timeout("secret"))
    monkeypatch.setattr(analytics.requests, "post", post)
    with pytest.raises(analytics.AnalyticsUpstreamError, match="temporarily unavailable"):
        analytics.daily_traffic(7)
    assert analytics._cache == {}


def test_daily_buckets_cannot_be_mislabeled_as_another_timezone(monkeypatch):
    monkeypatch.setattr(analytics, "CLOUDFLARE_ANALYTICS_TIMEZONE", "America/Toronto")
    with pytest.raises(analytics.AnalyticsConfigurationError, match="UTC"):
        analytics.daily_traffic(7)
