"""Pure business rules for "year Y" logic. No DB, no I/O. See README "Regras do ano Y"."""

from collections.abc import Iterable, Sequence


def _ordinal(year: int) -> int:
    """Map years onto a line without a hole: ..., -2 -> -2, -1 -> -1, 1 -> 0, 2 -> 1, ..."""
    if year == 0:
        raise ValueError("there is no year 0 (1 BCE = -1, 1 CE = 1)")
    return year if year < 0 else year - 1


def year_distance(a: int, b: int) -> int:
    """Absolute number of years between a and b, skipping the missing year 0 (-1 -> 1 is 1)."""
    return abs(_ordinal(a) - _ordinal(b))


def exists_in_year(start_year: int, end_year: int | None, year: int) -> bool:
    """Both ends inclusive; end_year is the last year of existence; null = still exists."""
    _ordinal(year)
    return start_year <= year and (end_year is None or year <= end_year)


def name_as_of(
    default_name: str, periods: Iterable[tuple[str, int, int | None]], year: int
) -> str:
    """Covering (name, from_year, to_year) period, else the polity's default name."""
    for name, from_year, to_year in periods:
        if exists_in_year(from_year, to_year, year):
            return name
    return default_name


def nearest_snapshot(snapshot_years: Sequence[int], year: int) -> tuple[int, int]:
    """(snapshot_year, distance_years). Ties go to the earlier snapshot. Empty -> ValueError."""
    if not snapshot_years:
        raise ValueError("no snapshots")
    best = min(snapshot_years, key=lambda s: (year_distance(s, year), s))
    return best, year_distance(best, year)


def has_content(summary: str | None, event_count: int) -> bool:
    return bool(summary and summary.strip()) or event_count >= 1
