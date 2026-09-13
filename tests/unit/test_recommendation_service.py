from services.recommendation_service import recommend_novels


def novel(identity, tags=None, **extra):
    return {"id": identity, "title": f"Novel {identity}", "genres": tags or [], **extra}


def test_tag_overlap_ranking_excludes_source_and_limits_to_five():
    source = novel(1, ["Fantasy", "Mystery"])
    candidates = [source, novel(2, ["Drama"]), novel(3, [" fantasy ", "MYSTERY"])]
    candidates += [novel(i, ["Fantasy"]) for i in range(4, 10)]
    result = recommend_novels(source, candidates)
    assert len(result) == 5
    assert result[0]["id"] == 3
    assert all(row["id"] not in (1, 2) for row in result)


def test_closer_profiles_rank_higher_and_both_embed_shapes_work():
    source = novel(1, protagonist_profiles={"impulsivity": 80, "selflessness": 20})
    close = novel(2, protagonist_profiles=[{"impulsivity": 75, "selflessness": 25}])
    distant = novel(3, protagonist_profiles={"impulsivity": 20, "selflessness": 80})
    assert [row["id"] for row in recommend_novels(source, [distant, close])] == [2, 3]


def test_missing_values_do_not_count_as_zero_or_outscore_complete_profiles():
    source = novel(1, philosophy_profiles={"freedom": 0, "survival": 80})
    complete = novel(2, philosophy_profiles={"freedom": 10, "survival": 70})
    sparse = novel(3, philosophy_profiles={"freedom": 0})
    absent = novel(4, philosophy_profiles={"freedom": None})
    assert [row["id"] for row in recommend_novels(source, [sparse, absent, complete])] == [2, 3]


def test_no_evidence_returns_empty_and_ties_are_stable():
    assert recommend_novels(novel(1), [novel(2)]) == []
    source = novel(1, ["Fantasy"])
    candidates = [novel(3, ["Fantasy"]), novel(2, ["Fantasy"])]
    assert recommend_novels(source, candidates) == recommend_novels(source, list(reversed(candidates)))


def test_shared_tags_and_minimal_payload():
    result = recommend_novels(novel(1, ["Fantasy"]), [novel(2, ["Fantasy", "Drama"], synopsis="Long text")])
    assert result[0]["shared_tags"] == ["Fantasy"]
    assert "synopsis" not in result[0]


def test_protagonist_match_outweighs_other_profiles_with_equal_tags():
    source = novel(1, ["Fantasy"], protagonist_profiles={"impulsivity": 100},
                   philosophy_profiles={"freedom": 100}, storytelling_style_profiles={"action": 100})
    character_match = novel(2, ["Fantasy"], protagonist_profiles={"impulsivity": 100},
                            philosophy_profiles={"freedom": 0}, storytelling_style_profiles={"action": 0})
    other_match = novel(3, ["Fantasy"], protagonist_profiles={"impulsivity": 0},
                        philosophy_profiles={"freedom": 100}, storytelling_style_profiles={"action": 100})
    assert [row["id"] for row in recommend_novels(source, [other_match, character_match])] == [2, 3]


def test_shared_tags_are_capped_at_three():
    tags = ["Fantasy", "Mystery", "Adventure", "Drama"]
    result = recommend_novels(novel(1, tags), [novel(2, tags)])
    assert result[0]["shared_tags"] == ["Adventure", "Drama", "Fantasy"]


def test_tags_and_protagonist_have_equal_weight():
    source = novel(1, ["Fantasy"], protagonist_profiles={"impulsivity": 100})
    tags_only = novel(2, ["Fantasy"], protagonist_profiles={"impulsivity": 0})
    protagonist_only = novel(3, ["Drama"], protagonist_profiles={"impulsivity": 100})
    for first, second in [(tags_only, protagonist_only), (protagonist_only, tags_only)]:
        first["title"], second["title"] = "A", "Z"
        result = recommend_novels(source, [second, first])
        assert result[0]["id"] == first["id"]
