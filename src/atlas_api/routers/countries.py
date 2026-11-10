from typing import Annotated

from fastapi import APIRouter, Path

from atlas_api.deps import Store
from atlas_api.errors import NotFoundError
from atlas_api.schemas import CountryDetail, CountryList

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("")
def list_countries(store: Store) -> CountryList:
    return CountryList(items=store.country_summaries())


@router.get("/{iso2}")
def get_country(store: Store, iso2: Annotated[str, Path(pattern=r"^[A-Z]{2}$")]) -> CountryDetail:
    for c in store.countries:
        if c.iso2 == iso2:
            return c
    raise NotFoundError(f"Unknown country {iso2}")
