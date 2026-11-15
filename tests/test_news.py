"""spec 008: news rules (offline) and the news endpoints on a sample import."""
import re
from datetime import UTC, datetime
from pathlib import Path

from etl.news.pipeline import (
    apply_policy,
    candidates,
    clean_url,
    name_index,
    parse_gkg_row,
    stamps,
    top_per_file,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas_api.facts import import_news


def _names() -> list[tuple[re.Pattern[str], str]]:
    rows = [{"iso2": {"value": "KR"}, "label": {"value": "Coreia do Sul"}}, {"iso2": {"value": "BR"}, "label": {"value": "Brasil"}},
            {"iso2": {"value": "BR"}, "demonym": {"value": "brasileiro"}}, {"iso2": {"value": "IR"}, "label": {"value": "Irã"}}]
    return name_index(rows)


def _row(themes: str = "ARMEDCONFLICT;TAX_FNCACT_PRESIDENT", title: str = "R&#xFA;ssia e Ucr&#xE2;nia retomam negocia&#xE7;&#xF5;es",
         lang: str = "srclc:por;eng:GT-POR 1.0", url: str = "https://Ex.org/n?id=1&utm_source=x#top") -> list[str]:
    cols = [""] * 27
    cols[1], cols[3], cols[4], cols[7], cols[25] = "20261114101500", "ex.org", url, themes, lang
    cols[26] = f"<PAGE_PRECISEPUBTIMESTAMP>x</PAGE_PRECISEPUBTIMESTAMP><PAGE_TITLE>{title}</PAGE_TITLE>"
    return cols


def test_parse_gkg_row() -> None:
    got = parse_gkg_row(_row(), translated=True)
    assert got is not None
    it, n = got
    assert n == 2 and it["url"] == "https://ex.org/n?id=1" and it["language"] == "pt" and it["outlet"] == "ex.org"
    assert it["title"] == "Rússia e Ucrânia retomam negociações" and it["published_at"] == "2026-11-14T10:15:00+00:00"
    assert parse_gkg_row(_row(lang="srclc:ita"), translated=True) is None  # not pt/es
    assert parse_gkg_row(_row(themes="SPORTS;MUSIC"), translated=True) is None  # no geopolitical theme
    assert parse_gkg_row(_row(lang=""), translated=False)[0]["language"] == "en"  # type: ignore[index]
    assert clean_url("https://x.org/a?b=1&fbclid=9") == "https://x.org/a?b=1"


def test_window_and_cap() -> None:
    s = stamps(datetime(2026, 11, 14, 12, 7, tzinfo=UTC), hours=1)
    assert s == ["20261114120000", "20261114114500", "20261114113000", "20261114111500"]
    rows = [({"language": "en", "id": str(i)}, i % 3) for i in range(30)] + [({"language": "pt", "id": "p"}, 1)]
    top = top_per_file(rows)
    assert len([x for x in top if x["language"] == "en"]) == 12 and {"id": "p", "language": "pt"} in top


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
