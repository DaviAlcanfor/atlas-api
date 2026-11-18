"""BACI trade ETL (spec 029 phase 2) -> data_out/trade.json: per country, total exports and imports, top 10 exports by HS
4 digits, top 10 destinations and top 10 origins, each with its share.

Read 2026-11-16: https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37 -- "Licence: Etalab 2.0", "Last update:
January 30, 2026", "This is the 202601 version"; HS92 (1995-2024) ... HS22 (2022-2024). Etalab 2.0 lets anyone reuse,
redistribute and publish the data "for commercial or non-commercial purposes" provided there is "an acknowledgement of the
authorship of the 'Information': its source (at least, the name of the 'Grantor') and the date of the most recent update"
-> Source.title carries "CEPII, BACI (versão 202601, atualizada em 30/01/2026)".
We use HS22: same latest year (2024) as HS92, products already in the 2022 nomenclature that the pt-BR headings use, and a
301 MB zip instead of 2.4 GB. The zip (Readme: "Values in thousand USD") holds one CSV per year (t,i,j,k,v,q) and
country_codes_V202601.csv (country_code -> country_iso2). Codes without ISO2 ("Other Asia, nes" = 490, regional "nes" groups)
count in the totals but are never listed as partners; Namibia's ISO2 is blank in that file ("NA" read as missing), so we take
it from its ISO3 NAM.

Product names: MDIC/Secex auxiliary table NCM_SH.csv, column NO_SH4_POR (https://www.gov.br/mdic/pt-br/assuntos/comercio-
exterior/estatisticas/base-de-dados-bruta, read 2026-11-16: "Todo o conteúdo deste site está publicado sob a licença Creative
Commons Atribuição-SemDerivações 3.0 Não Adaptada"). ND: the headings are served VERBATIM (never shortened or reworded).
"""

import csv
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings

VERSION = "202601"
UPDATED = "30/01/2026"  # "Last update" on the CEPII page (Etalab: date of the most recent update)
ZIP_URL = f"https://www.cepii.fr/DATA_DOWNLOAD/baci/data/BACI_HS22_V{VERSION}.zip"
NCM_SH_URL = "https://balanca.mdic.gov.br/balanca/bd/tabelas/NCM_SH.csv"
TOP = 10
TECH = ("8542", "8471", "8802", "8803", "8541", "8517")  # spec 041, per flow
TECH_TOP = 5  # partners per tech product
SOURCES = [
    {"id": "baci", "title": f"CEPII, BACI (versão {VERSION}, atualizada em {UPDATED}); HS 2022, agregado por Atlas",
     "url": "https://www.cepii.fr/CEPII/en/bdd_modele/bdd_modele_item.asp?id=37", "license": "Etalab 2.0"},
    {"id": "mdic-sh", "title": "MDIC/Secex, tabela NCM_SH (nomes das posições do SH em português)",
     "url": "https://www.gov.br/mdic/pt-br/assuntos/comercio-exterior/estatisticas/base-de-dados-bruta",
     "license": "CC BY-ND 3.0"},
]
UA = {"User-Agent": "atlas-etl/0.1 (generic client)"}


def _download(url: str, f: Path) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    with httpx.stream("GET", url, headers=UA, timeout=600, follow_redirects=True) as r:
        r.raise_for_status()
        with tmp.open("wb") as out:
            for chunk in r.iter_bytes(1 << 20):
                out.write(chunk)
    tmp.replace(f)


def country_iso2(rows: list[dict[str, str]]) -> dict[str, str]:
    out = {}
    for r in rows:
        iso2 = r["country_iso2"] or ("NA" if r["country_iso3"] == "NAM" else "")
        if re.fullmatch(r"[A-Z]{2}", iso2):
            out[r["country_code"]] = iso2
    return out


def sh4_labels(rows: list[dict[str, str]]) -> dict[str, str]:
    return {r["CO_SH4"]: r["NO_SH4_POR"] for r in rows if r["CO_SH4"] and r["NO_SH4_POR"]}


def _top(d: dict[str, float], total: float) -> list[tuple[str, float, float]]:
    best = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]
    return [(k, round(v * 1000, 0), round(v / total, 4)) for k, v in best]


def _tech(tech: dict[tuple[str, str, str], dict[str, float]], c: str, e: float, m: float,
          labels: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    for hs in TECH:
        for flow, total in (("export", e), ("import", m)):
            parts = tech.get((c, flow, hs))
            if not parts:
                continue
            v = sum(parts.values())
            out.append({"hs": hs, "label": labels[hs], "flow": flow, "value_usd": round(v * 1000, 0),
                        "share": round(v / total, 4),  # of the country's exports (or imports)
                        "partners": [{"iso2": k, "value_usd": pv, "share": ps}  # share of this product flow
                                     for k, pv, ps in _top({k: x for k, x in parts.items() if k}, v)[:TECH_TOP]]})
    return out


def aggregate(lines: Any, iso: dict[str, str], labels: dict[str, str]) -> dict[str, dict[str, Any]]:
    """`lines`: csv rows t,i,j,k,v (header first), values in thousand USD -> per-ISO2 aggregates."""
    exp: dict[str, float] = defaultdict(float)
    imp: dict[str, float] = defaultdict(float)
    prod: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    dest: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    orig: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # spec 041: (country, flow, hs4) -> {partner: value}; partner "" = unmapped, so the sum is the product total
    tech: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    it = iter(lines)
    head = next(it)
    ci, cj, ck, cv = (head.index(c) for c in ("i", "j", "k", "v"))
    for row in it:
        v = float(row[cv])
        a, b = iso.get(row[ci]), iso.get(row[cj])
        hs4 = row[ck].zfill(6)[:4]
        if a:
            exp[a] += v
            prod[a][hs4] += v
            if hs4 in TECH:
                tech[a, "export", hs4][b if b and b != a else ""] += v
            if b and b != a:
                dest[a][b] += v
        if b:
            imp[b] += v
            if hs4 in TECH:
                tech[b, "import", hs4][a if a and a != b else ""] += v
            if a and a != b:
                orig[b][a] += v
    missing = {hs for p in prod.values() for hs in p} - labels.keys()
    if missing:
        raise SystemExit(f"HS4 codes without a pt-BR heading (we never invent one): {sorted(missing)}")
    out = {}
    for c in sorted(exp.keys() | imp.keys()):
        e, m = exp.get(c, 0.0), imp.get(c, 0.0)
        if e <= 0 or m <= 0:
            continue  # ponytail: a country needs both sides to be served (shares divide by them)
        out[c] = {
            "exports_usd": round(e * 1000, 0), "imports_usd": round(m * 1000, 0),
            "top_exports": [{"hs": k, "label": labels[k], "value_usd": v, "share": s} for k, v, s in _top(prod[c], e)],
            "top_destinations": [{"iso2": k, "value_usd": v, "share": s} for k, v, s in _top(dest[c], e)],
            "top_origins": [{"iso2": k, "value_usd": v, "share": s} for k, v, s in _top(orig[c], m)],
            "tech": _tech(tech, c, e, m, labels),
        }
    return out


def run() -> None:
    s = get_etl_settings()
    zf, ncm = s.cache_dir / "baci" / ZIP_URL.rsplit("/", 1)[-1], s.cache_dir / "mdic" / "NCM_SH.csv"
    refresh = "--refresh" in sys.argv
    for url, f in ((ZIP_URL, zf), (NCM_SH_URL, ncm)):
        if refresh or not f.exists():
            print(f"downloading {url}")
            _download(url, f)
    retrieved = datetime.fromtimestamp(zf.stat().st_mtime, UTC)
    with ncm.open(encoding="latin-1", newline="") as fh:  # the MDIC tables are ISO-8859-1
        labels = sh4_labels(list(csv.DictReader(fh, delimiter=";")))
    with zipfile.ZipFile(zf) as z:
        years = {int(m.group(1)): n for n in z.namelist() if (m := re.fullmatch(r"BACI_HS22_Y(\d{4})_V\d+\.csv", n))}
        year = max(years)
        with z.open(f"country_codes_V{VERSION}.csv") as fh:
            iso = country_iso2(list(csv.DictReader(io.TextIOWrapper(fh, "utf-8"))))
        print(f"aggregating {years[year]}")
        with z.open(years[year]) as fh:
            countries = aggregate(csv.reader(io.TextIOWrapper(fh, "utf-8", newline="")), iso, labels)
    payload = {"sources": SOURCES, "retrieved_at": retrieved.isoformat(), "year": year, "countries": countries}
    (s.out_dir / "trade.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/trade.json: {year}, {len(countries)} countries")
