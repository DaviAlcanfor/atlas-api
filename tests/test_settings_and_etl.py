import pytest
from etl.restcountries.models import RawCountry
from etl.restcountries.transform import to_facts

from atlas_api.config import Settings


def test_cors_origins_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://x.example")
    assert Settings().cors_origins == ["http://localhost:5173", "https://x.example"]


def test_to_facts_maps_and_never_invents() -> None:
    raw = RawCountry.model_validate({
        "names": {"official": "Canada"},
        "codes": {"alpha_2": "CA"},
        "capitals": [
            {"name": "X", "primary": False},
            {"name": "Ottawa", "primary": True, "coordinates": {"lat": 45.42, "lng": -75.7}},
        ],
        "languages": [{"name": "English", "bcp47": "en"}],
        "memberships": {"un": True, "eu": False, "g7": True, "nato": None},
        "unknown_field": 1,
    })
    f = to_facts(raw, "t")
    assert f is not None
    assert (f.capital, f.capital_lat) == ("Ottawa", 45.42)
    assert f.memberships == ["g7", "un"]
    assert f.population is None and f.population_year is None and f.area_km2 is None


def test_to_facts_skips_records_without_iso2() -> None:
    assert to_facts(RawCountry(), "t") is None
