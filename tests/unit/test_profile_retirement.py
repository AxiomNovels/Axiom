from services import novel_profiling_service as profiling
from routes.admin import PROFILES
from routes.novels import NOVEL_DETAIL_COLUMNS
from routes.search import SEARCH_COLUMNS


def test_only_protagonist_is_generated_and_editable():
    specs = profiling._load_specs()
    assert [spec.kind for spec in specs] == ["protagonist"]
    assert set(PROFILES) == {"protagonist"}
    assert len(specs[0].measures) == 6


def test_catalogue_queries_do_not_require_retired_tables():
    for columns in (NOVEL_DETAIL_COLUMNS, SEARCH_COLUMNS):
        assert "philosophy_profiles" not in columns
        assert "storytelling_style_profiles" not in columns
        assert "protagonist_profiles" in columns


def test_upload_preview_generates_only_protagonist(monkeypatch):
    monkeypatch.setattr(profiling, "_collect_comments", lambda novel: [])
    monkeypatch.setattr(profiling, "_generate_protagonist", lambda novel, comments, measures: {
        "scores": {measure: 40 for measure in measures},
        "protagonist_name": "Example Hero", "confidence": 80,
    })
    results = profiling._generate_all({"title": "Example"}, profiling._load_specs())
    assert len(results) == 1
    assert results[0].kind == "protagonist"
    assert results[0].status == profiling.STATUS_READY


def test_admin_preview_returns_score_mapping(monkeypatch):
    monkeypatch.setattr(profiling, "_collect_comments", lambda novel: [])
    monkeypatch.setattr(profiling, "_generate_protagonist", lambda novel, comments, measures: {
        "scores": {measure: 30 for measure in measures}, "protagonist_name": "Hero"
    })
    draft = profiling.generate_protagonist_preview({"title": "Example"})
    assert draft["status"] == "ready"
    assert draft["protagonist_name"] == "Hero"
    assert draft["scores"] == dict.fromkeys(profiling._load_specs()[0].measures, 30)
