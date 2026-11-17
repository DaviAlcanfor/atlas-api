"""spec 033: Nobel laureates per country. build() on recorded API responses (no network) + the endpoint on a sample import."""
import json
from pathlib import Path

from etl.nobel.pipeline import SOURCE, build, qid_to_iso2
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas_api.facts import import_nobel
from atlas_api.schemas import CountryNobel

RAW = json.loads(Path("tests/fixtures/nobel_laureates_sample.json").read_text(encoding="utf-8"))["laureates"]


def test_build() -> None:
    iso = qid_to_iso2(Path("content/polities"))
    assert iso["Q55"] == "NL" and iso["Q155"] == "BR"
    rows = build(RAW, iso)
    medawar = next(r for r in rows if r["name"] == "Peter Medawar")
    assert medawar["origin_iso2"] == "BR" and medawar["category"] == "medicine" and medawar["year"] == 1960
    assert medawar["affiliations"][0]["iso2"] == "GB"
    assert medawar["motivation"] == "for discovery of acquired immunological tolerance"  # English, verbatim
    lorentz = next(r for r in rows if r["name"] == "Hendrik A. Lorentz")
    assert lorentz["origin_iso2"] == "NL" and lorentz["affiliations"][0]["iso2"] == "NL"  # Q55 alias
    red_cross = [r for r in rows if r["kind"] == "organization"]
    assert len(red_cross) == 3 and {r["origin_iso2"] for r in red_cross} == {"CH"}  # founded in Geneva; 3 Peace prizes
    assert rows == sorted(rows, key=lambda r: (r["year"], r["category"], r["laureate_id"]))


def test_nobel_endpoint(api_client: TestClient, tmp_path: Path) -> None:
    f = tmp_path / "nobel.json"
    f.write_text(json.dumps({"source": {**SOURCE, "retrieved_at": "2026-11-17T00:00:00+00:00"},
                             "items": build(RAW, qid_to_iso2(Path("content/polities")))}), encoding="utf-8")
    eng = create_engine(api_client.app.state.test_url)  # type: ignore[attr-defined]
    with Session(eng) as s, s.begin():
        assert import_nobel(s, f) == 5
    eng.dispose()
    br = CountryNobel.model_validate(api_client.get("/v1/countries/BR/nobel").json())
    assert (br.born, br.affiliated) == (1, 0) and br.items[0].name == "Peter Medawar"
    assert br.sources[0].license == "CC0 1.0"
    gb = CountryNobel.model_validate(api_client.get("/v1/countries/GB/nobel").json())
    assert (gb.born, gb.affiliated) == (0, 1) and not gb.items[0].born_here
    ch = CountryNobel.model_validate(api_client.get("/v1/countries/CH/nobel").json())
    assert ch.born == 3 and [x.year for x in ch.items] == sorted((x.year for x in ch.items), reverse=True)
    uy = api_client.get("/v1/countries/UY/nobel").json()
    assert uy["items"] == [] and uy["sources"] == []
    assert api_client.get("/v1/countries/ZZ/nobel").status_code == 404
