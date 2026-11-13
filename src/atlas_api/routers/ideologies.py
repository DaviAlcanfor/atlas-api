"""v1.3 proposal (spec 018, CR-004 addendum 3): a political current worldwide."""
from fastapi import APIRouter

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import NotFoundError
from atlas_api.schemas import IdeologyDetail

router = APIRouter(prefix="/ideologies", tags=["ideologies"])


@router.get("/{id}")
def get_ideology(db: DbSession, id: str) -> IdeologyDetail:
    detail = queries.get_ideology(db, id)
    if detail is None:
        raise NotFoundError(f"Unknown ideology {id}")
    return detail
