from pathlib import Path

from etl.wikidata.pipeline import build, map_regime, regime_report


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


RULES = [{"when": ["Q41614", "Q184558"], "regime_id": None},
         {"when": ["Q184558"], "regime_id": "monarquia-absoluta"},
         {"when": ["Q41614"], "regime_id": "monarquia-constitucional"},
         {"when": ["Q7270"], "regime_id": "republica"}]
REGIMES = {"labels": {"monarquia-absoluta": "Monarquia absoluta",
                      "monarquia-constitucional": "Monarquia constitucional",
                      "republica": "República"}, "rules": RULES}


def test_map_regime_first_rule_wins_and_conflict_is_null() -> None:
    assert map_regime({"Q41614", "Q179164"}, RULES) == "monarquia-constitucional"
    assert map_regime({"Q41614", "Q184558"}, RULES) is None  # explicit conflict rule
    assert map_regime({"Q179164"}, RULES) is None  # no rule


def test_build_regime_and_clues() -> None:
    e = "http://www.wikidata.org/entity/"
    pref, norm = "x#PreferredRank", "x#NormalRank"
    raw = {
        "states": {"rows": [_row(iso2="JP", c=e + "Q17", cLabel="Japão"),
                            _row(iso2="DO", c=e + "Q786", cLabel="República Dominicana")]},
        "official_name": {"rows": []}, "capital": {"rows": []}, "population": {"rows": []},
        "area": {"rows": []}, "languages": {"rows": []}, "currencies": {"rows": []},
        "memberships": {"rows": []}, "continent": {"rows": []}, "flag": {"rows": []},
        "regime": {"rows": [_row(iso2="JP", g=e + "Q41614"), _row(iso2="JP", g=e + "Q179164")]},
        "driving_side": {"rows": [_row(iso2="JP", v=e + "Q11920728", rank=norm)]},
        "calling_code": {"rows": [_row(iso2="JP", v="+81", rank=norm),
                                  _row(iso2="DO", v="+1809", rank=norm),
                                  _row(iso2="DO", v="+1829", rank=norm)]},  # tie -> null
        "tld": {"rows": [_row(iso2="JP", vLabel=".jp", rank=norm),
                         _row(iso2="JP", vLabel=".nihon", rank=norm),  # loses to the 2-letter ccTLD
                         _row(iso2="DO", vLabel=".do", rank=pref),
                         _row(iso2="DO", vLabel=".x", rank=norm)]},
        "plate_code": {"rows": [_row(iso2="JP", v="J", rank=norm)]},
        "scripts": {"rows": [_row(iso2="JP", sLabel="hiragana", code="Hira"),
                             _row(iso2="JP", sLabel="Braille", code="Brai"),  # excluded
                             _row(iso2="JP", sLabel="Katakana", code="Kana")]},
    }
    out = build(raw, regimes=REGIMES)
    jp, do = out["JP"], out["DO"]
    assert jp["regime_qids"] == ["Q179164", "Q41614"]
    assert (jp["regime_id"], jp["regime"]) == ("monarquia-constitucional", "Monarquia constitucional")
    assert jp["clues"] == {"driving_side": "left", "calling_code": "+81", "tld": ".jp",
                           "plate_code": "J", "scripts": ["Katakana", "hiragana"]}
    assert do["regime_id"] is None and do["clues"]["calling_code"] is None
    assert do["clues"]["tld"] == ".do" and do["clues"]["scripts"] == []
    report = regime_report(out, REGIMES)
    assert "  unmapped Q179164: JP" in report and report[-1].endswith("(0): ")


def test_curated_memberships_join_wikidata_and_match_glossary() -> None:
    """spec 026: every curated organization has a glossary term with the same label; merge keeps order, skips unknown ISO2."""
    import yaml
    from etl.wikidata.pipeline import ORGANIZATIONS, add_curated_memberships

    orgs = yaml.safe_load(ORGANIZATIONS.read_text(encoding="utf-8"))
    glossary = yaml.safe_load(Path("content/glossary.yaml").read_text(encoding="utf-8"))
    terms = glossary["terms"] if isinstance(glossary, dict) else glossary
    assert set(orgs) <= {t["label"] for t in terms if t["kind"] == "membership"}
    assert all(len(set(o["members"])) == len(o["members"]) for o in orgs.values())
    countries = {"BR": {"memberships": ["ONU"]}, "VE": {"memberships": ["ONU"]}}
    add_curated_memberships(countries, orgs)
    assert {"ONU", "Mercosul", "BRICS", "G20", "CPLP"} == set(countries["BR"]["memberships"])
    assert "Mercosul" not in countries["VE"]["memberships"]  # suspended since 2016
