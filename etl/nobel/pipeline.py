"""spec 033: Nobel Prize laureates per country, from the Nobel Prize API v2.1 (api.nobelprize.org).

Terms read 2026-11-17 (https://www.nobelprize.org/about/terms-of-use-for-api-nobelprize-org-and-data-nobelprize-org/):
"The Services are free to use according to the Creative Commons Zero (CC0) license." ... "Applications that use the Services
should not deliberately alter or censor the data" ... "Consider using a local cache instead of performing many API calls."
... "you are encouraged to cite the Services as the data source". Trademarks: no Nobel name/logo in our titles or logos.

Countries are the API's `countryNow` (today's borders), matched to our polities by Wikidata Q-id (its `sameAs`), so
"born in Prussia" counts for the country that holds that city now. Organizations (e.g. the Red Cross) count by where they
were founded. Motivation stays in English, the official text of the API (never translated). One API call per 1000 laureates.
"""
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from etl.settings import get_etl_settings

API = "https://api.nobelprize.org/2.1/laureates"
CATEGORIES = {"Physics": "physics", "Chemistry": "chemistry", "Physiology or Medicine": "medicine",
              "Literature": "literature", "Peace": "peace", "Economic Sciences": "economics"}
# The API's countryNow for these is a constituent part; our polity is the sovereign state. Territories with their own ISO code
# (Faroe Islands, Guadeloupe) stay null: they are not polities here.
ALIASES = {"Q55": "NL", "Q26": "GB"}  # the Netherlands (of the Kingdom), Northern Ireland (UK)
SOURCE = {"id": "nobelprize", "title": "Nobel Prize API v2.1 (Nobel Prize Outreach)", "url": "https://www.nobelprize.org/",
          "license": "CC0 1.0"}


def _qid(place: dict[str, Any] | None) -> str | None:
    """Q-id of a place's countryNow (sameAs is a list or a string in the API)."""
    same = ((place or {}).get("countryNow") or {}).get("sameAs") or []
    for url in [same] if isinstance(same, str) else same:
        if m := re.search(r"/(Q\d+)$", url):
            return m.group(1)
    return None


def qid_to_iso2(polities_dir: Path) -> dict[str, str]:
    out: dict[str, str] = dict(ALIASES)
    for p in polities_dir.glob("*.yaml"):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        if d.get("iso2") and d.get("wikidata_qid"):
            out[d["wikidata_qid"]] = d["iso2"]
    return out


def build(laureates: list[dict[str, Any]], iso: dict[str, str]) -> list[dict[str, Any]]:
    """One row per (laureate, prize). Unknown country = null; never guessed."""
    rows = []
    for x in laureates:
        person = "orgName" not in x
        origin = (x.get("birth") if person else x.get("founded")) or {}
        name = (x.get("knownName") or x.get("orgName") or {}).get("en")
        for p in x.get("nobelPrizes") or []:
            cat = CATEGORIES.get((p.get("category") or {}).get("en", ""))
            if not name or not cat:
                continue
            affs = []
            for a in p.get("affiliations") or []:
                affs.append({"name": (a.get("name") or {}).get("en"), "city": (a.get("cityNow") or {}).get("en"),
                             "iso2": iso.get(_qid(a) or "")})
            rows.append({
                "laureate_id": x["id"], "name": name, "kind": "person" if person else "organization",
                "year": int(p["awardYear"]), "category": cat,
                "motivation": (p.get("motivation") or {}).get("en"), "portion": p.get("portion"),
                "origin_iso2": iso.get(_qid(origin.get("place")) or ""),
                "affiliations": [a for a in affs if a["name"]],
                "wikipedia_url": (x.get("wikipedia") or {}).get("english"),
                "url": f"https://www.nobelprize.org/laureate/{x['id']}"})
    return sorted(rows, key=lambda r: (r["year"], r["category"], r["laureate_id"]))


def run() -> None:
    s = get_etl_settings()
    laureates: list[dict[str, Any]] = []
    with httpx.Client(headers={"User-Agent": "atlas-api/0.1 (etl nobel)"}, timeout=120) as client:
        while True:
            r = client.get(API, params={"offset": len(laureates), "limit": 1000})
            r.raise_for_status()
            page = r.json()
            laureates += page["laureates"]
            if len(laureates) >= page["meta"]["count"] or not page["laureates"]:
                break
    rows = build(laureates, qid_to_iso2(Path("content/polities")))
    now = datetime.now(UTC).isoformat(timespec="seconds")
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "nobel.json").write_text(json.dumps({"source": {**SOURCE, "retrieved_at": now}, "items": rows},
                                                     ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(rows)
    print(f"wrote data_out/nobel.json: {len(laureates)} laureates, {n} prizes")
    print(f"  origin country matched: {sum(r['origin_iso2'] is not None for r in rows)}/{n}")
    affs = [a for r in rows for a in r["affiliations"]]
    print(f"  affiliations with a country: {sum(a['iso2'] is not None for a in affs)}/{len(affs)}")
    print(f"  countries: {len({r['origin_iso2'] for r in rows} | {a['iso2'] for a in affs} - {None})}")
