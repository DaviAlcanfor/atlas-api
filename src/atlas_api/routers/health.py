import logging

from fastapi import APIRouter
from sqlalchemy.exc import SQLAlchemyError

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.schemas import Health

router = APIRouter(tags=["system"])
log = logging.getLogger("atlas_api")


@router.get("/health")
def health(db: DbSession) -> Health:
    try:
        queries.ping(db)
        return Health(status="ok", db="ok")
    except SQLAlchemyError:
        log.exception("health: database check failed")
        return Health(status="ok", db="error")  # contract: status stays "ok", db tells the truth
