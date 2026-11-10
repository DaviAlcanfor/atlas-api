"""Contract models: search."""
from typing import Literal

from pydantic import BaseModel


class SearchItem(BaseModel):
    kind: Literal["country", "polity"]
    id: str
    name: str
    iso2: str | None
    start_year: int
    end_year: int | None


class SearchResults(BaseModel):
    items: list[SearchItem]
