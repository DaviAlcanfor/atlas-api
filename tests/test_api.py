"""The API end to end: real app, real Postgres, real content (no mocks, no fixtures)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas_api.schemas import (
    CountryDetail,
    CountryList,
    GlossaryList,
    GlossaryTerm,
    LeaderList,
    Meta,
    PersonList,
    PolityDetail,
    PolityList,
    SearchResults,
)

CONTRACT_MODERN = {"AT", "BR", "DE", "EG", "JP", "TR", "RU", "RS"}
CONTRACT_HISTORICAL = {"ottoman-empire", "austria-hungary", "german-empire", "weimar-republic",
                       "nazi-germany", "east-germany", "soviet-union", "yugoslavia"}


def test_health_meta_and_counts(api_client: TestClient) -> None:
    assert api_client.get("/v1/health").json() == {"status": "ok", "db": "ok"}
    meta = Meta.model_validate(api_client.get("/v1/meta").json())
    assert meta.counts.countries == 197 and meta.counts.polities == 205
    assert meta.counts.events == 23 and meta.year_min == -3000
    assert meta.data_version not in ("", "empty")


def test_countries_list_and_markers(api_client: TestClient) -> None:
    items = CountryList.model_validate(api_client.get("/v1/countries").json()).items
    by_iso = {c.iso2: c for c in items}
    assert len(items) == 197 and {"XK", "TW", "PS", "NO", "DK"} <= set(by_iso)
    assert CONTRACT_MODERN <= set(by_iso)
    assert by_iso["MC"].marker is not None and by_iso["BR"].marker is None  # micro-state vs big
    assert sum(c.marker is not None for c in items) == 22
    assert by_iso["AT"].has_content and not by_iso["NO"].has_content


def test_country_detail_is_real_data(api_client: TestClient) -> None:
    c = CountryDetail.model_validate(api_client.get("/v1/countries/BR").json())
    assert c.polity_id == "brazil" and c.name == "Brasil"
    assert c.official_name == "República Federativa do Brasil"
    assert c.flag_url == "https://flagcdn.com/br.svg" and c.capital == "Brasília"
    assert c.population and c.population.source_id == "wikidata" and c.population.year
    assert [x.code for x in c.currencies] == ["BRL"] and c.region == "América do Sul"
    assert c.memberships == ["ONU"] and any(s.id == "wikidata" for s in c.sources)
    at = CountryDetail.model_validate(api_client.get("/v1/countries/AT").json())
    assert len(at.timeline) == 5 and all(e.source_ids == [] for e in at.timeline)  # unverified
    assert [e.year_start for e in at.timeline] == sorted(e.year_start for e in at.timeline)
    eg = CountryDetail.model_validate(api_client.get("/v1/countries/EG").json())
    assert eg.timeline[0].year_start == -2560 and eg.timeline[0].precision == "circa"


def test_polities_by_year(api_client: TestClient) -> None:
    l1900 = PolityList.model_validate(api_client.get("/v1/polities?year=1900&limit=1000").json())
    ids = {p.id for p in l1900.items}
    assert {"ottoman-empire", "german-empire", "austria-hungary"} <= ids
    assert "brazil" not in ids and l1900.total == len(l1900.items)  # modern placeholders start 1946
    l1946 = PolityList.model_validate(api_client.get("/v1/polities?year=1946&limit=1000").json())
    assert "brazil" in {p.id for p in l1946.items}
    every = PolityList.model_validate(api_client.get("/v1/polities?limit=1000").json())
    assert CONTRACT_HISTORICAL <= {p.id for p in every.items}
    page = api_client.get("/v1/polities?limit=5&offset=2").json()
    assert len(page["items"]) == 5 and page["total"] == 205


def test_polity_detail(api_client: TestClient) -> None:
    p = PolityDetail.model_validate(api_client.get("/v1/polities/ottoman-empire").json())
    assert (p.start_year, p.end_year, p.start_precision) == (1299, 1922, "circa")
    assert p.predecessors == [] and p.successors == []  # succession not curated yet


def test_search_accent_insensitive_prefix_first(api_client: TestClient) -> None:
    items = SearchResults.model_validate(api_client.get("/v1/search?q=austria").json()).items
    assert [i.id for i in items][:2] == ["austria", "austria-hungary"]  # prefix matches, A-Z
    assert items[0].kind == "country" and items[0].iso2 == "AT"
    assert items[1].kind == "polity"
    # accents and case are ignored in both directions; substring matches come after prefixes
    assert api_client.get("/v1/search?q=BRÁS").json()["items"][0]["id"] == "brazil"
    sub = [i["id"] for i in api_client.get("/v1/search?q=hungria").json()["items"]]
    assert sub == ["hungria", "austria-hungary"]  # prefix match first, then substring
    # LIKE wildcards are plain text, not patterns
    assert api_client.get("/v1/search?q=%25%25").json()["items"] == []


def test_snapshots_empty_until_phase_3(api_client: TestClient) -> None:
    assert api_client.get("/v1/snapshots").json() == {"items": []}
    assert api_client.get("/v1/meta").json()["snapshot_years"] == []
    assert api_client.get("/v1/snapshots/nearest?year=1900").status_code == 404
    assert api_client.get("/v1/snapshots/1900/links").status_code == 404


def test_errors_are_problem_json(api_client: TestClient) -> None:
    cases = [
        ("/v1/countries/de", 422), ("/v1/countries/ZZ", 404), ("/v1/search?q=a", 422),
        ("/v1/polities?limit=5000", 422), ("/v1/polities?year=99999", 422),
        ("/v1/polities?year=0", 422), ("/v1/snapshots/nearest?year=-99999", 422),
        ("/v1/polities/nope", 404), ("/v1/does-not-exist", 404),
    ]
    for path, code in cases:
        r = api_client.get(path)
        assert r.status_code == code, path
        assert r.headers["content-type"].startswith("application/problem+json"), path
        assert set(r.json()) == {"type", "title", "status", "detail"}, path
    assert api_client.post("/v1/meta").status_code == 405


def test_version_header_matches_meta_and_304(api_client: TestClient) -> None:
    r = api_client.get("/v1/countries/BR")
    assert r.headers["x-data-version"] == api_client.get("/v1/meta").json()["data_version"]
    again = api_client.get("/v1/countries/BR", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304 and again.content == b""



# --- v1.1 (CR-002, specs 003-007) -----------------------------------------------------------


def test_capital_coords_and_regime_id(api_client: TestClient) -> None:  # specs 004 + 005
    by_iso = {c.iso2: c for c in CountryList.model_validate(api_client.get("/v1/countries").json()).items}
    br = by_iso["BR"]
    assert [c.name for c in br.capital_coords] == ["Brasília"]
    assert -16 < br.capital_coords[0].lat < -15 and -48 < br.capital_coords[0].lng < -47
    assert br.regime_id == "republica-presidencialista" and br.regime == "República presidencialista"
    assert by_iso["JP"].regime_id == "monarquia-constitucional"
    assert all(c.capital_coords for c in by_iso.values())  # 197/197 have coordinates
    assert sum(c.regime_id is not None for c in by_iso.values()) >= 150
    no = by_iso["CR"]  # Costa Rica has no P122 in Wikidata: null, never guessed
    assert no.regime_id is None and no.regime is None


def test_country_clues(api_client: TestClient) -> None:  # spec 003
    br = CountryDetail.model_validate(api_client.get("/v1/countries/BR").json())
    assert br.clues is not None and br.regime_id == "republica-presidencialista"
    assert (br.clues.driving_side, br.clues.calling_code, br.clues.tld, br.clues.plate_code) == (
        "right", "+55", ".br", "BR")
    assert br.clues.scripts == ["alfabeto latino"]
    jp = CountryDetail.model_validate(api_client.get("/v1/countries/JP").json())
    assert jp.clues is not None and jp.clues.driving_side == "left" and jp.clues.tld == ".jp"


def test_glossary(api_client: TestClient) -> None:  # spec 004
    items = GlossaryList.model_validate(api_client.get("/v1/glossary").json()).items
    by_id = {t.id: t for t in items}
    used = {c["regime_id"] for c in api_client.get("/v1/countries").json()["items"]} - {None}
    assert used <= set(by_id)  # every regime in use has a term
    assert {"onu", "africa", "europa"} <= set(by_id) and all(t.sources for t in items)
    rep = GlossaryTerm.model_validate(api_client.get("/v1/glossary/republica-presidencialista").json())
    assert rep.kind == "regime" and "BR" in rep.examples and len(rep.examples) <= 8
    assert by_id["onu"].examples and by_id["europa"].kind == "region"
    r = api_client.get("/v1/glossary/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")


def test_leaders_and_people_errors(api_client: TestClient) -> None:
    for path in ("/v1/countries/ZZ/leaders", "/v1/countries/ZZ/people"):
        assert api_client.get(path).status_code == 404
    assert api_client.get("/v1/countries/BR/leaders?role=king").status_code == 422
    assert api_client.get("/v1/countries/BR/people?limit=51").status_code == 422
    assert api_client.get("/v1/countries/BR/people?domain=magic").status_code == 422


@pytest.mark.skipif(not Path("data_out/leaders.json").exists(), reason="run `etl wikidata-leaders`")
def test_leaders(api_client: TestClient) -> None:  # spec 006
    br = LeaderList.model_validate(api_client.get("/v1/countries/BR/leaders").json()).items
    assert br and {x.role for x in br} == {"head_of_state"}  # one office for both roles
    lula = [x for x in br if x.name == "Luiz Inácio Lula da Silva"]
    assert lula and lula[-1].start == "2023-01-01" and lula[-1].end is None
    assert all(x.image is None or (x.image.credit and x.image.license) for x in br)
    starts = [x.start for x in br if x.start]
    assert starts == sorted(starts)
    gov = LeaderList.model_validate(
        api_client.get("/v1/countries/DE/leaders?role=head_of_government").json()).items
    assert gov and {x.role for x in gov} == {"head_of_government"}


@pytest.mark.skipif(not Path("data_out/pantheon.json").exists(), reason="run `etl pantheon`")
def test_people(api_client: TestClient) -> None:  # spec 007
    res = PersonList.model_validate(api_client.get("/v1/countries/BR/people").json())
    assert len(res.items) == 10 and [p.rank for p in res.items] == list(range(1, 11))
    assert res.source.id == "pantheon" and "CC BY-SA" in (res.source.license or "")
    assert "Pantheon" in res.method
    sports = PersonList.model_validate(
        api_client.get("/v1/countries/BR/people?domain=sports&limit=50").json()).items
    assert sports and {p.domain for p in sports} == {"sports"}
