"""Contract models: countries. Fields marked v1.1 are the CR-002 proposal (not in CONTRACT.md yet)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Event, Politics, Source


class Marker(BaseModel):
    lat: float
    lng: float


class CapitalCoord(BaseModel):  # v1.1 (spec 005)
    name: str
    lat: float
    lng: float


class Clues(BaseModel):  # v1.1 (spec 003)
    driving_side: Literal["left", "right"] | None
    calling_code: str | None
    tld: str | None
    plate_code: str | None
    scripts: list[str]


class CountrySummary(BaseModel):
    iso2: str
    polity_id: str
    name: str
    capital: str | None
    region: str | None
    regime: str | None
    has_content: bool
    marker: Marker | None
    regime_id: str | None  # v1.1 (spec 004)
    capital_coords: list[CapitalCoord]  # v1.1 (spec 005)


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
    regime_id: str | None  # v1.1 (spec 004)
    clues: Clues | None  # v1.1 (spec 003)


class CountryList(BaseModel):
    items: list[CountrySummary]


# --- v1.1 (spec 006): leaders ---------------------------------------------------------------

LeaderRole = Literal["head_of_state", "head_of_government"]


class Party(BaseModel):
    id: str
    name: str


class Image(BaseModel):
    url: str
    credit: str
    license: str


class Leader(BaseModel):
    person_id: str
    name: str
    role: LeaderRole
    office: str | None
    start: str | None
    end: str | None
    party: Party | None
    image: Image | None
    wikipedia_url: str | None


class LeaderList(BaseModel):
    items: list[Leader]


# --- v1.1 (spec 007): notable people --------------------------------------------------------

PersonDomain = Literal["arts", "business_law", "exploration", "humanities", "institutions",
                       "public_figure", "science_technology", "sports"]


class Person(BaseModel):
    id: str
    name: str
    occupation: str | None
    domain: PersonDomain | None
    birth_year: int | None
    death_year: int | None
    image: Image | None
    wikipedia_url: str | None
    rank: int


class PersonList(BaseModel):
    items: list[Person]
    method: str
    source: Source
