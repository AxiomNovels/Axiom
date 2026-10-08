"""Country catalog shared by API validation and the generated browser asset."""
import unicodedata

import pycountry


def country_key(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.strip().casefold())
        if not unicodedata.combining(char)
    )


# Familiar labels, while retaining ISO names as searchable aliases.
DISPLAY_NAMES = {
    "BO": "Bolivia", "BN": "Brunei", "CD": "Democratic Republic of the Congo",
    "CG": "Republic of the Congo", "IR": "Iran", "KP": "North Korea",
    "KR": "South Korea", "LA": "Laos", "MD": "Moldova", "PS": "Palestine",
    "RU": "Russia", "SY": "Syria", "TW": "Taiwan", "TZ": "Tanzania",
    "TR": "Turkey", "VA": "Vatican City", "VE": "Venezuela", "VN": "Vietnam",
}
EXTRA_ALIASES = {"US": ["USA", "U.S.", "U.S.A.", "America"], "GB": ["UK", "U.K.", "Great Britain"]}

COUNTRIES = []
for country in pycountry.countries:
    fields = dict(country)
    name = DISPLAY_NAMES.get(country.alpha_2, fields.get("common_name", country.name))
    aliases = sorted(set(
        [country.alpha_2, country.alpha_3, country.name, name]
        + [fields[key] for key in ("common_name", "official_name") if key in fields]
        + EXTRA_ALIASES.get(country.alpha_2, [])
    ))
    COUNTRIES.append({"code": country.alpha_2, "name": name, "aliases": aliases})
COUNTRIES.sort(key=lambda country: country_key(country["name"]))
COUNTRY_NAMES = {
    country_key(alias): country["name"]
    for country in COUNTRIES for alias in country["aliases"]
}


def normalize_country(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    name = COUNTRY_NAMES.get(country_key(value))
    if name is None:
        raise ValueError("Please choose a country from the list or leave it blank.")
    return name
