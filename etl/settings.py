"""ETL settings (pydantic-settings). Separate from the API settings: the API never needs these."""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class EtlSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    restcountries_api_key: SecretStr | None = None
    restcountries_base_url: str = "https://api.restcountries.com/countries/v5"
    # Contact (email or URL) for the Wikimedia User-Agent policy. Env var, never committed.
    wikidata_contact: str | None = None
    cache_dir: Path = Path("etl_cache")
    out_dir: Path = Path("data_out")


@lru_cache
def get_etl_settings() -> EtlSettings:
    return EtlSettings()
