import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from atlas_api.db.models import Polity


def _polity(**kw: object) -> Polity:
    base = {"id": "x", "name": "X", "type": "empire", "start_year": 1800}
    return Polity(**{**base, **kw})


def test_valid_polity_roundtrip(session: Session) -> None:
    session.add(_polity(start_year=-300, end_year=-100))
    session.flush()
    assert session.get(Polity, "x").start_year == -300  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "kw",
    [
        {"start_year": 0},
        {"start_year": 5, "end_year": 0},
        {"start_year": 1900, "end_year": 1800},
        {"iso2": "br"},
        {"type": "galaxy"},
        {"start_precision": "maybe"},
    ],
)
def test_checks_reject_bad_rows(session: Session, kw: dict[str, object]) -> None:
    session.add(_polity(**kw))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unaccent_expression_matches_index(session: Session) -> None:
    got = session.execute(text("select lower(public.f_unaccent('Áustria'))")).scalar()
    assert got == "austria"
