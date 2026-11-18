"""spec 008 (CR-008): geopolitical news, world feed and per country. Refreshed every 6 h by the news job."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query

from atlas_api import queries
from atlas_api.core.deps import DbSession
from atlas_api.core.errors import InvalidParameterError, NotFoundError
from atlas_api.schemas import NewsList

router = APIRouter(tags=["news"])


def _cursor(before: str | None) -> tuple[datetime, str] | None:
    if not before:
        return None
    try:
        ts, item_id = before.rsplit("|", 1)
        return datetime.fromisoformat(ts), item_id
    except ValueError as e:
        raise InvalidParameterError("before: use the `next` value of a previous page") from e


@router.get("/news")
def list_news(
    db: DbSession,
    region: Annotated[str | None, Query(max_length=40)] = None,
    type: Annotated[str | None, Query()] = None,
    lang: Annotated[str | None, Query(pattern=r"^[a-z]{2}$")] = None,
    country: Annotated[str | None, Query(pattern=r"^[A-Z]{2}$")] = None,
    min_p: Annotated[float, Query(ge=0, le=1)] = 0.7,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: str | None = None,
) -> NewsList:
    if type and type not in queries.NEWS_TYPES:
        raise InvalidParameterError(f"type: one of {', '.join(queries.NEWS_TYPES)}")
    return queries.list_news(db, region=region, event_type=type, lang=lang, country=country, min_p=min_p, limit=limit,
                             before=_cursor(before))


@router.get("/countries/{iso2}/news")
def country_news(db: DbSession, iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")],
                 limit: Annotated[int, Query(ge=1, le=100)] = 20) -> NewsList:
    if not queries.country_exists(db, iso2):
        raise NotFoundError(f"Unknown country {iso2}")
    return queries.list_news(db, country=iso2, limit=limit)
