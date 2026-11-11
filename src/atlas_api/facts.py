"""import-facts: data_out/wikidata.json -> country_facts (+ the `wikidata` source row).

Reads a plain JSON file (the API process never imports the `etl` group). Only countries that
already exist as polities (iso2) are imported; others are reported, never created here.
Idempotent: upsert by iso2, one transaction (the CLI owns it).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.db.models import CountryFacts, Polity, Source


def import_facts(session: Session, path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    src = data["source"]
    fetched = max(datetime.fromisoformat(v) for v in data["retrieved_at"].values())
    session.merge(Source(id=src["id"], title=src["title"], url=src["url"],
                         license=src["license"], retrieved_at=fetched))
    session.flush()
    known = set(session.scalars(select(Polity.iso2).where(Polity.iso2.is_not(None))))
    imported, skipped = 0, []
    for iso2, c in data["countries"].items():
        if iso2 not in known:
            skipped.append(iso2)
            continue
        session.merge(CountryFacts(
            iso2=iso2, official_name=c["official_name"], capital=c["capital"],
            capital_lat=c["capital_lat"], capital_lng=c["capital_lng"], flag_url=c["flag_url"],
            region=c["region"], area_km2=c["area_km2"], population=c["population"],
            population_year=c["population_year"], languages=c["languages"],
            currencies=c["currencies"], memberships=c["memberships"],
            source_id=src["id"], fetched_at=fetched))
        imported += 1
    session.flush()
    return {"countries_imported": imported, "skipped_no_polity": skipped or 0}
