"""spec 022: the country summary formula (offline) and the guard on the AI rewording."""
from etl.ai.summaries import big, first_sentence, keeps_facts, template


def _facts(**kw: object) -> dict[str, object]:
    base = {"name": "Brasil", "region": "América do Sul", "capital": "Brasília", "area": 8509360.8,
            "population": {"value": 214211951, "year": 2026}, "history": "A história do Brasil começa cedo. Depois veio mais.",
            "leaders": [{"office": "presidente", "name": "Fulano", "party": {"name": "Partido X"}, "start": "2023-01-01"}],
            "ind": {"HDR.HDI": {"value": 0.786, "year": 2023, "median": 0.761},
                    "FP.CPI.TOTL.ZG": {"value": 5.04, "year": 2025, "median": None}}, "sources": []}
    return {**base, **kw}


def test_formula_uses_only_the_facts_it_has() -> None:
    t = template(_facts())
    assert t["tldr"].startswith("Brasil fica na América do Sul, com capital em Brasília. Tem 8,5 milhões de km² e 214 milhões de habitantes (2026).")
    assert "A história do Brasil começa cedo." in t["tldr"] and "acima da mediana mundial (0,761)" in t["tldr"]
    assert t["now"] == "No governo: presidente: Fulano (Partido X), desde 2023. Dados mais recentes: inflação de 5% (2025)."
    bare = template(_facts(region=None, capital=None, area=None, population=None, history=None, leaders=[], ind={}))
    assert bare == {"tldr": "Brasil fica no mapa.", "now": ""}


def test_helpers() -> None:
    assert big(214_211_951) == "214 milhões" and big(2.3e12) == "2,3 trilhões" and big(1_000_000) == "1 milhão" and big(950) == "950"
    assert first_sentence("O Japão (japonês: 日本) é um país insular no leste da Ásia. Segunda frase.") == "O Japão é um país insular no leste da Ásia."


def test_rewording_may_not_change_numbers() -> None:
    old = {"tldr": "Tem 214 milhões de habitantes (2026).", "now": "Inflação de 5% (2025)."}
    assert keeps_facts({"tldr": "Sua população é de 214 milhões (2026).", "now": "A inflação foi de 5% em 2025."}, old)
    assert not keeps_facts({"tldr": "Tem 215 milhões de habitantes (2026).", "now": ""}, old)  # changed figure
    assert not keeps_facts({"tldr": "", "now": "Inflação de 5% (2025)."}, old)


def test_brief_endpoint(api_client) -> None:  # type: ignore[no-untyped-def]
    """spec 022: GET /v1/countries/{iso2}/brief serves the imported summary with its sources."""
    from pathlib import Path

    import pytest

    if not Path("data_out/summaries.json").exists():
        pytest.skip("run `python -m etl ai-summaries` first")
    b = api_client.get("/v1/countries/BR/brief").json()
    assert b["tldr"].count("Brasil") >= 1 and b["method"].startswith("template") and {s["id"] for s in b["sources"]} >= {"wikidata"}
    assert api_client.get("/v1/countries/ZZ/brief").status_code == 404
