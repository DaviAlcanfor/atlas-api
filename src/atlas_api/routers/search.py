from typing import Annotated

from fastapi import APIRouter, Query

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.schemas import SearchResults

router = APIRouter(tags=["search"])


@router.get("/search")
def search(
    db: DbSession,
    q: Annotated[str, Query(min_length=2)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> SearchResults:
    return SearchResults(items=queries.search(db, q, limit))
