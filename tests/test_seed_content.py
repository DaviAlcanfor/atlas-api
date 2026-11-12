"""The real content/ and data_out/ files: valid, complete, and importable into real Postgres."""
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas_api.db.models import CountryFacts, Polity
from atlas_api.facts import import_facts
from atlas_api.importer import import_content, load_content, validate

CONTRACT_IDS = {"austria", "brazil", "germany", "egypt", "japan", "turkey", "russia", "serbia"}


def test_content_is_valid_and_has_contract_seed_ids() -> None:
    content = load_content(Path("content"))
    assert validate(content) == []
    ids = {p["id"] for p in content["polities"]}
    assert CONTRACT_IDS <= ids and len(ids) == 205
    assert {p.get("iso2") for p in content["polities"]} >= {"NO", "XK", "TW", "PS"}


@pytest.mark.skipif(not Path("data_out/wikidata.json").exists(), reason="run `etl wikidata` first")
def test_import_content_then_facts(session: Session) -> None:
    import_content(session, Path("content"))
    res = import_facts(session, Path("data_out/wikidata.json"))
    assert res["countries_imported"] == 197
    assert session.scalar(select(func.count()).select_from(CountryFacts)) == 197
    no = session.get(CountryFacts, "NO")
    assert no is not None and no.official_name == "Reino da Noruega"
    assert session.scalar(select(Polity.id).where(Polity.iso2 == "NO")) == "noruega"
