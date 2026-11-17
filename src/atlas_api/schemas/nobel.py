"""spec 033 (CR-014 proposal): Nobel Prize laureates per country (Nobel Prize API v2.1, CC0)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Source

NobelCategory = Literal["physics", "chemistry", "medicine", "literature", "peace", "economics"]


class NobelAffiliation(BaseModel):
    name: str
    city: str | None
    iso2: str | None  # today's borders; null = not a country of /v1/countries


class NobelPrizeOut(BaseModel):
    laureate_id: str
    name: str
    kind: Literal["person", "organization"]
    year: int
    category: NobelCategory
    motivation: str | None  # official English text of the API, verbatim
    portion: str | None  # share of the prize: "1", "1/2", "1/3", "1/4"
    born_here: bool  # born (organization: founded) in this country, today's borders
    affiliated_here: bool  # an affiliation at the time of the award is in this country
    affiliations: list[NobelAffiliation]
    wikipedia_url: str | None
    url: str  # the laureate's page on nobelprize.org


class CountryNobel(BaseModel):
    born: int  # prizes of laureates born (founded) here
    affiliated: int  # prizes with an affiliation here
    items: list[NobelPrizeOut]  # newest first
    sources: list[Source]
