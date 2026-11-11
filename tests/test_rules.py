import pytest

from atlas_api.rules import (
    exists_in_year,
    has_content,
    name_as_of,
    nearest_snapshot,
    year_distance,
)


def test_year_distance_skips_zero():
    assert year_distance(-1, 1) == 1
    assert year_distance(-2, 1) == 2
    assert year_distance(1, 2) == 1
    assert year_distance(-5, -1) == 4
    assert year_distance(100, 100) == 0
    with pytest.raises(ValueError):
        year_distance(0, 5)


def test_exists_inclusive_bounds():
    assert exists_in_year(1871, 1918, 1871)
    assert exists_in_year(1871, 1918, 1918)
    assert not exists_in_year(1871, 1918, 1919)
    assert not exists_in_year(1871, 1918, 1870)
    assert exists_in_year(1949, None, 2500)
    assert exists_in_year(-300, -100, -100)


def test_name_as_of():
    p = [("Constantinopla", 330, 1929), ("Istambul", 1930, None)]
    assert name_as_of("Istambul", p, 1500) == "Constantinopla"
    assert name_as_of("Istambul", p, 1930) == "Istambul"
    assert name_as_of("Bizâncio", p, 100) == "Bizâncio"


def test_nearest_snapshot_tie_goes_earlier():
    assert nearest_snapshot([1880, 1914], 1897) == (1880, 17)
    assert nearest_snapshot([1900, 1920], 1910) == (1900, 10)  # tie -> earlier
    assert nearest_snapshot([-100, 100], 1) == (100, 99)
    assert nearest_snapshot([-1, 1], 1) == (1, 0)
    with pytest.raises(ValueError):
        nearest_snapshot([], 1900)


def test_has_content():
    assert has_content("resumo", 0)
    assert has_content(None, 1)
    assert not has_content("  ", 0)
    assert not has_content(None, 0)
