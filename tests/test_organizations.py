"""spec 032: curated organizations with join/leave dates (content/organizations.yaml -> import-content -> API)."""
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from atlas_api.importer.content import load_content, validate
from atlas_api.schemas import CountryDetail, CountryOrganizations, OrganizationList


def test_real_content_is_valid_and_every_membership_cites_a_source() -> None:
    content = load_content(Path("content"))
    assert validate(content) == []
    orgs = content["organizations"]
    assert len(orgs["onu"]["members"]) == 193
    assert all("oldid=" in o["source"]["url"] for o in orgs.values())  # revision permalink


def _content(members: list[dict[str, Any]]) -> dict[str, Any]:
    c = load_content(Path("content"))
    c["organizations"] = {"g7": {"source": {"title": "t", "url": "u", "license": "l", "retrieved": "2026-11-17"},
                                 "members": members}}
    return c


def test_validation_catches_bad_rows() -> None:
    errs = validate(_content([{"iso2": "ZZ", "joined": "1975"}, {"iso2": "FR", "joined": 1975},
                              {"iso2": "IT", "joined": "1975", "left": "1970"},
                              {"iso2": "JP", "joined": "1975"}, {"iso2": "JP", "joined": "1980"}]))
    assert any("ZZ: unknown iso2" in e for e in errs)
    assert any("FR: joined must be" in e for e in errs)
    assert any("IT: left must be" in e for e in errs)
    assert any("two open periods" in e for e in errs)
    c = _content([])
    c["organizations"]["nope"] = c["organizations"].pop("g7")
    assert any("nope: no glossary term" in e for e in validate(c))


def test_organizations_endpoint(api_client: TestClient) -> None:
    orgs = {o.id: o for o in OrganizationList.model_validate(api_client.get("/v1/organizations").json()).items}
    assert len(orgs) == 12 and orgs["otan"].label == "OTAN" and orgs["otan"].short
    eu = orgs["uniao-europeia"]
    gb = [m for m in eu.members if m.iso2 == "GB"]
    assert len(gb) == 1 and (gb[0].joined, gb[0].left) == ("1973-01-01", "2020-01-31")
    assert sum(m.left is None for m in eu.members) == 27
    assert [m.iso2 for m in eu.members[:6]] == ["BE", "DE", "FR", "IT", "LU", "NL"]  # by joined, then iso2
    assert eu.sources[0].license == "CC BY-SA 4.0" and "oldid=" in (eu.sources[0].url or "")


def test_country_organizations_and_detail(api_client: TestClient) -> None:
    ae = CountryOrganizations.model_validate(api_client.get("/v1/countries/AE/organizations").json())
    opep = [m for m in ae.items if m.id == "opep"]
    assert opep and opep[0].left == "2026-05-01" and ae.items[-1].id == "opep"  # former after current
    assert {m.id for m in ae.items if m.left is None} >= {"onu", "brics"}
    detail = CountryDetail.model_validate(api_client.get("/v1/countries/AE").json())
    assert "OPEP" not in detail.memberships and "BRICS" in detail.memberships  # curated list wins over Wikidata
    ve = CountryOrganizations.model_validate(api_client.get("/v1/countries/VE/organizations").json())
    assert any(m.id == "mercosul" and m.suspended for m in ve.items)
    assert api_client.get("/v1/countries/ZZ/organizations").status_code == 404
