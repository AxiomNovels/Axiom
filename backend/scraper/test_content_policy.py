"""
To run:
cd to the backend folder, then run:
python -m pytest scraper/test_content_policy.py
"""

from scraper.content_policy import (
    EXCLUDED_TAGS_BY_SOURCE,
    find_policy_violations,
)


def novel(tags=None, genres=None):
    return {"title": "Example", "tags": tags or [], "genres": genres or []}


def test_clean_novel_passes_on_every_source():
    clean = novel(tags=["PROGRESSION", "REINCARNATION", "SYSTEM"], genres=["Fantasy", "Action"])
    for label in ("Royal Road", "WebNovel", "Wattpad"):
        assert find_policy_violations(label, clean) == []


def test_royal_road_flags_sexual_content_and_harem_tags():
    # Scrapers store tags upper-cased; matching must not care.
    assert find_policy_violations("Royal Road", novel(tags=["SEXUAL CONTENT"])) == ["SEXUAL CONTENT"]
    assert find_policy_violations("Royal Road", novel(tags=["MULTIPLE LOVE INTERESTS"]))
    assert find_policy_violations("Royal Road", novel(tags=["Smut"]))


def test_wattpad_flags_its_own_vocabulary():
    assert find_policy_violations("Wattpad", novel(tags=["SMUT", "ACTION"])) == ["SMUT"]
    assert find_policy_violations("Wattpad", novel(tags=["REVERSEHAREM"]))
    assert find_policy_violations("Wattpad", novel(tags=["LEMON"]))


def test_webnovel_flags_its_own_vocabulary():
    assert find_policy_violations("WebNovel", novel(tags=["SEX SCENE"]))
    assert find_policy_violations("WebNovel", novel(tags=["REVERSE HAREM"]))
    assert find_policy_violations("WebNovel", novel(tags=["ECCHI"]))


def test_punctuation_and_spacing_do_not_defeat_the_filter():
    for variant in ("Reverse Harem", "reverse-harem", "REVERSE_HAREM", "reverseharem"):
        assert find_policy_violations("WebNovel", novel(tags=[variant])) == [variant]
    assert find_policy_violations("WebNovel", novel(tags=["Non-Con"]))


def test_lists_are_per_source_like_the_discovery_scripts():
    # "ecchi" is on WebNovel's list only, "mates" on Wattpad's only.
    assert find_policy_violations("Royal Road", novel(tags=["ECCHI", "MATES"])) == []
    assert find_policy_violations("Wattpad", novel(tags=["ECCHI"])) == []
    assert find_policy_violations("Wattpad", novel(tags=["MATES"]))


def test_genres_are_checked_too():
    assert find_policy_violations("Royal Road", novel(genres=["Erotica"]))


def test_unknown_source_fails_closed():
    assert find_policy_violations("Some Other Site", novel(tags=["ECCHI"]))
    assert find_policy_violations(None, novel(tags=["HAREM"]))


def test_missing_or_odd_values_do_not_crash():
    assert find_policy_violations("Wattpad", {}) == []
    assert find_policy_violations("Wattpad", {"tags": None, "genres": None}) == []
    assert find_policy_violations("Wattpad", {"tags": [None, 5, "", "SMUT"]}) == ["SMUT"]


def test_each_violation_is_reported_once():
    assert find_policy_violations("Wattpad", novel(tags=["SMUT", "SMUT"])) == ["SMUT"]


def test_every_listed_tag_is_caught_for_its_own_source():
    for source, tags in EXCLUDED_TAGS_BY_SOURCE.items():
        for tag in tags:
            assert find_policy_violations(source, novel(tags=[tag])), (source, tag)


def test_matching_is_whole_tag_not_substring():
    # Tags that merely contain a banned word must not be rejected.
    harmless = ["HARMONY", "MATURE PROTAGONIST", "CHARACTER DEVELOPMENT", "LIMESTONE", "ROMANCE"]
    for label in ("Royal Road", "WebNovel", "Wattpad"):
        assert find_policy_violations(label, novel(tags=harmless)) == []