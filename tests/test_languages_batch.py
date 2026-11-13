"""Languages ETL: a WDQS query timeout (HTTP 500) splits the batch at once instead of retrying it (the old retries hung for hours)."""
from pathlib import Path

import httpx
from etl.wikidata import languages


def test_timeout_splits_without_retry(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("etl.wikidata.leaders.time.sleep", lambda s: None)
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        n = req.url.params["query"].count("wd:Q")
        calls.append(n)
        if n > 2:  # big batches "time out"
            return httpx.Response(500)
        return httpx.Response(200, json={"results": {"bindings": [{"n": {"value": str(n)}}]}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows = languages._batched(client, tmp_path, "SELECT ?x WHERE {{ VALUES ?l {{ {ids} }} {label} }}",
                                  [f"Q{i}" for i in range(8)], refresh=False)
    assert sum(int(r["n"]["value"]) for r in rows) == 8  # every id fetched once
    assert calls == [8, 4, 2, 2, 4, 2, 2]  # each failure costs ONE request, then splits


def _lang(name: str, ancestors: set[str]) -> dict[str, object]:
    return {"name": name, "lang": True, "sign": False, "dead": False, "admin": False, "codes": set(), "status": None,
            "wikipedia_url": None, "ancestors": ancestors, "speakers": []}


def test_indo_european_is_never_indigenous_in_the_americas() -> None:
    fams = {"Q19860": {"label": "indo-europeia", "regions": [], "foreign_in": ["América do Sul"]},
            "Q34070": {"label": "tupi", "regions": ["América do Sul"]}}
    row = lambda q, kind: {"l": {"value": f"http://www.wikidata.org/entity/{q}"}, "kind": {"value": kind}}
    attrs = {"Q1": _lang("talian", {"Q19860"}), "Q2": _lang("nheengatu", {"Q34070"}), "Q3": _lang("guarani", set())}
    out = {x["name"]: x["status"] for x in languages.classify(
        "Q155", "América do Sul", [row("Q1", "indigenous_to"), row("Q2", "used"), row("Q3", "indigenous_to")], attrs, fams)}
    assert out == {"talian": "immigrant", "nheengatu": "indigenous", "guarani": "indigenous"}
