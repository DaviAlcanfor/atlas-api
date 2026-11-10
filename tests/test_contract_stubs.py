from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from atlas_api.main import app


@pytest.fixture(scope="module")
def c() -> Iterator[TestClient]:
    with TestClient(app) as client:  # `with` runs the lifespan (loads fixtures)
        yield client


def test_ok_paths(c: TestClient) -> None:
    for p in [
        "/v1/health", "/v1/meta", "/v1/countries", "/v1/countries/DE", "/v1/polities",
        "/v1/polities?year=1900", "/v1/polities/ottoman-empire", "/v1/snapshots",
        "/v1/snapshots/nearest?year=1880", "/v1/snapshots/1914/links", "/v1/search?q=al",
    ]:
        assert c.get(p).status_code == 200, p


def test_errors_are_problem_json(c: TestClient) -> None:
    cases = [
        ("/v1/countries/de", 422), ("/v1/countries/ZZ", 404), ("/v1/search?q=a", 422),
        ("/v1/snapshots/1800/links", 404), ("/v1/polities?limit=5000", 422),
        ("/v1/polities?year=99999", 422), ("/v1/snapshots/nearest?year=-99999", 422),
        ("/v1/polities/nope", 404), ("/v1/does-not-exist", 404),
    ]
    for p, code in cases:
        r = c.get(p)
        assert r.status_code == code, p
        assert r.headers["content-type"].startswith("application/problem+json"), p
        assert set(r.json()) == {"type", "title", "status", "detail"}, p


def test_method_not_allowed_is_problem_json(c: TestClient) -> None:
    r = c.post("/v1/meta")
    assert r.status_code == 405
    assert r.headers["content-type"].startswith("application/problem+json")


def test_nearest_picks_closest(c: TestClient) -> None:
    body = c.get("/v1/snapshots/nearest?year=1864").json()
    assert body["snapshot"]["year"] == 1815
    assert body["distance_years"] == 49
