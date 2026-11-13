"""ETL entry point: `python -m etl <command>`."""
import argparse
import sys
from collections.abc import Callable

from etl.fx import pipeline as fx
from etl.pantheon import pipeline as pantheon
from etl.restcountries import pipeline as restcountries
from etl.restcountries.client import RestCountriesError
from etl.undp import pipeline as undp
from etl.wikidata import languages as wikidata_languages
from etl.wikidata import leaders as wikidata_leaders
from etl.wikidata import pipeline as wikidata
from etl.wikidata import subdivisions as wikidata_subdivisions
from etl.wikipedia import history as wikipedia_history
from etl.worldbank import pipeline as worldbank

COMMANDS: dict[str, Callable[[], None]] = {
    "restcountries": restcountries.run, "wikidata": wikidata.run, "worldbank": worldbank.run,
    "wikidata-leaders": wikidata_leaders.run, "wikidata-subdivisions": wikidata_subdivisions.run, "pantheon": pantheon.run,
    "wikidata-languages": wikidata_languages.run, "undp": undp.run, "fx": fx.run,
    "wikipedia-history": wikipedia_history.run,
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="etl")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--refresh", action="store_true", help="refetch (wikidata ignores its cache)")
    parser.add_argument("only", nargs="*", help="ISO2 codes (wikidata-languages: sample run)")
    args = parser.parse_args()
    try:
        COMMANDS[args.command]()
    except RestCountriesError as e:
        sys.exit(str(e))
