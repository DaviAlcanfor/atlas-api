"""`python -m atlas_api.cli import-content | import-facts | import-fx | import-news | import-trade | import-subdivisions | currency-codes`

import-subdivisions: only the subdivisions table and its source rows, from data_out/subdivisions.json (+ shdi.json, heads.json;
spec 024 phase 2). import-facts does the same as part of everything else.

import-live-events: only data_out/live_events.json (the 30-min job, spec 034), only live_events; no data_version bump.
import-nobel: only data_out/nobel.json (etl nobel, spec 033), only nobel_prizes and its source row.

import-trade: only data_out/trade.json (etl baci, spec 029), only country_trade, country_tech_trade and their source rows.

import-news: only data_out/news.json (the 6-hourly job, spec 008), only the news tables.

import-fx: only data_out/fx.json (the daily job, spec 009); currency-codes: prints the ISO 4217 codes of the imported countries,
one per line (the FX ETL needs them and CI has no data_out/wikidata.json)."""

import argparse
import hashlib
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api import chat_logs
from atlas_api.core.config import get_settings
from atlas_api.db.models import CountryFacts, Polity
from atlas_api.db.session import make_engine
from atlas_api.importer.content import ContentError, import_content, set_version
from atlas_api.importer.facts import (
    import_facts,
    import_fx,
    import_live_events,
    import_news,
    import_nobel,
    import_subdivisions,
    import_trade,
)


def main() -> int:
    ap = argparse.ArgumentParser(prog="atlas_api.cli")
    ap.add_argument("command", choices=["import-content", "import-facts", "import-fx", "import-news", "import-trade", "import-live-events", "import-nobel", "import-subdivisions", "currency-codes", "chat-logs"])
    ap.add_argument("--content", default="content", type=Path)
    ap.add_argument("--data-out", default="data_out", type=Path)
    ap.add_argument("--since", default="1d", help="chat-logs: window, e.g. 1d or 6h")
    args = ap.parse_args()
    engine = make_engine(get_settings().database_url)
    if args.command == "currency-codes":
        with Session(engine) as session:
            codes = {code for cs in session.scalars(select(CountryFacts.currencies)) for c in cs or []
                     if (code := c.get("code")) and re.fullmatch(r"[A-Z]{3}", code)}  # ISO 4217 only (Wikidata has stray values)
        print("\n".join(sorted(codes)))
        return 0
    if args.command == "chat-logs":
        with Session(engine) as session:
            res = chat_logs.summary(session, chat_logs.parse_since(args.since))
        print(f"tool calls in the last {args.since}: {res['calls']} ({res['errors']} with error)")
        for label, rows in (("per tool", res["per_tool"]), ("top countries", res["top_countries"])):
            print(f"{label}:")
            print(*[f"  {k}: {n}" for k, n in rows] or ["  (none)"], sep="\n")
        return 0
    try:
        with Session(engine) as session, session.begin():  # one transaction
            if args.command == "import-facts":
                summary = import_facts(session, args.data_out / "wikidata.json")
            elif args.command == "import-fx":
                fx = args.data_out / "fx.json"
                summary = {"fx_rates_imported": import_fx(session, fx),
                           "data_version": set_version(session, "fx", hashlib.sha256(fx.read_bytes()).hexdigest()[:16])}
            elif args.command == "import-news":
                news = args.data_out / "news.json"
                summary = {**import_news(session, news),
                           "data_version": set_version(session, "news", hashlib.sha256(news.read_bytes()).hexdigest()[:16])}
            elif args.command == "import-trade":
                trade = args.data_out / "trade.json"
                summary = {"countries_with_trade": import_trade(session, trade),
                           "data_version": set_version(session, "trade", hashlib.sha256(trade.read_bytes()).hexdigest()[:16])}
            elif args.command == "import-live-events":
                summary = import_live_events(session, args.data_out / "live_events.json")
            elif args.command == "import-nobel":
                nobel = args.data_out / "nobel.json"
                summary = {"nobel_prizes_imported": import_nobel(session, nobel),
                           "data_version": set_version(session, "nobel", hashlib.sha256(nobel.read_bytes()).hexdigest()[:16])}
            elif args.command == "import-subdivisions":
                files = [args.data_out / n for n in ("subdivisions.json", "shdi.json", "heads.json")]
                known = set(session.scalars(select(Polity.iso2).where(Polity.iso2.is_not(None))))
                summary = {"subdivisions_imported": import_subdivisions(session, files[0], known),
                           "data_version": set_version(session, "subdivisions", hashlib.sha256(
                               b"".join(f.read_bytes() for f in files if f.exists())).hexdigest()[:16])}
            else:
                summary = import_content(session, args.content)
    except ContentError as e:
        print("Import aborted, nothing written:\n  " + "\n  ".join(e.problems), file=sys.stderr)
        return 1
    for k, v in summary.items():
        print(f"{k}: {v}")
    if summary.get("unverified_events"):
        print(f"WARNING: {summary['unverified_events']} events have no sources (unverified).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
