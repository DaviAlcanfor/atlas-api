from typing import Annotated

from fastapi import APIRouter, Query

from atlas_api.deps import Store
from atlas_api.schemas import SearchItem, SearchResults

router = APIRouter(tags=["search"])


@router.get("/search")
def search(
    store: Store,
    q: Annotated[str, Query(min_length=2)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> SearchResults:
    needle = q.casefold()  # stub: no accent folding yet (Phase 1: unaccent)
    items = [
        SearchItem(
            kind="polity",
            id=p.id,
            name=p.name,
            iso2=p.iso2,
            start_year=p.start_year,
            end_year=p.end_year,
        )
        for p in store.polity_summaries()
        if needle in p.name.casefold()
    ]
    return SearchResults(items=items[:limit])
