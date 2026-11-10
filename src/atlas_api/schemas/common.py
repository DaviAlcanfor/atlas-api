"""Contract models: common."""
from typing import Literal

from pydantic import BaseModel

Precision = Literal["exact", "circa", "decade", "century"]
PolityType = Literal[
    "empire", "kingdom", "republic", "federation", "confederation",
    "colony", "protectorate", "city_state", "other",
]
EventKind = Literal["political", "war", "treaty", "cultural", "economic", "other"]
LinkKind = Literal["renamed", "succeeded", "split", "merged", "absorbed", "conquered"]


class Source(BaseModel):
    id: str
    title: str
    url: str | None
    license: str | None
    retrieved_at: str | None


class Event(BaseModel):
    id: str
    year_start: int
    year_end: int | None
    precision: Precision
    title: str
    summary: str
    kind: EventKind
    source_ids: list[str]


class Politics(BaseModel):
    system: str | None
    note: str | None
    updated_at: str | None
