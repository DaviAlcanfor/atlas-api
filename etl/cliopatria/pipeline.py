"""Historical borders ETL (spec 012, stage 1): Cliopatria -> one GeoJSON per snapshot year + data_out/snapshots.json.

Source: Cliopatria (Seshat Global History Databank), github.com/Seshat-Global-History-Databank/cliopatria, release v0.2.1
(2026-10-03), file `cliopatria.geojson.zip` (sha256 below). Licence read 2026-11-13 (LICENSE.md): "Creative Commons Attribution
4.0 International License, which permits use, sharing, adaptation, distribution and reproduction in any medium or format, as long
as you give appropriate credit to the original author(s) and the source, provide a link to the Creative Commons license, and
indicate if changes were made". Our changes (clients must say so): coordinates snapped to a grid, aggregates dropped, names
translated. Rows: Name, FromYear, ToYear (negative = BCE), Type (POLITY/RELATION), Wikipedia (en title), Wikidata, Components, MemberOf.

Per snapshot year: rows of Type POLITY alive that year, minus aggregates. An aggregate is a row named in parentheses
("(British Empire)") whose shape is the union of its components, so it overlaps them; the components keep it as `member_of`.
Measured 2026-11-13: the heaviest year has ~33 000 points, so snapping to GRID (0.01 degree, ~1 km) is enough to stay under
MAX_BYTES; no topology step. Shapes that vanish at that grid (micro-states) are snapped at FINE_GRID instead.
GeoJSON rather than the TopoJSON first proposed: the files are already small and the web draws GeoJSON features everywhere else.
Files go straight into the WEB repo (`HISTORICAL_DIR`, default ../geo/public/data/historical, committed there: ~36 MB) and
`geometry_url` is the path relative to the web origin, as contract v1 says. No Storage: nothing to configure or keep in sync.
pt-BR names and pt.wikipedia titles come from Wikidata (CC0) by the row's Q-id; without one, the Cliopatria name (English).
"""

import hashlib
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached

RELEASE = "v0.2.1"
URL = f"https://raw.githubusercontent.com/Seshat-Global-History-Databank/cliopatria/{RELEASE}/cliopatria.geojson.zip"
SHA256 = "e10a4e429fca708788ff9e7572a95fce801fae55852d217cffabc1c59cd4eed4"
GRID, FINE_GRID = 0.01, 0.001
MAX_BYTES = 600_000  # per file, uncompressed (spec 012)
KEY_YEARS = [1492, 1648, 1789, 1815, 1871, 1914, 1918, 1939, 1945, 1989]
BATCH = 200
LABELS_QUERY = """SELECT ?q ?label ?pt WHERE {{ VALUES ?q {{ {ids} }}
 OPTIONAL {{ ?q rdfs:label ?label. FILTER(LANG(?label) IN ("pt-br", "pt")) }}
 OPTIONAL {{ ?pt schema:about ?q; schema:isPartOf <https://pt.wikipedia.org/> }} }}"""


def snapshot_years(first: int = -3400, last: int = 2024) -> list[int]:
    """Denser as records get denser: every 100 years to 1400, 50 to 1700, 25 to 1800, 10 to 1900, 5 to 1990, yearly after,
    plus KEY_YEARS. There is no year 0 (1 BCE = -1): the step that would land on it uses 1."""
    steps = [(first, 1400, 100), (1400, 1700, 50), (1700, 1800, 25), (1800, 1900, 10), (1900, 1990, 5), (1990, last + 1, 1)]
    years = {y or 1 for a, b, step in steps for y in range(a, b, step)} | set(KEY_YEARS)
    return sorted(y for y in years if first <= y <= last)


def is_aggregate(name: str) -> bool:
    return name.startswith("(")


def alive(rows: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    return [r for r in rows if r["Type"] == "POLITY" and not is_aggregate(r["Name"]) and r["FromYear"] <= year <= r["ToYear"]]


def lifespans(rows: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """Name -> (first year, last year) over all of its rows (a polity's shape changes, so it has many rows)."""
    out: dict[str, tuple[int, int]] = {}
    for r in rows:
        a, b = out.get(r["Name"], (r["FromYear"], r["ToYear"]))
        out[r["Name"]] = (min(a, r["FromYear"]), max(b, r["ToYear"]))
    return out


def labels(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Q-id -> {name?, wikipedia_pt?} from the SPARQL rows; a pt-br label wins over pt."""
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        q = r["q"]["value"].rsplit("/", 1)[-1]
        d = out.setdefault(q, {})
        lab = r.get("label")
        if lab and (lab.get("xml:lang") == "pt-br" or "name" not in d):
            d["name"] = lab["value"]
        if "pt" in r:
            d["wikipedia_pt"] = r["pt"]["value"]
    return out


def feature(r: dict[str, Any], life: tuple[int, int], lab: dict[str, str]) -> dict[str, Any] | None:
    """One GeoJSON feature; None when the shape is empty even at the fine grid."""
    import shapely  # type: ignore[import-untyped]  # etl group only

    geom = shapely.set_precision(r["geometry"], GRID)
    if geom.is_empty:
        geom = shapely.set_precision(r["geometry"], FINE_GRID)
    if geom.is_empty:
        return None
    qid = r["Wikidata"] if r["Wikidata"].startswith("Q") else None
    wiki = lab.get("wikipedia_pt") or (f"https://en.wikipedia.org/wiki/{r['Wikipedia'].replace(' ', '_')}" if r["Wikipedia"] else None)
    return {"type": "Feature", "geometry": json.loads(shapely.to_geojson(geom)), "properties": {
        "name": lab.get("name") or r["Name"], "name_en": r["Name"], "wikidata": qid, "from_year": life[0], "to_year": life[1],
        "member_of": r["MemberOf"].strip("()") or None, "wikipedia_url": wiki}}


def load(cache: Path) -> list[dict[str, Any]]:
    import geopandas as gpd  # type: ignore[import-untyped]  # etl group only

    z = cache / "cliopatria.geojson.zip"
    if not z.exists():
        cache.mkdir(parents=True, exist_ok=True)
        z.write_bytes(httpx.get(URL, follow_redirects=True, timeout=300).raise_for_status().content)
    if hashlib.sha256(z.read_bytes()).hexdigest() != SHA256:
        sys.exit(f"{z}: sha256 differs from the pinned release {RELEASE}; delete the file or update SHA256 after reading the changes")
    with zipfile.ZipFile(z) as zf, zf.open(zf.namelist()[0]) as f:
        return gpd.read_file(f).to_dict("records")  # type: ignore[no-any-return]


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    cache = s.cache_dir / "cliopatria"
    rows = load(cache)
    life = lifespans(rows)
    qids = sorted({r["Wikidata"] for r in rows if r["Wikidata"].startswith("Q")})
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    out_dir = s.historical_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        lab_rows: list[Any] = []
        for i in range(0, len(qids), BATCH):
            ids = " ".join("wd:" + q for q in qids[i:i + BATCH])
            lab_rows += _cached(client, cache / f"labels_{i // BATCH:03d}.json", LABELS_QUERY.format(ids=ids), "--refresh" in sys.argv)
        labs = labels(lab_rows)
        items: list[dict[str, Any]] = []
        for year in snapshot_years():
            feats = [f for r in alive(rows, year) if (f := feature(r, life[r["Name"]], labs.get(r["Wikidata"], {})))]
            if not feats:
                continue
            body = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":")).encode()
            name = f"world_{year}.geojson"
            (out_dir / name).write_bytes(body)
            items.append({"year": year, "geometry_url": f"/data/historical/{name}", "feature_count": len(feats), "bytes": len(body)})
    payload = {"source": {"id": "cliopatria", "title": f"Cliopatria {RELEASE} (Seshat Global History Databank)",
                          "url": "https://github.com/Seshat-Global-History-Databank/cliopatria", "license": "CC BY 4.0",
                          "retrieved_at": datetime.now(UTC).isoformat()}, "items": items}
    (s.out_dir / "snapshots.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    sizes = [x["bytes"] for x in items]
    big = [x["year"] for x in items if x["bytes"] > MAX_BYTES]
    print(f"wrote {len(items)} snapshots to {out_dir}: {sum(sizes) / 1e6:.1f} MB total, largest {max(sizes) / 1e3:.0f} KB")
    print(f"  with a pt name: {sum('name' in v for v in labs.values())}/{len(qids)} entities; over {MAX_BYTES // 1000} KB: {big or 'none'}")
