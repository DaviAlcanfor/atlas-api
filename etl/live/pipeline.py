"""spec 034: "acontecendo agora" - recent earthquakes (USGS) and natural events (NASA EONET), every 30 min by
.github/workflows/live-events.yml -> data_out/live_events.json -> `atlas_api.cli import-live-events`.

USGS (read 2026-11-17, https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits): "USGS-authored or
produced data and information are considered to be in the U.S. Public Domain." Credit asked: "U.S. Geological Survey".
Feed: M4.5+ of the past week (GeoJSON summary feed, "Updated every minute").
NASA EONET v3 (read 2026-11-17): no licence of its own; NASA media guidelines: content "generally [is] not subject to
copyright in the United States"; EONET disclaimer: "intended to be used for visualization and general information purposes
only and should not be construed as 'official' with regards to spatial or temporal extent". Each event links to its source
(InciWeb, JTWC, ...): we keep that link. One call per category (the all-events endpoint answered 500 on 2026-11-17).
A source that fails is reported as not ok: the import then keeps that source's previous rows.
"""
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from etl.settings import get_etl_settings

USGS = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
EONET = "https://eonet.gsfc.nasa.gov/api/v3/categories/{}"
EONET_TYPES = {"wildfires": "wildfire", "severeStorms": "severe_storm", "volcanoes": "volcano", "floods": "flood",
               "landslides": "landslide", "dustHaze": "dust_haze", "tempExtremes": "temp_extreme", "drought": "drought",
               "snow": "snow"}  # left out: earthquakes (USGS has them), sea/lake ice (icebergs tracked for years), manmade, water color
RETENTION_DAYS = 7


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def from_usgs(feed: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for f in feed.get("features") or []:
        p, (lng, lat, *_) = f["properties"], f["geometry"]["coordinates"]
        out.append({"id": f"usgs:{f['id']}", "source": "usgs", "type": "earthquake", "lat": lat, "lng": lng,
                    "magnitude": p.get("mag"), "magnitude_unit": p.get("magType"), "title": p.get("title") or p.get("place"),
                    "url": p.get("url"), "time": _iso(datetime.fromtimestamp(p["time"] / 1000, UTC))})
    return out


def _point(g: dict[str, Any]) -> tuple[float, float]:
    """(lat, lng) of a GeoJSON Point, or the mean of a Polygon's outer ring."""
    if g["type"] == "Point":
        return g["coordinates"][1], g["coordinates"][0]
    ring = g["coordinates"][0]
    return sum(c[1] for c in ring) / len(ring), sum(c[0] for c in ring) / len(ring)


def from_eonet(by_category: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One row per event, at its LATEST geometry (a storm's current position)."""
    out = []
    for cat, events in by_category.items():
        for e in events:
            if not e.get("geometry"):
                continue
            g = max(e["geometry"], key=lambda x: x["date"])
            lat, lng = _point(g)
            out.append({"id": f"eonet:{e['id']}", "source": "eonet", "type": EONET_TYPES[cat], "lat": lat, "lng": lng,
                        "magnitude": g.get("magnitudeValue"), "magnitude_unit": g.get("magnitudeUnit"), "title": e["title"],
                        "url": next((s["url"] for s in e.get("sources") or [] if s.get("url")), e.get("link")),
                        "time": _iso(datetime.fromisoformat(g["date"]))})
    return out


def run() -> None:
    s = get_etl_settings()
    now = datetime.now(UTC)
    since = _iso(now - timedelta(days=RETENTION_DAYS))
    items: list[dict[str, Any]] = []
    ok = {"usgs": False, "eonet": False}
    with httpx.Client(headers={"User-Agent": "atlas-api/0.1 (etl live-events)"}, timeout=60) as client:
        try:
            r = client.get(USGS)
            r.raise_for_status()
            items += from_usgs(r.json())
            ok["usgs"] = True
        except (httpx.HTTPError, ValueError, KeyError) as e:
            print(f"usgs failed: {e}")
        try:
            cats = {}
            for cat in EONET_TYPES:
                r = client.get(EONET.format(cat), params={"days": RETENTION_DAYS})
                r.raise_for_status()
                cats[cat] = r.json().get("events") or []
            items += from_eonet(cats)
            ok["eonet"] = True
        except (httpx.HTTPError, ValueError, KeyError) as e:
            print(f"eonet failed: {e}")
    items = sorted((x for x in items if x["time"] >= since), key=lambda x: (x["time"], x["id"]), reverse=True)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "live_events.json").write_text(json.dumps(
        {"fetched_at": _iso(now), "ok": ok, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/live_events.json: {len(items)} events, sources ok: {ok}")
    if not any(ok.values()):
        raise SystemExit("both sources failed")
