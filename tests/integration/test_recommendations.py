from types import SimpleNamespace
from fastapi.testclient import TestClient
from main import app
import routes.novels as routes


class Catalogue:
    def __init__(self, rows, pages):
        self.rows, self.pages = rows, pages
    def table(self, name):
        return Catalogue(self.rows[:], self.pages)
    def select(self, columns):
        return self
    def neq(self, field, value):
        self.rows = [row for row in self.rows if row[field] != value]
        return self
    def order(self, field):
        self.rows.sort(key=lambda row: row[field])
        return self
    def range(self, start, end):
        self.pages.append((start, end))
        self.rows = self.rows[start:end + 1]
        return self
    def execute(self):
        return SimpleNamespace(data=self.rows)


def test_similar_endpoint_searches_beyond_first_page(monkeypatch):
    source = {"id": 1, "genres": ["Fantasy", "Mystery"]}
    rows = [{"id": i, "title": str(i), "genres": ["Fantasy"]} for i in range(2, 503)]
    rows[-1]["genres"] = ["Fantasy", "Mystery"]
    pages = []
    monkeypatch.setattr(routes, "get_novel", lambda identity: source)
    monkeypatch.setattr(routes, "supabase", Catalogue(rows, pages))
    response = TestClient(app).get("/api/novels/1/similar")
    assert response.status_code == 200
    assert len(response.json()) == 5
    assert response.json()[0]["id"] == 502
    assert pages == [(0, 499), (500, 999)]


def test_similar_endpoint_missing_source(monkeypatch):
    monkeypatch.setattr(routes, "get_novel", lambda identity: None)
    assert TestClient(app).get("/api/novels/999/similar").status_code == 404
