from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from main import app
from models.protagonist_definition import DefinitionUpdate
from profiler import gemini
from profiler.prompt import build_prompt
from profiler.prompt_playground import build_prompt as build_playground_prompt
from routes import admin, search, novels
from services import protagonist_definition_service as definitions
from services import novel_profiling_service as profiling
from services import protagonist_rebuild_service as rebuilds
from profiler.gemini import GeminiAPIError
from services.recommendation_service import recommend_novels


DEFINITION = {"revision": 7, "instructions": "Use evidence, score 0-100.", "traits": [
    {"key": "resilience", "name": "Resilience", "prompt": "0 gives up; 100 perseveres."},
    {"key": "empathy", "name": "Empathy", "prompt": "0 indifferent; 100 deeply empathetic."},
]}


def test_definition_editor_is_special_only(monkeypatch):
    from core.auth import get_current_user
    client = MagicMock()
    monkeypatch.setattr(admin, "create_service_client", lambda: client)
    api = TestClient(app)
    path = "/api/admin/protagonist-definition"
    assert api.get(path).status_code == 401
    assert api.put(path, json=DEFINITION).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: ("ordinary", None)
    try:
        for metadata in [{}, {"axiom_special": True, "axiom_banned": True}]:
            client.auth.admin.get_user_by_id.return_value.user = SimpleNamespace(app_metadata=metadata)
            assert api.get(path).status_code == 403
            assert api.put(path, json=DEFINITION).status_code == 403
        client.rpc.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("code,status", [("40001",409), ("22023",422), ("PGRST202",503)])
def test_definition_write_maps_errors_without_partial_python_writes(code, status):
    client = MagicMock()
    client.rpc.return_value.execute.side_effect = APIError({"code": code, "message": "Conflict"})
    with pytest.raises(Exception) as error:
        admin.update_protagonist_definition(DefinitionUpdate(**DEFINITION), ("admin", client))
    assert error.value.status_code == status
    client.table.assert_not_called()


def test_definition_write_is_one_atomic_rpc():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = DEFINITION
    assert admin.update_protagonist_definition(DefinitionUpdate(**DEFINITION), ("admin", client)) == DEFINITION
    client.rpc.assert_called_once_with("update_protagonist_definition", {
        "p_revision": 7, "p_instructions": DEFINITION["instructions"], "p_traits": DEFINITION["traits"],
    })
    client.table.assert_not_called()


@pytest.mark.parametrize("key", ["novel_id", "id", "scores_locked", "pg_catalog", "x;drop table novels", "A", "a" * 49])
def test_trait_keys_reject_reserved_or_unsafe_identifiers(key):
    data = deepcopy(DEFINITION)
    data["traits"][0]["key"] = key
    with pytest.raises(ValueError):
        DefinitionUpdate(**data)


@pytest.mark.parametrize("change", [
    {"traits": []}, {"revision": True}, {"instructions": " "},
    {"traits": [DEFINITION["traits"][0]] * 2},
    {"traits": [{"key": "x", "name": " ", "prompt": "Text"}]},
])
def test_definition_shape_is_validated(change):
    with pytest.raises(ValueError):
        DefinitionUpdate(**{**DEFINITION, **change})


def test_definition_reads_are_live_and_fail_closed():
    client = MagicMock()
    client.rpc.return_value.execute.side_effect = [SimpleNamespace(data=DEFINITION), SimpleNamespace(data={**DEFINITION,"revision":8}), RuntimeError("offline")]
    assert definitions.load_definition(client)["revision"] == 7
    assert definitions.load_definition(client)["revision"] == 8
    with pytest.raises(Exception) as error:
        definitions.load_definition(client)
    assert error.value.status_code == 503


@pytest.mark.parametrize("builder", [build_prompt, build_playground_prompt])
def test_prompt_and_gemini_schema_use_one_snapshot(monkeypatch, builder):
    prompt = builder({"title": "Novel"}, "Hero", [], definition=DEFINITION)
    assert "Score exactly 2 protagonist traits" in prompt
    assert "0 gives up; 100 perseveres." in prompt
    assert "INTELLECTUAL_DRIVE" not in prompt
    request = MagicMock(return_value={"scores": {"resilience":0,"empathy":100}, "confidence":80,"evidence_summary":"Evidence"})
    monkeypatch.setattr(gemini, "request_structured", request)
    monkeypatch.setattr(definitions, "load_definition", lambda: pytest.fail("Must use the prompt snapshot"))
    result = gemini.generate_profile(prompt)
    assert result["revision"] == 7
    assert request.call_args.args[1]["properties"]["scores"]["required"] == ["resilience","empathy"]


def test_preview_token_invalidates_on_prompt_only_edit(monkeypatch):
    monkeypatch.setenv("PROFILE_TOKEN_SECRET", "isolated-test-secret")
    monkeypatch.setattr(definitions, "load_definition", lambda: DEFINITION)
    specs = profiling._load_specs()
    result = profiling.ProfileResult("protagonist", "Profile", "Description", status="ready",
                                    scores={"resilience":0,"empathy":100}, protagonist_name="Hero", revision=7)
    novel = {"title":"Novel"}
    token = profiling._issue_token("user","source","url",novel,[result])
    assert profiling._results_from_token(token,"user","source","url",novel,specs)[0].revision == 7
    monkeypatch.setattr(definitions, "load_definition", lambda: {**DEFINITION,"revision":8})
    assert profiling._results_from_token(token,"user","source","url",novel,profiling._load_specs()) is None


def test_dynamic_search_and_recommendations(monkeypatch):
    rows = [{"id":1,"title":"One","protagonist_profiles":{"resilience":80}},
            {"id":2,"title":"Two","protagonist_profiles":{"resilience":10}}]
    monkeypatch.setattr(search,"load_definition",lambda: DEFINITION)
    monkeypatch.setattr(search,"_fetch_catalogue",lambda: deepcopy(rows))
    response = TestClient(app).get("/api/search?resilience_min=70")
    assert response.status_code == 200
    assert [n["id"] for n in response.json()] == [1]
    assert TestClient(app).get("/api/search?resilience_min=101").status_code == 422
    assert TestClient(app).get("/api/search/protagonist-definition").json() == DEFINITION
    source = {"id":3,"protagonist_profiles":{"resilience":90}}
    assert recommend_novels(source,rows,measures=("resilience",))[0]["id"] == 1
    monkeypatch.setattr(novels,"get_novel",lambda novel_id: source)
    monkeypatch.setattr(novels,"load_definition",lambda: DEFINITION)


def test_dynamic_traits_preserve_equal_recommendation_weight():
    source = {"id":1,"tags":["Fantasy"],"protagonist_profiles":{"resilience":100}}
    tags = {"id":2,"title":"Z","tags":["Fantasy"],"protagonist_profiles":{"resilience":0}}
    trait = {"id":3,"title":"A","tags":["Drama"],"protagonist_profiles":{"resilience":100}}
    assert recommend_novels(source,[tags,trait],measures=("resilience",))[0]["id"] == 3
    tags["title"], trait["title"] = "A", "Z"
    assert recommend_novels(source,[tags,trait],measures=("resilience",))[0]["id"] == 2


def test_rebuild_eligibility_uses_current_traits(monkeypatch):
    monkeypatch.setattr(rebuilds,"load_definition",lambda client: DEFINITION)
    monkeypatch.setattr(rebuilds,"_rows",lambda client,table,columns: (
        [{"id":1},{"id":2},{"id":3}] if table=="novels" else
        [{"novel_id":1,"resilience":0,"empathy":0},{"novel_id":2,"resilience":50,"empathy":None}]
    ))
    assert rebuilds.candidate_novel_ids(object(),False) == [2,3]


def test_profile_generation_explains_temporary_gemini_failures():
    unavailable = GeminiAPIError(503, '{"error":{"status":"UNAVAILABLE"}}')
    limited = GeminiAPIError(429, '{"error":{"status":"RESOURCE_EXHAUSTED"}}')
    assert "temporarily unavailable" in profiling._generation_failure_message(unavailable)
    assert "rate-limited" in profiling._generation_failure_message(limited)


def test_cancel_rebuild_preserves_completed_history(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(rebuilds, "create_service_client", lambda: client)
    monkeypatch.setattr(rebuilds, "job_status", lambda job_id, client=None: {"id": job_id, "status": "running"})
    assert rebuilds.cancel_job("job-1") is True
    updates = client.table.return_value.update.call_args_list
    assert updates[0].args[0]["status"] == "cancelled"
    assert updates[1].args[0] == {
        "status": "cancelled", "error": "Cancelled by an administrator", "finished_at": updates[0].args[0]["finished_at"],
    }


def test_manual_scores_require_current_trait_set_and_revision(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(admin,"load_definition",lambda client: DEFINITION)
    monkeypatch.setattr(admin,"find_novel",lambda client,id: {"id":id})
    payload = admin.ProfileScores(scores={"resilience":0,"empathy":100},protagonist_name="Hero",revision=7)
    assert admin.save_scores(1,"protagonist",payload,("admin",client)) == {"saved":True}
    assert client.rpc.call_args.args[1]["p_revision"] == 7
    client.rpc.return_value.execute.side_effect = APIError({"code":"40001","message":"Changed"})
    with pytest.raises(Exception) as error:
        admin.save_scores(1,"protagonist",payload,("admin",client))
    assert error.value.status_code == 409
