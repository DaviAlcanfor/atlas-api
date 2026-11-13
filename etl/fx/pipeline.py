"""FX ETL (spec 009) -> data_out/fx.json: 1 EUR = rate units of each currency, per date.

Primary: ECB euro reference rates through Frankfurter (https://api.frankfurter.dev/v2, no key, "no
quotas ... rate-limited to prevent abuse"). Read 2026-11-12: Frankfurter's code is MIT; for the
data "Frankfurter doesn't own the rates ... If a provider publishes terms of use, they apply".
ECB terms (https://www.ecb.europa.eu/services/disclaimer/html/index.en.html): "users of this
website may make free use of the information obtained directly from it" provided "it must appear
accurately and the ECB must be cited as the source", and "If the information is modified by the
user (e.g. ... calculation of growth rates) ... this must be stated explicitly" -> the API's
cross rates and stats are labelled as our calculation in the Source title. ECB series start
1999-01-04 (Frankfurter /v2/providers/ecb: start_date). One request per year, cached in
etl_cache/fx/ecb_<year>.json; the current year is refetched on every run (incremental).

Secondary (currencies the ECB does not publish): fawazahmed0/exchange-api via jsDelivr
(https://github.com/fawazahmed0/exchange-api), licence "CC0-1.0", "No Rate limits", "Please
include Fallback mechanism" (we fall back to <date>.currency-api.pages.dev). Dated files exist
from 2024-03-02 only, one request per date, so we take ONE DATE PER WEEK (Wednesdays) plus the
latest: history for these currencies is weekly and starts in 2024-03. Marked source
"exchange-api" (secondary). Only ISO 4217 codes used by our countries are kept.
"""

import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings

FRANKFURTER = "https://api.frankfurter.dev/v2/rates"
ECB_START = 1999
SECONDARY_START = date(2024, 3, 6)  # first Wednesday with a dated exchange-api file
CDN = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{d}/v1/currencies/eur.min.json"
FALLBACK = "https://{d}.currency-api.pages.dev/v1/currencies/eur.min.json"
SOURCES = {
    "ecb": {"id": "ecb", "title": "European Central Bank: euro foreign exchange reference rates "
            "(via Frankfurter; cross rates and statistics calculated by Atlas)",
            "url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html",
            "license": "ECB: free reuse, source must be cited"},
    "exchange-api": {"id": "exchange-api", "title": "fawazahmed0/exchange-api (secondary source, "
                     "weekly; cross rates and statistics calculated by Atlas)",
                     "url": "https://github.com/fawazahmed0/exchange-api", "license": "CC0 1.0"},
}


def _get(client: httpx.Client, urls: list[str], params: dict[str, str] | None = None) -> Any:
    for attempt in range(1, 6):
        wait = 15 * attempt
        for url in urls:
            try:
                r = client.get(url, params=params)
            except httpx.TransportError:
                continue
            if r.status_code == 404:
                return None
            if r.status_code < 400:
                return r.json()
            if r.status_code == 429:
                wait = min(int(r.headers.get("Retry-After", "60")), 300)
        time.sleep(wait)
    raise RuntimeError(f"gave up: {urls[0]}")


def _cached(f: Path, fetch: Any, refresh: bool) -> Any:
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    data = fetch()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"retrieved_at": datetime.now(UTC).isoformat(), "data": data}), encoding="utf-8")
    time.sleep(0.5)
    return json.loads(f.read_text(encoding="utf-8"))


def ecb_rows(raw_years: list[Any]) -> list[list[Any]]:
    return [[r["date"], r["quote"], r["rate"], "ecb"] for y in raw_years for r in (y["data"] or [])
            if r.get("base") == "EUR" and len(r["quote"]) == 3]


def secondary_rows(raw_days: list[Any], wanted: set[str], ecb_codes: set[str]) -> list[list[Any]]:
    out = []
    for d in raw_days:
        data = d["data"]
        if not data:
            continue
        for code, rate in (data.get("eur") or {}).items():
            c = code.upper()
            if c in wanted and c not in ecb_codes and isinstance(rate, int | float) and rate > 0:
                out.append([data["date"], c, float(rate), "exchange-api"])
    return out


def wednesdays(start: date, end: date) -> list[date]:
    return [start + timedelta(weeks=i) for i in range((end - start).days // 7 + 1)]


def run() -> None:
    s = get_etl_settings()
    wd = s.out_dir / "wikidata.json"
    if wd.exists():
        countries = json.loads(wd.read_text(encoding="utf-8"))["countries"]
        wanted = {c["code"] for x in countries.values() for c in x["currencies"] if c.get("code")}
    else:  # CI (daily job): codes from the database, written by `atlas_api.cli currency-codes` (FX_CODES_FILE)
        codes = Path(os.environ.get("FX_CODES_FILE", "fx_codes.txt"))
        if not codes.exists():
            sys.exit(f"no {wd} and no {codes}: run `python -m atlas_api.cli currency-codes > {codes}` first")
        wanted = {c.strip() for c in codes.read_text(encoding="utf-8").split() if c.strip()}
    refresh, cache, today = "--refresh" in sys.argv, s.cache_dir / "fx", datetime.now(UTC).date()
    with httpx.Client(headers={"User-Agent": "atlas-etl/0.1 (generic client)"}, timeout=120) as client:
        years = [_cached(cache / f"ecb_{y}.json", lambda y=y: _get(client, [FRANKFURTER], {
            "from": f"{y}-01-01", "to": f"{y}-12-31", "base": "EUR", "providers": "ecb"}),
            refresh or y == today.year) for y in range(ECB_START, today.year + 1)]
        ecb = ecb_rows(years)
        last_ecb = max(r[0] for r in ecb)
        ecb_codes = {r[1] for r in ecb if r[0] == last_ecb}  # currencies the ECB still publishes
        days = [d.isoformat() for d in wednesdays(SECONDARY_START, today)] + ["latest"]
        raw = [_cached(cache / f"xapi_{d}.json", lambda d=d: _get(
            client, [CDN.format(d=d), FALLBACK.format(d=d)]), refresh or d == "latest") for d in days]
    sec = secondary_rows(raw, wanted, ecb_codes)
    rows = sorted({(r[0], r[1]): r for r in ecb + sec}.values())
    s.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"sources": list(SOURCES.values()), "retrieved_at": datetime.now(UTC).isoformat(),
               "columns": ["date", "code", "rate", "source_id"], "rows": rows}
    (s.out_dir / "fx.json").write_text(json.dumps(payload), encoding="utf-8")
    have = {r[1] for r in rows}
    print(f"wrote data_out/fx.json: {len(rows)} rows, {len(have)} currencies "
          f"(ECB {len({r[1] for r in ecb})}, secondary {len({r[1] for r in sec})})")
    print(f"  country currencies without any rate: {sorted(wanted - have)}")
