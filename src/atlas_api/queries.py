"""All read queries (SQLAlchemy ORM, bound parameters only). Each function takes a Session and
returns contract (Pydantic) models, so routers stay thin. Business rules live in `rules.py`.
"""

import logging
import unicodedata
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from atlas_api.db.models import (
    CountryFacts,
    Event,
    GlossaryTerm,
    Leader,
    Meta,
    Person,
    Polity,
    PolityName,
    Snapshot,
    SnapshotLink,
    Source,
    Succession,
)
from atlas_api.rules import has_content, name_as_of
from atlas_api.schemas import (
    CapitalCoord,
    Clues,
    CountryDetail,
    CountrySummary,
    Counts,
    Currency,
    Image,
    Language,
    Link,
    Marker,
    NamePeriod,
    Party,
    PersonList,
    Politics,
    PolityDetail,
    PolityList,
    PolitySummary,
    Population,
    SearchItem,
    SnapshotInfo,
    Wikipedia,
)
from atlas_api.schemas import Event as EventOut
from atlas_api.schemas import GlossaryTerm as GlossaryTermOut
from atlas_api.schemas import Leader as LeaderOut
from atlas_api.schemas import (
    Meta as MetaOut,
)
from atlas_api.schemas import Person as PersonOut
from atlas_api.schemas import (
    SnapshotLink as SnapshotLinkOut,
)
from atlas_api.schemas import Source as SourceOut

log = logging.getLogger("atlas_api")
YEAR_MIN = -3000  # ponytail: fixed lower bound of the slider; move to config if it ever changes
MARKERS_FILE = Path("content/markers.yaml")


def year_max() -> int:
    return date.today().year


def _ts(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z") if dt else None


def _source(s: Source) -> SourceOut:
    return SourceOut(id=s.id, title=s.title, url=s.url, license=s.license,
                     retrieved_at=_ts(s.retrieved_at))


def _event(e: Event) -> EventOut:
    return EventOut(id=e.id, year_start=e.year_start, year_end=e.year_end, precision=e.precision,
                    title=e.title, summary=e.summary, kind=e.kind,
                    source_ids=sorted(s.id for s in e.sources))


def _politics(p: Polity) -> Politics | None:
    if not (p.politics_system or p.politics_note or p.politics_updated_at):
        return None
    return Politics(system=p.politics_system, note=p.politics_note, updated_at=_ts(p.politics_updated_at))


@lru_cache
def load_markers() -> dict[str, Marker]:
    if not MARKERS_FILE.exists():
        log.warning("%s not found: no micro-state markers will be served", MARKERS_FILE)
        return {}
    raw = yaml.safe_load(MARKERS_FILE.read_text(encoding="utf-8")) or {}
    return {str(k): Marker(lat=v["lat"], lng=v["lng"]) for k, v in raw.items()}


def ping(s: Session) -> None:
    s.execute(text("SELECT 1"))


def data_version(s: Session) -> str:
    row = s.get(Meta, "data_version")
    return row.value if row else "empty"


# --- meta -----------------------------------------------------------------------------------


def get_meta(s: Session) -> MetaOut:
    generated = s.get(Meta, "generated_at")
    return MetaOut(
        data_version=data_version(s),
        generated_at=generated.value if generated else "1970-01-01T00:00:00Z",
        year_min=YEAR_MIN,
        year_max=year_max(),
        snapshot_years=list(s.scalars(select(Snapshot.year).order_by(Snapshot.year))),
        counts=Counts(
            countries=s.scalar(select(func.count()).select_from(Polity).where(Polity.iso2.is_not(None))) or 0,
            polities=s.scalar(select(func.count()).select_from(Polity)) or 0,
            events=s.scalar(select(func.count()).select_from(Event)) or 0,
        ),
    )


# --- countries ------------------------------------------------------------------------------


def _regime(p: Polity, f: CountryFacts | None) -> str | None:
    """Wikidata regime (spec 004) overrides the legacy, unverified seed text."""
    return f.regime if f and f.regime_id else p.regime


def _capital_coords(f: CountryFacts | None) -> list[CapitalCoord]:
    # ponytail: one capital (preferred rank) from the current columns; spec 005 phase 2 adds more.
    if f is None or f.capital is None or f.capital_lat is None or f.capital_lng is None:
        return []
    return [CapitalCoord(name=f.capital, lat=f.capital_lat, lng=f.capital_lng)]


def _clues(f: CountryFacts | None) -> Clues | None:
    if f is None or not (f.driving_side or f.calling_code or f.tld or f.plate_code or f.scripts):
        return None
    return Clues(driving_side=f.driving_side, calling_code=f.calling_code,
                 tld=f.tld, plate_code=f.plate_code, scripts=list(f.scripts or []))



def list_countries(s: Session) -> list[CountrySummary]:
    event_counts = {pid: n for pid, n in s.execute(select(Event.polity_id, func.count()).group_by(Event.polity_id))}
    markers = load_markers()
    rows = s.execute(
        select(Polity, CountryFacts)
        .outerjoin(CountryFacts, CountryFacts.iso2 == Polity.iso2)
        .where(Polity.iso2.is_not(None))
        .order_by(Polity.name, Polity.id)
    )
    return [
        CountrySummary(
            iso2=p.iso2 or "", polity_id=p.id, name=p.name,
            capital=f.capital if f else None, region=f.region if f else None, regime=_regime(p, f),
            has_content=has_content(p.summary, event_counts.get(p.id, 0)),
            marker=markers.get(p.iso2 or ""),
            regime_id=f.regime_id if f else None, capital_coords=_capital_coords(f),
        )
        for p, f in rows
    ]


def get_country(s: Session, iso2: str) -> CountryDetail | None:
    p = s.scalar(
        select(Polity).where(Polity.iso2 == iso2)
        .options(selectinload(Polity.events).selectinload(Event.sources))
    )
    if p is None:
        return None
    f = s.get(CountryFacts, iso2)
    sources: dict[str, Source] = {src.id: src for e in p.events for src in e.sources}
    if f and f.source_id and (fs := s.get(Source, f.source_id)):
        sources[fs.id] = fs
    population = None
    if f and f.population is not None and f.source_id:
        population = Population(value=f.population, year=f.population_year, source_id=f.source_id)
    return CountryDetail(
        iso2=iso2, polity_id=p.id, name=p.name,
        official_name=f.official_name if f else None, capital=f.capital if f else None,
        flag_url=f.flag_url if f else None, region=f.region if f else None,
        regime=_regime(p, f), summary=p.summary,
        # The contract needs a code for every language/currency; entries without one are dropped.
        languages=[Language(code=x["code"], name=x["name"]) for x in (f.languages or [] if f else [])
                   if x.get("code") and x.get("name")],
        currencies=[Currency(code=x["code"], name=x["name"], symbol=x.get("symbol"))
                    for x in (f.currencies or [] if f else []) if x.get("code") and x.get("name")],
        population=population, area_km2=f.area_km2 if f else None,
        memberships=sorted(f.memberships or []) if f else [],
        politics=_politics(p),
        timeline=[_event(e) for e in p.events],  # relationship is ordered by (year_start, id)
        sources=[_source(x) for _, x in sorted(sources.items())],
        updated_at=_ts(p.updated_at) or "",
        regime_id=f.regime_id if f else None, clues=_clues(f),
    )


def country_exists(s: Session, iso2: str) -> bool:
    return s.scalar(select(Polity.id).where(Polity.iso2 == iso2)) is not None


def list_leaders(s: Session, iso2: str, role: str | None) -> list[LeaderOut]:
    """Terms of office, oldest first (unknown start last); `role` filters when given."""
    stmt = select(Leader).where(Leader.iso2 == iso2)
    if role is not None:
        stmt = stmt.where(Leader.role == role)
    rows = s.scalars(stmt.order_by(Leader.start.is_(None), Leader.start, Leader.person_id, Leader.id))
    return [
        LeaderOut(
            person_id=x.person_id, name=x.name, role=x.role,
            office=x.office, start=x.start, end=x.end,
            party=Party(id=x.party_id, name=x.party_name) if x.party_id and x.party_name else None,
            image=_image(x.image_url, x.image_credit, x.image_license),
            wikipedia_url=x.wikipedia_url,
        )
        for x in rows
    ]


def _image(url: str | None, credit: str | None, lic: str | None) -> Image | None:
    return Image(url=url, credit=credit, license=lic) if url and credit and lic else None


def list_people(s: Session, iso2: str, domain: str | None, limit: int) -> PersonList | None:
    """Pantheon rank order; None when the people dataset was never imported."""
    src, method = s.get(Source, "pantheon"), s.get(Meta, "people_method")
    if src is None or method is None:
        return None
    stmt = select(Person).where(Person.iso2 == iso2)
    if domain is not None:
        stmt = stmt.where(Person.domain == domain)
    rows = s.scalars(stmt.order_by(Person.rank).limit(limit))
    return PersonList(
        items=[PersonOut(id=p.id, name=p.name, occupation=p.occupation, domain=p.domain,
                         birth_year=p.birth_year, death_year=p.death_year,
                         image=_image(p.image_url, p.image_credit, p.image_license),
                         wikipedia_url=p.wikipedia_url, rank=p.rank) for p in rows],
        method=method.value, source=_source(src))


# --- glossary -------------------------------------------------------------------------------

EXAMPLES_MAX = 8


def _examples(s: Session, terms: list[GlossaryTerm]) -> dict[str, list[str]]:
    """term id -> up to 8 iso2, by country name: same regime_id / region contains the label /
    membership in the list. One pass over the 196 country rows."""
    rows = list(s.execute(
        select(Polity.iso2, CountryFacts.regime_id, CountryFacts.region, CountryFacts.memberships)
        .join(CountryFacts, CountryFacts.iso2 == Polity.iso2).order_by(Polity.name, Polity.id)
    ))
    out: dict[str, list[str]] = {}
    for t in terms:
        if t.kind == "regime":
            hits = [r[0] for r in rows if r[1] == t.id]
        elif t.kind == "region":
            hits = [r[0] for r in rows if t.label in (r[2] or "").split(" / ")]
        elif t.kind == "membership":
            hits = [r[0] for r in rows if t.label in (r[3] or [])]
        else:
            hits = []
        out[t.id] = [h for h in hits if h][:EXAMPLES_MAX]
    return out


def _term(t: GlossaryTerm, examples: list[str]) -> GlossaryTermOut:
    return GlossaryTermOut(
        id=t.id, kind=t.kind, label=t.label, short=t.short, body=t.body,
        icon=t.icon, examples=examples,
        sources=[SourceOut(id=x["id"] or "", title=x["title"] or "", url=x.get("url"),
                           license=x.get("license"), retrieved_at=x.get("retrieved_at"))
                 for x in t.sources],
    )


def list_glossary(s: Session) -> list[GlossaryTermOut]:
    terms = list(s.scalars(select(GlossaryTerm).order_by(GlossaryTerm.kind, GlossaryTerm.label)))
    ex = _examples(s, terms)
    return [_term(t, ex[t.id]) for t in terms]


def get_glossary_term(s: Session, term_id: str) -> GlossaryTermOut | None:
    t = s.get(GlossaryTerm, term_id)
    return _term(t, _examples(s, [t])[t.id]) if t else None


# --- polities -------------------------------------------------------------------------------


def list_polities(s: Session, year: int | None, limit: int, offset: int) -> PolityList:
    cond: list[Any] = []
    if year is not None:
        cond = [Polity.start_year <= year, or_(Polity.end_year.is_(None), Polity.end_year >= year)]
    total = s.scalar(select(func.count()).select_from(Polity).where(*cond)) or 0
    rows = list(
        s.scalars(select(Polity).where(*cond).order_by(Polity.start_year, Polity.id)
                  .offset(offset).limit(limit))
    )
    periods: dict[str, list[tuple[str, int, int | None]]] = {}
    if year is not None and rows:
        for n in s.scalars(select(PolityName).where(PolityName.polity_id.in_([p.id for p in rows]))):
            periods.setdefault(n.polity_id, []).append((n.name, n.from_year, n.to_year))
    items = [
        PolitySummary(
            id=p.id, type=p.type,
            name=name_as_of(p.name, periods.get(p.id, []), year) if year is not None else p.name,
            start_year=p.start_year, end_year=p.end_year, iso2=p.iso2,
        )
        for p in rows
    ]
    return PolityList(year=year, items=items, total=total)


def _links(s: Session, polity_id: str, *, predecessors: bool) -> list[Link]:
    other, mine = (Succession.predecessor_id, Succession.successor_id) if predecessors else (
        Succession.successor_id, Succession.predecessor_id)
    rows = s.execute(
        select(Succession, Polity).join(Polity, Polity.id == other).where(mine == polity_id)
        .order_by(Succession.year, Polity.id)
    )
    return [Link(polity_id=p.id, name=p.name, year=sc.year, kind=sc.kind) for sc, p in rows]


def get_polity(s: Session, polity_id: str) -> PolityDetail | None:
    p = s.scalar(
        select(Polity).where(Polity.id == polity_id)
        .options(selectinload(Polity.names), selectinload(Polity.events).selectinload(Event.sources))
    )
    if p is None:
        return None
    sources = {src.id: src for e in p.events for src in e.sources}
    return PolityDetail(
        id=p.id, name=p.name, type=p.type, start_year=p.start_year, end_year=p.end_year,
        iso2=p.iso2, start_precision=p.start_precision, end_precision=p.end_precision,
        names=[NamePeriod(name=n.name, from_year=n.from_year, to_year=n.to_year) for n in p.names],
        predecessors=_links(s, p.id, predecessors=True),
        successors=_links(s, p.id, predecessors=False),
        regime=p.regime, summary=p.summary, politics=_politics(p),
        timeline=[_event(e) for e in p.events],
        wikipedia=Wikipedia(title=p.wikipedia_title,
                            url="https://pt.wikipedia.org/wiki/" + p.wikipedia_title.replace(" ", "_"))
        if p.wikipedia_title else None,
        sources=[_source(x) for _, x in sorted(sources.items())],
        updated_at=_ts(p.updated_at) or "",
    )


# --- search ---------------------------------------------------------------------------------


def _fold(text_: str) -> str:
    """lowercase + strip accents, same idea as lower(f_unaccent(col)) used by the index."""
    return "".join(c for c in unicodedata.normalize("NFKD", text_.casefold())
                   if not unicodedata.combining(c))


def search(s: Session, q: str, limit: int) -> list[SearchItem]:
    needle = _fold(q.strip())
    best: dict[str, tuple[int, Polity]] = {}  # polity id -> (0 prefix / 1 substring, polity)
    for table_name, col in ((Polity, Polity.name), (PolityName, PolityName.name)):
        expr = func.lower(func.public.f_unaccent(col))
        for rank, cond in ((0, expr.startswith(needle, autoescape=True)),
                           (1, expr.contains(needle, autoescape=True))):
            stmt = (select(Polity).join(PolityName, PolityName.polity_id == Polity.id).where(cond)
                    if table_name is PolityName else select(Polity).where(cond))
            for p in s.scalars(stmt):
                if p.id not in best or rank < best[p.id][0]:
                    best[p.id] = (rank, p)
    ordered = sorted(best.values(), key=lambda t: (t[0], _fold(t[1].name), t[1].id))[:limit]
    # For kind "country", `id` is the polity id too (use `iso2` to call /countries/{iso2}).
    return [SearchItem(kind="country" if p.iso2 else "polity", id=p.id, name=p.name, iso2=p.iso2,
                       start_year=p.start_year, end_year=p.end_year) for _, p in ordered]


# --- snapshots ------------------------------------------------------------------------------


def list_snapshots(s: Session) -> list[SnapshotInfo]:
    linked = {
        year: n
        for year, n in s.execute(
            select(SnapshotLink.snapshot_year, func.count())
            .where(SnapshotLink.polity_id.is_not(None)).group_by(SnapshotLink.snapshot_year)
        )
    }
    return [
        SnapshotInfo(year=x.year, geometry_url=x.geometry_path, feature_count=x.feature_count,
                     link_coverage=min(1.0, linked.get(x.year, 0) / x.feature_count) if x.feature_count else 0.0)
        for x in s.scalars(select(Snapshot).order_by(Snapshot.year))
    ]


def snapshot_links(s: Session, year: int) -> list[SnapshotLinkOut] | None:
    if s.get(Snapshot, year) is None:
        return None
    rows = s.scalars(select(SnapshotLink).where(SnapshotLink.snapshot_year == year)
                     .order_by(SnapshotLink.source_name))
    return [SnapshotLinkOut(source_name=r.source_name, polity_id=r.polity_id, status=r.status)
            for r in rows]
