"""spec 012 stage 1: Cliopatria snapshot rules (offline)."""
import itertools

from etl.cliopatria.pipeline import alive, feature, labels, lifespans, snapshot_years


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


def test_feature_rings_are_clockwise_for_d3_and_snapped() -> None:
    from shapely.geometry import Polygon

    ccw = Polygon([(0, 0), (1.004, 0), (1.004, 1), (0, 1)])  # RFC 7946 winding, off-grid coordinate
    row = {"Name": "Kingdom of X", "geometry": ccw, "Wikidata": "Q1", "Wikipedia": "Kingdom of X", "MemberOf": "(Y Empire)"}
    f = feature(row, (1500, 1600), {"name": "Reino de X"})
    assert f is not None
    ring = f["geometry"]["coordinates"][0]
    signed = sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in itertools.pairwise(ring))
    assert signed > 0  # shoelace: positive = clockwise
    assert {c for pt in ring for c in pt} <= {0.0, 1.0}
    assert f["properties"] == {"name": "Reino de X", "name_en": "Kingdom of X", "wikidata": "Q1", "from_year": 1500, "to_year": 1600,
                               "member_of": "Y Empire", "wikipedia_url": "https://en.wikipedia.org/wiki/Kingdom_of_X"}
