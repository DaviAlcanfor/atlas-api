"""Pure transforms of the leaders (spec 006) and Pantheon (spec 007) ETLs: no network."""
from etl.pantheon.pipeline import top_by_country
from etl.wikidata.leaders import _strip_html, build_leaders

E = "http://www.wikidata.org/entity/"


def _r(**kw: str) -> dict:
    return {k: {"value": v} for k, v in kw.items()}


def test_build_leaders_party_at_start_shared_office_and_humans_only() -> None:
    base = {"office": E + "Q1", "officeLabel": "Presidente", "person": E + "Q10",
            "personLabel": "Ana", "start": "2003-01-01T00:00:00Z", "human": "true",
            "pt": "https://pt.wikipedia.org/wiki/Ana"}
    bia = {**base, "person": E + "Q11", "personLabel": "Bia", "start": "2011-01-01T00:00:00Z"}
    rows = [
        # same office for both roles -> kept once, as head_of_state
        _r(**base, role="head_of_state", party=E + "Q100", partyLabel="Partido A",
           pstart="1980-01-01T00:00:00Z", pend="2016-01-01T00:00:00Z",
           image="http://commons.wikimedia.org/wiki/Special:FilePath/Ana%20.jpg"),
        _r(**base, role="head_of_state", party=E + "Q200", partyLabel="Partido B",
           pstart="2016-01-02T00:00:00Z"),  # joined after the term started: not this term
        _r(**base, role="head_of_government", party=E + "Q100", partyLabel="Partido A"),
        # two photos and two open party memberships: no pick
        _r(**bia, role="head_of_state", party=E + "Q100", partyLabel="Partido A",
           image="http://x/Special:FilePath/1.jpg"),
        _r(**bia, role="head_of_state", party=E + "Q200", partyLabel="Partido B",
           image="http://x/Special:FilePath/2.jpg"),
        # not a human (e.g. an election item with P39)
        _r(**{**base, "person": E + "Q12", "personLabel": "Eleicao", "human": "false"},
           role="head_of_state"),
    ]
    out = build_leaders(rows)
    assert [(t["person_id"], t["role"]) for t in out] == [("Q10", "head_of_state"),
                                                          ("Q11", "head_of_state")]
    ana, b = out
    assert ana["party"] == {"id": "Q100", "name": "Partido A"} and ana["image_file"] == "Ana .jpg"
    assert ana["start"] == "2003-01-01" and ana["end"] is None and ana["office"] == "Presidente"
    assert b["party"] is None and b["image_file"] is None


def test_pantheon_top_by_country_ranks_and_years() -> None:
    def row(name: str, hpi: str, country: str = "Brazil", by: str = "1900") -> dict:
        return {"wd_id": "Q" + name, "name": name, "occupation": "WRITER",
                "bplace_country": country, "birthyear": by, "deathyear": "", "hpi": hpi}

    rows = [row("b", "50"), row("a", "90", by="-100"), row("c", "70", by="0"),
            row("z", "99", country="Atlantis")]
    out = top_by_country(rows, {"Brazil": "BR"}, {"WRITER": "humanities"})
    assert list(out) == ["BR"]
    assert [(p["name"], p["rank"]) for p in out["BR"]] == [("a", 1), ("c", 2), ("b", 3)]
    assert out["BR"][0]["birth_year"] == -100 and out["BR"][1]["birth_year"] is None  # no year 0
    assert out["BR"][0]["domain"] == "humanities" and out["BR"][0]["death_year"] is None


def test_commons_credit_drops_hidden_spans() -> None:
    hidden = 'Unknown author<span style="display: none;">Unknown author</span>'
    assert _strip_html(hidden) == 'Unknown author'
    assert _strip_html('<a href="x">Pal&aacute;cio</a>  do Planalto') == 'Palácio do Planalto'
