"""All read queries (SQLAlchemy ORM, bound parameters only). Each function takes a Session and
returns contract (Pydantic) models, so routers stay thin. Business rules live in `rules.py`.
"""

import logging
import unicodedata
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, aliased, selectinload

from atlas_api.db.models import (
    Capital,
    Composition,
    CountryFacts,
    CountryHistory,
    CountryLanguage,
    CurrencyStat,
    Event,
    FxRate,
    GlossaryTerm,
    HistoryEvent,
    HistoryPeriod,
    IdeologyFigure,
    IdeologyParty,
    IdeologyPerson,
    Indicator,
    IndicatorDef,
    IndicatorLatest,
    IndicatorStat,
    Leader,
    Meta,
    Person,
    Polity,
    PolityName,
    Snapshot,
    SnapshotLink,
    Source,
    Subdivision,
    Succession,
)
from atlas_api.rules import has_content, name_as_of
from atlas_api.schemas import (
    CapitalCoord,
    Clues,
    CompareIndicator,
    CompositionOut,
    CountryDetail,
    CountryEconomy,
    CountryIdeologies,
    CountryIdeology,
    CountryProfile,
    CountrySummary,
    Counts,
    Currency,
    CurrencyDetail,
    CurrencyHistory,
    CurrencyStats,
    EconomyCompare,
    EconomyIndicator,
    Governed,
    HistoryItem,
    IdeologyDetail,
    Image,
    Language,
    LanguageSpoken,
    Link,
    Marker,
    NamePeriod,
    Party,
    PartyRef,
    PersonList,
    Point,
    Politics,
    PolityDetail,
    PolityList,
    PolitySummary,
    Population,
    ProfileGroup,
    ProfileIndicator,
    RateItem,
    Rates,
    SearchItem,
    Share,
    SnapshotInfo,
    Speakers,
    SubdivisionList,
    SubdivisionPopulation,
    Wikipedia,
    WorldStats,
    YearValue,
)
from atlas_api.schemas import CountryHistory as CountryHistoryOut
from atlas_api.schemas import Event as EventOut
from atlas_api.schemas import GlossaryTerm as GlossaryTermOut
from atlas_api.schemas import HistoryEvent as HistoryEventOut
from atlas_api.schemas import IdeologyFigure as IdeologyFigureOut
from atlas_api.schemas import Leader as LeaderOut
from atlas_api.schemas import (
    Meta as MetaOut,
)
from atlas_api.schemas import Period as PeriodOut
from atlas_api.schemas import Person as PersonOut
from atlas_api.schemas import (
    SnapshotLink as SnapshotLinkOut,
)
from atlas_api.schemas import Source as SourceOut
from atlas_api.schemas import Subdivision as SubdivisionOut

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


def _capital_coords(s: Session) -> dict[str, list[CapitalCoord]]:
    """iso2 -> every capital with coordinates (spec 019), in `capitals.ord` order."""
    out: dict[str, list[CapitalCoord]] = {}
    for c in s.scalars(select(Capital).where(Capital.lat.is_not(None), Capital.lng.is_not(None))
                       .order_by(Capital.iso2, Capital.ord)):
        out.setdefault(c.iso2, []).append(CapitalCoord(name=c.name, lat=c.lat or 0.0, lng=c.lng or 0.0))
    return out


def _clues(f: CountryFacts | None) -> Clues | None:
    if f is None or not (f.driving_side or f.calling_code or f.tld or f.plate_code or f.scripts):
        return None
    return Clues(driving_side=f.driving_side, calling_code=f.calling_code,
                 tld=f.tld, plate_code=f.plate_code, scripts=list(f.scripts or []))



def list_countries(s: Session) -> list[CountrySummary]:
    event_counts = {pid: n for pid, n in s.execute(select(Event.polity_id, func.count()).group_by(Event.polity_id))}
    markers = load_markers()
    capitals = _capital_coords(s)
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
            regime_id=f.regime_id if f else None, capital_coords=capitals.get(p.iso2 or "", []),
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
        languages_spoken=_languages_spoken(s, iso2),
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


# --- v1.2 part A: profile (spec 015), economy + currencies (spec 009) -----------------------

PROFILE_GROUPS: dict[str, tuple[str, ...]] = {
    "life": ("SP.DYN.LE00.IN", "SP.DYN.IMRT.IN", "SP.DYN.TFRT.IN", "HDR.HDI"),
    "society": ("SP.URB.TOTL.IN.ZS", "SE.ADT.LITR.ZS", "IT.NET.USER.ZS", "VC.IHR.PSRC.P5",
                "HDR.MYS"),
    "income": ("NY.GDP.PCAP.PP.CD", "SI.POV.GINI", "SI.POV.DDAY", "SL.UEM.TOTL.ZS"),
    "environment": ("EN.GHG.CO2.PC.CE.AR5", "EG.FEC.RNEW.ZS", "AG.LND.FRST.ZS"),
}
ECONOMY_IDS = ("NY.GDP.MKTP.CD", "NY.GDP.PCAP.PP.CD", "NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG",
               "SL.UEM.TOTL.ZS", "GC.DOD.TOTL.GD.ZS", "BN.CAB.XOKA.GD.ZS", "FI.RES.TOTL.CD",
               "SI.POV.GINI", "PA.NUS.PPP")
SERIES_YEARS = 20
HISTORY_MAX_DAYS = 30 * 366
WEEKLY_ABOVE_DAYS = 2 * 366
RATE_LOOKBACK_DAYS = 7


def _sources(s: Session, ids: set[str]) -> list[SourceOut]:
    return [_source(x) for x in s.scalars(select(Source).where(Source.id.in_(ids)).order_by(Source.id))]


def _languages_spoken(s: Session, iso2: str) -> list[LanguageSpoken]:
    return [
        LanguageSpoken(code=x.code, name=x.name, status=x.status, where=x.where,
                       speakers=Speakers(value=x.speakers, year=x.speakers_year)
                       if x.speakers is not None else None,
                       family=x.family, endangerment=x.endangerment, wikipedia_url=x.wikipedia_url)
        for x in s.scalars(select(CountryLanguage).where(CountryLanguage.iso2 == iso2)
                           .order_by(CountryLanguage.ord))
    ]


def get_profile(s: Session, iso2: str) -> CountryProfile:
    ids = [i for g in PROFILE_GROUPS.values() for i in g]
    defs = {d.id: d for d in s.scalars(select(IndicatorDef).where(IndicatorDef.id.in_(ids)))}
    stats = {x.id: x for x in s.scalars(select(IndicatorStat).where(IndicatorStat.id.in_(ids)))}
    latest = {x.id: x for x in s.scalars(select(IndicatorLatest).where(
        IndicatorLatest.iso2 == iso2, IndicatorLatest.id.in_(ids)))}
    groups, used = [], set()
    for gid, members in PROFILE_GROUPS.items():
        items = []
        for i in members:
            x, d, st = latest.get(i), defs.get(i), stats.get(i)
            if x is None or d is None:
                continue  # no value for this country: the indicator is left out of the group
            used.add(d.source_id)
            items.append(ProfileIndicator(
                id=i, label=d.label, unit=d.unit, value=x.value, year=x.year, source_id=d.source_id,
                rank=x.rank, rank_of=st.n if st else None,
                world=WorldStats(min=st.min, median=st.median, max=st.max) if st else None,
                region_avg=x.region_avg))
        groups.append(ProfileGroup(id=gid, indicators=items))
    comp = list(s.scalars(select(Composition).where(Composition.iso2 == iso2)
                          .order_by(Composition.kind, Composition.share.desc(), Composition.label)))
    by = {k: [Share(label=c.label, share=c.share) for c in comp if c.kind == k] or None
          for k in ("religion", "ethnicity")}
    years = [c.year for c in comp if c.year is not None]
    if comp:
        used.add("wikidata")
    return CountryProfile(
        groups=groups,
        composition=CompositionOut(religion=by["religion"], ethnicity=by["ethnicity"],
                                   year=max(years) if years else None,
                                   source_id="wikidata" if comp else None),
        sources=_sources(s, used))


def get_economy(s: Session, iso2: str) -> CountryEconomy:
    defs = {d.id: d for d in s.scalars(select(IndicatorDef).where(IndicatorDef.id.in_(ECONOMY_IDS)))}
    rows: dict[str, list[Indicator]] = {}
    for r in s.scalars(select(Indicator).where(Indicator.iso2 == iso2, Indicator.id.in_(ECONOMY_IDS))
                       .order_by(Indicator.id, Indicator.year)):
        rows.setdefault(r.id, []).append(r)
    out = []
    for i in ECONOMY_IDS:
        d = defs.get(i)
        if d is None:
            continue
        series = rows.get(i, [])
        last = series[-1] if series else None
        recent = [p for p in series if last and p.year > last.year - SERIES_YEARS]
        out.append(EconomyIndicator(
            id=i, label=d.label, unit=d.unit, value=last.value if last else None,
            year=last.year if last else None, source_id=d.source_id,
            series=[Point(year=p.year, value=p.value) for p in recent]))
    return CountryEconomy(indicators=out, sources=_sources(s, {d.source_id for d in defs.values()}))


def compare_economy(s: Session, countries: list[str], ids: list[str]) -> EconomyCompare:
    defs = {d.id: d for d in s.scalars(select(IndicatorDef).where(IndicatorDef.id.in_(ids)))}
    latest = {(x.id, x.iso2): x for x in s.scalars(select(IndicatorLatest).where(
        IndicatorLatest.id.in_(ids), IndicatorLatest.iso2.in_(countries)))}
    items = []
    for i in ids:
        d = defs.get(i)
        if d is None:
            continue
        vals: dict[str, YearValue | None] = {}
        for c in countries:
            x = latest.get((i, c))
            vals[c] = YearValue(value=x.value, year=x.year) if x else None
        items.append(CompareIndicator(id=i, label=d.label, unit=d.unit, values=vals))
    return EconomyCompare(countries=countries, indicators=items,
                          sources=_sources(s, {d.source_id for d in defs.values()}))


def _currency_info(s: Session, code: str) -> tuple[str, str | None, list[str]] | None:
    """(name, symbol, iso2 list) from country_facts.currencies (Wikidata P38), or None."""
    name, symbol, isos = None, None, []
    for iso2, curs in s.execute(select(CountryFacts.iso2, CountryFacts.currencies)
                                .order_by(CountryFacts.iso2)):
        for c in curs or []:
            if c.get("code") == code:
                isos.append(iso2)
                name, symbol = name or c.get("name"), symbol or c.get("symbol")
    return (name, symbol, isos) if name else None


def currency_known(s: Session, code: str) -> bool:
    return s.scalar(select(FxRate.code).where(FxRate.code == code).limit(1)) is not None


def get_currency(s: Session, code: str) -> CurrencyDetail | None:
    info = _currency_info(s, code)
    if info is None:
        return None
    name, symbol, isos = info
    last = s.scalar(select(func.max(FxRate.date)).where(FxRate.code == code))
    rates, used = None, set()
    if last is not None:
        mine = s.scalars(select(FxRate).where(FxRate.code == code, FxRate.date == last)).one()
        others = s.scalars(
            select(FxRate).distinct(FxRate.code)
            .where(FxRate.code != code, FxRate.date <= last,
                   FxRate.date >= last - timedelta(days=RATE_LOOKBACK_DAYS))
            .order_by(FxRate.code, FxRate.date.desc()))
        items = []
        for o in others:  # 1 unit of `code` = rate units of o.code (both quoted per 1 EUR)
            items.append(RateItem(code=o.code, rate=o.rate / mine.rate))
            used.add(o.source_id)
        used.add(mine.source_id)
        rates = Rates(date=last.isoformat(), base=code, items=items)
    st = s.get(CurrencyStat, code)
    return CurrencyDetail(
        code=code, name=name, symbol=symbol, countries=isos, rates=rates,
        stats=CurrencyStats(change_1y=st.change_1y, change_5y=st.change_5y,
                            volatility_1y=st.volatility_1y, max_drawdown_1y=st.max_drawdown_1y)
        if st else None,
        sources=_sources(s, used | {"wikidata"}))


def currency_history(s: Session, base: str, vs: list[str], start: date | None,
                     end: date | None) -> CurrencyHistory:
    """Cross rates base->vs per date (1 base = x vs); weekly (last point of each ISO week) when
    the window is longer than 2 years. Caller validates codes and the window."""
    a, b = aliased(FxRate), aliased(FxRate)
    end = end or s.scalar(select(func.max(FxRate.date)).where(FxRate.code == base)) or date.today()
    start = start or end - timedelta(days=365)
    rows = s.execute(
        select(a.date, b.code, (b.rate / a.rate).label("x"), a.source_id, b.source_id)
        .join(b, b.date == a.date)
        .where(a.code == base, b.code.in_(vs), a.date >= start, a.date <= end)
        .order_by(a.date, b.code)).all()
    by: dict[date, dict[str, float]] = {}
    secondary = False
    for d, code, x, sa, sb in rows:
        by.setdefault(d, {})[code] = x
        secondary = secondary or "exchange-api" in (sa, sb)
    days = sorted(by)
    if (end - start).days > WEEKLY_ABOVE_DAYS:
        week: dict[tuple[int, int], date] = {}
        for d in days:
            week[d.isocalendar()[:2]] = d  # the last day seen in each ISO week wins
        days = sorted(week.values())
    src = s.get(Source, "exchange-api" if secondary else "ecb")
    assert src is not None, "fx sources are written by import-facts together with the rates"
    return CurrencyHistory(base=base, vs=vs, source=_source(src),
                           items=[HistoryItem(date=d.isoformat(), rates=by[d]) for d in days])


def _in_period(y: int, start: int | None, end: int | None) -> bool:
    """Event year inside a period's years; a period without any year holds no events (event_count 0)."""
    if start is None and end is None:
        return False
    return (start is None or y >= start) and (end is None or y <= end)


def get_history(s: Session, iso2: str) -> CountryHistoryOut:
    """spec 016: condensed pt.wikipedia history (stage 1) + Wikidata events (stage 2). Nothing = empty lists, summary null."""
    h = s.get(CountryHistory, iso2)
    evs = list(s.scalars(select(HistoryEvent).where(HistoryEvent.iso2 == iso2)
                         .order_by(HistoryEvent.year_start, HistoryEvent.qid)))
    events = [HistoryEventOut(id=e.qid, title=e.title, summary=e.summary, kind=e.kind, year_start=e.year_start,
                              year_end=e.year_end, wikipedia_url=e.wikipedia_url) for e in evs]
    sources = _sources(s, {"wikidata"}) if events else []
    if h is None:
        return CountryHistoryOut(summary=None, periods=[], events=events, sources=sources)
    rows = s.scalars(select(HistoryPeriod).where(HistoryPeriod.iso2 == iso2).order_by(HistoryPeriod.ord))
    periods = [PeriodOut(id=f"{iso2.lower()}-{p.ord + 1}", title=p.title, year_start=p.year_start, year_end=p.year_end,
                         summary=p.text, event_count=sum(_in_period(e.year_start, p.year_start, p.year_end) for e in evs))
               for p in rows]
    rev = f" (revisão {h.revision})" if h.revision else ""
    url = f"https://pt.wikipedia.org/w/index.php?oldid={h.revision}" if h.revision else h.article_url
    src = SourceOut(id="wikipedia-pt", title=f"Wikipédia: {h.article_title}{rev}", url=url,
                    license="CC BY-SA 4.0", retrieved_at=h.retrieved_at)
    return CountryHistoryOut(summary=h.summary, periods=periods, events=events, sources=[src, *sources])


def list_subdivisions(s: Session, iso2: str) -> SubdivisionList:
    """spec 024: the country's admin-1 units in the web's file order; empty when the country has none."""
    rows = list(s.scalars(select(Subdivision).where(Subdivision.iso2 == iso2).order_by(Subdivision.ord)))
    items = [SubdivisionOut(
        wikidata_id=x.wikidata_id, code=x.code, name=x.name, capital=x.capital, area_km2=x.area_km2,
        population=SubdivisionPopulation(value=x.population, year=x.population_year) if x.population is not None else None,
        flag=Image(url=x.flag_url, credit=x.flag_credit or "", license=x.flag_license or "") if x.flag_url else None)
        for x in rows]
    return SubdivisionList(items=items, sources=_sources(s, {"wikidata"}) if items else [])


# --- ideologies (spec 018) ------------------------------------------------------------------------------------------------
PARTIES_SHOWN = 5


def _figures(s: Session, ideology_ids: list[str], scope: str) -> dict[str, list[IdeologyFigureOut]]:
    rows = s.execute(select(IdeologyFigure, IdeologyPerson).join(IdeologyPerson, IdeologyPerson.person_id == IdeologyFigure.person_id)
                     .where(IdeologyFigure.scope == scope, IdeologyFigure.ideology_id.in_(ideology_ids))
                     .order_by(IdeologyFigure.ideology_id, IdeologyFigure.ord)).all()
    out: dict[str, list[IdeologyFigureOut]] = {}
    for f, p in rows:
        image = Image(url=p.image_url, credit=p.image_credit or "", license=p.image_license or "") if p.image_url else None
        out.setdefault(f.ideology_id, []).append(IdeologyFigureOut(
            person_id=p.person_id, name=p.name, role=p.role, birth_year=p.birth_year, death_year=p.death_year,
            summary=p.summary, works=p.works, image=image, wikipedia_url=p.wikipedia_url, via=f.via,
            party=PartyRef(id=f.party_id, name=f.party_name) if f.party_id and f.party_name else None))
    return out


def list_country_ideologies(s: Session, iso2: str) -> CountryIdeologies:
    """spec 018: currents present in the country (figures or parties), most figures first, then A-Z."""
    terms = {t.id: t for t in s.scalars(select(GlossaryTerm).where(GlossaryTerm.kind == "ideology"))}
    figs = _figures(s, list(terms), iso2)
    parties: dict[str, list[PartyRef]] = {}
    for p in s.scalars(select(IdeologyParty).where(IdeologyParty.iso2 == iso2).order_by(IdeologyParty.ideology_id, IdeologyParty.ord)):
        if len(parties.setdefault(p.ideology_id, [])) < PARTIES_SHOWN:
            parties[p.ideology_id].append(PartyRef(id=p.party_id, name=p.name))
    ids = sorted(set(figs) | set(parties), key=lambda i: (-len(figs.get(i, [])), terms[i].label))
    ex = _examples(s, [terms[i] for i in ids]) if ids else {}
    items = [CountryIdeology(term=_term(terms[i], ex[i]), figures=figs.get(i, []), parties=parties.get(i, []), milestones=[])
             for i in ids]
    return CountryIdeologies(items=items, sources=_sources(s, {"wikidata"}) if items else [])


def _merge_terms(terms: list[tuple[str, int, int | None]]) -> list[Governed]:
    """(iso2, from, to) mandates -> one row per continuous stretch in a country (to None = still in office)."""
    out: list[Governed] = []
    for iso2, start, end in sorted(terms, key=lambda t: (t[0], t[1])):
        last = out[-1] if out and out[-1].iso2 == iso2 else None
        if last and (last.to_year is None or start <= last.to_year + 1):
            last.to_year = None if last.to_year is None or end is None else max(last.to_year, end)
        else:
            out.append(Governed(iso2=iso2, from_year=start, to_year=end))
    return out


def get_ideology(s: Session, ideology_id: str) -> IdeologyDetail | None:
    """spec 018: the current worldwide. governed = heads of state/government (spec 006) whose party has this current."""
    t = s.get(GlossaryTerm, ideology_id)
    if t is None or t.kind != "ideology":
        return None
    party_ids = set(s.scalars(select(IdeologyParty.party_id).where(IdeologyParty.ideology_id == ideology_id)))
    mandates = []
    if party_ids:
        for ld in s.scalars(select(Leader).where(Leader.party_id.in_(party_ids), Leader.start.is_not(None))):
            y0 = int(ld.start[:4]) if ld.start and ld.start[:4].isdigit() else None
            y1 = int(ld.end[:4]) if ld.end and ld.end[:4].isdigit() else None
            if y0:
                mandates.append((ld.iso2, y0, y1))
    sources = _sources(s, {"wikidata"})
    return IdeologyDetail(term=_term(t, _examples(s, [t])[t.id]), founders=_figures(s, [ideology_id], "WORLD").get(ideology_id, []),
                          timeline=[], governed=_merge_terms(mandates), sources=sources)
