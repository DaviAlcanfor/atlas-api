"""import-facts: data_out/wikidata.json -> country_facts (+ the `wikidata` source row), and,
when present, data_out/leaders.json -> leaders and data_out/pantheon.json -> people (+ the
`pantheon` source row and its method text in meta).

Reads plain JSON files (the API process never imports the `etl` group). Only countries that
already exist as polities (iso2) are imported; others are reported, never created here.
Idempotent: upsert by iso2 (leaders: delete + insert per file), one transaction (the CLI owns it).
Run import-content first: regime_id references glossary_terms; an id without a term is dropped
(set to null) and reported.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from atlas_api.db.models import CountryFacts, GlossaryTerm, Leader, Meta, Person, Polity, Source


def import_facts(session: Session, path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    src = data["source"]
    fetched = max(datetime.fromisoformat(v) for v in data["retrieved_at"].values())
    session.merge(Source(id=src["id"], title=src["title"], url=src["url"],
                         license=src["license"], retrieved_at=fetched))
    session.flush()
    known = set(session.scalars(select(Polity.iso2).where(Polity.iso2.is_not(None))))
    terms = set(session.scalars(select(GlossaryTerm.id)))
    imported, skipped, no_term = 0, [], set()
    for iso2, c in data["countries"].items():
        if iso2 not in known:
            skipped.append(iso2)
            continue
        regime_id = c.get("regime_id")
        if regime_id and regime_id not in terms:
            no_term.add(regime_id)
            regime_id = None
        clues = c.get("clues") or {}
        session.merge(CountryFacts(
            iso2=iso2, official_name=c["official_name"], capital=c["capital"],
            capital_lat=c["capital_lat"], capital_lng=c["capital_lng"], flag_url=c["flag_url"],
            region=c["region"], area_km2=c["area_km2"], population=c["population"],
            population_year=c["population_year"], languages=c["languages"],
            currencies=c["currencies"], memberships=c["memberships"],
            regime_id=regime_id, regime=c.get("regime") if regime_id else None,
            driving_side=clues.get("driving_side"), calling_code=clues.get("calling_code"),
            tld=clues.get("tld"), plate_code=clues.get("plate_code"),
            scripts=clues.get("scripts") or [],
            source_id=src["id"], fetched_at=fetched))
        imported += 1
    session.flush()
    summary: dict[str, Any] = {"countries_imported": imported, "skipped_no_polity": skipped or 0,
                               "regime_ids_without_glossary_term": sorted(no_term) or 0}
    leaders = path.parent / "leaders.json"
    if leaders.exists():
        summary["leaders_imported"] = import_leaders(session, leaders, known)
    people = path.parent / "pantheon.json"
    if people.exists():
        summary["people_imported"] = import_people(session, people, known)
    return summary


def import_leaders(session: Session, path: Path, known: set[str | None]) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    session.execute(delete(Leader))  # rebuilt from the file: simpler than diffing
    n = 0
    for iso2, terms in data["countries"].items():
        if iso2 not in known:
            continue
        for t in terms:
            party, image = t.get("party") or {}, t.get("image") or {}
            session.add(Leader(
                iso2=iso2, person_id=t["person_id"], name=t["name"], role=t["role"],
                office=t.get("office"), start=t.get("start"), end=t.get("end"),
                party_id=party.get("id"), party_name=party.get("name"),
                image_url=image.get("url"), image_credit=image.get("credit"),
                image_license=image.get("license"), wikipedia_url=t.get("wikipedia_url")))
            n += 1
    session.flush()
    return n


def import_people(session: Session, path: Path, known: set[str | None]) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    src = data["source"]
    session.merge(Source(id=src["id"], title=src["title"], url=src["url"], license=src["license"],
                         retrieved_at=datetime.fromisoformat(src["retrieved_at"])))
    session.merge(Meta(key="people_method", value=data["method"]))
    session.execute(delete(Person))
    session.flush()
    n = 0
    for iso2, people in data["countries"].items():
        if iso2 not in known:
            continue
        for p in people:
            image = p.get("image") or {}
            session.add(Person(
                iso2=iso2, id=p["id"], name=p["name"], occupation=p.get("occupation"),
                domain=p.get("domain"), birth_year=p.get("birth_year"),
                death_year=p.get("death_year"), rank=p["rank"], image_url=image.get("url"),
                image_credit=image.get("credit"), image_license=image.get("license"),
                wikipedia_url=p.get("wikipedia_url")))
            n += 1
    session.flush()
    return n
