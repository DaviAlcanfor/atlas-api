"""Contract models: snapshots."""
from typing import Literal

from pydantic import BaseModel


class SnapshotInfo(BaseModel):
    year: int
    geometry_url: str
    feature_count: int
    link_coverage: float


class SnapshotList(BaseModel):
    items: list[SnapshotInfo]


class SnapshotNearest(BaseModel):
    requested_year: int
    snapshot: SnapshotInfo
    distance_years: int


class SnapshotLink(BaseModel):
    source_name: str
    polity_id: str | None
    status: Literal["curated", "auto", "unresolved"]


class SnapshotLinks(BaseModel):
    snapshot_year: int
    links: list[SnapshotLink]
