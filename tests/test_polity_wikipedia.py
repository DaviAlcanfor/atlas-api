"""spec 042: Wikipedia summary of historical entities. parse()/titles() on a recorded REST answer (no network) + the endpoints."""
import json
from pathlib import Path

from etl.wikipedia.polities import parse, titles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas_api.importer.facts import import_polity_summaries
from atlas_api.schemas import WikipediaSummary

RAW = json.loads(Path("tests/fixtures/wikipedia_summary_otomano_pt.json").read_text(encoding="utf-8"))
NOW = "2026-11-18T00:00:00+00:00"


def test_parse_and_titles() -> None:
    row = parse("pt", RAW, NOW)
    assert row and row["title"] == RAW["title"] and row["extract"] == RAW["extract"].strip()
    assert row["license"] == "CC BY-SA 4.0" and row["page_url"].startswith("https://pt.wikipedia.org/wiki/")
    assert parse("pt", {**RAW, "type": "disambiguation"}, NOW) is None and parse("pt", {**RAW, "extract": ""}, NOW) is None
    rows = [{"Type": "POLITY", "Name": "A", "Wikidata": "Q1", "Wikipedia": "Alpha"},
            {"Type": "POLITY", "Name": "(R)", "Wikidata": "Q9", "Wikipedia": "Rel"},   # relation: skipped
            {"Type": "POLITY", "Name": "B", "Wikidata": "Q2", "Wikipedia": ""}]
    labs = {"Q1": {"wikipedia_pt": "https://pt.wikipedia.org/wiki/Alfa_(imp%C3%A9rio)"}}
    assert titles(rows, labs) == {"Q1": [("pt", "Alfa (império)"), ("en", "Alpha")], "Q2": []}


def test_endpoints(api_client: TestClient, tmp_path: Path) -> None:
    row = parse("pt", RAW, NOW)
    assert row
    f = tmp_path / "polity_summaries.json"
    # Q155 is Brazil's Q-id in content/polities: exercises PolityDetail.wikipedia_summary (text is the recorded Ottoman one)
    f.write_text(json.dumps({"items": [{"wikidata_qid": "Q12560", **row}, {"wikidata_qid": "Q155", **row}]}), encoding="utf-8")
    eng = create_engine(api_client.app.state.test_url)  # type: ignore[attr-defined]
    with Session(eng) as s, s.begin():
        assert import_polity_summaries(s, f) == 2
    eng.dispose()
    r = api_client.get("/v1/entities/Q12560/wikipedia")
    assert r.status_code == 200 and "thumbnail_url" not in r.json()
    w = WikipediaSummary.model_validate(r.json())
    assert w.lang == "pt" and w.text == row["extract"] and w.license_url.endswith("by-sa/4.0/")
    assert "CC BY-SA 4.0" in w.attribution and w.title in w.attribution
    assert api_client.get("/v1/entities/Q1/wikipedia").status_code == 404
    assert api_client.get("/v1/polities/brazil").json()["wikipedia_summary"]["title"] == w.title
    assert api_client.get("/v1/polities/argentina").json()["wikipedia_summary"] is None
