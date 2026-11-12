"""Contract models: glossary (v1.1, spec 004; CR-002 proposal, not in CONTRACT.md yet)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Source

GlossaryKind = Literal["regime", "system", "region", "membership", "currency", "other"]


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
