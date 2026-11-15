"""spec 008: news rules (offline) and the news endpoints on a sample import."""
import re
from pathlib import Path

from etl.news.pipeline import apply_policy, candidates, clean_url, name_index, parse_article
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas_api.facts import import_news


def _names() -> list[tuple[re.Pattern[str], str]]:
    rows = [{"iso2": {"value": "KR"}, "label": {"value": "Coreia do Sul"}}, {"iso2": {"value": "BR"}, "label": {"value": "Brasil"}},
            {"iso2": {"value": "BR"}, "demonym": {"value": "brasileiro"}}, {"iso2": {"value": "IR"}, "label": {"value": "Irã"}}]
    return name_index(rows)


def test_parse_and_clean() -> None:
    a = {"title": "  Rússia  e Ucrânia retomam negociações ", "url": "https://Ex.org/n?id=1&utm_source=x#top", "domain": "ex.org",
         "language": "Portuguese", "seendate": "20261114T101500Z"}
    it = parse_article(a)
    assert it is not None and it["url"] == "https://ex.org/n?id=1" and it["language"] == "pt"
    assert it["title"] == "Rússia e Ucrânia retomam negociações" and it["published_at"] == "2026-11-14T10:15:00+00:00"
    assert parse_article({**a, "seendate": "ontem"}) is None and parse_article({**a, "title": "curto"}) is None
    assert clean_url("https://x.org/a?b=1&fbclid=9") == "https://x.org/a?b=1"


def test_candidates_by_name_and_demonym() -> None:
    idx = _names()
    assert candidates("Governo brasileiro critica testes na Coreia do Sul", idx) == ["KR", "BR"]
    assert candidates("Ira de torcedores", idx) == []  # short names match only with their accent
    assert candidates("EUA ameaçam o Irã com sanções", idx) == ["US", "IR"]
    assert candidates("Nada a ver", idx) == []


def test_policy() -> None:
    it = {"id": "x", "title": "t"}
    assert apply_policy(it, {"geo": 0.4, "type": "conflict", "about": {}}) is None
    out = apply_policy(it, {"geo": 0.83, "type": "weird", "about": {"BR": 0.9, "AR": 0.5}})
    assert out is not None and out["event_type"] == "other" and out["countries"] == [{"iso2": "BR", "p": 0.9}]


def test_news_endpoints(api_client: TestClient) -> None:
    eng = create_engine(api_client.app.state.test_url)  # type: ignore[attr-defined]
    with Session(eng) as s, s.begin():
        summary = import_news(s, Path("tests/fixtures/news_sample.json"))
    eng.dispose()
    assert summary == {"news_upserted": 4, "news_deleted_old": 1}
    feed = api_client.get("/v1/news").json()  # default min_p 0.7
    assert [x["id"] for x in feed["items"]] == ["a1", "a2"] and feed["items"][0]["countries"] == ["RU", "UA"]
    assert feed["fetched_at"].startswith("2026-11-14") and feed["sources"][0]["id"] == "gdelt" and feed["next"] is None
    assert [x["id"] for x in api_client.get("/v1/news?min_p=0.5&lang=en").json()["items"]] == ["a3"]
    page = api_client.get("/v1/news?limit=1").json()
    assert [x["id"] for x in page["items"]] == ["a1"] and page["next"]
    assert [x["id"] for x in api_client.get("/v1/news", params={"limit": 1, "before": page["next"]}).json()["items"]] == ["a2"]
    assert [x["id"] for x in api_client.get("/v1/countries/AR/news").json()["items"]] == ["a2"]
    assert [x["id"] for x in api_client.get("/v1/news?region=Europa").json()["items"]] == ["a1"]
    assert api_client.get("/v1/news?type=nope").status_code == 422
    assert api_client.get("/v1/news?before=garbage").status_code == 422
    assert api_client.get("/v1/countries/ZZ/news").status_code == 404
