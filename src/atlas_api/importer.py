"""import-content: the ONLY writer of the database. Reads content/ (YAML), validates, upserts
everything in ONE transaction (all or nothing) and recomputes meta.data_version
(= hash of content/ + the last import-facts files, see set_version).

content/
  sources.yaml      list of {id, title, url, license, retrieved_at}
  polities/*.yaml   one polity each (keys: see Polity model; plus names[] and events[])
  succession.yaml   list of {predecessor, successor, year, kind, note}
  glossary.yaml     {terms: [{id, kind, label, short, body, icon, sources[]}]} (spec 004)
  regimes.yaml      read by the Wikidata ETL; here only checked: every regime_id needs a term

An event with empty source_ids counts as UNVERIFIED in the summary.
Idempotent: running twice on the same content changes nothing (same data_version).
ponytail: polities removed from content/ are NOT deleted from the DB (FKs from facts/links);
delete by hand until this matters.
"""

import hashlib
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from atlas_api.db.models import (
    EVENT_KINDS,
    GLOSSARY_KINDS,
    LINK_KINDS,
    POLITY_TYPES,
    PRECISIONS,
    Event,
    EventSource,
    GlossaryTerm,
    Meta,
    Polity,
    PolityName,
    Source,
    Succession,
)


class ContentError(Exception):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("\n".join(problems))
        self.problems = problems


def _yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_content(root: Path) -> dict[str, Any]:
    sources = _yaml(root / "sources.yaml") if (root / "sources.yaml").exists() else []
    succ = _yaml(root / "succession.yaml") if (root / "succession.yaml").exists() else []
    polities = [_yaml(p) for p in sorted((root / "polities").glob("*.yaml"))]
    glossary = _yaml(root / "glossary.yaml") if (root / "glossary.yaml").exists() else {}
    regimes = _yaml(root / "regimes.yaml") if (root / "regimes.yaml").exists() else {}
    return {"sources": sources or [], "succession": succ or [], "polities": polities,
            "glossary": (glossary or {}).get("terms") or [],
            "regime_ids": sorted((regimes or {}).get("labels") or {})}


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)
    state: dict[str, int] = {}  # 1 = visiting, 2 = done

    def visit(n: str) -> bool:
        if state.get(n) == 1:
            return True
        if state.get(n) == 2:
            return False
        state[n] = 1
        if any(visit(m) for m in graph.get(n, [])):
            return True
        state[n] = 2
        return False

    return any(visit(n) for n in list(graph))


def _bad_years(start: Any, end: Any) -> bool:
    return not isinstance(start, int) or start == 0 or (end is not None and (end == 0 or end < start))


def validate(content: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    source_ids = {s["id"] for s in content["sources"]}
    polity_ids: set[str] = set()
    event_ids: set[str] = set()
    for p in content["polities"]:
        pid = p.get("id", "?")
        if pid in polity_ids:
            errs.append(f"polity {pid}: duplicate id")
        polity_ids.add(pid)
        if p.get("iso2") is not None and not (isinstance(p["iso2"], str) and len(p["iso2"]) == 2):
            errs.append(f"polity {pid}: iso2 must be a 2-letter string (quote it: NO is a YAML boolean)")
        if p.get("type") not in POLITY_TYPES:
            errs.append(f"polity {pid}: bad type {p.get('type')!r}")
        if _bad_years(p.get("start_year"), p.get("end_year")):
            errs.append(f"polity {pid}: bad years start={p.get('start_year')} end={p.get('end_year')}")
        for key in ("start_precision", "end_precision"):
            if p.get(key) is not None and p[key] not in PRECISIONS:
                errs.append(f"polity {pid}: bad {key}")
        periods = sorted(p.get("names") or [], key=lambda n: n["from_year"])
        for a, b in itertools.pairwise(periods):
            if a.get("to_year") is None or a["to_year"] >= b["from_year"]:
                errs.append(f"polity {pid}: name periods overlap ({a['name']} / {b['name']})")
        for ev in p.get("events") or []:
            eid = ev.get("id", "?")
            if eid in event_ids:
                errs.append(f"event {eid}: duplicate id")
            event_ids.add(eid)
            if ev.get("kind") not in EVENT_KINDS or ev.get("precision") not in PRECISIONS:
                errs.append(f"event {eid}: bad kind/precision")
            if _bad_years(ev.get("year_start"), ev.get("year_end")):
                errs.append(f"event {eid}: bad years")
            for sid in ev.get("source_ids") or []:
                if sid not in source_ids:
                    errs.append(f"event {eid}: unknown source {sid}")
    edges: list[tuple[str, str]] = []
    for s_ in content["succession"]:
        a, b = s_["predecessor"], s_["successor"]
        if a not in polity_ids or b not in polity_ids:
            errs.append(f"succession {a}->{b}: unknown polity")
        if a == b or s_.get("kind") not in LINK_KINDS or s_.get("year") in (None, 0):
            errs.append(f"succession {a}->{b}: bad row")
        edges.append((a, b))
    if _has_cycle(edges):
        errs.append("succession has a cycle")
    term_ids: set[str] = set()
    for t in content.get("glossary", []):
        tid = t.get("id", "?")
        if tid in term_ids:
            errs.append(f"glossary {tid}: duplicate id")
        term_ids.add(tid)
        if t.get("kind") not in GLOSSARY_KINDS:
            errs.append(f"glossary {tid}: bad kind {t.get('kind')!r}")
        if not all(isinstance(t.get(k), str) and t[k].strip() for k in ("label", "short", "body")):
            errs.append(f"glossary {tid}: label, short and body are required")
        if not t.get("sources") or not all(x.get("id") and x.get("title") and x.get("url")
                                           for x in t["sources"]):
            errs.append(f"glossary {tid}: needs >= 1 source with id, title, url")
    regime_terms = {t.get("id") for t in content.get("glossary", []) if t.get("kind") == "regime"}
    for rid in content.get("regime_ids", []):
        if rid not in regime_terms:
            errs.append(f"regimes.yaml: regime_id {rid} has no glossary term (kind: regime)")
    return errs


def set_version(session: Session, part: str, digest: str) -> str:
    """Record the digest of one input ("content" or "facts") and recompute meta.data_version from
    both, so `import-facts` invalidates ETags too (spec 019). generated_at moves only on change."""
    session.merge(Meta(key=f"{part}_version", value=digest))
    session.flush()
    parts = [session.get(Meta, f"{k}_version") for k in ("content", "facts")]
    blob = "|".join(m.value if m else "" for m in parts)
    version = hashlib.sha256(blob.encode()).hexdigest()[:16]
    cur = session.get(Meta, "data_version")
    if cur is None or cur.value != version:
        session.merge(Meta(key="data_version", value=version))
        session.merge(Meta(key="generated_at", value=datetime.now(UTC).isoformat()))
    session.flush()
    return version


def import_content(session: Session, root: Path) -> dict[str, Any]:
    """Caller owns the transaction (the CLI wraps this in session.begin())."""
    content = load_content(root)
    problems = validate(content)
    if problems:
        raise ContentError(problems)

    for s in content["sources"]:
        session.merge(Source(id=s["id"], title=s["title"], url=s.get("url"),
                             license=s.get("license"), retrieved_at=s.get("retrieved_at")))
    session.flush()

    keys = ("id", "name", "type", "start_year", "end_year", "end_precision", "iso2", "regime",
            "summary", "wikipedia_title", "wikidata_qid")
    unverified = events = 0
    for p in content["polities"]:
        pol = Polity(**{k: p.get(k) for k in keys},
                     start_precision=p.get("start_precision", "exact"))
        politics = p.get("politics") or {}
        pol.politics_system = politics.get("system")
        pol.politics_note = politics.get("note")
        pol.politics_updated_at = politics.get("updated_at")
        session.merge(pol)
    session.flush()

    ids = [p["id"] for p in content["polities"]]
    # Children are rebuilt from content: delete + insert is simpler than diffing.
    old = select(Event.id).where(Event.polity_id.in_(ids))
    session.execute(delete(EventSource).where(EventSource.event_id.in_(old)))
    session.execute(delete(Event).where(Event.polity_id.in_(ids)))
    session.execute(delete(PolityName).where(PolityName.polity_id.in_(ids)))
    session.execute(delete(Succession))
    for p in content["polities"]:
        for n in p.get("names") or []:
            session.add(PolityName(polity_id=p["id"], name=n["name"],
                                   from_year=n["from_year"], to_year=n.get("to_year")))
        for ev in p.get("events") or []:
            events += 1
            unverified += not ev.get("source_ids")
            session.add(Event(id=ev["id"], polity_id=p["id"], year_start=ev["year_start"],
                              year_end=ev.get("year_end"), precision=ev["precision"],
                              title=ev["title"], summary=ev.get("summary", ""), kind=ev["kind"]))
    session.flush()
    for p in content["polities"]:
        for ev in p.get("events") or []:
            for sid in ev.get("source_ids") or []:
                session.add(EventSource(event_id=ev["id"], source_id=sid))
    for s_ in content["succession"]:
        session.add(Succession(predecessor_id=s_["predecessor"], successor_id=s_["successor"],
                               year=s_["year"], kind=s_["kind"], note=s_.get("note")))

    # ponytail: terms removed from glossary.yaml are not deleted (country_facts FK); same as polities.
    keys_t = ("id", "kind", "label", "short", "body", "icon")
    for t in content["glossary"]:
        session.merge(GlossaryTerm(**{k: t.get(k) for k in keys_t}, sources=[
            {k: x.get(k) for k in ("id", "title", "url", "license", "retrieved_at")}
            for x in t["sources"]]))
    session.flush()

    blob = json.dumps(content, sort_keys=True, default=str, ensure_ascii=False)
    version = set_version(session, "content", hashlib.sha256(blob.encode()).hexdigest()[:16])
    return {"polities": len(ids), "events": events, "unverified_events": unverified,
            "sources": len(content["sources"]), "succession": len(content["succession"]),
            "glossary_terms": len(content["glossary"]),
            "data_version": version}
