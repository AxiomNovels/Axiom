from services.search_service import novel_relevance, rank_novels, searchable_text


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
