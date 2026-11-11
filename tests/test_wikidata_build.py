from etl.wikidata.pipeline import build


def _row(**kw: str) -> dict:
    return {k: {"value": v} for k, v in kw.items()}


def test_build_merges_and_never_invents() -> None:
    raw = {
        "states": {"rows": [_row(iso2="BR", c="http://www.wikidata.org/entity/Q155", cLabel="Brasil"),
                            _row(iso2="UY", c="http://www.wikidata.org/entity/Q77", cLabel="Uruguai")]},
        "official_name": {"rows": [{"iso2": {"value": "BR"}, "n": {"value": "Brasil", "xml:lang": "pt"}},
                                   {"iso2": {"value": "BR"}, "n": {"value": "Brazil", "xml:lang": "en"}}]},
        "capital": {"rows": [_row(iso2="BR", capLabel="Brasília", coord="Point(-47.9 -15.8)",
                                  rank="http://wikiba.se/ontology#NormalRank")]},
        "population": {"rows": [
            _row(iso2="BR", pop="100", when="2010-01-01T00:00:00Z", rank="x#NormalRank"),
            _row(iso2="BR", pop="200", when="2022-01-01T00:00:00Z", rank="x#NormalRank"),
            _row(iso2="BR", pop="999", when="2023-01-01T00:00:00Z", rank="x#DeprecatedRank")]},
        "area": {"rows": [_row(iso2="BR", area="8500000000000")]},
        "languages": {"rows": [_row(iso2="BR", lLabel="português", code="pt"),
                               _row(iso2="BR", lLabel="Q12345")]},  # unlabeled item is dropped
        "currencies": {"rows": [_row(iso2="BR", curLabel="real", code="BRL", symbol="R$")]},
        "memberships": {"rows": [_row(iso2="BR", org="http://www.wikidata.org/entity/Q1065")]},
        "continent": {"rows": [_row(iso2="BR", contLabel="América do Sul")]},
        "flag": {"rows": [_row(iso2="BR", flag="http://commons.wikimedia.org/wiki/Special:FilePath/Flag%20of%20Brazil.svg")]},
    }
    br, uy = build(raw)["BR"], build(raw)["UY"]
    assert br["official_name"] == "Brasil"
    assert (br["capital_lat"], br["capital_lng"]) == (-15.8, -47.9)
    assert (br["population"], br["population_year"]) == (200, 2022)  # latest, deprecated ignored
    assert br["area_km2"] == 8500000.0
    assert br["languages"] == [{"code": "pt", "name": "português"}]
    assert br["memberships"] == ["ONU"] and br["flag_file"] == "Flag%20of%20Brazil.svg"
    assert br["region"] == "América do Sul" and uy["region"] is None
    assert uy["population"] is None and uy["languages"] == [] and uy["capital"] is None
