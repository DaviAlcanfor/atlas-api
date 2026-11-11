"""World Bank Indicators ETL (CC BY 4.0) -> data_out/worldbank.json.

Docs read 2026-11-11: base https://api.worldbank.org/v2, `format=json`, no key, `page`/`per_page`
(default 50; no maximum documented, so we page by the `pages` field), `mrnev=N` = most recent
non-empty values. Found by testing: `country.id` is ISO2, and `country/all` ALSO returns ~79
aggregates (World, income groups...), so we keep only the ISO2 codes that Wikidata gave us.
Licence: CC BY 4.0, attribution "The World Bank: <dataset name>: <data source>". No rate limit is
documented ("reasonable request volume"): 3 indicators x 1 request each, polite pause.

Long format on purpose: one row per (iso2, indicator, year). Adding an indicator = one entry in
INDICATORS, no schema change.
"""

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings

BASE = "https://api.worldbank.org/v2"
# label/unit are pt-BR display strings written by us (not from the API).
INDICATORS = {
    "SP.POP.TOTL": {"label": "População total", "unit": "pessoas"},
    "NY.GDP.PCAP.CD": {"label": "PIB per capita (US$ correntes)", "unit": "US$"},
    "SP.DYN.LE00.IN": {"label": "Expectativa de vida ao nascer", "unit": "anos"},
}
SOURCE = {
    "id": "worldbank", "title": "World Bank: World Development Indicators",
    "url": "https://data.worldbank.org/", "license": "CC BY 4.0",
}


def _get(client: httpx.Client, path: str, params: dict[str, Any], cache: Path, name: str,
         refresh: bool) -> dict[str, Any]:
    f = cache / f"{name}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    rows: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    page = 1
    while True:
        r = client.get(f"{BASE}/{path}", params={**params, "format": "json", "page": page, "per_page": 500})
        r.raise_for_status()
        meta, data = r.json()[:2]
        rows += data
        if page >= int(meta["pages"]):
            break
        page += 1
        time.sleep(1)
    wrapped = {"retrieved_at": datetime.now(UTC).isoformat(), "lastupdated": meta.get("lastupdated"),
               "rows": rows}
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(wrapped, ensure_ascii=False), encoding="utf-8")
    time.sleep(1)
    return wrapped


def build(raw: dict[str, dict[str, Any]], iso2s: set[str]) -> list[dict[str, Any]]:
    """Flat rows for the given countries only; null values are skipped (missing = no row)."""
    out = []
    for ind, wrapped in raw.items():
        for r in wrapped["rows"]:
            iso, value, year = r["country"]["id"], r["value"], r["date"]
            if iso in iso2s and value is not None and str(year).isdigit():
                out.append({"iso2": iso, "indicator_id": ind, "year": int(year), "value": value,
                            "unit": INDICATORS[ind]["unit"], "label": INDICATORS[ind]["label"]})
    return sorted(out, key=lambda x: (x["iso2"], x["indicator_id"], x["year"]))


def run() -> None:
    s = get_etl_settings()
    wiki = s.out_dir / "wikidata.json"
    if not wiki.exists():
        raise SystemExit("Run `python -m etl wikidata` first (it provides the list of ISO2 codes).")
    iso2s = set(json.loads(wiki.read_text(encoding="utf-8"))["countries"])
    ua = f"atlas-api/0.1 ({s.wikidata_contact or 'no-contact'}) python-httpx/{httpx.__version__}"
    cache = s.cache_dir / "worldbank"
    refresh = "--refresh" in sys.argv
    with httpx.Client(headers={"User-Agent": ua}, timeout=60) as client:
        raw = {i: _get(client, f"country/all/indicator/{i}", {"mrnev": 1}, cache, i, refresh)
               for i in INDICATORS}
        meta = {i: client.get(f"{BASE}/indicator/{i}", params={"format": "json"}).json()[1][0]
                for i in INDICATORS}
    rows = build(raw, iso2s)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": SOURCE,
        "retrieved_at": {k: v["retrieved_at"] for k, v in raw.items()},
        "indicators": {i: {**INDICATORS[i], "name_en": m["name"],
                           "source_organization": m["sourceOrganization"].strip()}
                       for i, m in meta.items()},
        "rows": rows,
    }
    (s.out_dir / "worldbank.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/worldbank.json: {len(rows)} rows")
    for i in INDICATORS:
        have = {r["iso2"] for r in rows if r["indicator_id"] == i}
        print(f"  {i}: {len(have)}/{len(iso2s)} countries; missing: {sorted(iso2s - have)}")
