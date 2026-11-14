"""spec 027: ranking of every country by one indicator (the map's ranking layer)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas_api.schemas import IndicatorCatalog, IndicatorRanking

pytestmark = pytest.mark.skipif(not Path("data_out/worldbank.json").exists(), reason="needs the World Bank / UNDP data_out files")


def test_catalog_lists_rankable_indicators_plus_density(api_client: TestClient) -> None:
    cat = IndicatorCatalog.model_validate(api_client.get("/v1/indicators").json())
    ids = {x.id for x in cat.items}
    assert {"HDR.HDI", "SP.POP.TOTL", "density"} <= ids and "PA.NUS.PPP" not in ids
    assert [x.label for x in cat.items] == sorted(x.label for x in cat.items)


def test_ranking_is_ordered_and_competition_ranked(api_client: TestClient) -> None:
    r = IndicatorRanking.model_validate(api_client.get("/v1/indicators/SP.POP.TOTL/ranking").json())
    assert [x.iso2 for x in r.items[:2]] == ["IN", "CN"] and r.items[0].rank == 1
    assert all(a.value >= b.value and a.rank <= b.rank for a, b in zip(r.items, r.items[1:], strict=False))
    d = IndicatorRanking.model_validate(api_client.get("/v1/indicators/density/ranking").json())
    assert d.unit == "hab/km²" and d.items[0].iso2 in {"MC", "SG"} and d.sources[0].id == "wikidata"
    assert api_client.get("/v1/indicators/PA.NUS.PPP/ranking").status_code == 404
    assert api_client.get("/v1/indicators/NOPE/ranking").status_code == 404
