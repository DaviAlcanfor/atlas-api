from fastapi import APIRouter

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import InvalidParameterError, NotFoundError
from atlas_api.rules import nearest_snapshot
from atlas_api.schemas import SnapshotLinks, SnapshotList, SnapshotNearest

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("")
def list_snapshots(db: DbSession) -> SnapshotList:
    return SnapshotList(items=queries.list_snapshots(db))


@router.get("/nearest")
def nearest(db: DbSession, year: int) -> SnapshotNearest:
    if not queries.YEAR_MIN <= year <= queries.year_max() or year == 0:
        raise InvalidParameterError(f"year must be between {queries.YEAR_MIN} and {queries.year_max()} (no year 0)")
    infos = queries.list_snapshots(db)
    if not infos:
        raise NotFoundError("No snapshots available yet")
    best_year, distance = nearest_snapshot([s.year for s in infos], year)
    best = next(s for s in infos if s.year == best_year)
    return SnapshotNearest(requested_year=year, snapshot=best, distance_years=distance)


@router.get("/{year}/links")
def links(db: DbSession, year: int) -> SnapshotLinks:
    found = queries.snapshot_links(db, year)
    if found is None:
        raise NotFoundError(f"No snapshot for year {year}")
    return SnapshotLinks(snapshot_year=year, links=found)
