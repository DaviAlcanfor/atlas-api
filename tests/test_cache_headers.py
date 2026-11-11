import pytest
from fastapi.testclient import TestClient

from atlas_api.main import create_app


def test_ok_response_has_cache_headers(api_client: TestClient) -> None:
    r = api_client.get("/v1/countries")
    assert r.status_code == 200
    assert r.headers["x-data-version"]
    assert r.headers["etag"].startswith('W/"')
    assert r.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=86400"


def test_if_none_match_gives_304_without_body(api_client: TestClient) -> None:
    etag = api_client.get("/v1/polities?year=1900").headers["etag"]
    r = api_client.get("/v1/polities?year=1900", headers={"If-None-Match": etag})
    assert r.status_code == 304 and r.content == b""
    assert r.headers["etag"] == etag
    # different query => different ETag => full response
    assert api_client.get("/v1/polities?year=1901", headers={"If-None-Match": etag}).status_code == 200


def test_health_has_no_cache_headers(api_client: TestClient) -> None:
    r = api_client.get("/v1/health")
    assert "etag" not in r.headers and "cache-control" not in r.headers


def test_errors_carry_version_but_are_not_cacheable(api_client: TestClient) -> None:
    r = api_client.get("/v1/polities/nope")
    assert r.status_code == 404
    assert "x-data-version" in r.headers and "etag" not in r.headers
    assert "cache-control" not in r.headers


def test_cors_exposes_headers(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas_api.config import get_settings

    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(api_client.app.state.test_url)) as c:  # type: ignore[attr-defined]
            r = c.get("/v1/meta", headers={"Origin": "http://localhost:5173"})
        assert "etag" in r.headers["access-control-expose-headers"].lower()
    finally:
        get_settings.cache_clear()


def test_database_down_gives_503_problem_json() -> None:
    bad = "postgresql+psycopg://atlas:atlas@localhost:1/atlas_api_test"  # nothing listens on port 1
    with TestClient(create_app(bad), raise_server_exceptions=False) as c:
        h = c.get("/v1/health")
        assert h.status_code == 200 and h.json() == {"status": "ok", "db": "error"}
        r = c.get("/v1/countries")
        assert r.status_code == 503
        assert r.headers["content-type"].startswith("application/problem+json")
