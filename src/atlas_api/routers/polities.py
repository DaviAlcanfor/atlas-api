from typing import Annotated

from fastapi import APIRouter, Query

from atlas_api import queries
from atlas_api.core.deps import DbSession
from atlas_api.core.errors import InvalidParameterError, NotFoundError
from atlas_api.schemas import PolityDetail, PolityList, WikipediaSummary

router = APIRouter(prefix="/polities", tags=["polities"])
entities = APIRouter(prefix="/entities", tags=["polities"])


@router.get("")
def list_polities(
    db: DbSession,
    year: int | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PolityList:
    if year is not None and not queries.YEAR_MIN <= year <= queries.year_max():
        raise InvalidParameterError(f"year must be between {queries.YEAR_MIN} and {queries.year_max()}")
    if year == 0:
        raise InvalidParameterError("there is no year 0 (1 BCE = -1, 1 CE = 1)")
    return queries.list_polities(db, year, limit, offset)


@router.get("/{id}")
def get_polity(db: DbSession, id: str) -> PolityDetail:
    polity = queries.get_polity(db, id)
    if polity is None:
        raise NotFoundError(f"Unknown polity {id}")
    return polity


@entities.get("/{qid}/wikipedia")
def entity_wikipedia(db: DbSession, qid: str) -> WikipediaSummary:
    """spec 042: Wikipedia summary of a historical-map entity by its Wikidata Q-id (the `wikidata` of a snapshot feature)."""
    found = queries.wikipedia_summary(db, qid)
    if found is None:
        raise NotFoundError(f"No Wikipedia summary for {qid}")
    return found
