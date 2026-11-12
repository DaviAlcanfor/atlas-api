"""Pure transforms of the v1.2 ETLs / import stats (specs 009, 015, 017): no network, no DB."""
import math
from datetime import date, timedelta

from etl.fx.pipeline import ecb_rows, secondary_rows, wednesdays
from etl.undp.pipeline import build as undp_build
from etl.wikidata.languages import attributes, classify
from etl.wikidata.pipeline import composition

from atlas_api.facts import _ranks, currency_stats

E = "http://www.wikidata.org/entity/"


def _r(**kw: str) -> dict:
    return {k: {"value": v} for k, v in kw.items()}


def _info(q: str, name: str, **kw: str) -> dict:
    base = {"l": E + q, "lLabel": name, "isLang": "true", "isSign": "false", "isDead": "false",
            "isAdmin": "false"}
    return _r(**{**base, **kw})


def test_classify_languages_order_and_rules() -> None:
    cand = [
        _r(l=E + "Q5146", kind="official"),
        _r(l=E + "Q750553", kind="indigenous_to"),  # pt-BR: a variety of the official one
        _r(l=E + "Q1248654", kind="sub", sub=E + "Q1", subLabel="Serafina Corrêa"),
        _r(l=E + "Q1248654", kind="sub", sub=E + "Q9", subLabel="Mercosul"),  # not admin
        _r(l=E + "Q1248654", kind="indigenous_to"),
        _r(l=E + "Q3436689", kind="used"),  # Libras
        _r(l=E + "Q34333", kind="used"),  # Nheengatu: Tupian family -> indigenous via yaml
        _r(l=E + "Q188", kind="used"),  # German: immigrant
        _r(l=E + "Q99", kind="used"),  # dead language
        _r(l=E + "Q7", kind="used"),  # not a language at all
    ]
    info = [_info("Q5146", "português", c1="pt"), _info("Q750553", "português brasileiro"),
            _info("Q1248654", "talian", c3="vec"), _info("Q3436689", "Libras", isSign="true"),
            _info("Q34333", "nheengatu", c3="yrl", st=E + "Q20672089"), _info("Q188", "alemão"),
            _info("Q99", "tupinambá", isDead="true"), _info("Q7", "Caipora", isLang="false"),
            _r(l=E + "Q1", lLabel="Serafina Corrêa", isAdmin="true", isLang="false"),
            _r(l=E + "Q9", lLabel="Mercosul", isAdmin="false", isLang="false")]
    anc = [_r(l=E + "Q750553", a=E + "Q5146"), _r(l=E + "Q34333", a=E + "Q12"),
           _r(l=E + "Q34333", a=E + "Q13")]
    spk = [_r(l=E + "Q34333", n="6000", when="2010-01-01T00:00:00Z", place=E + "Q155"),
           _r(l=E + "Q34333", n="20000", when="2005-01-01T00:00:00Z", place=E + "Q155"),
           _r(l=E + "Q188", n="90000000", place=E + "Q183")]  # Germany: not Brazil -> ignored
    attrs = attributes({"info": info}, anc, spk)
    fams = {"Q13": {"label": "tupi", "regions": ["América do Sul"]}, "Q12": {"regions": []}}
    out = classify("Q155", "América do Sul", cand, attrs, fams)
    assert [(x["name"], x["status"]) for x in out] == [
        ("português", "official"), ("talian", "co_official"), ("nheengatu", "indigenous"),
        ("alemão", "immigrant"), ("Libras", "sign"), ("tupinambá", "historical")]
    tal, nhe, de = out[1], out[2], out[3]
    assert tal["where"] == "Serafina Corrêa" and tal["code"] == "vec"
    assert nhe["speakers"] == {"value": 6000, "year": 2010} and nhe["family"] == "tupi"
    assert nhe["endangerment"] == "severamente em perigo" and de["speakers"] is None
    # same family outside its region is not "indigenous"
    assert classify("Q183", "Europa", [_r(l=E + "Q34333", kind="used")], attrs, fams)[0][
        "status"] == "immigrant"


def test_composition_needs_80_to_105_percent() -> None:
    rows = [_r(iso2="BR", vLabel="catolicismo", share="0.5", when="2010-01-01T00:00:00Z"),
            _r(iso2="BR", vLabel="protestantismo", share="0.3", when="2010-01-01T00:00:00Z"),
            _r(iso2="BR", vLabel="catolicismo", share="0.6", when="2022-01-01T00:00:00Z"),  # 60%
            _r(iso2="XX", vLabel="a", share="50"), _r(iso2="XX", vLabel="b", share="45"),
            _r(iso2="YY", vLabel="a", share="0.4")]
    got = composition(rows)
    assert got["BR"] == {"year": 2010, "items": [{"label": "catolicismo", "share": 0.5},
                                                 {"label": "protestantismo", "share": 0.3}]}
    assert got["XX"]["year"] is None and got["XX"]["items"][0]["share"] == 0.5  # percent read
    assert "YY" not in got


def test_ranks_ties_share_a_rank() -> None:
    assert _ranks({"A": 3.0, "B": 5.0, "C": 3.0, "D": 1.0}) == {"B": 1, "A": 2, "C": 2, "D": 4}


def test_currency_stats() -> None:
    start = date(2020, 1, 1)
    days = [start + timedelta(days=i) for i in range(0, 6 * 365, 1)]
    series = [(d, 2.0 if i < len(days) - 365 else 1.0 + (i % 2) * 0.1) for i, d in enumerate(days)]
    st = currency_stats(series)
    assert st["change_1y"] is not None and math.isclose(st["change_1y"], 1.1 / 2.0 - 1)
    assert st["change_5y"] is not None and math.isclose(st["change_5y"], 1.1 / 2.0 - 1)
    assert st["max_drawdown_1y"] is not None and math.isclose(st["max_drawdown_1y"], 1.0 / 2.0 - 1)
    assert st["volatility_1y"] is not None and st["volatility_1y"] > 1
    short = currency_stats([(start, 1.0), (start + timedelta(days=7), 1.1)])
    assert short["change_1y"] is None and short["volatility_1y"] is None
    assert short["max_drawdown_1y"] == 0.0


def test_fx_rows_and_dates() -> None:
    ecb = ecb_rows([{"data": [{"date": "2026-01-02", "base": "EUR", "quote": "BRL", "rate": 6.1},
                              {"date": "2026-01-02", "base": "EUR", "quote": "EUR", "rate": 1.0}]},
                    {"data": None}])
    assert ecb == [["2026-01-02", "BRL", 6.1, "ecb"], ["2026-01-02", "EUR", 1.0, "ecb"]]
    sec = secondary_rows([{"data": {"date": "2026-01-07", "eur": {"ars": 1500.5, "brl": 6.2,
                                                                  "btc": 0.00001, "xyz": 0}}},
                          {"data": None}], wanted={"ARS", "BRL", "XYZ"}, ecb_codes={"BRL"})
    assert sec == [["2026-01-07", "ARS", 1500.5, "exchange-api"]]  # ECB wins, junk dropped
    assert wednesdays(date(2024, 3, 6), date(2024, 3, 20)) == [
        date(2024, 3, 6), date(2024, 3, 13), date(2024, 3, 20)]


def test_undp_build_maps_iso3_and_skips_blanks() -> None:
    text = "iso3,country,hdi_2022,hdi_2023,mys_2023,le_2023\nBRA,Brazil,0.76,,8.4,75\nZZA,World,0.7,0.7,8,72\n"
    rows = undp_build(text, {"BRA": "BR"})
    assert rows == [{"iso2": "BR", "indicator_id": "HDR.HDI", "year": 2022, "value": 0.76},
                    {"iso2": "BR", "indicator_id": "HDR.MYS", "year": 2023, "value": 8.4}]
