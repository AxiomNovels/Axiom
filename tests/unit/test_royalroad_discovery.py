"""Discovery selection, current search markup, and strict content filtering."""
import csv
import json
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock

import pytest
import httpx

from scraper import discover_royalroad_popular as discovery
from scraper.royalroad import parse_royalroad


URL = "https://www.royalroad.com/fiction/123"


def fiction_html(description="An adventure.", followers=1000, rating=4.7, ratings=200):
    follower_markup = "" if followers is None else f"<li>Followers :</li><li>{followers}</li>"
    return f"""<html><h1>Story</h1><h4><a href="/profile/1">Author</a></h4>
    <div class="fiction-info"><span class="tags">
    <a href="/fictions/search?tagsAdd=fantasy">Fantasy</a></span>
    <div class="description"><p>{description}</p></div>
    <div class="fiction-stats"><span title="Overall Score" data-content="{rating} / 5"></span>
    <ul><li>Average Views :</li><li>999,000</li>{follower_markup}
    <li>Ratings :</li><li>{ratings}</li></ul></div></div></html>"""


def candidate(identity, followers, genres, score=0):
    return discovery.Candidate(
        url=f"https://www.royalroad.com/fiction/{identity}", fiction_id=identity,
        title=f"Story {identity}", synopsis="A synopsis.", genres=genres,
        followers=followers, popularity_score=score,
    )


def test_metrics_use_story_stats_and_displayed_overall_score():
    html = "<p>88,888 followers in a review</p>" + fiction_html(followers="1,234")
    assert discovery.extract_fiction_metrics(html) == (1234, 4.7, 200)


def test_counts_before_label_are_supported_for_listings():
    assert discovery.extract_fiction_metrics("<p>12.5K Followers</p>")[0] == 12500


@pytest.mark.parametrize("genre,slug", [
    ("Sci-fi", "sci_fi"), ("Romance", "romance_main"),
    ("Short Story", "one_shot"), ("Horror", "horror"),
])
def test_current_search_parameter_names(genre, slug):
    query = parse_qs(urlparse(discovery.search_seed("followers", genre)).query)
    assert query["orderBy"] == ["followers"]
    assert query["tagsAdd"] == [slug]
    assert query["tagsRemove"] == ["sexuality", "harem", "competing_love"]


def test_discovery_ignores_ads_and_deduplicates_slug_changes():
    html = """<a href="/fiction/666/ad">Ad</a>
    <div class="fiction-list-item"><h2><a href="/fiction/123/old">Story</a></h2></div>
    <div class="fiction-list-item"><h2><a href="/fiction/123/new">Story</a></h2></div>
    <div class="fiction-list-item"><h2><a href="https://other.test/fiction/999">Other</a></h2></div>"""
    assert discovery.extract_fiction_urls(html, discovery.BASE_URL) == {URL}


def test_pagination_follows_only_next_page_and_retains_filters():
    seed = discovery.search_seed("followers", "Horror") + "&page=2"
    html = """<a href="/fictions/search?page=50">Other page</a>
    <ul class="pagination"><li><a href="?page=1">Previous</a></li>
    <li><a href="?page=3">3</a></li><li><a href="?page=99">Last</a></li></ul>"""
    result = discovery.extract_next_listing_urls(html, seed)
    assert len(result) == 1
    query = parse_qs(urlparse(result[0]).query)
    assert query["page"] == ["3"]
    assert query["tagsAdd"] == ["horror"]
    assert query["tagsRemove"] == ["sexuality", "harem", "competing_love"]


def test_pagination_cannot_switch_genre_or_host():
    html = """<ul class="pagination">
    <a href="?page=2&tagsAdd=fantasy">Next</a>
    <a href="https://other.test/fictions/search?page=2">Next</a></ul>"""
    assert discovery.extract_next_listing_urls(html, discovery.search_seed("followers", "Horror")) == []


@pytest.mark.parametrize("text", [
    "This contains explicit sexual content.", "There are sex scenes.",
    "A steamy romance.", "NSFW adventure.", "A harem story.",
    "Smut versions are linked on Patreon.",
])
def test_description_disclosures_are_excluded(text):
    html = fiction_html(text)
    assert discovery.sexual_content_reasons(html, parse_royalroad(html, URL))


def test_disclosures_after_synopsis_separator_are_still_excluded():
    html = fiction_html("An adventure.</p><p>***</p><p>Contains explicit sexual content.")
    novel = parse_royalroad(html, URL)
    assert novel["synopsis"] == "An adventure."
    assert discovery.sexual_content_reasons(html, novel)


@pytest.mark.parametrize("text", [
    "No harem. No sexual content.", "An adventure without smut.",
    "Romance (not harem).",
    "A smut-free romance.", "A fantasy adventure with graphic violence.",
])
def test_explicit_absence_and_unrelated_content_are_allowed(text):
    html = fiction_html(text)
    assert discovery.sexual_content_reasons(html, parse_royalroad(html, URL)) == []


def test_reviews_and_ads_do_not_trigger_description_filter():
    html = fiction_html() + "<div class='review'>Read my smut story.</div>"
    assert discovery.sexual_content_reasons(html, parse_royalroad(html, URL)) == []


@pytest.fixture
def isolated_scraping(monkeypatch):
    fetcher = Mock(return_value=fiction_html())
    monkeypatch.setattr(discovery, "fetch_html", fetcher)
    monkeypatch.setattr(discovery.time, "sleep", Mock())
    return fetcher


def test_scraping_uses_one_page_for_payload_and_metrics(isolated_scraping):
    results = discovery.scrape_and_score({URL + "/old": 3, URL + "/new": 2})
    assert len(results) == 1
    isolated_scraping.assert_called_once()
    assert results[0].followers == 1000
    assert results[0].rating == 4.7
    assert results[0].rating_count == 200
    assert results[0].url == URL
    assert results[0].popularity_hits == 3


@pytest.mark.parametrize("followers,rating,ratings", [
    (None, 4.7, 200), (249, 4.7, 200), (1000, 3.0, 200), (1000, 4.7, 10),
])
def test_unestablished_or_low_quality_novels_are_rejected(isolated_scraping, followers, rating, ratings):
    isolated_scraping.return_value = fiction_html(followers=followers, rating=rating, ratings=ratings)
    assert discovery.scrape_and_score({URL: 10}) == []


def test_content_filter_precedes_popularity(isolated_scraping):
    isolated_scraping.return_value = fiction_html("Contains sexual content.", followers=100000)
    assert discovery.scrape_and_score({URL: 10}) == []


@pytest.mark.parametrize("status", [403, 429, 503])
def test_source_refusal_stops_scraping_instead_of_retrying_pool(isolated_scraping, status):
    request = httpx.Request("GET", URL)
    response = httpx.Response(status, request=request)
    isolated_scraping.side_effect = httpx.HTTPStatusError(
        "Source refusal", request=request, response=response,
    )
    with pytest.raises(httpx.HTTPStatusError):
        discovery.scrape_and_score({URL: 3, URL.replace("123", "124"): 2})
    isolated_scraping.assert_called_once()


def test_missing_fiction_page_is_skipped_without_stopping_pool(isolated_scraping):
    request = httpx.Request("GET", URL)
    error = httpx.HTTPStatusError(
        "Missing fiction", request=request, response=httpx.Response(404, request=request),
    )
    isolated_scraping.side_effect = [error, fiction_html()]
    results = discovery.scrape_and_score({URL: 3, URL.replace("123", "124"): 2})
    assert len(results) == 1
    assert results[0].fiction_id == 124


def test_popularity_dominates_and_diversity_counts_all_genres():
    popular = [candidate(i, 10000 - i * 100, ["Action", "Fantasy"]) for i in range(1, 16)]
    horror = candidate(100, 6000, ["Action", "Horror"], score=999)
    mystery = candidate(101, 5000, ["Action", "Mystery"])
    obscure = candidate(102, 300, ["Romance"])
    pool = popular + [horror, mystery, obscure]
    selected = discovery.select_popular_diverse(pool, target=10)
    assert [c.fiction_id for c in selected[:8]] == list(range(1, 9))
    assert {c.fiction_id for c in selected[8:]} == {100, 101}
    assert obscure not in selected
    # Genre order must not determine representation.
    for c in pool:
        c.genres.reverse()
    assert discovery.select_popular_diverse(pool, target=10) == selected


def test_popularity_backfills_when_no_genre_alternatives_exist():
    pool = [candidate(i, 10000 - i, ["Fantasy"]) for i in range(1, 21)]
    assert discovery.select_popular_diverse(pool, target=10) == pool[:10]


def test_followers_rank_above_inflated_listing_score():
    high = candidate(1, 10000, ["Fantasy"], score=1)
    low = candidate(2, 1000, ["Fantasy"], score=100)
    assert discovery.select_popular_diverse([low, high], target=1) == [high]


def test_selection_handles_empty_target_small_pool_and_duplicate_ids():
    novel = candidate(1, 1000, ["Fantasy"])
    alias = candidate(1, 1000, ["Fantasy"])
    alias.url += "/new-title"
    assert discovery.select_popular_diverse([novel, alias], target=10) == [novel]
    assert discovery.select_popular_diverse([novel], target=0) == []
    assert discovery.select_popular_diverse([], target=10) == []


def test_empty_run_preserves_existing_outputs(monkeypatch):
    monkeypatch.setattr(discovery, "discover_candidates", lambda: {})
    monkeypatch.setattr(discovery, "scrape_and_score", lambda hits: [])
    writer = Mock()
    monkeypatch.setattr(discovery, "write_outputs", writer)
    with pytest.raises(RuntimeError, match="outputs were preserved"):
        discovery.main()
    writer.assert_not_called()


def test_outputs_preserve_json_url_list_and_csv_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    high = candidate(1, 10000, ["Fantasy"], score=1)
    low = candidate(2, 1000, ["Horror"], score=100)
    discovery.write_outputs([high], [low, high])
    assert json.loads((tmp_path / "popular_royalroad_urls.txt").read_text()) == [high.url]
    with (tmp_path / "popular_royalroad_audit.csv").open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames == [
            "selected", "url", "fiction_id", "title", "popularity_score", "followers",
            "rating", "rating_count", "popularity_hits", "genres", "tags",
            "quality_reasons", "synopsis",
        ]
        rows = list(reader)
    assert [row["fiction_id"] for row in rows] == ["1", "2"]
    assert [row["selected"] for row in rows] == ["True", "False"]
    assert json.loads(rows[0]["genres"]) == ["Fantasy"]
