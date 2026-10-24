from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
import routes.novels as routes


class Query:
    def __init__(self, database, table):
        self.database = database
        self.table = table
        self.ids = None
        self.bounds = None

    def select(self, columns):
        self.columns = [column.strip() for column in columns.split(",")]
        return self

    def order(self, column):
        self.sort_column = column
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def in_(self, column, ids):
        assert column == "id"
        self.ids = ids
        return self

    def execute(self):
        rows = self.database[self.table]
        if self.ids is not None:
            assert len(self.ids) <= 20
            rows = [row for row in rows if row["id"] in self.ids]
        if self.bounds:
            rows = sorted(rows, key=lambda row: row[self.sort_column])
            rows = rows[self.bounds[0]:self.bounds[1] + 1]
        return SimpleNamespace(data=[{key: row.get(key) for key in self.columns} for row in rows])


@pytest.fixture
def catalogue(monkeypatch):
    database = {
        "novels": [{"id": i, "title": f"Novel {i}"} for i in range(1, 46)],
        "reviews": [
            {"id": 1, "novel_id": 1, "rating": 5},
            {"id": 2, "novel_id": 1, "rating": 4},
            {"id": 3, "novel_id": 2, "rating": 5},
            {"id": 4, "novel_id": 3, "rating": 4.5},
        ],
    }
    monkeypatch.setattr(routes, "supabase", SimpleNamespace(table=lambda name: Query(database, name)))
    return database


def fetch(page=1, seed="test"):
    response = TestClient(app).get("/api/novels/popular", params={"page": page, "seed": seed})
    assert response.status_code == 200, response.text
    return response.json()


def test_ratings_random_ties_and_complete_pagination(catalogue):
    pages = [fetch(page) for page in (1, 2, 3)]
    assert [len(page["novels"]) for page in pages] == [20, 20, 5]
    assert pages[0]["total"] == 45
    assert pages[0]["total_pages"] == 3
    assert pages[0]["page_size"] == 20
    ranked = [novel for page in pages for novel in page["novels"]]
    assert ranked[0]["id"] == 2
    assert ranked[0]["average_rating"] == 5
    assert {novel["id"] for novel in ranked[1:3]} == {1, 3}
    assert all(novel["average_rating"] is None for novel in ranked[3:])
    first = next(novel for novel in ranked if novel["id"] == 1)
    assert first["average_rating"] == 4.5
    assert first["review_count"] == 2
    assert len({novel["id"] for novel in ranked}) == 45
    assert fetch() == pages[0]
    changed = fetch(seed="different-seed")
    assert changed["novels"][0]["id"] == 2
    assert changed["novels"] != pages[0]["novels"]


def test_complete_catalogue_and_reviews_beyond_database_page_cap(catalogue):
    catalogue["novels"] = [{"id": i, "title": str(i)} for i in range(1, 1102)]
    catalogue["reviews"] = [
        {"id": i, "novel_id": 1, "rating": 1} for i in range(1, 1102)
    ] + [{"id": 1102, "novel_id": 1101, "rating": 5}]
    data = fetch()
    assert data["total"] == 1101
    assert data["total_pages"] == 56
    assert data["novels"][0]["id"] == 1101
    assert data["novels"][1]["review_count"] == 1101
    assert data["novels"][1]["average_rating"] == 1
    assert len(fetch(page=56)["novels"]) == 1


def test_out_of_range_empty_and_generated_seed(catalogue):
    assert fetch(page=999)["page"] == 3
    response = TestClient(app).get("/api/novels/popular")
    assert response.status_code == 200
    assert len(response.json()["seed"]) == 32
    catalogue["novels"] = []
    data = fetch(page=999)
    assert data["novels"] == []
    assert data["page"] == 1
    assert data["total"] == data["total_pages"] == 0


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page=no", "seed=", "seed=a%20b", "seed=" + "a" * 65])
def test_invalid_parameters(catalogue, query):
    assert TestClient(app).get("/api/novels/popular?" + query).status_code == 422


def test_database_failure_is_recoverable_and_does_not_leak_details(monkeypatch):
    def fail(_name):
        raise RuntimeError("private database detail")

    monkeypatch.setattr(routes, "supabase", SimpleNamespace(table=fail))
    response = TestClient(app).get("/api/novels/popular")
    assert response.status_code == 503
    assert response.json() == {"detail": "Popular novels are temporarily unavailable."}
