"""Contract models: polities."""
from pydantic import BaseModel

from atlas_api.schemas.common import (
    Event,
    LinkKind,
    Politics,
    PolityType,
    Precision,
    Source,
)


class PolitySummary(BaseModel):
    id: str
    name: str
    type: PolityType
    start_year: int
    end_year: int | None
    iso2: str | None


class Link(BaseModel):
    polity_id: str
    name: str
    year: int
    kind: LinkKind


class NamePeriod(BaseModel):
    name: str
    from_year: int
    to_year: int | None


class Wikipedia(BaseModel):
    title: str
    url: str


class PolityDetail(PolitySummary):
    start_precision: Precision
    end_precision: Precision | None
    names: list[NamePeriod]
    predecessors: list[Link]
    successors: list[Link]
    regime: str | None
    summary: str | None
    politics: Politics | None
    timeline: list[Event]
    wikipedia: Wikipedia | None
    sources: list[Source]
    updated_at: str


class PolityList(BaseModel):
    year: int | None
    items: list[PolitySummary]
    total: int
