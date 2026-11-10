"""Contract models: countries."""
from pydantic import BaseModel

from atlas_api.schemas.common import Event, Politics, Source


class Marker(BaseModel):
    lat: float
    lng: float


class CountrySummary(BaseModel):
    iso2: str
    polity_id: str
    name: str
    capital: str | None
    region: str | None
    regime: str | None
    has_content: bool
    marker: Marker | None


class Language(BaseModel):
    code: str
    name: str


class Currency(BaseModel):
    code: str
    name: str
    symbol: str | None


class Population(BaseModel):
    value: int
    year: int | None
    source_id: str


class CountryDetail(BaseModel):
    iso2: str
    polity_id: str
    name: str
    official_name: str | None
    capital: str | None
    flag_url: str | None
    region: str | None
    regime: str | None
    summary: str | None
    languages: list[Language]
    currencies: list[Currency]
    population: Population | None
    area_km2: float | None
    memberships: list[str]
    politics: Politics | None
    timeline: list[Event]
    sources: list[Source]
    updated_at: str


class CountryList(BaseModel):
    items: list[CountrySummary]
