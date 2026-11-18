"""spec 032 (CR-013 proposal): curated international organizations, written by import-content (content/organizations.yaml)."""
from fastapi import APIRouter

from atlas_api import queries
from atlas_api.core.deps import DbSession
from atlas_api.schemas import OrganizationList

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("")
def list_organizations(db: DbSession) -> OrganizationList:
    return queries.list_organizations(db)
