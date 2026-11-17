"""spec 024: subdivision facts (rules offline) and GET /v1/countries/{iso2}/subdivisions on the real data_out/ file."""
from pathlib import Path

import pytest
from etl.wikidata.subdivisions import area_codes, build, pick_population
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
    assert out[0]["area_codes"] == []


def test_area_codes_curated_wins_and_split() -> None:
    """spec 026: Wikidata strings may pack several codes; the curated table (by ISO 3166-2) wins over Wikidata."""
    codes = area_codes([_row(s="http://www.wikidata.org/entity/Q2", d="06 0774"), _row(s="http://www.wikidata.org/entity/Q2", d="06"),
                        _row(s="http://www.wikidata.org/entity/Q1", d="97")])
    assert codes == {"Q2": ["06", "0774"], "Q1": ["97"]}
    facts = [_row(s="http://www.wikidata.org/entity/Q1", sLabel="Um", iso="BR-AM"), _row(s="http://www.wikidata.org/entity/Q2", sLabel="Dois")]
    out = build([("Q1", "Um"), ("Q2", "Dois")], facts, [], codes, {"BR-AM": ["92", "97"]})
    assert [x["area_codes"] for x in out] == [["92", "97"], ["06", "0774"]]


@pytest.mark.skipif(not Path("data_out/subdivisions.json").exists(), reason="run `python -m etl wikidata-subdivisions` first")
def test_subdivisions_endpoint(api_client: TestClient) -> None:
    br = SubdivisionList.model_validate(api_client.get("/v1/countries/BR/subdivisions").json())
    by = {x.code: x for x in br.items}
    assert len(br.items) == 27 and by["BR-SP"].capital == "São Paulo"
    assert by["BR-SP"].population and by["BR-SP"].population.value > 40_000_000
    assert by["BR-RS"].flag and by["BR-RS"].flag.license and by["BR-RS"].flag.url.startswith("https://")
    assert "wikidata" in {x.id for x in br.sources}
    assert by["BR-SP"].area_codes[0] == "11" and {"anatel", "wikidata"} <= {x.id for x in br.sources}  # spec 026
    assert api_client.get("/v1/countries/ZZ/subdivisions").status_code == 404
    if Path("data_out/shdi.json").exists():  # CR-011
        assert by["BR-DF"].hdi and 0.8 < by["BR-DF"].hdi.value < 0.9 and by["BR-DF"].hdi.year >= 2023
        assert "gdl-shdi" in {x.id for x in br.sources}
    if Path("data_out/heads.json").exists():  # CR-011
        sp = by["BR-SP"].head
        assert sp and sp.office == "Governador" and sp.source_id == "wikipedia-heads-br" and sp.wikidata_id
        assert "wikipedia-heads-br" in {x.id for x in br.sources}


# --- phase 2 (CR-011): subnational HDI + head -------------------------------------------------------------------------------

def test_shdi_match_needs_unique_name_and_population() -> None:
    from etl.gdl.pipeline import match, norm
    assert norm("Província de São Paulo") == norm("Sao Paulo") == "sao paulo"
    subs = [{"wikidata_id": "Q1", "names": {"São Paulo"}, "population": 46_000_000},
            {"wikidata_id": "Q2", "names": {"Nord"}, "population": 2_600_000},   # department; GDL "Nord" = old region (4 M)
            {"wikidata_id": "Q3", "names": {"Centro", "Washington"}, "population": 700_000},
            {"wikidata_id": "Q4", "names": {"Washington"}, "population": 7_000_000}]
    regions = [{"region": "Sao Paulo", "shdi": 0.813, "year": 2023, "pop": 45_000_000},
               {"region": "Nord", "shdi": 0.897, "year": 2023, "pop": 4_000_000},
               {"region": "Washington", "shdi": 0.95, "year": 2023, "pop": 7_000_000}]  # two owners: ambiguous
    got, rejected = match(regions, subs)
    assert got == {"Q1": {"value": 0.813, "year": 2023}} and rejected == 1


def test_head_list_parsing() -> None:
    from etl.wikipedia.heads import list_rows, parse_date, pick
    assert parse_date("1.º de janeiro de 2023") == "2023-01-01" and parse_date("April 10, 2017") == "2017-04-10"
    assert parse_date("12 June 2024(2 years, 157 days)") == "2024-06-12" and parse_date("—") is None
    html = """<table><tr><th>Unidade federativa</th><th colspan="2">Governador</th><th>No cargo desde</th></tr>
      <tr><td rowspan="2"><a href="/wiki/Acre">Acre</a> (<a href="/wiki/Lista_de_governadores_do_Acre">lista</a>)</td>
          <td>img</td><td><a href="/wiki/Mailza_Assis">Mailza Assis</a><sup>[1]</sup></td><td>2 de abril de 2026</td></tr></table>"""
    rows = list_rows(html, [("Unidade federativa", "Governador", "No cargo desde", "Governador")])
    assert rows == [{"unit_titles": ["Acre", "Lista de governadores do Acre", "Acre"], "name": "Mailza Assis",
                     "person_title": "Mailza Assis", "since": "2026-04-02", "office": "Governador"}]
    w = "http://www.wikidata.org/entity/"
    cands = [_row(h=w + "Q1", hLabel="Velho", start="2019-01-01T00:00:00Z"),
             _row(h=w + "Q2", hLabel="Novo", start="2023-01-01T00:00:00Z", end="2030-12-31T00:00:00Z")]
    assert pick(cands, "2026-11-16") == {"name": "Novo", "office": None, "since": "2023-01-01", "wikidata_id": "Q2",
                                         "source_id": "wikidata"}  # a future end date is a scheduled term end
    assert pick([cands[0], _row(h=w + "Q3", hLabel="X", start="2025-01-01T00:00:00Z", end="2025-06-01T00:00:00Z")],
                "2026-11-16") is None  # the latest holder has left: nobody known is current
