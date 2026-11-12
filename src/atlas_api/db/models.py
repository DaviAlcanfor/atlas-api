"""SQLAlchemy 2.0 ORM models: the data model of the project (tables, CHECKs, indexes).

Enum-like columns are plain text + CHECK constraint (easy to evolve with a migration).
Keep the value lists in sync with contract/CONTRACT.md.
"""
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PRECISIONS = ("exact", "circa", "decade", "century")
POLITY_TYPES = (
    "empire", "kingdom", "republic", "federation", "confederation",
    "colony", "protectorate", "city_state", "other",
)
EVENT_KINDS = ("political", "war", "treaty", "cultural", "economic", "other")
LINK_KINDS = ("renamed", "succeeded", "split", "merged", "absorbed", "conquered")
LINK_STATUSES = ("curated", "auto", "unresolved")
GLOSSARY_KINDS = ("regime", "system", "region", "membership", "currency", "other")
DRIVING_SIDES = ("left", "right")
LEADER_ROLES = ("head_of_state", "head_of_government")
LANGUAGE_STATUSES = ("official", "co_official", "sign", "historical", "indigenous", "immigrant")
PERSON_DOMAINS = ("arts", "business_law", "exploration", "humanities", "institutions",
                  "public_figure", "science_technology", "sports")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    pass


class Polity(Base):
    __tablename__ = "polities"
    __table_args__ = (
        CheckConstraint("end_year IS NULL OR end_year >= start_year", name="ck_polities_years"),
        CheckConstraint("iso2 IS NULL OR iso2 ~ '^[A-Z]{2}$'", name="ck_polities_iso2"),
        CheckConstraint(_in("type", POLITY_TYPES), name="ck_polities_type"),
        CheckConstraint(_in("start_precision", PRECISIONS), name="ck_polities_start_precision"),
        CheckConstraint(
            "end_precision IS NULL OR " + _in("end_precision", PRECISIONS),
            name="ck_polities_end_precision",
        ),
        CheckConstraint("start_year <> 0 AND (end_year IS NULL OR end_year <> 0)", name="ck_polities_no_year_zero"),
        Index("ix_polities_years", "start_year", "end_year"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    start_year: Mapped[int] = mapped_column(Integer)
    start_precision: Mapped[str] = mapped_column(Text, server_default="exact")
    end_year: Mapped[int | None] = mapped_column(Integer)  # last year of existence, INCLUSIVE
    end_precision: Mapped[str | None] = mapped_column(Text)
    iso2: Mapped[str | None] = mapped_column(CHAR(2), unique=True)
    wikidata_qid: Mapped[str | None] = mapped_column(Text)
    regime: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    wikipedia_title: Mapped[str | None] = mapped_column(Text)
    politics_system: Mapped[str | None] = mapped_column(Text)
    politics_note: Mapped[str | None] = mapped_column(Text)
    politics_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    names: Mapped[list["PolityName"]] = relationship(
        back_populates="polity", order_by="PolityName.from_year", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="polity", order_by="(Event.year_start, Event.id)", cascade="all, delete-orphan"
    )


class PolityName(Base):
    __tablename__ = "polity_names"
    __table_args__ = (
        CheckConstraint("to_year IS NULL OR to_year >= from_year", name="ck_polity_names_years"),
        Index("ix_polity_names_polity", "polity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    polity_id: Mapped[str] = mapped_column(ForeignKey("polities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    from_year: Mapped[int] = mapped_column(Integer)
    to_year: Mapped[int | None] = mapped_column(Integer)

    polity: Mapped[Polity] = relationship(back_populates="names")


class Succession(Base):
    __tablename__ = "succession"
    __table_args__ = (
        CheckConstraint("predecessor_id <> successor_id", name="ck_succession_distinct"),
        CheckConstraint(_in("kind", LINK_KINDS), name="ck_succession_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    predecessor_id: Mapped[str] = mapped_column(ForeignKey("polities.id", ondelete="CASCADE"))
    successor_id: Mapped[str] = mapped_column(ForeignKey("polities.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("year_end IS NULL OR year_end >= year_start", name="ck_events_years"),
        CheckConstraint(_in("precision", PRECISIONS), name="ck_events_precision"),
        CheckConstraint(_in("kind", EVENT_KINDS), name="ck_events_kind"),
        Index("ix_events_polity_year", "polity_id", "year_start"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    polity_id: Mapped[str] = mapped_column(ForeignKey("polities.id", ondelete="CASCADE"))
    year_start: Mapped[int] = mapped_column(Integer)
    year_end: Mapped[int | None] = mapped_column(Integer)
    precision: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)

    polity: Mapped[Polity] = relationship(back_populates="events")
    sources: Mapped[list[Source]] = relationship(secondary="event_sources", order_by="Source.id")


class EventSource(Base):
    __tablename__ = "event_sources"
    __table_args__ = (PrimaryKeyConstraint("event_id", "source_id"),)

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))


class Snapshot(Base):
    __tablename__ = "snapshots"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    geometry_path: Mapped[str] = mapped_column(Text)
    feature_count: Mapped[int] = mapped_column(Integer)


class SnapshotLink(Base):
    __tablename__ = "snapshot_links"
    __table_args__ = (
        PrimaryKeyConstraint("snapshot_year", "source_name"),
        CheckConstraint(_in("status", LINK_STATUSES), name="ck_snapshot_links_status"),
    )

    snapshot_year: Mapped[int] = mapped_column(ForeignKey("snapshots.year", ondelete="CASCADE"))
    source_name: Mapped[str] = mapped_column(Text)
    polity_id: Mapped[str | None] = mapped_column(ForeignKey("polities.id"))
    status: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class CountryFacts(Base):
    __tablename__ = "country_facts"

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"), primary_key=True)
    official_name: Mapped[str | None] = mapped_column(Text)
    capital: Mapped[str | None] = mapped_column(Text)
    capital_lat: Mapped[float | None] = mapped_column(Float)
    capital_lng: Mapped[float | None] = mapped_column(Float)
    flag_url: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    area_km2: Mapped[float | None] = mapped_column(Float)
    population: Mapped[int | None] = mapped_column(BigInteger)
    population_year: Mapped[int | None] = mapped_column(Integer)
    languages: Mapped[list[dict[str, str | None]] | None] = mapped_column(JSONB)
    currencies: Mapped[list[dict[str, str | None]] | None] = mapped_column(JSONB)
    memberships: Mapped[list[str] | None] = mapped_column(JSONB)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # spec 004: from Wikidata P122 via content/regimes.yaml (overrides the legacy polities.regime)
    regime_id: Mapped[str | None] = mapped_column(ForeignKey("glossary_terms.id"))
    regime: Mapped[str | None] = mapped_column(Text)
    # spec 003: GeoGuessr clues
    driving_side: Mapped[str | None] = mapped_column(Text)
    calling_code: Mapped[str | None] = mapped_column(Text)
    tld: Mapped[str | None] = mapped_column(Text)
    plate_code: Mapped[str | None] = mapped_column(Text)
    scripts: Mapped[list[str] | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("driving_side IS NULL OR " + _in("driving_side", DRIVING_SIDES),
                        name="ck_country_facts_driving_side"),
    )


class GlossaryTerm(Base):
    """spec 004. Written only by import-content (content/glossary.yaml)."""

    __tablename__ = "glossary_terms"
    __table_args__ = (CheckConstraint(_in("kind", GLOSSARY_KINDS), name="ck_glossary_terms_kind"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    short: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, str | None]]] = mapped_column(JSONB)  # contract Source objects


class Leader(Base):
    """spec 006 (v1.1). One row per term of office; written only by import-facts."""

    __tablename__ = "leaders"
    __table_args__ = (
        CheckConstraint(_in("role", LEADER_ROLES), name="ck_leaders_role"),
        Index("ix_leaders_iso2", "iso2"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    person_id: Mapped[str] = mapped_column(Text)  # Wikidata Q-id
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    office: Mapped[str | None] = mapped_column(Text)
    start: Mapped[str | None] = mapped_column(Text)  # 'YYYY-MM-DD' as given by Wikidata
    end: Mapped[str | None] = mapped_column(Text)
    party_id: Mapped[str | None] = mapped_column(Text)
    party_name: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(Text)
    image_license: Mapped[str | None] = mapped_column(Text)
    wikipedia_url: Mapped[str | None] = mapped_column(Text)


class Person(Base):
    """spec 007. Top people per country (Pantheon rank); written only by import-facts."""

    __tablename__ = "people"
    __table_args__ = (
        PrimaryKeyConstraint("iso2", "id"),
        CheckConstraint("domain IS NULL OR " + _in("domain", PERSON_DOMAINS), name="ck_people_domain"),
        CheckConstraint("birth_year IS NULL OR birth_year <> 0", name="ck_people_no_year_zero"),
    )

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    id: Mapped[str] = mapped_column(Text)  # Wikidata Q-id (from Pantheon wd_id)
    name: Mapped[str] = mapped_column(Text)
    occupation: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    death_year: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(Text)
    image_license: Mapped[str | None] = mapped_column(Text)
    wikipedia_url: Mapped[str | None] = mapped_column(Text)


class Meta(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Capital(Base):
    """spec 019/005: every current capital (ZA has 3); ord 0 = country_facts.capital."""

    __tablename__ = "capitals"
    __table_args__ = (PrimaryKeyConstraint("iso2", "ord"),)

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    ord: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)


class CountryLanguage(Base):
    """spec 017: languages spoken in a country; `ord` = contract order (status, speakers desc)."""

    __tablename__ = "country_languages"
    __table_args__ = (
        PrimaryKeyConstraint("iso2", "qid"),
        CheckConstraint(_in("status", LANGUAGE_STATUSES), name="ck_country_languages_status"),
    )

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    qid: Mapped[str] = mapped_column(Text)
    ord: Mapped[int] = mapped_column(Integer)
    code: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    where: Mapped[str | None] = mapped_column(Text)
    speakers: Mapped[int | None] = mapped_column(BigInteger)
    speakers_year: Mapped[int | None] = mapped_column(Integer)
    family: Mapped[str | None] = mapped_column(Text)
    endangerment: Mapped[str | None] = mapped_column(Text)
    wikipedia_url: Mapped[str | None] = mapped_column(Text)


class IndicatorDef(Base):
    """specs 009/015: one row per indicator id (pt-BR label/unit written by the ETL)."""

    __tablename__ = "indicator_defs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))


class Indicator(Base):
    """Long format: one value per (country, indicator, year). Shared by 009, 015 (and 012)."""

    __tablename__ = "indicators"
    __table_args__ = (PrimaryKeyConstraint("iso2", "id", "year"), Index("ix_indicators_id", "id"))

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    id: Mapped[str] = mapped_column(ForeignKey("indicator_defs.id"))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))


class IndicatorStat(Base):
    """World stats over each country's LATEST value (computed by import-facts)."""

    __tablename__ = "indicator_stats"

    id: Mapped[str] = mapped_column(ForeignKey("indicator_defs.id"), primary_key=True)
    n: Mapped[int] = mapped_column(Integer)
    min: Mapped[float] = mapped_column(Float)
    median: Mapped[float] = mapped_column(Float)
    max: Mapped[float] = mapped_column(Float)


class IndicatorLatest(Base):
    """Latest value per (country, indicator) + rank (1 = highest) + simple regional mean."""

    __tablename__ = "indicator_latest"
    __table_args__ = (PrimaryKeyConstraint("iso2", "id"),)

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    id: Mapped[str] = mapped_column(ForeignKey("indicator_defs.id"))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    region_avg: Mapped[float | None] = mapped_column(Float)


class Composition(Base):
    """spec 015: religion / ethnicity shares from Wikidata (only when they sum to 80-105%)."""

    __tablename__ = "compositions"
    __table_args__ = (
        PrimaryKeyConstraint("iso2", "kind", "label"),
        CheckConstraint("kind IN ('religion', 'ethnicity')", name="ck_compositions_kind"),
    )

    iso2: Mapped[str] = mapped_column(CHAR(2), ForeignKey("polities.iso2"))
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    share: Mapped[float] = mapped_column(Float)
    year: Mapped[int | None] = mapped_column(Integer)


class FxRate(Base):
    """spec 009: 1 EUR = `rate` units of `code` on `date`. Cross rates are computed in SQL."""

    __tablename__ = "fx_rates"
    __table_args__ = (PrimaryKeyConstraint("code", "date"), Index("ix_fx_rates_date", "date"))

    date: Mapped[date] = mapped_column(Date)
    code: Mapped[str] = mapped_column(CHAR(3))
    rate: Mapped[float] = mapped_column(Float)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))


class CurrencyStat(Base):
    """spec 009: stats of the currency's value in `vs` (USD; EUR for USD), computed at import."""

    __tablename__ = "currency_stats"

    code: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    vs: Mapped[str] = mapped_column(CHAR(3))
    as_of: Mapped[date] = mapped_column(Date)
    change_1y: Mapped[float | None] = mapped_column(Float)
    change_5y: Mapped[float | None] = mapped_column(Float)
    volatility_1y: Mapped[float | None] = mapped_column(Float)
    max_drawdown_1y: Mapped[float | None] = mapped_column(Float)
