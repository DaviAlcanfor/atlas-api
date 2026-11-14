"""spec 027 (CR-006): every country's latest value of one indicator, ranked, for the map's ranking layer."""
from typing import Annotated

from fastapi import APIRouter, Path

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import NotFoundError
from atlas_api.schemas import IndicatorCatalog, IndicatorRanking

router = APIRouter(tags=["indicators"])


@router.get("/indicators")
def list_indicators(db: DbSession) -> IndicatorCatalog:
    return queries.list_ranked_indicators(db)


@router.get("/indicators/{id}/ranking")
def indicator_ranking(db: DbSession, id: Annotated[str, Path(pattern=r"^[A-Za-z0-9.]{1,40}$")]) -> IndicatorRanking:
    r = queries.indicator_ranking(db, id)
    if r is None:
        raise NotFoundError(f"Unknown indicator {id}")
    return r
