from typing import Annotated

from fastapi import APIRouter, Query

from atlas_api.deps import Store
from atlas_api.errors import InvalidParameterError, NotFoundError
from atlas_api.schemas import PolityDetail, PolityList

router = APIRouter(prefix="/polities", tags=["polities"])


@router.get("")
def list_polities(
    store: Store,
    year: int | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PolityList:
    if year is not None and not store.year_min <= year <= store.year_max:
        raise InvalidParameterError(f"year must be between {store.year_min} and {store.year_max}")
    items = [
        p
        for p in store.polity_summaries()
        if year is None or (p.start_year <= year and (p.end_year is None or year <= p.end_year))
    ]
    return PolityList(year=year, items=items[offset : offset + limit], total=len(items))


@router.get("/{id}")
def get_polity(store: Store, id: str) -> PolityDetail:
    for p in store.polities:
        if p.id == id:
            return p
    raise NotFoundError(f"Unknown polity {id}")
