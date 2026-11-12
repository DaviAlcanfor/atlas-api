"""import-facts: data_out/wikidata.json -> country_facts (+ the `wikidata` source row), and,
when present, data_out/leaders.json -> leaders and data_out/pantheon.json -> people (+ the
`pantheon` source row and its method text in meta). v1.2: languages.json -> country_languages
(spec 017); worldbank.json + undp.json -> indicators + precomputed world/regional stats (specs 009,
015); fx.json -> fx_rates + currency_stats (spec 009); wikidata.json composition -> compositions.

Reads plain JSON files (the API process never imports the `etl` group). Only countries that
already exist as polities (iso2) are imported; others are reported, never created here.
Idempotent: upsert by iso2 (leaders: delete + insert per file), one transaction (the CLI owns it).
meta.data_version is recomputed from the bytes of every file read (spec 019), so a new import
invalidates the ETags.
Run import-content first: regime_id references glossary_terms; an id without a term is dropped
(set to null) and reported.
"""

import hashlib
import itertools
import json
import math
import statistics
from bisect import bisect_right
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from atlas_api.db.models import (
    Capital,
    Composition,
    CountryFacts,
    CountryHistory,
    CountryLanguage,
    CurrencyStat,
    FxRate,
    GlossaryTerm,
    HistoryPeriod,
    Indicator,
    IndicatorDef,
    IndicatorLatest,
    IndicatorStat,
    Leader,
    Meta,
    Person,
    Polity,
    Source,
)
from atlas_api.importer import set_version


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
    session.execute(delete(Capital))
    session.execute(delete(Composition))
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
        for i, cap in enumerate(c.get("capitals") or []):
            session.add(Capital(iso2=iso2, ord=i, name=cap["name"], lat=cap["lat"], lng=cap["lng"]))
        for kind, comp in (c.get("composition") or {}).items():
            for item in comp["items"]:
                session.add(Composition(iso2=iso2, kind=kind, label=item["label"],
                                        share=item["share"], year=comp["year"]))
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
    langs = path.parent / "languages.json"
    if langs.exists():
        summary["languages_imported"] = import_languages(session, langs, known)
    ind_files = [f for f in (path.parent / "worldbank.json", path.parent / "undp.json") if f.exists()]
    if ind_files:
        summary["indicator_values_imported"] = import_indicators(session, ind_files, known)
    fx = path.parent / "fx.json"
    if fx.exists():
        summary["fx_rates_imported"] = import_fx(session, fx)
    history = path.parent / "history.json"
    if history.exists():
        summary["history_imported"] = import_history(session, history, known)
    read = [f for f in (path, leaders, people, langs, *ind_files, fx, history) if f.exists()]
    digest = hashlib.sha256(b"".join(f.read_bytes() for f in read)).hexdigest()[:16]
    summary["data_version"] = set_version(session, "facts", digest)
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


def import_history(session: Session, path: Path, known: set[str | None]) -> int:
    """spec 016 stage 1: data_out/history.json -> country_history + history_periods (rebuilt)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    session.execute(delete(HistoryPeriod))
    session.execute(delete(CountryHistory))
    session.flush()
    n = 0
    for iso2, h in data["countries"].items():
        if iso2 not in known:
            continue
        session.add(CountryHistory(iso2=iso2, summary=h.get("summary"), article_title=h["title"],
                                   article_url=h["url"], revision=h.get("revision"),
                                   retrieved_at=h.get("retrieved_at")))
        session.flush()
        for i, p in enumerate(h["periods"]):
            session.add(HistoryPeriod(iso2=iso2, ord=i, title=p["title"], year_start=p.get("year_start"),
                                      year_end=p.get("year_end"), text=p["text"]))
        n += 1
    session.flush()
    return n


def import_languages(session: Session, path: Path, known: set[str | None]) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    session.execute(delete(CountryLanguage))
    n = 0
    for iso2, langs in data["countries"].items():
        if iso2 not in known:
            continue
        for i, x in enumerate(langs):
            sp = x.get("speakers") or {}
            session.add(CountryLanguage(
                iso2=iso2, qid=x["qid"], ord=i, code=x.get("code"), name=x["name"],
                status=x["status"], where=x.get("where"), speakers=sp.get("value"),
                speakers_year=sp.get("year"), family=x.get("family"),
                endangerment=x.get("endangerment"), wikipedia_url=x.get("wikipedia_url")))
            n += 1
    session.flush()
    return n


def _ranks(values: dict[str, float]) -> dict[str, int]:
    """Competition ranking, 1 = highest value (ties share a rank)."""
    ordered = sorted(values.values(), reverse=True)
    first: dict[float, int] = {}
    for i, v in enumerate(ordered):
        first.setdefault(v, i + 1)
    return {k: first[v] for k, v in values.items()}


def import_indicators(session: Session, files: list[Path], known: set[str | None]) -> int:
    """Rebuild indicators from the ETL files, then the latest-value stats (spec 015)."""
    for t in (IndicatorLatest, IndicatorStat, Indicator, IndicatorDef):
        session.execute(delete(t))
    session.flush()
    rows: list[dict[str, Any]] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        src = data["source"]
        retrieved = data["retrieved_at"]
        when = max(retrieved.values()) if isinstance(retrieved, dict) else retrieved
        session.merge(Source(id=src["id"], title=src["title"], url=src["url"],
                             license=src["license"], retrieved_at=datetime.fromisoformat(when)))
        session.flush()  # no ORM relationship: the source row must exist before its defs
        for ind, meta in data["indicators"].items():
            session.add(IndicatorDef(id=ind, label=meta["label"], unit=meta["unit"],
                                     source_id=src["id"]))
        rows += [{"iso2": r["iso2"], "id": r["indicator_id"], "year": r["year"],
                  "value": float(r["value"]), "source_id": src["id"]}
                 for r in data["rows"] if r["iso2"] in known]
    session.flush()
    if rows:
        session.execute(insert(Indicator), rows)
    regions = {iso: reg for iso, reg in session.execute(select(CountryFacts.iso2, CountryFacts.region))}
    latest: dict[str, dict[str, tuple[int, float]]] = {}
    for r in rows:
        cur = latest.setdefault(r["id"], {}).get(r["iso2"])
        if cur is None or r["year"] > cur[0]:
            latest[r["id"]][r["iso2"]] = (r["year"], r["value"])
    for ind, by in latest.items():
        vals = {k: v for k, (_, v) in by.items()}
        session.add(IndicatorStat(id=ind, n=len(vals), min=min(vals.values()),
                                  median=statistics.median(vals.values()), max=max(vals.values())))
        ranks = _ranks(vals)
        by_region: dict[str | None, list[float]] = {}
        for iso2, v in vals.items():
            by_region.setdefault(regions.get(iso2), []).append(v)
        for iso2, (year, v) in by.items():
            reg = regions.get(iso2)
            session.add(IndicatorLatest(iso2=iso2, id=ind, year=year, value=v, rank=ranks[iso2],
                                        region_avg=statistics.fmean(by_region[reg]) if reg else None))
    session.flush()
    return len(rows)


def currency_stats(series: list[tuple[date, float]]) -> dict[str, float | None]:
    """Stats of a price series (value of 1 unit in the reference currency), sorted by date.
    change_Ny = last / value N years before (nearest earlier point, at most 14 days off) - 1;
    volatility_1y = sample stdev of log returns in the last year x sqrt(number of returns in that
    year), i.e. annualised whatever the frequency (daily ECB, weekly secondary);
    max_drawdown_1y = worst fall from a running peak inside the last year (<= 0)."""
    dates = [d for d, _ in series]
    last_d, last_v = series[-1]

    def change(days: int) -> float | None:
        target = last_d - timedelta(days=days)
        i = bisect_right(dates, target) - 1
        ok = i >= 0 and (target - dates[i]).days <= 14
        return last_v / series[i][1] - 1 if ok else None

    year = [v for d, v in series if d >= last_d - timedelta(days=365)]
    rets = [math.log(b / a) for a, b in itertools.pairwise(year)]
    vol = statistics.stdev(rets) * math.sqrt(len(rets)) if len(rets) >= 20 else None
    peak, mdd = year[0], 0.0
    for v in year:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return {"change_1y": change(365), "change_5y": change(5 * 365), "volatility_1y": vol,
            "max_drawdown_1y": mdd if len(year) >= 2 else None}


def import_fx(session: Session, path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    for src in data["sources"]:
        session.merge(Source(id=src["id"], title=src["title"], url=src["url"],
                             license=src["license"],
                             retrieved_at=datetime.fromisoformat(data["retrieved_at"])))
    session.execute(delete(FxRate))
    session.execute(delete(CurrencyStat))
    session.flush()
    rows = [{"date": date.fromisoformat(d), "code": c, "rate": float(r), "source_id": s}
            for d, c, r, s in data["rows"]]
    if rows:
        session.execute(insert(FxRate), rows)
    by: dict[str, dict[date, float]] = {}
    for r in rows:
        by.setdefault(r["code"], {})[r["date"]] = r["rate"]
    for code, rates in by.items():
        vs = "EUR" if code == "USD" else "USD"
        ref = by.get(vs, {})
        series = sorted((d, ref[d] / rate) for d, rate in rates.items() if d in ref)
        if len(series) >= 2:
            session.add(CurrencyStat(code=code, vs=vs, as_of=series[-1][0], **currency_stats(series)))
    session.flush()
    return len(rows)
