"""Subdivisions ETL (spec 024): facts + flag of every state/province drawn by the web -> data_out/subdivisions.json.

Which subdivisions: the Wikidata ids already on the web's admin-1 polygons (Natural Earth `wikidataid`), read from
`<ADMIN1_DIR>/<ISO2>.geojson` (default ../geo/public/data/admin1), so the API answers exactly for the shapes on the globe.
Wikidata (CC0), same endpoint/politeness/cache as pipeline.py, batches of 100 ids, two queries per batch (one for population:
joined with the rest it multiplies rows):
  P300 ISO 3166-2 code · P2046 area (normalized value, m² -> km²) · P36 capital · P41 flag image ·
  P1082 population: preferred rank, else the statement with the latest P585 date.
NO head of government: tested 2026-11-12, Wikidata's governors are stale (P6 of Rio de Janeiro = Witzel, removed 2021; the
office route P1313 + P39 returns 19th-century holders without end dates). A wrong governor is worse than none: left out.
Flags: Commons, licence PER FILE (MediaWiki imageinfo extmetadata, docs read 2026-11-11 for spec 006): `LicenseShortName` +
`Artist`. Flags are nearly all public domain without a named artist, so for flags a public-domain/CC0 licence alone is enough
(credit "Wikimedia Commons"); anything else still needs both. Thumbnails mirrored like leader photos (mirror_images).
"""

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached, _file, commons_images
from etl.wikidata.pipeline import LABEL, _qid, _v

BATCH = 100
FACTS_QUERY = """SELECT ?s ?sLabel ?iso ?area ?cap ?capLabel ?flag WHERE {{
 VALUES ?s {{ {ids} }}
 OPTIONAL {{ ?s wdt:P300 ?iso }}
 OPTIONAL {{ ?s p:P2046/psn:P2046/wikibase:quantityAmount ?area }}
 OPTIONAL {{ ?s wdt:P36 ?cap }}
 OPTIONAL {{ ?s wdt:P41 ?flag }}
 {label} }}"""
POP_QUERY = """SELECT ?s ?pop ?when ?rank WHERE {{ VALUES ?s {{ {ids} }}
 ?s p:P1082 ?ps. ?ps ps:P1082 ?pop; wikibase:rank ?rank. FILTER(?rank != wikibase:DeprecatedRank)
 OPTIONAL {{ ?ps pq:P585 ?when }} }}"""
PD = re.compile(r"public domain|domínio público|^pd|cc0", re.IGNORECASE)


def admin1_ids(folder: Path) -> dict[str, list[tuple[str, str]]]:
    """ISO2 -> [(Q-id, polygon name)] in file order, from the web's admin-1 files."""
    out: dict[str, list[tuple[str, str]]] = {}
    for f in sorted(folder.glob("*.geojson")):
        feats = json.loads(f.read_text(encoding="utf-8"))["features"]
        ids = [(p["wikidataid"], p.get("name") or "") for x in feats if (p := x.get("properties") or {}).get("wikidataid")]
        if ids:
            out[f.stem] = ids
    return out


def pick_population(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Preferred rank wins; else the latest dated statement; undated ones only when nothing is dated."""
    if not rows:
        return None
    def key(r: dict[str, Any]) -> tuple[bool, str]:
        return (_v(r, "rank") == "http://wikiba.se/ontology#PreferredRank", _v(r, "when") or "")
    best = max(rows, key=key)
    when = _v(best, "when")
    return {"value": int(float(_v(best, "pop") or 0)), "year": int(when[:4]) if when and when[:4].isdigit() else None}


def build(ids: list[tuple[str, str]], facts: list[dict[str, Any]], pops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_facts: dict[str, list[dict[str, Any]]] = {}
    for r in facts:
        by_facts.setdefault(_qid(_v(r, "s")) or "", []).append(r)
    by_pop: dict[str, list[dict[str, Any]]] = {}
    for r in pops:
        by_pop.setdefault(_qid(_v(r, "s")) or "", []).append(r)
    out = []
    for qid, poly_name in ids:
        rs = by_facts.get(qid, [])

        def first(k: str, rs: list[dict[str, Any]] = rs) -> str | None:
            return next((v for r in rs if (v := _v(r, k))), None)
        label = first("sLabel")
        area = first("area")
        out.append({
            "wikidata_id": qid,
            "name": label if label and label != qid else poly_name,
            "code": first("iso"),
            "capital": first("capLabel"),
            "area_km2": round(float(area) / 1e6, 1) if area else None,
            "population": pick_population(by_pop.get(qid, [])),
            "flag_file": _file(first("flag")),
        })
    return out


def collect(client: httpx.Client, folder: Path, cache: Path, refresh: bool,
            only: list[str] | None = None) -> dict[str, Any]:
    countries = {k: v for k, v in admin1_ids(folder).items() if not only or k in only}
    qids = sorted({q for ids in countries.values() for q, _ in ids})
    facts: list[dict[str, Any]] = []
    pops: list[dict[str, Any]] = []
    for i in range(0, len(qids), BATCH):
        vals = " ".join("wd:" + q for q in qids[i:i + BATCH])
        facts += _cached(client, cache / f"facts_{i // BATCH:03d}.json", FACTS_QUERY.format(ids=vals, label=LABEL), refresh)
        pops += _cached(client, cache / f"pop_{i // BATCH:03d}.json", POP_QUERY.format(ids=vals), refresh)
    by_country = {iso2: build(ids, facts, pops) for iso2, ids in countries.items()}
    files = {s["flag_file"] for ss in by_country.values() for s in ss if s["flag_file"]}
    flags = commons_images(client, files, cache, refresh, accept_without_artist=PD)
    for ss in by_country.values():
        for s in ss:
            s["flag"] = flags.get(s.pop("flag_file") or "")
    return {"source": {"id": "wikidata", "title": "Wikidata", "url": "https://www.wikidata.org/",
                       "license": "CC0 1.0 (flags: per-file licence from Wikimedia Commons, see flag.license)"},
            "retrieved_at": datetime.now(UTC).isoformat(), "countries": by_country}


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    folder = Path(s.admin1_dir)
    if not folder.is_dir():
        sys.exit(f"admin-1 folder not found: {folder} (set ADMIN1_DIR to the web repo's public/data/admin1)")
    only = [a for a in sys.argv[2:] if re.fullmatch(r"[A-Z]{2}", a)] or None
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        payload = collect(client, folder, s.cache_dir / "wikidata" / "subdivisions", "--refresh" in sys.argv, only)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    name = "subdivisions.json" if not only else "subdivisions_sample.json"
    (s.out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    ss = [x for v in payload["countries"].values() for x in v]
    print(f"wrote data_out/{name}: {len(ss)} subdivisions in {len(payload['countries'])} countries")
    for k in ("code", "capital", "area_km2", "population", "flag"):
        print(f"  with {k}: {sum(x[k] is not None for x in ss)}")
