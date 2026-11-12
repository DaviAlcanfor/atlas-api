"""v1.2 part A (CR-003) end to end on the real data_out/ files: specs 009, 015, 017, 019."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from atlas_api.schemas import (
    CountryDetail,
    CountryEconomy,
    CountryList,
    CountryProfile,
    CurrencyDetail,
    CurrencyHistory,
    EconomyCompare,
)

ORDER = ["official", "co_official", "indigenous", "immigrant", "sign", "historical"]


def test_several_capitals(api_client: TestClient) -> None:  # spec 019
    by = {c.iso2: c for c in CountryList.model_validate(api_client.get("/v1/countries").json()).items}
    assert len(by["ZA"].capital_coords) == 3 and len(by["BO"].capital_coords) == 2
    assert by["DK"].capital_coords[0].name == "Copenhague"


def test_languages_spoken(api_client: TestClient) -> None:  # spec 017
    br = CountryDetail.model_validate(api_client.get("/v1/countries/BR").json())
    langs = br.languages_spoken
    assert langs and langs[0].status == "official" and langs[0].code == "pt"
    assert [ORDER.index(x.status) for x in langs] == sorted(ORDER.index(x.status) for x in langs)
    statuses = {x.status for x in langs}
    assert {"official", "co_official", "indigenous", "immigrant", "sign"} <= statuses
    assert any(x.status == "sign" and "sinais" in x.name.lower() for x in langs)  # Libras
    assert any(x.name.lower() == "talian" and x.where for x in langs)


def test_profile(api_client: TestClient) -> None:  # spec 015
    p = CountryProfile.model_validate(api_client.get("/v1/countries/BR/profile").json())
    assert [g.id for g in p.groups] == ["life", "society", "income", "environment"]
    life = {i.id: i for i in p.groups[0].indicators}
    le = life["SP.DYN.LE00.IN"]
    assert le.rank and le.rank_of and 1 <= le.rank <= le.rank_of and le.world
    assert le.world.min <= le.value <= le.world.max and le.region_avg
    assert "HDR.HDI" in life and 0 < life["HDR.HDI"].value < 1
    assert {s.id for s in p.sources} >= {"worldbank", "undp-hdr"}
    assert api_client.get("/v1/countries/ZZ/profile").status_code == 404


def test_economy_and_compare(api_client: TestClient) -> None:  # spec 009
    e = CountryEconomy.model_validate(api_client.get("/v1/countries/BR/economy").json())
    gdp = next(i for i in e.indicators if i.id == "NY.GDP.MKTP.CD")
    assert gdp.value and gdp.year and 10 <= len(gdp.series) <= 20
    assert [p.year for p in gdp.series] == sorted(p.year for p in gdp.series)
    assert gdp.series[-1].year == gdp.year
    c = EconomyCompare.model_validate(
        api_client.get("/v1/economy/compare?countries=BR,AR,MX&ids=FP.CPI.TOTL.ZG").json())
    assert c.countries == ["BR", "AR", "MX"] and len(c.indicators) == 1
    assert set(c.indicators[0].values) == {"BR", "AR", "MX"}
    full = EconomyCompare.model_validate(api_client.get("/v1/economy/compare?countries=BR,AR").json())
    assert len(full.indicators) == 10


@pytest.mark.parametrize(("url", "status"), [
    ("/v1/economy/compare?countries=BR", 422),
    ("/v1/economy/compare?countries=BR,AR,MX,CL,PE,UY", 422),
    ("/v1/economy/compare?countries=BR,br", 422),
    ("/v1/economy/compare?countries=BR,ZZ", 404),
    ("/v1/economy/compare?countries=BR,AR&ids=NOPE", 422),
    ("/v1/currencies/brl", 422),
    ("/v1/currencies/XXX", 404),
    ("/v1/currencies/BRL/history?vs=USD,EUR,JPY,GBP,CHF", 422),
    ("/v1/currencies/BRL/history?vs=XXX", 404),
    ("/v1/currencies/BRL/history?from=1980-01-01&to=2026-01-01", 422),
    ("/v1/currencies/BRL/history?from=2026-01-02&to=2026-01-01", 422),
])
def test_v12_errors(api_client: TestClient, url: str, status: int) -> None:
    r = api_client.get(url)
    assert r.status_code == status and r.headers["content-type"].startswith("application/problem+json")


def test_currency(api_client: TestClient) -> None:  # spec 009
    c = CurrencyDetail.model_validate(api_client.get("/v1/currencies/BRL").json())
    assert c.countries == ["BR"] and c.rates and c.rates.base == "BRL"
    usd = next(i.rate for i in c.rates.items if i.code == "USD")
    assert 0.05 < usd < 1  # 1 BRL in USD
    assert c.stats and c.stats.volatility_1y and c.stats.change_5y is not None
    assert {s.id for s in c.sources} >= {"ecb", "wikidata"}
    ars = CurrencyDetail.model_validate(api_client.get("/v1/currencies/ARS").json())
    assert ars.rates and any(s.id == "exchange-api" for s in ars.sources)  # secondary source


def test_currency_history(api_client: TestClient) -> None:  # spec 009
    h = CurrencyHistory.model_validate(api_client.get("/v1/currencies/BRL/history?vs=USD,EUR").json())
    assert h.base == "BRL" and h.vs == ["USD", "EUR"] and 200 < len(h.items) < 270  # daily, 1 year
    assert h.source.id == "ecb" and set(h.items[-1].rates) == {"USD", "EUR"}
    dates = [date.fromisoformat(i.date) for i in h.items]
    assert dates == sorted(dates)
    long = CurrencyHistory.model_validate(
        api_client.get("/v1/currencies/BRL/history?vs=USD&from=2016-01-01&to=2025-12-31").json())
    assert 500 < len(long.items) < 530  # weekly above 2 years
    weeks = [date.fromisoformat(i.date).isocalendar()[:2] for i in long.items]
    assert len(weeks) == len(set(weeks))
