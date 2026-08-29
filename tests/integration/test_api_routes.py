from fastapi.testclient import TestClient

import routes.novels as novels_routes
import routes.search as search_routes
from main import app


NOVELS = [
    {
        "id": 1,
        "title": "Mother of Learning",
        "author": "nobody103",
        "cover_image_url": None,
        "synopsis": "A student becomes trapped in a repeating time loop.",
        "status": "completed",
        "genres": ["Fantasy", "Mystery"],
        "protagonist_profiles": [{"romantic_attachment": 25}],
        "philosophy_profiles": {"freedom": 80},
        "storytelling_style_profiles": {"mystery": 70},
    },
    {
        "id": 2,
        "title": "A Practical Guide to Evil",
        "author": "ErraticErrata",
        "cover_image_url": None,
        "synopsis": "A young woman chooses the villain's path.",
        "status": "completed",
        "genres": ["Fantasy"],
        "protagonist_profiles": [{"romantic_attachment": 70}],
        "philosophy_profiles": {"freedom": 30},
        "storytelling_style_profiles": {"mystery": 20},
    },
]


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.selected_id = None

    def select(self, *_args):
        return self

    def order(self, field):
        self.rows = sorted(self.rows, key=lambda row: row[field])
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def single(self):
        return self

    def execute(self):
        data = self.rows[0] if len(self.rows) == 1 else self.rows
        return FakeResponse(data)


class FakeSupabase:
    def table(self, _name):
        return FakeQuery([dict(novel) for novel in NOVELS])


def test_health_endpoint():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_local_numeric_frontend_origin_is_allowed():
    response = TestClient(app).get(
        "/api/health",
        headers={"Origin": "http://127.0.0.1:3000"},
    )
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_novel_list_endpoint(monkeypatch):
    monkeypatch.setattr(novels_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/novels")
    assert response.status_code == 200
    assert [novel["title"] for novel in response.json()] == [
        "A Practical Guide to Evil",
        "Mother of Learning",
    ]


def test_novel_detail_endpoint(monkeypatch):
    monkeypatch.setattr(novels_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/novels/1")
    assert response.status_code == 200
    assert response.json()["title"] == "Mother of Learning"


def test_search_endpoint_orders_by_relevance(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/search", params={"q": "Mother of Learning"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == 1


def test_empty_search_returns_no_results(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/search", params={"q": "  "})
    assert response.status_code == 200
    assert response.json() == []


def test_finder_options_are_derived_from_catalogue(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/search/options")
    assert response.status_code == 200
    assert response.json()["tags"] == ["Fantasy", "Mystery"]


def test_search_filters_by_tag_and_profile_value(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/search", params={"include_tags": "Fantasy", "romantic_attachment_min": 50})
    assert response.status_code == 200
    assert [novel["id"] for novel in response.json()] == [2]


def test_search_supports_or_tag_matching(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/search", params={"include_tags": "Mystery,Fantasy", "tag_mode": "or"})
    assert response.status_code == 200
    assert [novel["id"] for novel in response.json()] == [2, 1]


def test_search_accepts_blank_profile_thresholds_from_finder_form(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get(
        "/api/search",
        params={"include_tags": "Fantasy", "impulsivity_min": "", "romantic_attachment_max": ""},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_search_filters_philosophy_and_storytelling_ranges(monkeypatch):
    monkeypatch.setattr(search_routes, "supabase", FakeSupabase())
    response = TestClient(app).get("/api/search", params={"freedom_min": 60, "mystery_min": 50})
    assert response.status_code == 200
    assert [novel["id"] for novel in response.json()] == [1]
