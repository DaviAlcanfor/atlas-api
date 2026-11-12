"""v1.2 (spec 009, CR-003): currencies and the economy comparison."""
import re
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Path, Query

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import InvalidParameterError, NotFoundError
from atlas_api.schemas import CurrencyDetail, CurrencyHistory, EconomyCompare

router = APIRouter(tags=["economy"])
Code = Annotated[str, Path(pattern=r"^[A-Z]{3}$")]
VS_MAX = 4


def _csv(raw: str, pattern: str, what: str) -> list[str]:
    items = [x.strip() for x in raw.split(",") if x.strip()]
    bad = [x for x in items if not re.fullmatch(pattern, x)]
    if bad:
        raise InvalidParameterError(f"Invalid {what}: {', '.join(bad)}")
    return list(dict.fromkeys(items))  # de-duplicated, order kept


@router.get("/currencies/{code}")
def get_currency(db: DbSession, code: Code) -> CurrencyDetail:
    cur = queries.get_currency(db, code)
    if cur is None:
        raise NotFoundError(f"Unknown currency {code}")
    return cur


@router.get("/currencies/{code}/history")
def currency_history(
    db: DbSession, code: Code,
    vs: Annotated[str | None, Query(description="up to 4 ISO 4217 codes, comma-separated")] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> CurrencyHistory:
    if not queries.currency_known(db, code):
        raise NotFoundError(f"No rates for currency {code}")
    targets = _csv(vs, r"[A-Z]{3}", "currency code") if vs else [
        c for c in ("USD", "EUR") if c != code]
    targets = [c for c in targets if c != code]
    if not 1 <= len(targets) <= VS_MAX:
        raise InvalidParameterError(f"vs: 1 to {VS_MAX} codes other than {code}")
    for c in targets:
        if not queries.currency_known(db, c):
            raise NotFoundError(f"No rates for currency {c}")
    if from_ and to and from_ > to:
        raise InvalidParameterError("from must be <= to")
    if from_ and (to or date.today()) - from_ > timedelta(days=queries.HISTORY_MAX_DAYS):
        raise InvalidParameterError("window longer than 30 years")
    return queries.currency_history(db, code, targets, from_, to)


@router.get("/economy/compare")
def compare(
    db: DbSession,
    countries: Annotated[str, Query(description="2 to 5 ISO2 codes, comma-separated")],
    ids: Annotated[str | None, Query(description="indicator ids, comma-separated; default all")] = None,
) -> EconomyCompare:
    isos = _csv(countries, r"[A-Z]{2}", "country code")
    if not 2 <= len(isos) <= 5:
        raise InvalidParameterError("countries: 2 to 5 ISO2 codes")
    for iso2 in isos:
        if not queries.country_exists(db, iso2):
            raise NotFoundError(f"Unknown country {iso2}")
    wanted = _csv(ids, r"[A-Z0-9.]+", "indicator id") if ids else list(queries.ECONOMY_IDS)
    unknown = [i for i in wanted if i not in queries.ECONOMY_IDS]
    if unknown:
        raise InvalidParameterError(f"Unknown indicator ids: {', '.join(unknown)}")
    return queries.compare_economy(db, isos, wanted)
