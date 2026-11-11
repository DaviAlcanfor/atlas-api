from fastapi import APIRouter

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.schemas import Meta

router = APIRouter(tags=["system"])


@router.get("/meta")
def get_meta(db: DbSession) -> Meta:
    return queries.get_meta(db)
