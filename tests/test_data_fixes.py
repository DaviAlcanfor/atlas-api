"""spec 019: data_version after import-facts, Denmark, several capitals, image mirroring."""
import json
from pathlib import Path

import httpx
import pytest
from etl.wikidata import leaders
from etl.wikidata.pipeline import STATE, build
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from atlas_api import queries
from atlas_api.facts import import_facts
from atlas_api.importer import import_content
from atlas_api.main import create_app
from conftest import _fresh_database


def _country(**kw: object) -> dict[str, object]:
    base = {"official_name": "X", "capital": "A", "capital_lat": 1.0, "capital_lng": 2.0,
            "capitals": [{"name": "A", "lat": 1.0, "lng": 2.0}, {"name": "B", "lat": 3.0, "lng": 4.0},
                         {"name": "C", "lat": None, "lng": None}],
            "flag_url": None, "region": None, "area_km2": None, "population": 10,
            "population_year": 2020, "languages": [], "currencies": [], "memberships": []}
    return {**base, **kw}


def _facts(root: Path, **kw: object) -> Path:
    f = root / "wikidata.json"
    f.write_text(json.dumps({
        "source": {"id": "wikidata", "title": "Wikidata", "url": None, "license": "CC0"},
        "retrieved_at": {"states": "2026-01-01T00:00:00+00:00"},
        "countries": {"ZA": _country(**kw)}}), encoding="utf-8")
    return f


def test_import_facts_changes_data_version_and_etag(tmp_path: Path) -> None:
    content = tmp_path / "content"
    (content / "polities").mkdir(parents=True)
    (content / "polities" / "za.yaml").write_text(
        'id: za\nname: Africa do Sul\ntype: other\nstart_year: 1946\niso2: "ZA"\n', encoding="utf-8")
    eng = _fresh_database("atlas_version_test")
    try:
        with Session(eng) as s, s.begin():
            import_content(s, content)
            import_facts(s, _facts(tmp_path))
        with TestClient(create_app(eng.url.render_as_string(hide_password=False))) as c:
            first = c.get("/v1/countries/ZA")
            assert first.json()["population"]["value"] == 10
            caps = c.get("/v1/countries").json()["items"][0]["capital_coords"]
            assert [x["name"] for x in caps] == ["A", "B"]  # C has no coordinates
            with Session(eng) as s, s.begin():  # same files again: nothing changes
                import_facts(s, _facts(tmp_path))
            assert c.get("/v1/countries/ZA").headers["etag"] == first.headers["etag"]
            with Session(eng) as s, s.begin():
                import_facts(s, _facts(tmp_path, population=11))
            second = c.get("/v1/countries/ZA", headers={"If-None-Match": first.headers["etag"]})
            assert second.status_code == 200 and second.json()["population"]["value"] == 11
            assert second.headers["x-data-version"] != first.headers["x-data-version"]
    finally:
        eng.dispose()


def test_import_content_alone_keeps_a_version(session: Session, tmp_path: Path) -> None:
    (tmp_path / "polities").mkdir()
    v = import_content(session, tmp_path)["data_version"]
    assert queries.data_version(session) == v != "empty"


def test_denmark_is_in_the_state_query_and_the_seed(api_client: TestClient) -> None:
    assert "wd:Q35" in STATE  # Q35 carries ISO "DK" but is not P31 sovereign state
    assert Path("content/polities/dinamarca.yaml").exists()
    r = api_client.get("/v1/countries/DK")
    assert r.status_code == 200 and r.json()["name"] == "Dinamarca"


def test_build_lists_every_current_capital_preferred_first() -> None:
    def row(name: str, rank: str, coord: str | None = "Point(1 2)") -> dict[str, dict[str, str]]:
        r = {"iso2": {"value": "MY"}, "capLabel": {"value": name},
             "rank": {"value": "http://wikiba.se/ontology#" + rank}}
        return r | ({"coord": {"value": coord}} if coord else {})
    raw = {k: {"rows": []} for k in ("official_name", "population", "area", "languages",
                                      "currencies", "memberships", "continent", "flag")}
    raw["states"] = {"rows": [{"iso2": {"value": "MY"}, "c": {"value": "Q833"},
                               "cLabel": {"value": "Malásia"}}]}
    raw["capital"] = {"rows": [row("Putrajaya", "NormalRank"), row("Kuala Lumpur", "PreferredRank"),
                               row("Velha", "DeprecatedRank"), row("Putrajaya", "NormalRank", None)]}
    my = build(raw)["MY"]
    assert [c["name"] for c in my["capitals"]] == ["Kuala Lumpur", "Putrajaya"]
    assert my["capital"] == "Kuala Lumpur" and (my["capital_lat"], my["capital_lng"]) == (2.0, 1.0)


def test_mirror_images_skipped_without_credentials(monkeypatch: pytest.MonkeyPatch,
                                                   tmp_path: Path) -> None:
    monkeypatch.delenv("IMAGE_BUCKET_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    leaders.get_etl_settings.cache_clear()
    imgs = {"a.jpg": {"url": "https://upload.wikimedia.org/a.jpg", "credit": "c", "license": "l"}}
    try:
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))) as c:
            assert leaders.mirror_images(c, imgs, tmp_path) == imgs  # no request made
    finally:
        leaders.get_etl_settings.cache_clear()


def test_mirror_images_uploads_once_and_repoints(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    monkeypatch.setenv("IMAGE_BUCKET_URL", "https://x.supabase.co/storage/v1")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    leaders.get_etl_settings.cache_clear()
    calls: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        calls.append(r)
        if r.method == "GET":
            return httpx.Response(200, content=b"jpg", headers={"content-type": "image/jpeg"})
        assert r.headers["authorization"] == "Bearer secret" and r.content == b"jpg"
        return httpx.Response(200, json={"Key": "k"})

    imgs = {"a.jpg": {"url": "https://upload.wikimedia.org/t/320px-a.jpg", "credit": "c", "license": "l"}}
    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as c:
            out = leaders.mirror_images(c, imgs, tmp_path)
            again = leaders.mirror_images(c, imgs, tmp_path)
    finally:
        leaders.get_etl_settings.cache_clear()
    url = out["a.jpg"]["url"]
    assert url.startswith("https://x.supabase.co/storage/v1/object/public/atlas-images/")
    assert url.endswith(".jpg") and again == out and out["a.jpg"]["credit"] == "c"
    assert [r.method for r in calls] == ["GET", "POST"]  # second run hits the cache
