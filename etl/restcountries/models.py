"""Pydantic models: the raw REST Countries v5 response (only fields we request) and our output.

Raw models ignore unknown fields and make everything optional: the API may omit any field, and
a missing value must become null, never an invented one.
"""
from pydantic import BaseModel, ConfigDict


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RawNames(_Raw):
    common: str | None = None
    official: str | None = None


class RawCodes(_Raw):
    alpha_2: str | None = None


class RawCoordinates(_Raw):
    lat: float | None = None
    lng: float | None = None


class RawCapital(_Raw):
    name: str | None = None
    primary: bool = False
    coordinates: RawCoordinates | None = None


class RawFlag(_Raw):
    url_svg: str | None = None


class RawLanguage(_Raw):
    name: str | None = None
    bcp47: str | None = None


class RawCurrency(_Raw):
    code: str | None = None
    name: str | None = None
    symbol: str | None = None


class RawArea(_Raw):
    kilometers: float | None = None


class RawCountry(_Raw):
    names: RawNames = RawNames()
    codes: RawCodes = RawCodes()
    capitals: list[RawCapital] = []
    flag: RawFlag = RawFlag()
    region: str | None = None
    languages: list[RawLanguage] = []
    currencies: list[RawCurrency] = []
    population: int | None = None
    area: RawArea = RawArea()
    memberships: dict[str, bool | None] = {}


class RawMeta(_Raw):
    more: bool = False


class RawData(_Raw):
    objects: list[RawCountry] = []
    meta: RawMeta = RawMeta()


class RawPage(_Raw):
    data: RawData


# ---- output: shape of the country_facts table ----


class Language(BaseModel):
    code: str | None
    name: str | None


class Currency(BaseModel):
    code: str | None
    name: str | None
    symbol: str | None


class CountryFacts(BaseModel):
    iso2: str
    official_name: str | None
    capital: str | None
    capital_lat: float | None
    capital_lng: float | None
    flag_url: str | None
    region: str | None
    area_km2: float | None
    population: int | None
    population_year: int | None  # the API offers no year: always null
    languages: list[Language]
    currencies: list[Currency]
    memberships: list[str]
    source_id: str
    fetched_at: str
