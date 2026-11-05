"""Nonfiction aliases stay merged through scraping, staging, and searches."""
import copy

import pytest

from core.genres import canonicalize_genres
from scraper import royalroad, wattpad, webnovel
from scraper.genres import IN_HOUSE_GENRES
from scraper.transform import transform_staged_record
from services.search_service import filter_novels, rank_novels


ALIASES = ["Nonfiction", "Non Fiction", "Non-Fiction", " NONFICTION "]


def test_merge_preserves_order_and_unrelated_entries():
    genres = ["Fantasy", *ALIASES, "Science Fiction", "Fantasy", None]
    assert canonicalize_genres(genres) == ["Fantasy", "Non-Fiction", "Science Fiction", "Fantasy", None]
    assert canonicalize_genres([]) == []
    assert [genre for genre in IN_HOUSE_GENRES if genre in ALIASES] == ["Non-Fiction"]


@pytest.mark.parametrize("scraper", [royalroad, wattpad, webnovel])
@pytest.mark.parametrize("alias", ALIASES)
@pytest.mark.parametrize("source_field", ["genres", "tags"])
def test_scrapers_recognize_aliases_as_one_genre(scraper, alias, source_field):
    fields = {"genres": ["Fantasy"], "tags": ["MAGIC"]}
    fields[source_field].extend([alias, "Non-Fiction"])
    genres, tags = scraper.classify_genres_and_tags(**fields)
    assert set(genres) == {"Fantasy", "Non-Fiction"}
    assert len(genres) == 2
    assert tags == ["MAGIC"]


@pytest.mark.parametrize("source", ["royalroad", "wattpad", "webnovel"])
def test_pending_staging_payloads_are_normalized_without_rewriting_source(source):
    row = {"source": source, "raw_payload": {
        "title": "Example", "genres": ["Fantasy", *ALIASES, "History"],
        "tags": ["MEMOIR"],
    }}
    original = copy.deepcopy(row)
    result = transform_staged_record(row)
    assert result["genres"] == ["Fantasy", "Non-Fiction", "History"]
    assert result["tags"] == ["MEMOIR"]
    assert row == original


@pytest.mark.parametrize("alias", ALIASES)
def test_old_finder_links_include_and_exclude_canonical_genre(alias):
    novels = [{"id": 1, "genres": ["Non-Fiction"]}, {"id": 2, "genres": ["Fantasy"]}]
    assert [n["id"] for n in filter_novels(novels, include_genres=[alias])] == [1]
    assert [n["id"] for n in filter_novels(novels, exclude_genres=[alias])] == [2]
    assert [n["id"] for n in rank_novels(novels, alias)] == [1]


def test_finder_options_merge_legacy_rows(monkeypatch):
    from routes import search

    monkeypatch.setattr(search, "all_rows", lambda query: [{"genres": ALIASES}])
    monkeypatch.setattr(search, "load_definition", lambda: {})
    monkeypatch.setattr(search, "measures_for", lambda definition: [])
    assert search.search_options()["genres"] == ["Non-Fiction"]
