from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from atlas_api.db.models import Event, GlossaryTerm, Meta, Polity, PolityName, Succession
from atlas_api.importer import ContentError, import_content


def _write(root: Path, polities: list[dict], succession: list[dict] | None = None) -> None:
    (root / "polities").mkdir(parents=True, exist_ok=True)
    (root / "sources.yaml").write_text(
        yaml.safe_dump([{"id": "s1", "title": "Livro", "url": None, "license": None}])
    )
    for p in polities:
        (root / "polities" / f"{p['id']}.yaml").write_text(yaml.safe_dump(p, allow_unicode=True))
    (root / "succession.yaml").write_text(yaml.safe_dump(succession or []))


def _p(id_: str, **kw: object) -> dict:
    return {"id": id_, "name": id_.title(), "type": "empire", "start_year": 1800, **kw}


def _ev(id_: str, sources: list[str]) -> dict:
    return {"id": id_, "year_start": -300, "precision": "circa", "title": "t", "summary": "s",
            "kind": "other", "source_ids": sources}


def test_import_is_idempotent_and_counts_unverified(session: Session, tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            _p("a", end_year=1900,
               names=[{"name": "Velho", "from_year": 1800, "to_year": 1850},
                      {"name": "Novo", "from_year": 1851}],
               events=[_ev("e1", []), _ev("e2", ["s1"])]),
            _p("b", start_year=1901),
        ],
        [{"predecessor": "a", "successor": "b", "year": 1901, "kind": "succeeded"}],
    )
    first = import_content(session, tmp_path)
    second = import_content(session, tmp_path)
    assert first["unverified_events"] == 1 and first["events"] == 2
    assert first["data_version"] == second["data_version"]
    assert session.scalar(select(func.count()).select_from(Event)) == 2
    assert session.scalar(select(func.count()).select_from(PolityName)) == 2
    assert session.scalar(select(func.count()).select_from(Succession)) == 1
    assert session.get(Polity, "a").end_year == 1900  # type: ignore[union-attr]
    assert session.get(Meta, "data_version").value == first["data_version"]  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("polities", "succession", "needle"),
    [
        ([_p("a", events=[_ev("e", ["nope"])])], [], "unknown source"),
        ([_p("a", start_year=0)], [], "bad years"),
        ([_p("a", names=[{"name": "x", "from_year": 1, "to_year": 50},
                         {"name": "y", "from_year": 40}])], [], "overlap"),
        ([_p("a"), _p("b")],
         [{"predecessor": "a", "successor": "b", "year": 5, "kind": "split"},
          {"predecessor": "b", "successor": "a", "year": 6, "kind": "split"}], "cycle"),
        ([_p("a")], [{"predecessor": "a", "successor": "zz", "year": 5, "kind": "split"}],
         "unknown polity"),
    ],
)
def test_invalid_content_is_rejected_and_nothing_written(
    session: Session, tmp_path: Path, polities: list[dict], succession: list[dict], needle: str
) -> None:
    _write(tmp_path, polities, succession)
    with pytest.raises(ContentError, match=needle):
        import_content(session, tmp_path)
    assert session.scalar(select(func.count()).select_from(Polity)) == 0


def test_glossary_import_and_validation(session: Session, tmp_path: Path) -> None:
    _write(tmp_path, [_p("a")])
    term = {"id": "republica", "kind": "regime", "label": "República", "short": "s", "body": "b",
            "icon": None, "sources": [{"id": "w", "title": "W", "url": "https://x"}]}
    (tmp_path / "regimes.yaml").write_text(yaml.safe_dump({"labels": {"republica": "República"}}))
    (tmp_path / "glossary.yaml").write_text(yaml.safe_dump({"terms": [term]}))
    assert import_content(session, tmp_path)["glossary_terms"] == 1
    got = session.get(GlossaryTerm, "republica")
    assert got is not None and got.sources[0]["license"] is None
    bad = {**term, "kind": "galaxy", "sources": []}
    (tmp_path / "glossary.yaml").write_text(yaml.safe_dump({"terms": [bad]}))
    (tmp_path / "regimes.yaml").write_text(yaml.safe_dump({"labels": {"x": "X"}}))
    with pytest.raises(ContentError) as e:
        import_content(session, tmp_path)
    assert len(e.value.problems) == 3  # kind, sources, regime x without a term
