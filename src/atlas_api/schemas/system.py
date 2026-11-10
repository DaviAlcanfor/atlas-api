"""Contract models: system."""
from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    db: Literal["ok", "error"]


class Counts(BaseModel):
    countries: int
    polities: int
    events: int


class Meta(BaseModel):
    data_version: str
    generated_at: str
    year_min: int
    year_max: int
    snapshot_years: list[int]
    counts: Counts
