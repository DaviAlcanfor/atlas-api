from fastapi import APIRouter

from atlas_api.deps import Store
from atlas_api.errors import InvalidParameterError, NotFoundError
from atlas_api.schemas import SnapshotInfo, SnapshotLinks, SnapshotList, SnapshotNearest

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("")
def list_snapshots(store: Store) -> SnapshotList:
    return SnapshotList(items=store.snapshot_infos())


@router.get("/nearest")
def nearest(store: Store, year: int) -> SnapshotNearest:
    if not store.year_min <= year <= store.year_max:
        raise InvalidParameterError(f"year must be between {store.year_min} and {store.year_max}")
    best: SnapshotInfo = min(store.snapshot_infos(), key=lambda s: (abs(s.year - year), s.year))
    return SnapshotNearest(requested_year=year, snapshot=best, distance_years=abs(best.year - year))


@router.get("/{year}/links")
def links(store: Store, year: int) -> SnapshotLinks:
    for s in store.snapshots:
        if s.year == year:
            return SnapshotLinks(snapshot_year=year, links=s.links)
    raise NotFoundError(f"No snapshot for year {year}")
