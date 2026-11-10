"""Phase 0 stub data, stored as JSON in ./data and validated with Pydantic at load time.

NOT authoritative: placeholder values so the web can integrate. Phase 1 replaces this store
with DB-backed queries behind the same `get_store` dependency.
"""
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from atlas_api.schemas import (
    CountryDetail,
    CountrySummary,
    Counts,
    Meta,
    PolityDetail,
    PolitySummary,
    SnapshotInfo,
    SnapshotLink,
)

DATA = Path(__file__).parent / "data"


class SnapshotFixture(SnapshotInfo):
    links: list[SnapshotLink]


class _MetaFixture(BaseModel):
    data_version: str
    generated_at: str
    year_min: int
    year_max: int


def _load(name: str, tp: Any) -> Any:
    raw = json.loads((DATA / name).read_text(encoding="utf-8"))
    return TypeAdapter(tp).validate_python(raw)


class FixtureStore:
    """In-memory, validated copy of the JSON fixtures. Built once at startup (lifespan)."""

    def __init__(self) -> None:
        self.polities: list[PolityDetail] = _load("polities.json", list[PolityDetail])
        self.countries: list[CountryDetail] = _load("countries.json", list[CountryDetail])
        self.snapshots: list[SnapshotFixture] = _load("snapshots.json", list[SnapshotFixture])
        self._meta: _MetaFixture = _load("meta.json", _MetaFixture)

    @property
    def meta(self) -> Meta:
        return Meta(
            **self._meta.model_dump(),
            snapshot_years=[s.year for s in self.snapshots],
            counts=Counts(
                countries=len(self.countries),
                polities=len(self.polities),
                events=sum(len(p.timeline) for p in self.polities),
            ),
        )

    @property
    def year_min(self) -> int:
        return self._meta.year_min

    @property
    def year_max(self) -> int:
        return self._meta.year_max

    def polity_summaries(self) -> list[PolitySummary]:
        keys = set(PolitySummary.model_fields)
        return [PolitySummary(**p.model_dump(include=keys)) for p in self.polities]

    def country_summaries(self) -> list[CountrySummary]:
        return [
            CountrySummary(
                iso2=c.iso2,
                polity_id=c.polity_id,
                name=c.name,
                capital=c.capital,
                region=c.region,
                regime=c.regime,
                has_content=bool(c.summary or c.timeline),
                marker=None,
            )
            for c in self.countries
        ]

    def snapshot_infos(self) -> list[SnapshotInfo]:
        keys = set(SnapshotInfo.model_fields)
        return [SnapshotInfo(**s.model_dump(include=keys)) for s in self.snapshots]
