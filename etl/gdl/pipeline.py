"""Subnational HDI (spec 024 phase 2): Global Data Lab SHDI -> data_out/shdi.json, keyed by subdivision Wikidata id.

Read 2026-11-16. The GDL site (https://globaldatalab.org/termsofuse/) allows "noncommercial purposes ... provided that the
Global Data Lab is mentioned as the source of the indicators and a link to the GDL website including the data and version of the
download are clearly referenced", and its CSV downloads need a login. We use instead the copy the same authors archived at the
Radboud Data Repository (https://doi.org/10.34973/qbpx-by38, version 10.2): DataCite rights "Open Access" + "Creative Commons
Zero v1.0 Universal"; its LICENSE.txt: "You can copy, modify, distribute and perform the work, even for commercial purposes, all
without asking permission"; its ABOUT.txt asks to cite "Smits, J., Permanyer, I. (2026): Subnational Human Development Index
(Global Data Lab). Version 1. Radboud University" -> Source.title. Files are public over WebDAV (no login).

Mapping GDL region -> our subdivision (never guessed; unmatched = no HDI):
  1. same country (GDL ISO3 -> ISO2 via data_out/worldbank.json);
  2. the normalized GDL region name (accents/punctuation off, generic words like "province"/"state" dropped) equals a normalized
     name of exactly ONE subdivision of that country (its pt label, the web polygon name, Wikidata labels in a few Latin-script
     languages and English aliases), and that subdivision is claimed by exactly one GDL region;
  3. population check (a same-name unit at another level, e.g. GDL "Nord" = old Nord-Pas-de-Calais region vs the Nord
     department): GDL `pop` (thousands) and the Wikidata population must agree within POP_RATIO; no population = no match.
Value: the latest year with `shdi` (2023 for all but one region).
"""

import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached
from etl.wikidata.pipeline import _qid, _v
from etl.wikidata.subdivisions import admin1_ids

CSV_URL = "https://webdav.data.ru.nl/imr/gdl_shdi_dsc_770_v1/Subnational%20HDI%20Data%20v10.2.csv"
CSV_SHA256 = "2013c5b766149873988684acabe72459e1c4525bfac80d17e10bb7bbb9a526d9"  # MANIFEST.txt of the archive
SOURCE = {"id": "gdl-shdi",
          "title": "Smits, J., Permanyer, I. (2026): Subnational Human Development Index (Global Data Lab), v10.2. Radboud University",
          "url": "https://doi.org/10.34973/qbpx-by38", "license": "CC0 1.0"}
POP_RATIO = 1.5
LANGS = ("en", "es", "fr", "pt", "de", "it", "nl", "id", "tr", "pl", "sv", "ro", "cs", "hu", "vi", "ms")
NAMES_QUERY = """SELECT ?s ?l WHERE {{ VALUES ?s {{ {ids} }}
 {{ ?s rdfs:label ?l }} UNION {{ ?s skos:altLabel ?l FILTER(lang(?l) = "en") }}
 FILTER(lang(?l) IN ({langs})) }}"""
GENERIC = {"province", "provincia", "state", "estado", "region", "regiao", "department", "departamento", "departement",
           "governorate", "oblast", "county", "district", "prefecture", "territory", "of", "the", "de", "do", "da", "del", "la",
           "le", "das", "dos", "et", "and", "y", "e"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in re.sub(r"[^a-z0-9]+", " ", s).split() if w not in GENERIC)


def latest(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    """gdlcode -> {iso3, region, year, shdi, pop} at the latest year with an SHDI value; subnational rows only."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r["level"] != "Subnat" or not r["shdi"]:
            continue
        y = int(r["year"])
        if r["gdlcode"] not in out or y > out[r["gdlcode"]]["year"]:
            out[r["gdlcode"]] = {"iso3": r["isocode3"], "region": r["region"], "year": y, "shdi": float(r["shdi"]),
                                 "pop": float(r["pop"]) * 1000 if r["pop"] else None}
    return out


def match(regions: list[dict[str, Any]], subs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], int]:
    """One country. subs: {wikidata_id, names: set[str], population}. -> (qid -> {value, year}, rejected by population)."""
    owners: dict[str, set[str]] = {}
    for s in subs:
        for n in s["names"]:
            if k := norm(n):
                owners.setdefault(k, set()).add(s["wikidata_id"])
    claims: dict[str, list[dict[str, Any]]] = {}
    for g in regions:
        hit = owners.get(norm(g["region"]), set())
        if len(hit) == 1:
            claims.setdefault(next(iter(hit)), []).append(g)
    pop = {s["wikidata_id"]: s["population"] for s in subs}
    out, rejected = {}, 0
    for qid, gs in claims.items():
        if len(gs) != 1:
            continue
        g, p = gs[0], pop.get(qid)
        if not (p and g["pop"] and 1 / POP_RATIO <= g["pop"] / p <= POP_RATIO):
            rejected += 1
            continue
        out[qid] = {"value": g["shdi"], "year": g["year"]}
    return out, rejected


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    subs_file, wb = s.out_dir / "subdivisions.json", s.out_dir / "worldbank.json"
    if not subs_file.exists() or not wb.exists():
        sys.exit("Run `python -m etl wikidata-subdivisions` and `python -m etl worldbank` first.")
    iso3 = json.loads(wb.read_text(encoding="utf-8"))["iso3"]
    f = s.cache_dir / "gdl" / "shdi_v10.2.csv"
    if not f.exists() or "--refresh" in sys.argv:
        r = httpx.get(CSV_URL, headers={"User-Agent": "atlas-etl/0.1 (generic client)"}, timeout=300)
        r.raise_for_status()
        if hashlib.sha256(r.content).hexdigest() != CSV_SHA256:
            sys.exit("SHDI CSV does not match the archive's MANIFEST.txt SHA256: nothing written")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
    regions = latest(list(csv.DictReader(io.StringIO(f.read_text(encoding="utf-8")))))
    countries = json.loads(subs_file.read_text(encoding="utf-8"))["countries"]
    poly = {q: n for ids in admin1_ids(Path(s.admin1_dir)).values() for q, n in ids}
    qids = sorted({x["wikidata_id"] for xs in countries.values() for x in xs})
    names: dict[str, set[str]] = {}
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        for i in range(0, len(qids), 100):
            q = NAMES_QUERY.format(ids=" ".join("wd:" + x for x in qids[i:i + 100]), langs=", ".join(f'"{x}"' for x in LANGS))
            for row in _cached(client, s.cache_dir / "gdl" / f"names_{i // 100:03d}.json", q, "--refresh" in sys.argv):
                names.setdefault(_qid(_v(row, "s")) or "", set()).add(_v(row, "l") or "")
    by_iso2: dict[str, list[dict[str, Any]]] = {}
    for g in regions.values():
        if (i2 := iso3.get(g["iso3"])) in countries:
            by_iso2.setdefault(i2, []).append(g)
    out: dict[str, dict[str, Any]] = {}
    report = []
    for iso2, gs in sorted(by_iso2.items()):
        subs = [{"wikidata_id": x["wikidata_id"], "population": (x.get("population") or {}).get("value"),
                 "names": {x["name"], poly.get(x["wikidata_id"], "")} | names.get(x["wikidata_id"], set())}
                for x in countries[iso2]]
        got, rej = match(gs, subs)
        out.update(got)
        report.append((iso2, len(got), len(gs), len(subs), rej))
    payload = {"source": SOURCE, "retrieved_at": datetime.now(UTC).isoformat(), "items": out,
               "match": {iso2: {"matched": m, "gdl_regions": g, "subdivisions": n, "rejected_by_population": r}
                         for iso2, m, g, n, r in report}}
    (s.out_dir / "shdi.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/shdi.json: {len(out)} subdivisions with HDI; GDL regions in our countries: "
          f"{sum(r[2] for r in report)}; rejected by population: {sum(r[4] for r in report)}")
    print(f"  countries fully matched: {sum(m == g for _, m, g, _, _ in report)}/{len(report)}; none matched: "
          f"{sorted(i for i, m, *_ in report if m == 0)}")
