"""spec 012 stage 1: Cliopatria snapshot rules (offline)."""
from etl.cliopatria.pipeline import alive, labels, lifespans, snapshot_years


def _row(name: str, a: int, b: int, kind: str = "POLITY") -> dict[str, object]:
    return {"Name": name, "FromYear": a, "ToYear": b, "Type": kind}


def test_snapshot_years_have_no_year_zero_and_get_denser() -> None:
    ys = snapshot_years()
    assert ys[0] == -3400 and ys[-1] == 2024 and 0 not in ys and 1 in ys and ys == sorted(set(ys))
    assert {1492, 1789, 1914, 1945, 1989, 1991, 2023} <= set(ys) and 1913 not in ys and -3350 not in ys
    assert 120 <= len(ys) <= 140


def test_alive_drops_aggregates_and_relations() -> None:
    rows = [_row("British Raj", 1858, 1947), _row("(British Empire)", 1700, 1950), _row("Tibet", 1912, 1950),
            _row("Some union", 1900, 1920, "RELATION"), _row("Weimar Republic", 1919, 1933)]
    assert [r["Name"] for r in alive(rows, 1914)] == ["British Raj", "Tibet"]  # bounds inclusive, aggregate overlaps its parts
    assert [r["Name"] for r in alive(rows, 1919)] == ["British Raj", "Tibet", "Weimar Republic"]


def test_lifespan_spans_every_shape_and_labels_prefer_pt_br() -> None:
    assert lifespans([_row("Elam", -3200, -2701), _row("Elam", -2700, -540)]) == {"Elam": (-3200, -540)}
    q = {"value": "http://www.wikidata.org/entity/Q1"}
    rows = [{"q": q, "label": {"value": "Império Otomano", "xml:lang": "pt"}},
            {"q": q, "label": {"value": "Império Otomano (BR)", "xml:lang": "pt-br"}, "pt": {"value": "https://pt.wikipedia.org/wiki/X"}}]
    assert labels(rows) == {"Q1": {"name": "Império Otomano (BR)", "wikipedia_pt": "https://pt.wikipedia.org/wiki/X"}}
