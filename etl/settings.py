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
    # spec 019: Supabase Storage API base (https://<ref>.supabase.co/storage/v1) + service key.
    # Both set = Commons thumbnails are copied to the public bucket `atlas-images`; else hotlink.
    image_bucket_url: str | None = None
    supabase_service_key: SecretStr | None = None
    cache_dir: Path = Path("etl_cache")
    out_dir: Path = Path("data_out")
    admin1_dir: Path = Path("../geo/public/data/admin1")  # spec 024: the web repo's admin-1 polygons (their wikidataid)


@lru_cache
def get_etl_settings() -> EtlSettings:
    return EtlSettings()
