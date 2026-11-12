import logging

import anyio
from fastapi import APIRouter, Request
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from atlas_api import queries
from atlas_api.schemas import Health

router = APIRouter(tags=["system"])
log = logging.getLogger("atlas_api")
# Own thread limiter: health must answer even when every default worker thread is busy (spec 019.5).
_HEALTH_THREADS = anyio.CapacityLimiter(2)


def _saturated(engine: Engine) -> bool:
    pool = engine.pool
    in_use = getattr(pool, "checkedout", lambda: 0)()
    limit = getattr(pool, "size", lambda: 0)() + getattr(pool, "_max_overflow", 0)
    return bool(limit) and in_use >= limit


@router.get("/health")
async def health(request: Request) -> Health:
    """Never queues behind a busy pool: if every connection is in use it answers db="error" at
    once (the DB may be fine, but this process cannot reach it right now)."""
    engine: Engine = request.app.state.engine
    if _saturated(engine):
        log.warning("health: connection pool saturated")
        return Health(status="ok", db="error")

    def ping() -> None:
        with Session(engine) as s:
            queries.ping(s)

    try:
        await anyio.to_thread.run_sync(ping, limiter=_HEALTH_THREADS)
        return Health(status="ok", db="ok")
    except SQLAlchemyError:
        log.exception("health: database check failed")
        return Health(status="ok", db="error")  # contract: status stays "ok", db tells the truth
