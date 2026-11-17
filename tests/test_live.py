"""spec 034: live events. Parsers on recorded USGS/EONET responses (no network) + import and endpoint."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from etl.live.pipeline import from_eonet, from_usgs
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas_api.facts import import_live_events
from atlas_api.schemas import LiveEventList

USGS = json.loads(Path("tests/fixtures/usgs_4.5_week_sample.json").read_text(encoding="utf-8"))
EONET = json.loads(Path("tests/fixtures/eonet_categories_sample.json").read_text(encoding="utf-8"))


def test_parsers() -> None:
    q = from_usgs(USGS)
    assert len(q) == 3 and q[0]["id"] == "usgs:us7000tysq" and q[0]["type"] == "earthquake"
    assert q[0]["magnitude"] == 5.2 and q[0]["title"] == "M 5.2 - south of the Kermadec Islands"
    assert q[0]["time"].endswith("+00:00") and -90 <= q[0]["lat"] <= 90
    e = from_eonet(EONET)
    storm = next(x for x in e if x["type"] == "severe_storm")
    assert storm["title"] == "Tropical Cyclone Akvan" and (storm["lat"], storm["lng"]) == (11.4, 86.8)
    assert storm["magnitude_unit"] == "kts" and storm["url"].startswith("https://www.metoc.navy.mil/")
    assert {x["type"] for x in e} == {"wildfire", "severe_storm"}
    poly = from_eonet({"volcanoes": [{"id": "X", "title": "t", "sources": [], "link": "l", "geometry": [
        {"date": "2026-11-17T00:00:00Z", "type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2]]]}]}]})
    assert (poly[0]["lat"], poly[0]["lng"]) == (1, 1) and poly[0]["url"] == "l"


def _write(path: Path, now: datetime, items: list[dict], ok: dict[str, bool]) -> Path:
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "ok": ok, "items": items}), encoding="utf-8")
    return path


def test_import_and_endpoint(api_client: TestClient, tmp_path: Path) -> None:
    now = datetime.now(UTC)
    fresh = [{**x, "time": (now - timedelta(hours=i + 1)).isoformat()} for i, x in enumerate(from_usgs(USGS) + from_eonet(EONET))]
    old = {**fresh[0], "id": "usgs:old", "time": (now - timedelta(days=9)).isoformat()}
    eng = create_engine(api_client.app.state.test_url)  # type: ignore[attr-defined]
    with Session(eng) as s, s.begin():
        assert import_live_events(s, _write(tmp_path / "a.json", now, [*fresh, old], {"usgs": True, "eonet": True})) == {
            "live_events_imported": 7, "live_events_expired": 1}
    with Session(eng) as s, s.begin():  # EONET down: its rows stay, USGS replaced (now empty)
        import_live_events(s, _write(tmp_path / "b.json", now, [], {"usgs": True, "eonet": False}))
    r = api_client.get("/v1/live/events")
    assert r.headers["cache-control"] == "public, max-age=300" and "etag" not in r.headers
    body = LiveEventList.model_validate(r.json())
    assert {x.source for x in body.items} == {"eonet"} and len(body.items) == 3 and body.fetched_at
    assert [x.time for x in body.items] == sorted((x.time for x in body.items), reverse=True)
    assert [x.id for x in body.sources] == ["eonet"]
    with Session(eng) as s, s.begin():
        import_live_events(s, _write(tmp_path / "c.json", now, fresh, {"usgs": True, "eonet": True}))
    eng.dispose()
    quakes = api_client.get("/v1/live/events?type=earthquake").json()["items"]
    assert len(quakes) == 3 and all(x["type"] == "earthquake" for x in quakes)
    since = (now - timedelta(hours=2, minutes=30)).isoformat().replace("+00:00", "Z")
    assert len(api_client.get("/v1/live/events", params={"since": since}).json()["items"]) == 2
    assert api_client.get("/v1/live/events?type=meteor").status_code == 422
