"""fetch -> transform -> write data_out/facts.json."""
import json
from datetime import UTC, datetime

from etl.restcountries.client import RestCountriesClient
from etl.restcountries.transform import to_facts
from etl.settings import get_etl_settings


def run() -> None:
    settings = get_etl_settings()
    client = RestCountriesClient(settings)
    fetched_at = datetime.now(UTC).isoformat()
    try:
        facts = [f for raw in client.countries() if (f := to_facts(raw, fetched_at))]
    finally:
        client.close()
    facts.sort(key=lambda f: f.iso2)
    out = settings.out_dir / "facts.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([f.model_dump(mode="json") for f in facts], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(facts)} countries -> {out}")
