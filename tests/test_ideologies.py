"""spec 018: who counts as a figure of a current, and the two endpoints on the real data_out/ file."""
from pathlib import Path

import pytest
from etl.wikidata.ideologies import rank, role
from fastapi.testclient import TestClient

from atlas_api.queries import _merge_terms
from atlas_api.schemas import CountryIdeologies, GlossaryList, IdeologyDetail


def test_role_from_occupations() -> None:
    assert role({"Q4964182"}, held_position=True) == "leader"  # office wins (a president who studied economics)
    assert role({"Q4964182"}, held_position=False) == "thinker"
    assert role({"Q82955"}, held_position=False) == "leader"
    assert role(set(), held_position=True) == "leader"
    assert role({"Q3242115"}, held_position=False) == "activist"
    assert role(set(), held_position=False) == "other"


def test_declared_figures_come_before_party_members() -> None:
    out = rank({"Q1": 20}, {"Q2": (99, "P"), "Q1": (50, "P"), "Q3": (30, "P")}, 3)
    assert [(f["id"], f["via"]) for f in out] == [("Q1", "declared"), ("Q2", "party"), ("Q3", "party")]


def test_mandates_merge_into_stretches() -> None:
    g = _merge_terms([("DE", 1998, 2005), ("DE", 2005, 2009), ("DE", 2021, None), ("BR", 2003, 2010)])
    assert [(x.iso2, x.from_year, x.to_year) for x in g] == [("BR", 2003, 2010), ("DE", 1998, 2009), ("DE", 2021, None)]


@pytest.mark.skipif(not Path("data_out/ideologies.json").exists(), reason="run `python -m etl wikidata-ideologies` first")
def test_ideology_endpoints(api_client: TestClient) -> None:
    kinds = {t.kind for t in GlossaryList.model_validate(api_client.get("/v1/glossary").json()).items}
    assert "ideology" in kinds
    br = CountryIdeologies.model_validate(api_client.get("/v1/countries/BR/ideologies").json())
    sd = next(i for i in br.items if i.term.id == "social-democracia")
    lula = next(f for f in sd.figures if f.name.startswith("Luiz Inácio Lula"))
    assert lula.via == "party" and lula.party and "Trabalhadores" in lula.party.name  # membership, not a label on the person
    assert len(sd.parties) <= 5 and all(f.via in ("declared", "party") for i in br.items for f in i.figures)
    fa = IdeologyDetail.model_validate(api_client.get("/v1/ideologies/fascismo").json())
    assert fa.term.kind == "ideology"
    assert all(f.via == "declared" for f in fa.founders)  # worldwide list: stated on the person, never party-derived
    assert "Donald Trump" not in {f.name for f in fa.founders}  # neutrality regression (2026-11-13)
    sd_world = IdeologyDetail.model_validate(api_client.get("/v1/ideologies/social-democracia").json())
    assert any(g.iso2 == "DE" for g in sd_world.governed)
    assert api_client.get("/v1/ideologies/republica").status_code == 404  # a glossary term, but not a current
    assert api_client.get("/v1/countries/ZZ/ideologies").status_code == 404
