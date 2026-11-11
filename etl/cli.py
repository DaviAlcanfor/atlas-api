"""ETL entry point: `python -m etl <command>`."""
import argparse
import sys
from collections.abc import Callable

from etl.restcountries import pipeline as restcountries
from etl.restcountries.client import RestCountriesError
from etl.wikidata import pipeline as wikidata
from etl.worldbank import pipeline as worldbank

COMMANDS: dict[str, Callable[[], None]] = {"restcountries": restcountries.run, "wikidata": wikidata.run, "worldbank": worldbank.run}


def main() -> None:
    parser = argparse.ArgumentParser(prog="etl")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--refresh", action="store_true", help="refetch (wikidata ignores its cache)")
    args = parser.parse_args()
    try:
        COMMANDS[args.command]()
    except RestCountriesError as e:
        sys.exit(str(e))
