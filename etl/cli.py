"""ETL entry point: `python -m etl <command>`."""
import argparse
import sys
from collections.abc import Callable

from etl.restcountries import pipeline as restcountries
from etl.restcountries.client import RestCountriesError

COMMANDS: dict[str, Callable[[], None]] = {"restcountries": restcountries.run}


def main() -> None:
    parser = argparse.ArgumentParser(prog="etl")
    parser.add_argument("command", choices=COMMANDS)
    args = parser.parse_args()
    try:
        COMMANDS[args.command]()
    except RestCountriesError as e:
        sys.exit(str(e))
