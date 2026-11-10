"""HTTP client for REST Countries v5.

Free plan: 1,000 requests/month, 20 requests/10s, max page size 100. We use the paginated LIST
endpoint (~3 requests for every country) and cache raw pages on disk. The terms allow caching API
data for at most 3 days, so older cache files are refetched.
"""
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from etl.restcountries.models import RawCountry, RawPage
from etl.settings import EtlSettings

PAGE_SIZE = 100  # maximum on the free plan
CACHE_MAX_AGE_S = 3 * 24 * 3600
# Only fields present in the contract (population year does not exist in the API).
FIELDS = (
    "names.common,names.official,codes.alpha_2,capitals,flag.url_svg,region,"
    "languages,currencies,population,area.kilometers,memberships"
)


class RestCountriesError(RuntimeError):
    pass


class RestCountriesClient:
    def __init__(self, settings: EtlSettings) -> None:
        if settings.restcountries_api_key is None:
            raise RestCountriesError("Set RESTCOUNTRIES_API_KEY (env var or .env).")
        self._cache = settings.cache_dir / "restcountries"
        self._base = settings.restcountries_base_url
        key = settings.restcountries_api_key.get_secret_value()
        self._http = httpx.Client(headers={"Authorization": f"Bearer {key}"}, timeout=30)

    def close(self) -> None:
        self._http.close()

    def _page(self, offset: int) -> RawPage:
        f: Path = self._cache / f"list_offset{offset}.json"
        if f.exists() and time.time() - f.stat().st_mtime < CACHE_MAX_AGE_S:
            return RawPage.model_validate_json(f.read_text(encoding="utf-8"))
        r = self._http.get(
            self._base,
            params={"response_fields": FIELDS, "limit": PAGE_SIZE, "offset": offset},
        )
        if r.status_code in (401, 403, 429):
            raise RestCountriesError(
                f"REST Countries answered {r.status_code} (401 bad key, 403 quota/plan, 429 rate)."
            )
        r.raise_for_status()
        page = RawPage.model_validate_json(r.text)  # validate BEFORE caching
        self._cache.mkdir(parents=True, exist_ok=True)
        f.write_text(r.text, encoding="utf-8")
        time.sleep(1)  # limit is 20 req/10s; we stay far below it
        return page

    def countries(self) -> Iterator[RawCountry]:
        offset = 0
        while True:
            data = self._page(offset).data
            yield from data.objects
            if not data.meta.more:
                return
            offset += PAGE_SIZE
