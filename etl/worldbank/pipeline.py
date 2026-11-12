"""World Bank Indicators ETL (CC BY 4.0) -> data_out/worldbank.json.

Docs read 2026-11-11: classic API https://api.worldbank.org/v2, no key. v1.2 (2026-11-12): that host
answered 502 or timed out for most requests all day (JSON and bulk CSV alike), so the ETL now reads
the SAME dataset (WDI, DATABASE_ID=WB_WDI) from the World Bank Data360 API
(https://data360api.worldbank.org/data360/data, documented at https://data360.worldbank.org/en/api):
no key, pages of 1000 observations via `skip`, indicator id = "WB_WDI_" + WDI code with "_" for ".",
REF_AREA = ISO3. Each of our 23 indicators has a single breakdown combination (checked), so no
filter on SEX/AGE/URBANISATION is needed.
ISO3 -> ISO2 comes from Wikidata P298 (wikidata.json) plus WB_ONLY_ISO3 (Kosovo: the World Bank
uses XKX, which is not an ISO code). Cache: etl_cache/worldbank/<id>.data360.json.
Licence: CC BY 4.0 (https://datacatalog.worldbank.org/public-licenses#cc-by), attribution "The
World Bank: <dataset name>: <data source>". No rate limit is documented ("reasonable request
volume"): ~15 pages per indicator, one at a time, 0.5 s apart, retried on 5xx/timeouts.

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

DATA360 = "https://data360api.worldbank.org/data360/data"
WB_ONLY_ISO3 = {"XKX": "XK"}
# label/unit are pt-BR display strings written by us (not from the API). v1.2 (specs 009, 015):
# series since FIRST_YEAR for every indicator; the API decides which ids each endpoint shows.
FIRST_YEAR = 1990
INDICATORS = {
    "SP.POP.TOTL": {"label": "População total", "unit": "pessoas"},
    "NY.GDP.PCAP.CD": {"label": "PIB per capita (US$ correntes)", "unit": "US$"},
    "SP.DYN.LE00.IN": {"label": "Expectativa de vida ao nascer", "unit": "anos"},
    "SP.DYN.IMRT.IN": {"label": "Mortalidade infantil", "unit": "por 1.000 nascidos vivos"},
    "SP.DYN.TFRT.IN": {"label": "Fecundidade", "unit": "filhos por mulher"},
    "SP.URB.TOTL.IN.ZS": {"label": "População urbana", "unit": "% da população"},
    "SE.ADT.LITR.ZS": {"label": "Alfabetização de adultos", "unit": "% (15 anos ou mais)"},
    "IT.NET.USER.ZS": {"label": "Usuários de internet", "unit": "% da população"},
    "VC.IHR.PSRC.P5": {"label": "Homicídios", "unit": "por 100 mil habitantes"},
    "NY.GDP.PCAP.PP.CD": {"label": "PIB per capita (PPC)", "unit": "US$ internacionais correntes"},
    "SI.POV.GINI": {"label": "Índice de Gini", "unit": "0-100"},
    "SI.POV.DDAY": {"label": "Pobreza extrema (US$ 3,00/dia, PPC 2021)", "unit": "% da população"},
    "SL.UEM.TOTL.ZS": {"label": "Desemprego", "unit": "% da força de trabalho (OIT)"},
    "EN.GHG.CO2.PC.CE.AR5": {"label": "Emissões de CO2 per capita", "unit": "t CO2e por pessoa"},
    "EG.FEC.RNEW.ZS": {"label": "Energia renovável", "unit": "% do consumo final"},
    "AG.LND.FRST.ZS": {"label": "Área de floresta", "unit": "% do território"},
    "NY.GDP.MKTP.CD": {"label": "PIB", "unit": "US$ correntes"},
    "NY.GDP.MKTP.KD.ZG": {"label": "Crescimento do PIB", "unit": "% ao ano"},
    "FP.CPI.TOTL.ZG": {"label": "Inflação (preços ao consumidor)", "unit": "% ao ano"},
    "GC.DOD.TOTL.GD.ZS": {"label": "Dívida do governo central", "unit": "% do PIB"},
    "BN.CAB.XOKA.GD.ZS": {"label": "Saldo em conta corrente", "unit": "% do PIB"},
    "FI.RES.TOTL.CD": {"label": "Reservas totais (com ouro)", "unit": "US$ correntes"},
    "PA.NUS.PPP": {"label": "Fator de conversão PPC", "unit": "moeda local por US$ internacional"},
}
SOURCE = {
    "id": "worldbank", "title": "World Bank: World Development Indicators",
    "url": "https://data.worldbank.org/", "license": "CC BY 4.0",
}


def _download(client: httpx.Client, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    for attempt in range(1, 4):  # 502s and timeouts happen: back off and retry
        try:
            r = client.get(url, params=params)
        except httpx.TransportError:
            if attempt == 3:
                raise
        else:
            if r.status_code < 500 or attempt == 3:
                r.raise_for_status()
                return r
        time.sleep(15 * attempt)
    raise RuntimeError(f"gave up: {url}")


def _fetch(client: httpx.Client, ind: str, cache: Path, refresh: bool) -> dict[str, Any]:
    """Every observation of one WDI indicator since FIRST_YEAR (pages of 1000), cached."""
    f = cache / f"{ind}.data360.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    rows: list[dict[str, Any]] = []
    while True:
        page = _download(client, DATA360, {"DATABASE_ID": "WB_WDI", "INDICATOR": "WB_WDI_" + ind.replace(".", "_"),
                                           "timePeriodFrom": str(FIRST_YEAR), "skip": str(len(rows))}).json()
        rows += page["value"]
        if not page["value"] or len(rows) >= page["count"]:
            break
        time.sleep(0.5)
    wrapped = {"retrieved_at": datetime.now(UTC).isoformat(), "rows": rows}
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(wrapped), encoding="utf-8")
    return wrapped


def build(raw: dict[str, list[dict[str, Any]]], iso3_to_iso2: dict[str, str]) -> list[dict[str, Any]]:
    """Flat rows since FIRST_YEAR for our countries only; empty values are skipped (missing = no row)."""
    out = {}
    for ind, rows in raw.items():
        for r in rows:
            iso, year, v = iso3_to_iso2.get(r.get("REF_AREA") or ""), str(r.get("TIME_PERIOD")), r.get("OBS_VALUE")
            if iso and year.isdigit() and int(year) >= FIRST_YEAR and v not in ("", None):
                out[(iso, ind, int(year))] = float(v)  # aggregates (WLD...) have no ISO2 of ours
    return [{"iso2": k[0], "indicator_id": k[1], "year": k[2], "value": v} for k, v in sorted(out.items())]


def run() -> None:
    s = get_etl_settings()
    wiki = s.out_dir / "wikidata.json"
    if not wiki.exists():
        raise SystemExit("Run `python -m etl wikidata` first (it provides ISO2 + ISO3 codes).")
    countries = json.loads(wiki.read_text(encoding="utf-8"))["countries"]
    iso3 = {c["iso3"]: iso2 for iso2, c in countries.items() if c.get("iso3")} | {
        k: v for k, v in WB_ONLY_ISO3.items() if v in countries}
    ua = f"atlas-etl/0.1 (generic client) python-httpx/{httpx.__version__}"
    cache = s.cache_dir / "worldbank"
    refresh = "--refresh" in sys.argv
    raw, failed = {}, []
    with httpx.Client(headers={"User-Agent": ua}, timeout=60) as client:
        for i in INDICATORS:  # try them all: one failure must not block the others
            try:
                raw[i] = _fetch(client, i, cache, refresh)
            except httpx.HTTPError as e:
                failed.append(f"{i} ({type(e).__name__})")
    if failed:
        sys.exit(f"World Bank download failed for {failed}; finished indicators are cached, run again.")
    rows = build({i: w["rows"] for i, w in raw.items()}, iso3)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": SOURCE,
        "retrieved_at": {i: w["retrieved_at"] for i, w in raw.items()},
        "indicators": INDICATORS,
        "rows": rows,
        "iso3": iso3,  # ISO3 -> ISO2 for our countries (the UNDP ETL joins on ISO3)
    }
    (s.out_dir / "worldbank.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/worldbank.json: {len(rows)} rows")
    for i in INDICATORS:
        have = {r["iso2"] for r in rows if r["indicator_id"] == i}
        print(f"  {i}: {len(have)}/{len(countries)} countries; missing: {sorted(set(countries) - have)}")
