"""`python -m atlas_api.cli import-content | import-facts | import-fx | currency-codes`

import-fx: only data_out/fx.json (the daily job, spec 009); currency-codes: prints the ISO 4217 codes of the imported countries,
one per line (the FX ETL needs them and CI has no data_out/wikidata.json)."""

import argparse
import hashlib
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.config import get_settings
from atlas_api.db.models import CountryFacts
from atlas_api.db.session import make_engine
from atlas_api.facts import import_facts, import_fx
from atlas_api.importer import ContentError, import_content, set_version


def main() -> int:
    ap = argparse.ArgumentParser(prog="atlas_api.cli")
    ap.add_argument("command", choices=["import-content", "import-facts", "import-fx", "currency-codes"])
    ap.add_argument("--content", default="content", type=Path)
    ap.add_argument("--data-out", default="data_out", type=Path)
    args = ap.parse_args()
    engine = make_engine(get_settings().database_url)
    if args.command == "currency-codes":
        with Session(engine) as session:
            codes = {code for cs in session.scalars(select(CountryFacts.currencies)) for c in cs or []
                     if (code := c.get("code")) and re.fullmatch(r"[A-Z]{3}", code)}  # ISO 4217 only (Wikidata has stray values)
        print("\n".join(sorted(codes)))
        return 0
    try:
        with Session(engine) as session, session.begin():  # one transaction
            if args.command == "import-facts":
                summary = import_facts(session, args.data_out / "wikidata.json")
            elif args.command == "import-fx":
                fx = args.data_out / "fx.json"
                summary = {"fx_rates_imported": import_fx(session, fx),
                           "data_version": set_version(session, "fx", hashlib.sha256(fx.read_bytes()).hexdigest()[:16])}
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
