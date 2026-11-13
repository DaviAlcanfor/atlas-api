"""spec 024: subdivision facts (rules offline) and GET /v1/countries/{iso2}/subdivisions on the real data_out/ file."""
from pathlib import Path

import pytest
from etl.wikidata.subdivisions import build, pick_population
from fastapi.testclient import TestClient

from atlas_api.schemas import SubdivisionList

PREF, NORMAL = "http://wikiba.se/ontology#PreferredRank", "http://wikiba.se/ontology#NormalRank"


def _row(**kv: str) -> dict[str, dict[str, str]]:
    return {k: {"value": v} for k, v in kv.items()}


def test_population_preferred_then_latest() -> None:
    rows = [_row(pop="100", when="2022-08-01T00:00:00Z", rank=NORMAL), _row(pop="90", when="2010-01-01T00:00:00Z", rank=PREF)]
    assert pick_population(rows) == {"value": 90, "year": 2010}  # preferred rank wins even when older
    rows[1]["rank"] = {"value": NORMAL}
    assert pick_population(rows) == {"value": 100, "year": 2022}
    assert pick_population([]) is None


def test_build_keeps_web_order_and_converts_area() -> None:
    facts = [_row(s="http://www.wikidata.org/entity/Q2", sLabel="Dois", iso="XX-B", area="2500000"),
             _row(s="http://www.wikidata.org/entity/Q1", sLabel="Q1")]  # label missing in pt/en: Wikidata echoes the id
    out = build([("Q1", "Um (polígono)"), ("Q2", "Dois")], facts, [])
    assert [x["name"] for x in out] == ["Um (polígono)", "Dois"]
    assert out[1]["area_km2"] == 2.5 and out[1]["code"] == "XX-B" and out[0]["population"] is None


@pytest.mark.skipif(not Path("data_out/subdivisions.json").exists(), reason="run `python -m etl wikidata-subdivisions` first")
def test_subdivisions_endpoint(api_client: TestClient) -> None:
    br = SubdivisionList.model_validate(api_client.get("/v1/countries/BR/subdivisions").json())
    by = {x.code: x for x in br.items}
    assert len(br.items) == 27 and by["BR-SP"].capital == "São Paulo"
    assert by["BR-SP"].population and by["BR-SP"].population.value > 40_000_000
    assert by["BR-RS"].flag and by["BR-RS"].flag.license and by["BR-RS"].flag.url.startswith("https://")
    assert br.sources[0].id == "wikidata"
    assert api_client.get("/v1/countries/ZZ/subdivisions").status_code == 404
