from services.search_service import filter_novels, novel_relevance, rank_novels, searchable_text


NOVELS = [
    {
        "id": 1,
        "title": "Mother of Learning",
        "author": "nobody103",
        "genres": ["Fantasy", "Mystery"],
        "synopsis": "A student becomes trapped in a repeating time loop.",
    },
    {
        "id": 2,
        "title": "Another Mother",
        "author": "Example Author",
        "genres": ["Drama"],
        "synopsis": "A quiet family story.",
    },
]


def test_searchable_text_normalizes_case_and_punctuation():
    assert searchable_text("Time-Loop: FANTASY!") == ["time", "loop", "fantasy"]


def test_exact_title_is_ranked_above_partial_title():
    results = rank_novels(NOVELS, "Mother of Learning")
    assert results[0]["id"] == 1


def test_genre_and_synopsis_terms_are_searchable():
    assert novel_relevance(NOVELS[0], "Fantasy") > 0
    assert novel_relevance(NOVELS[0], "time loop") > 0


def test_unmatched_novels_are_excluded():
    assert rank_novels(NOVELS, "unmatched phrase") == []


def test_finder_combines_tags_status_and_profile_ranges():
    novels = [
        {"id": 1, "genres": ["Fantasy", "Romance"], "status": "ongoing", "protagonist_profiles": [{"romantic_attachment": 70}]},
        {"id": 2, "genres": ["Fantasy"], "status": "ongoing", "protagonist_profiles": [{"romantic_attachment": 80}]},
        {"id": 3, "genres": ["Fantasy", "Romance"], "status": "completed", "protagonist_profiles": [{"romantic_attachment": 40}]},
    ]
    results = filter_novels(novels, include_tags=["Fantasy", "Romance"], status="ongoing", profile_ranges={"romantic_attachment": (50, None)})
    assert [novel["id"] for novel in results] == [1]


def test_trait_filter_omits_unprofiled_novels_and_excluded_tags():
    novels = [
        {"id": 1, "genres": ["Fantasy", "Horror"], "protagonist_profiles": [{"selflessness": 80}]},
        {"id": 2, "genres": ["Fantasy"], "protagonist_profiles": []},
        {"id": 3, "genres": ["Fantasy"], "protagonist_profiles": [{"selflessness": 80}]},
    ]
    results = filter_novels(novels, exclude_tags=["Horror"], profile_ranges={"selflessness": (50, 100)})
    assert [novel["id"] for novel in results] == [3]


def test_tag_or_mode_matches_any_included_tag():
    novels = [
        {"id": 1, "genres": ["Fantasy"]},
        {"id": 2, "genres": ["Romance"]},
        {"id": 3, "genres": ["Mystery"]},
    ]
    results = filter_novels(novels, include_tags=["Fantasy", "Romance"], tag_mode="or")
    assert [novel["id"] for novel in results] == [1, 2]


def test_finder_filters_philosophy_and_storytelling_profiles():
    novels = [
        {"id": 1, "philosophy_profiles": {"freedom": 80}, "storytelling_style_profiles": {"mystery": 70}},
        {"id": 2, "philosophy_profiles": {"freedom": 30}, "storytelling_style_profiles": {"mystery": 80}},
    ]
    results = filter_novels(
        novels,
        philosophy_ranges={"freedom": (60, None)},
        storytelling_ranges={"mystery": (50, None)},
    )
    assert [novel["id"] for novel in results] == [1]
