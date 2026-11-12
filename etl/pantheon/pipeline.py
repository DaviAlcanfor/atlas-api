"""Pantheon ETL (spec 007): notable people per country -> data_out/pantheon.json.

Read 2026-11-11, https://pantheon.world/data/permissions: "Pantheon by Datawheel is licensed under
a Creative Commons Attribution-ShareAlike 4.0 International License." and "If you use the Pantheon
dataset, please cite:" Yu, A. Z., et al. (2016) Pantheon 1.0, Scientific Data 3:150075.
https://pantheon.world/data/datasets: direct file downloads, no login, e.g.
person_2025_update.csv.bz2 (bzip2 CSV, one row per person; columns include wd_id, name,
occupation, bplace_country, birthyear, deathyear, hpi). ShareAlike: what we serve from it stays
CC BY-SA 4.0 with attribution (the endpoint's `source` carries both).
Years: Pantheon writes 100 BC as -100 (Julius Caesar: -100, "0100-07-01 BC"), our convention.
Occupation -> domain: Pantheon's own taxonomy, https://api.pantheon.world/occupation (cached).
Country = modern country of the birthplace, as decided by Pantheon (`bplace_country`, English
name), matched to our ISO2 by the Wikidata English label/aliases + NAME_FIXES below.
Photo + link: Wikidata (CC0) P18 + pt/en sitelink by wd_id; photo licence per file from Commons
(same rule as leaders: licence AND artist, else null).
"""

import bz2
import csv
import hashlib
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached, _get_json, commons_images
from etl.wikidata.pipeline import STATE, _qid, _v

DATASET_URL = "https://storage.googleapis.com/pantheon-public-data/person_2025_update.csv.bz2"
OCCUPATIONS_URL = "https://api.pantheon.world/occupation"
TOP_N = 50
DOMAINS = {  # Pantheon domain -> our id (same 8 areas, no regrouping)
    "ARTS": "arts", "BUSINESS & LAW": "business_law", "EXPLORATION": "exploration",
    "HUMANITIES": "humanities", "INSTITUTIONS": "institutions", "PUBLIC FIGURE": "public_figure",
    "SCIENCE & TECHNOLOGY": "science_technology", "SPORTS": "sports",
}
# Pantheon country names that are not an English label/alias of the state in Wikidata.
NAME_FIXES = {
    "Bahamas, The": "BS", "The Bahamas": "BS", "The Gambia": "GM", "Myanmar (Burma)": "MM",
    "Czech Republic": "CZ", "Swaziland": "SZ", "Türkiye": "TR", "Micronesia": "FM",
    "Federated States of Micronesia": "FM", "Republic of the Congo": "CG",
    "Democratic Republic of the Congo": "CD", "Palestine": "PS", "Vatican City": "VA",
    "Cabo Verde": "CV", "China": "CN", "Denmark": "DK", "Côte d'Ivoire": "CI", "São Tomé and Príncipe": "ST",
}
EN_NAMES_QUERY = (
    f"SELECT ?iso2 ?n WHERE {{ {STATE} {{ ?c rdfs:label ?n }} UNION {{ ?c skos:altLabel ?n }} "
    'FILTER(LANG(?n) = "en") }'
)
MEDIA_QUERY = """SELECT ?p ?image ?pt ?en WHERE {{ VALUES ?p {{ {qids} }}
 OPTIONAL {{ ?p wdt:P18 ?image }}
 OPTIONAL {{ ?pt schema:about ?p; schema:isPartOf <https://pt.wikipedia.org/> }}
 OPTIONAL {{ ?en schema:about ?p; schema:isPartOf <https://en.wikipedia.org/> }} }}"""
METHOD = (
    "Ranking pelo Historical Popularity Index (HPI) do Pantheon 2025 (Datawheel), que combina o "
    "número de edições da Wikipédia e as visualizações das biografias. País = país moderno do "
    "local de nascimento, como definido pelo Pantheon. Viés conhecido da fonte: super-representa "
    "homens, Europa e figuras antigas. Foto e link vêm do Wikidata."
)
SOURCE = {
    "id": "pantheon", "title": "Pantheon 2025 (Datawheel)", "url": "https://pantheon.world/",
    "license": "CC BY-SA 4.0. Cite: Yu, A. Z., et al. (2016) Pantheon 1.0, a manually verified "
               "dataset of globally famous biographies. Scientific Data 3:150075.",
}


def _year(s: str) -> int | None:
    try:
        y = int(s)
    except ValueError:
        return None
    return y or None  # no year 0 in our convention


def top_by_country(rows: list[dict[str, str]], names: dict[str, str],
                   domains: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """Top TOP_N rows by HPI per ISO2 -> Person records (image/link filled later)."""
    by: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        iso = names.get(r["bplace_country"])
        if iso and r.get("hpi") and r.get("wd_id"):
            by.setdefault(iso, []).append(r)
    out: dict[str, list[dict[str, Any]]] = {}
    for iso, rs in by.items():
        rs.sort(key=lambda r: (-float(r["hpi"]), r["name"]))
        out[iso] = [{
            "id": r["wd_id"], "name": r["name"], "occupation": r["occupation"] or None,
            "domain": domains.get(r["occupation"]), "birth_year": _year(r["birthyear"]),
            "death_year": _year(r["deathyear"]), "rank": i, "hpi": float(r["hpi"]),
        } for i, r in enumerate(rs[:TOP_N], 1)]
    return out


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL): required by the Wikimedia User-Agent policy.")
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    with httpx.Client(headers={"User-Agent": ua}, timeout=120, follow_redirects=True) as client:
        payload = collect(client, s.cache_dir, "--refresh" in sys.argv)
    write(payload, s.out_dir)


def collect(client: httpx.Client, cache_dir: Path, refresh: bool) -> dict[str, Any]:
    cache = cache_dir / "pantheon"
    cache.mkdir(parents=True, exist_ok=True)
    data = cache / DATASET_URL.rsplit("/", 1)[-1]
    if refresh or not data.exists():
        r = client.get(DATASET_URL)
        r.raise_for_status()
        data.write_bytes(r.content)
    occ_file = cache / "occupations.json"
    if refresh or not occ_file.exists():
        occ = _get_json(client, OCCUPATIONS_URL, {"select": "occupation,domain"})
        occ_file.write_text(json.dumps(occ, ensure_ascii=False), encoding="utf-8")
    domains = {o["occupation"]: DOMAINS[o["domain"]] for o in
               json.loads(occ_file.read_text(encoding="utf-8")) if o.get("domain") in DOMAINS}
    names = {_v(r, "n") or "": _v(r, "iso2") or "" for r in _cached(
        client, cache_dir / "wikidata" / "en_names.json", EN_NAMES_QUERY, refresh)}
    names |= NAME_FIXES
    with bz2.open(data) as fh:
        rows = list(csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8")))
    unmatched = sorted({r["bplace_country"] for r in rows} - set(names) - {""})
    people = top_by_country(rows, names, domains)

    qids = sorted({p["id"] for ps in people.values() for p in ps})
    files: dict[str, set[str]] = {}
    links: dict[str, dict[str, str]] = {}
    for i in range(0, len(qids), 200):  # 200 Q-ids per query
        q = MEDIA_QUERY.format(qids=" ".join("wd:" + x for x in qids[i:i + 200]))
        key = hashlib.sha256(q.encode()).hexdigest()[:12]  # cache keyed by the batch content
        for r in _cached(client, cache / f"media_{key}.json", q, refresh):
            pid = _qid(_v(r, "p")) or ""
            if img := _v(r, "image"):
                files.setdefault(pid, set()).add(unquote(img.rsplit("/", 1)[-1]))
            for lang in ("pt", "en"):
                if url := _v(r, lang):
                    links.setdefault(pid, {})[lang] = url
    single = {pid: next(iter(f)) for pid, f in files.items() if len(f) == 1}  # several = no pick
    images = commons_images(client, set(single.values()), cache, refresh)
    for ps in people.values():
        for p in ps:
            p["image"] = images.get(single.get(p["id"], ""))
            lk = links.get(p["id"], {})
            p["wikipedia_url"] = lk.get("pt") or lk.get("en")
    return {"source": {**SOURCE, "retrieved_at": datetime.now(UTC).isoformat()},
            "method": METHOD, "unmatched_countries": unmatched,
            "countries": dict(sorted(people.items()))}


def write(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pantheon.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    cs = payload["countries"]
    n = sum(len(v) for v in cs.values())
    print(f"wrote data_out/pantheon.json: {n} people, {len(cs)} countries")
    print(f"  with image: {sum(p['image'] is not None for v in cs.values() for p in v)}/{n}")
    print(f"  with wikipedia_url: {sum(bool(p['wikipedia_url']) for v in cs.values() for p in v)}/{n}")
    print(f"  without domain: {sum(p['domain'] is None for v in cs.values() for p in v)}/{n}")
    print(f"  Pantheon names not matched to a state (territories etc.): {payload['unmatched_countries']}")
