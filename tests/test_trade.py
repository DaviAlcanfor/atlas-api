"""spec 029 phase 2: BACI aggregation (offline) and GET /v1/countries/{iso2}/trade on a sample import."""
import csv
import io
from pathlib import Path

import pytest
from etl.baci.pipeline import aggregate, country_iso2
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas_api.facts import import_trade

CSV = """t,i,j,k,v,q
2024,76,156,270900,600,1
2024,76,840,120190,300,1
2024,76,156,120110,100,1
2024,156,76,10121,50,1
2024,490,76,854231,25,1
2024,840,76,270900,25,1
"""


def test_country_codes() -> None:
    rows = [{"country_code": "76", "country_iso2": "BR", "country_iso3": "BRA"},
            {"country_code": "516", "country_iso2": "", "country_iso3": "NAM"},  # "NA" lost as missing in BACI's file
            {"country_code": "490", "country_iso2": "", "country_iso3": "S19"}]  # Other Asia, nes: no ISO2, never a partner
    assert country_iso2(rows) == {"76": "BR", "516": "NA"}


def test_aggregate() -> None:
    iso = {"76": "BR", "156": "CN", "840": "US"}
    labels = {"2709": "Óleos brutos", "1201": "Soja", "0101": "Cavalos", "8542": "Circuitos"}
    out = aggregate(csv.reader(io.StringIO(CSV)), iso, labels)
    br = out["BR"]
    assert br["exports_usd"] == 1_000_000 and br["imports_usd"] == 100_000  # thousand USD -> USD; 490 counts in totals
    assert br["top_exports"] == [{"hs": "2709", "label": "Óleos brutos", "value_usd": 600_000, "share": 0.6},
                                 {"hs": "1201", "label": "Soja", "value_usd": 400_000, "share": 0.4}]
    assert br["top_destinations"] == [{"iso2": "CN", "value_usd": 700_000, "share": 0.7},
                                      {"iso2": "US", "value_usd": 300_000, "share": 0.3}]
    assert [x["iso2"] for x in br["top_origins"]] == ["CN", "US"]  # 490 left out of the partner list
    assert out["CN"]["top_exports"][0]["hs"] == "0101"  # HS code read as text, leading zero restored
    with pytest.raises(SystemExit):
        aggregate(csv.reader(io.StringIO(CSV)), iso, {"2709": "x"})  # never invent a heading


def test_trade_endpoint(api_client: TestClient) -> None:
    eng = create_engine(api_client.app.state.test_url)  # type: ignore[attr-defined]
    with Session(eng) as s, s.begin():
        n = import_trade(s, Path("tests/fixtures/trade_sample.json"))
    eng.dispose()
    assert n == 1  # HK is not a polity: stored only as BR's partner
    t = api_client.get("/v1/countries/BR/trade").json()
    assert t["year"] == 2024 and t["exports_usd"] == 1000 and t["imports_usd"] == 800
    assert t["top_exports"][0] == {"hs": "2709", "label": "Óleos brutos de petróleo ou de minerais betuminosos",
                                   "value_usd": 600, "share": 0.6}
    assert [x["iso2"] for x in t["top_destinations"]] == ["CN", "HK"] and t["top_origins"][0]["share"] == 1.0
    assert [x["id"] for x in t["sources"]] == ["baci", "mdic-sh"]
    assert "atualizada em 30/01/2026" in t["sources"][0]["title"] and t["sources"][0]["license"] == "Etalab 2.0"
    assert api_client.get("/v1/countries/UY/trade").status_code == 404  # country without BACI data
    assert api_client.get("/v1/countries/ZZ/trade").status_code == 404
