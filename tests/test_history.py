"""spec 016 stage 1: condensing pt.wikipedia history articles (offline) and GET /v1/countries/{iso2}/history."""
from pathlib import Path

import pytest
from etl.wikipedia.history import condense, parse_years, split
from fastapi.testclient import TestClient

from atlas_api.schemas import CountryHistory

LONG = "Frase longa sobre o período em questão, com detalhes suficientes para passar do filtro. " * 3


def test_parse_years() -> None:
    assert parse_years("Império (1822–1889)") == ("Império", 1822, 1889)
    assert parse_years("Período pré-colonial (até 1500)") == ("Período pré-colonial", None, 1500)
    assert parse_years("República (1889–presente)") == ("República", 1889, None)
    assert parse_years("Antiguidade (3100 a.C.–332 a.C.)") == ("Antiguidade", -3100, -332)
    assert parse_years("Os Habsburgo") == ("Os Habsburgo", None, None)


def test_condense_drops_maintenance_tags() -> None:
    assert condense("Dom Pedro II governou o Brasil por quase cinquenta anos.[carece de fontes]? E caiu em 1889.[3]", 500) == (
        "Dom Pedro II governou o Brasil por quase cinquenta anos. E caiu em 1889.")


def test_condense_cuts_at_sentence() -> None:
    out = condense("Primeira frase bem longa sobre história. Segunda frase também longa. " * 20, 200)
    assert len(out) <= 200 and out.endswith(".")


def test_split_history_article_and_fallbacks() -> None:
    art = f"{LONG}\n== Colônia (1500–1815) ==\n{LONG}\n== Império (1822–1889) ==\n{LONG}\n== B (1) ==\n{LONG}\n== Referências ==\n{LONG}"
    h = split(art)
    assert h["summary"] and [p["title"] for p in h["periods"]] == ["Colônia", "Império", "B"]
    # one big level-2 section: periods come from level 3 (Japan)
    jp = split(f"{LONG}\n== Pré-história e antigo ==\n=== Jomon ===\n{LONG}\n=== Yayoi ===\n{LONG}\n=== Kofun ===\n{LONG}")
    assert [p["title"] for p in jp["periods"]] == ["Jomon", "Yayoi", "Kofun"]
    # no history article: the country page's "História" section (Mali)
    ml = split(f"{LONG}\n== Etimologia ==\n{LONG}\n== História ==\nO território do atual Mali. {LONG}\n== Geografia ==\n{LONG}",
               country_article=True)
    assert ml["summary"] and ml["summary"].startswith("O território") and ml["periods"] == []


@pytest.mark.skipif(not Path("data_out/history.json").exists(), reason="run `python -m etl wikipedia-history` first")
def test_history_endpoint(api_client: TestClient) -> None:
    h = CountryHistory.model_validate(api_client.get("/v1/countries/BR/history").json())
    assert h.summary and "Brasil" in h.summary
    titles = [p.title for p in h.periods]
    assert "Império" in titles and h.periods[0].id == "br-1"
    imp = next(p for p in h.periods if p.title == "Império")
    assert (imp.year_start, imp.year_end) == (1822, 1889)
    assert h.sources[0].license == "CC BY-SA 4.0" and "oldid=" in (h.sources[0].url or "")
    assert api_client.get("/v1/countries/ZZ/history").status_code == 404


def test_event_years_have_no_year_zero() -> None:
    from etl.wikidata.events import year_of
    assert year_of("1822-09-07T00:00:00Z") == 1822
    assert year_of("0000-01-01T00:00:00Z") == -1  # astronomical 0 = 1 BCE
    assert year_of("-0489-01-01T00:00:00Z") == -490  # Marathon
    assert year_of(None) is None


def test_pick_keeps_the_most_linked_events_of_the_states() -> None:
    from etl.wikidata.events import pick
    links = {"Q1": ("Q198", 50, {"Q155"}), "Q2": ("Q198", 90, {"Q217230"}), "Q3": ("Q198", 99, {"Q45"}), "Q4": ("Q178561", 10, {"Q155"})}
    assert pick(links, {"Q155", "Q217230"}) == ["Q2", "Q1", "Q4"]  # predecessor (Empire of Brazil) counts; Portugal does not


@pytest.mark.skipif(not Path("data_out/events.json").exists(), reason="run `python -m etl wikidata-events` first")
def test_history_events(api_client: TestClient) -> None:
    h = CountryHistory.model_validate(api_client.get("/v1/countries/BR/history").json())
    titles = {e.title for e in h.events}
    assert "Guerra do Paraguai" in titles and all(e.id.startswith("Q") for e in h.events)
    assert [e.year_start for e in h.events] == sorted(e.year_start for e in h.events)
    imperio = next(p for p in h.periods if p.title == "Império")
    assert imperio.event_count >= 3  # Cisplatina, Farrapos, Paraguai... fall inside 1822-1889
    assert {s.id for s in h.sources} == {"wikipedia-pt", "wikidata"}
