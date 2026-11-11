"""`python -m atlas_api.cli import-content [--content content]`"""

import argparse
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from atlas_api.config import get_settings
from atlas_api.db.session import make_engine
from atlas_api.facts import import_facts
from atlas_api.importer import ContentError, import_content


def main() -> int:
    ap = argparse.ArgumentParser(prog="atlas_api.cli")
    ap.add_argument("command", choices=["import-content", "import-facts"])
    ap.add_argument("--content", default="content", type=Path)
    ap.add_argument("--data-out", default="data_out", type=Path)
    args = ap.parse_args()
    engine = make_engine(get_settings().database_url)
    try:
        with Session(engine) as session, session.begin():  # one transaction
            if args.command == "import-facts":
                summary = import_facts(session, args.data_out / "wikidata.json")
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
