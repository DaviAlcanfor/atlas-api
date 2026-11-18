"""spec 034 (CR-015 proposal): recent natural events, refreshed every 30 min by .github/workflows/live-events.yml.
Outside the data_version ETag (cache.py): a short public Cache-Control instead."""
from datetime import UTC, datetime, timedelta
from typing import Annotated, get_args

from fastapi import APIRouter, Query, Response

from atlas_api import queries
from atlas_api.core.deps import DbSession
from atlas_api.core.errors import InvalidParameterError
from atlas_api.schemas import LiveEventList
from atlas_api.schemas.live import LiveEventType

router = APIRouter(prefix="/live", tags=["live"])
TYPES = get_args(LiveEventType)


@router.get("/events")
def live_events(
    db: DbSession, response: Response,
    since: Annotated[datetime | None, Query(description="ISO 8601; default and minimum: 7 days ago")] = None,
    type: Annotated[str | None, Query(description="comma-separated event types")] = None,
) -> LiveEventList:
    types = [t.strip() for t in type.split(",") if t.strip()] if type else []
    bad = [t for t in types if t not in TYPES]
    if bad:
        raise InvalidParameterError(f"type: one of {', '.join(TYPES)}")
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    floor = datetime.now(UTC) - timedelta(days=7)
    response.headers["Cache-Control"] = "public, max-age=300"
    return queries.list_live_events(db, max(since or floor, floor), types)
