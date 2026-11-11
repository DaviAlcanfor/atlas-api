from typing import Annotated

from fastapi import APIRouter, Path

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import NotFoundError
from atlas_api.schemas import CountryDetail, CountryList

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("")
def list_countries(db: DbSession) -> CountryList:
    return CountryList(items=queries.list_countries(db))


@router.get("/{iso2}")
def get_country(db: DbSession, iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")]) -> CountryDetail:
    country = queries.get_country(db, iso2)
    if country is None:
        raise NotFoundError(f"Unknown country {iso2}")
    return country
