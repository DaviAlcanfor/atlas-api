"""Raw REST Countries record -> CountryFacts (pure function, easy to test)."""
from etl.restcountries.models import (
    CountryFacts,
    Currency,
    Language,
    RawCountry,
)

SOURCE_ID = "restcountries"


def to_facts(raw: RawCountry, fetched_at: str) -> CountryFacts | None:
    """Return None when the record has no ISO alpha-2 code (cannot be joined to a polity)."""
    if not raw.codes.alpha_2:
        return None
    cap = next((c for c in raw.capitals if c.primary), raw.capitals[0] if raw.capitals else None)
    coords = cap.coordinates if cap else None
    return CountryFacts(
        iso2=raw.codes.alpha_2,
        official_name=raw.names.official,
        capital=cap.name if cap else None,
        capital_lat=coords.lat if coords else None,
        capital_lng=coords.lng if coords else None,
        flag_url=raw.flag.url_svg,
        region=raw.region,
        area_km2=raw.area.kilometers,
        population=raw.population,
        population_year=None,
        languages=[Language(code=x.bcp47, name=x.name) for x in raw.languages],
        currencies=[Currency(code=x.code, name=x.name, symbol=x.symbol) for x in raw.currencies],
        memberships=sorted(k for k, v in raw.memberships.items() if v is True),
        source_id=SOURCE_ID,
        fetched_at=fetched_at,
    )
