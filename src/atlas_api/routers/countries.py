from typing import Annotated

from fastapi import APIRouter, Path, Query

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import NotFoundError, ServiceUnavailableError
from atlas_api.schemas import (
    CountryDetail,
    CountryEconomy,
    CountryList,
    CountryProfile,
    LeaderList,
    LeaderRole,
    PersonDomain,
    PersonList,
)

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


@router.get("/{iso2}/leaders")  # v1.1 (spec 006, CR-002)
def list_leaders(
    db: DbSession,
    iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")],
    role: LeaderRole | None = None,
) -> LeaderList:
    if not queries.country_exists(db, iso2):
        raise NotFoundError(f"Unknown country {iso2}")
    return LeaderList(items=queries.list_leaders(db, iso2, role))


@router.get("/{iso2}/people")  # v1.1 (spec 007, CR-002)
def list_people(
    db: DbSession,
    iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")],
    domain: PersonDomain | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> PersonList:
    if not queries.country_exists(db, iso2):
        raise NotFoundError(f"Unknown country {iso2}")
    people = queries.list_people(db, iso2, domain, limit)
    if people is None:
        raise ServiceUnavailableError("People dataset not imported yet")
    return people


@router.get("/{iso2}/profile")  # v1.2 (spec 015, CR-003)
def get_profile(db: DbSession, iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")]) -> CountryProfile:
    if not queries.country_exists(db, iso2):
        raise NotFoundError(f"Unknown country {iso2}")
    return queries.get_profile(db, iso2)


@router.get("/{iso2}/economy")  # v1.2 (spec 009, CR-003)
def get_economy(db: DbSession, iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")]) -> CountryEconomy:
    if not queries.country_exists(db, iso2):
        raise NotFoundError(f"Unknown country {iso2}")
    return queries.get_economy(db, iso2)
