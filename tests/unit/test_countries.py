"""Country selections are validated independently of external services."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.countries import COUNTRIES, country_key
from models.profile import ProfileUpdate


@pytest.mark.parametrize("value, expected", [
    ("  Canada  ", "Canada"), ("us", "United States"), ("USA", "United States"),
    ("UK", "United Kingdom"), ("Korea, Republic of", "South Korea"),
    ("", None), ("  ", None), (None, None),
])
def test_profile_country_normalization(value, expected):
    assert ProfileUpdate(gender="Prefer not to say", country=value).country == expected


@pytest.mark.parametrize("value", ["Atlantis", "Canada<script>", "United"])
def test_profile_rejects_arbitrary_country(value):
    with pytest.raises(ValidationError, match="choose a country"):
        ProfileUpdate(gender="Prefer not to say", country=value)


def test_catalog_is_complete_sorted_and_matches_browser():
    assert len(COUNTRIES) == 249
    assert len({country["code"] for country in COUNTRIES}) == 249
    names = [country_key(country["name"]) for country in COUNTRIES]
    assert names == sorted(names)
    for country in COUNTRIES:
        assert ProfileUpdate(gender="Prefer not to say", country=country["name"]).country == country["name"]
    asset = Path(__file__).resolve().parents[2] / "frontend/public/country-data.js"
    data = asset.read_text(encoding="utf-8").split("const COUNTRY_OPTIONS = ", 1)[1].strip().removesuffix(";")
    assert json.loads(data) == COUNTRIES
