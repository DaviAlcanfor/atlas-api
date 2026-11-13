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
