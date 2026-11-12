"""UNDP Human Development Report ETL (spec 015) -> data_out/undp.json.

Read 2026-11-12: https://hdr.undp.org/data-center/documentation-and-downloads offers one CSV,
"All composite indices and components time series (1990-2023)". Terms (https://hdr.undp.org/terms-use):
"All materials provided on this website are copyrighted under the Creative Commons Attribution
3.0 IGO license" ... "Share ... Adapt ... for any purpose, even commercially" ... "You must give
appropriate credit, provide a link to the license, and indicate where changes were made."
Changes we make: none to the values; we only select hdi_* and mys_* columns and compute ranks.
Rows are keyed by ISO3; we map to ISO2 with the World Bank ETL output (run it first).
Same long format as worldbank.json.
"""

import csv
import io
import json
import sys
from datetime import UTC, datetime

import httpx

from etl.settings import get_etl_settings

CSV_URL = ("https://hdr.undp.org/sites/default/files/2025_HDR/"
           "HDR25_Composite_indices_complete_time_series.csv")
INDICATORS = {
    "HDR.HDI": {"column": "hdi", "label": "Índice de Desenvolvimento Humano (IDH)", "unit": "0-1"},
    "HDR.MYS": {"column": "mys", "label": "Anos médios de estudo", "unit": "anos (25 anos ou mais)"},
}
SOURCE = {"id": "undp-hdr", "title": "UNDP Human Development Report 2025: composite indices time series",
          "url": "https://hdr.undp.org/data-center/documentation-and-downloads",
          "license": "CC BY 3.0 IGO"}


def build(text: str, iso3_to_iso2: dict[str, str]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for r in csv.DictReader(io.StringIO(text)):
        iso2 = iso3_to_iso2.get(r["iso3"])
        if not iso2:
            continue  # aggregates (ZZA...) and places we do not list
        for ind, meta in INDICATORS.items():
            prefix = meta["column"] + "_"
            for col, v in r.items():
                year = col.removeprefix(prefix)
                if col.startswith(prefix) and year.isdigit() and v not in ("", None):
                    out.append({"iso2": iso2, "indicator_id": ind, "year": int(year), "value": float(v)})
    return sorted(out, key=lambda x: (str(x["iso2"]), str(x["indicator_id"]), int(str(x["year"]))))


def run() -> None:
    s = get_etl_settings()
    wb = s.out_dir / "worldbank.json"
    if not wb.exists():
        raise SystemExit("Run `python -m etl worldbank` first (it provides ISO3 -> ISO2).")
    iso3 = json.loads(wb.read_text(encoding="utf-8"))["iso3"]
    f = s.cache_dir / "undp" / CSV_URL.rsplit("/", 1)[-1]
    retrieved = datetime.fromtimestamp(f.stat().st_mtime, UTC) if f.exists() else None
    if retrieved is None or "--refresh" in sys.argv:
        r = httpx.get(CSV_URL, headers={"User-Agent": "atlas-etl/0.1 (generic client)"}, timeout=120)
        r.raise_for_status()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
        retrieved = datetime.now(UTC)
    rows = build(f.read_text(encoding="latin-1"), iso3)  # the CSV is not UTF-8 (Côte d'Ivoire)
    payload = {"source": SOURCE, "retrieved_at": retrieved.isoformat(),
               "indicators": {k: {"label": v["label"], "unit": v["unit"]} for k, v in INDICATORS.items()},
               "rows": rows}
    (s.out_dir / "undp.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/undp.json: {len(rows)} rows")
    for i in INDICATORS:
        have = {r["iso2"] for r in rows if r["indicator_id"] == i}
        print(f"  {i}: {len(have)}/{len(set(iso3.values()))} countries; missing: {sorted(set(iso3.values()) - have)}")
