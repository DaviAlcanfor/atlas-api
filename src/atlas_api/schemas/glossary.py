"""Contract models: glossary (v1.1, spec 004; CR-002 proposal, not in CONTRACT.md yet)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Event, Source
from atlas_api.schemas.countries import Image

GlossaryKind = Literal["regime", "system", "region", "membership", "currency", "ideology", "other"]  # ideology: v1.3 proposal (spec 018)


class GlossaryTerm(BaseModel):
    id: str
    kind: GlossaryKind
    label: str
    short: str
    body: str
    icon: str | None
    examples: list[str]  # iso2
    sources: list[Source]


class GlossaryList(BaseModel):
    items: list[GlossaryTerm]


# ---- spec 018 (v1.3 proposal, CR-004 addendum 3): political currents ------------------------------------------------------
class PartyRef(BaseModel):
    id: str  # Wikidata Q-id
    name: str


class IdeologyFigure(BaseModel):
    person_id: str
    name: str
    role: Literal["thinker", "leader", "activist", "other"]
    birth_year: int | None
    death_year: int | None
    summary: str | None
    works: list[str]
    image: Image | None
    wikipedia_url: str | None
    via: Literal["declared", "party"]  # declared = the current is stated (with a reference) on the person; party = party member
    party: PartyRef | None


class CountryIdeology(BaseModel):
    term: GlossaryTerm
    figures: list[IdeologyFigure]
    parties: list[PartyRef]
    milestones: list[Event]


class CountryIdeologies(BaseModel):
    items: list[CountryIdeology]
    sources: list[Source]


class Governed(BaseModel):
    iso2: str
    from_year: int
    to_year: int | None


class IdeologyDetail(BaseModel):
    term: GlossaryTerm
    founders: list[IdeologyFigure]
    timeline: list[Event]
    governed: list[Governed]
    sources: list[Source]
