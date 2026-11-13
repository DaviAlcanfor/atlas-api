"""History events ETL (spec 016 stage 2): notable dated events of each country -> data_out/events.json.

Wikidata (CC0), same endpoint/politeness/cache as pipeline.py: raw answers cached in etl_cache/wikidata/events/.
An event belongs to a country when P17 (country), P710 (participant) or P1001 (applies to jurisdiction) is the country OR one of
its direct predecessor states (P1366 "replaced by" = the country: the Paraguayan War is linked to the Empire of Brazil).
Types (P31, direct, Q-ids checked against Wikidata on 2026-11-13 with wbgetentities/wbsearchentities, not typed from memory):
  war Q198 · civil war Q8465 · war of national liberation Q1006311 · battle Q178561            -> kind "war"
  revolution Q10931 · coup d'état Q45382 · military coup Q3449092 · declaration of independence Q1464916 · constitution Q7755 ·
  general election Q1076105 · political crisis Q3002772 · annexation Q194465                   -> kind "political"
  treaty Q131569                                                                               -> kind "treaty"
  genocide Q41397                                                                              -> kind "other"
Notability: >= MIN_SITELINKS Wikipedia editions; the MAX_PER_COUNTRY most linked are kept, then sorted by date.
Queries: per event type worldwide (item, linked state, sitelinks), per country its predecessors, then details of the chosen items:
see the comment above TYPE_QUERY.
Dates: P585 (point in time), else P580 start / P582 end. WDQS writes xsd:dateTime with astronomical years (0000 = 1 BCE), so
years <= 0 are shifted by one to the no-year-0 convention (-1 = 1 BCE). Undated events are dropped.
Title = pt label (may fall back to English through the label service), summary = pt description only; link = pt.wikipedia, else en.
These events are NOT reviewed by a human (`reviewed: false`); the web labels them as automatic.
"""

import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached
from etl.wikidata.pipeline import LABEL, _is_label, _qid, _v

MIN_SITELINKS = 10
MAX_PER_COUNTRY = 40
KIND = {"Q198": "war", "Q8465": "war", "Q1006311": "war", "Q178561": "war",
        "Q10931": "political", "Q45382": "political", "Q3449092": "political", "Q1464916": "political", "Q7755": "political",
        "Q1076105": "political", "Q3002772": "political", "Q194465": "political",
        "Q131569": "treaty", "Q41397": "other"}
# Three steps (every country-first join timed out on WDQS: "items linked to Brazil" means scanning ~10^5 places):
# 1. per event type, worldwide: notable items and the states they are linked to (14 small queries, cached once)
TYPE_QUERY = """SELECT ?e ?c ?sl WHERE {{ ?e wdt:P31 wd:{t}; wikibase:sitelinks ?sl. FILTER(?sl >= {min_sl})
 ?e wdt:P17|wdt:P710|wdt:P1001 ?c. }}"""
# 2. per country: its DIRECT predecessor states (P1366 "replaced by" = the country). One hop only, checked 2026-11-13: BR -> Empire of
#    Brazil, United States of Brazil; FR -> Kingdom of France; DE -> German Reich, Prussia, both Germanies. Two hops already pull in
#    the Almohad Caliphate for Portugal and Austria for Germany.
PRED_QUERY = "SELECT DISTINCT ?c WHERE {{ ?c wdt:P1366 wd:{q} }}"
# 3. details of the chosen items only, in batches
DETAIL_QUERY = """SELECT ?e ?eLabel ?desc ?when ?start ?end ?pt ?en WHERE {{ VALUES ?e {{ {ids} }}
 OPTIONAL {{ ?e schema:description ?desc. FILTER(LANG(?desc) = "pt") }}  # pt only: an English line in a pt-BR panel reads as a bug
 OPTIONAL {{ ?e wdt:P585 ?when }} OPTIONAL {{ ?e wdt:P580 ?start }} OPTIONAL {{ ?e wdt:P582 ?end }}
 OPTIONAL {{ ?pt schema:about ?e; schema:isPartOf <https://pt.wikipedia.org/> }}
 OPTIONAL {{ ?en schema:about ?e; schema:isPartOf <https://en.wikipedia.org/> }}
 {label} }}"""
DETAIL_BATCH = 100


def year_of(v: str | None) -> int | None:
    """xsd:dateTime (astronomical year) -> year without 0: '0000-..' = -1 (1 BCE), '-0479-..' = -480."""
    m = re.match(r"^(-?)(\d+)-", v or "")
    if not m:
        return None
    y = int(m.group(2)) * (-1 if m.group(1) else 1)
    return y if y > 0 else y - 1


def pick(links: dict[str, tuple[str, int, set[str]]], states: set[str]) -> list[str]:
    """Q-ids of the MAX_PER_COUNTRY most linked events tied to any of `states`. links: qid -> (type, sitelinks, linked states)."""
    mine = [(sl, q) for q, (_, sl, cs) in links.items() if cs & states]
    return [q for _, q in sorted(mine, key=lambda x: (-x[0], x[1]))[:MAX_PER_COUNTRY]]


def build(ids: list[str], links: dict[str, tuple[str, int, set[str]]], details: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Chosen Q-ids -> dated events sorted by year (undated or unlabelled items dropped)."""
    out = []
    for q in ids:
        rows = details.get(q, [])
        title = next((t for r in rows if (t := _v(r, "eLabel"))), None)
        starts = [y for r in rows if (y := year_of(_v(r, "when")) or year_of(_v(r, "start")))]
        if not title or not _is_label(title) or not starts:
            continue
        start = min(starts)
        ends = [y for r in rows if (y := year_of(_v(r, "end"))) and y > start]
        t, sl, _ = links[q]
        out.append({"qid": q, "title": title, "summary": next((d for r in rows if (d := _v(r, "desc"))), None),
                    "kind": KIND[t], "year_start": start, "year_end": max(ends) if ends else None, "sitelinks": sl,
                    "wikipedia_url": next((u for r in rows if (u := _v(r, "pt"))), None) or next((u for r in rows if (u := _v(r, "en"))), None)})
    return sorted(out, key=lambda e: (e["year_start"], e["qid"]))


def collect(client: httpx.Client, countries: dict[str, Any], cache: Path, refresh: bool,
            only: list[str] | None = None) -> dict[str, Any]:
    order = list(KIND)
    links: dict[str, tuple[str, int, set[str]]] = {}
    for t in KIND:
        for r in _cached(client, cache / f"type_{t}.json", TYPE_QUERY.format(t=t, min_sl=MIN_SITELINKS), refresh, retries=2):
            q, c = _qid(_v(r, "e")) or "", _qid(_v(r, "c")) or ""
            prev = links.get(q)
            kind_t = t if prev is None or order.index(t) < order.index(prev[0]) else prev[0]  # first type in KIND order wins
            links[q] = (kind_t, int(_v(r, "sl") or 0), (prev[2] if prev else set()) | {c})
    chosen: dict[str, list[str]] = {}
    for iso2, c in sorted(countries.items()):
        if only and iso2 not in only:
            continue
        preds = _cached(client, cache / f"{iso2}_pred.json", PRED_QUERY.format(q=c["qid"]), refresh, retries=2)
        chosen[iso2] = pick(links, {c["qid"]} | {_qid(_v(r, "c")) or "" for r in preds})
    every = sorted({q for qs in chosen.values() for q in qs})
    details: dict[str, list[dict[str, Any]]] = {}
    for i in range(0, len(every), DETAIL_BATCH):
        batch = every[i:i + DETAIL_BATCH]
        tag = hashlib.sha256(" ".join(batch).encode()).hexdigest()[:12]
        q = DETAIL_QUERY.format(ids=" ".join("wd:" + x for x in batch), label=LABEL)
        for r in _cached(client, cache / f"detail_{tag}.json", q, refresh, retries=2):
            details.setdefault(_qid(_v(r, "e")) or "", []).append(r)
    return {"source": {"id": "wikidata", "title": "Wikidata", "url": "https://www.wikidata.org/", "license": "CC0 1.0"},
            "retrieved_at": datetime.now(UTC).isoformat(),
            "countries": {iso2: build(qs, links, details) for iso2, qs in chosen.items()}}


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    countries = json.loads((s.out_dir / "wikidata.json").read_text(encoding="utf-8"))["countries"]
    only = [a for a in sys.argv[2:] if re.fullmatch(r"[A-Z]{2}", a)] or None
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        payload = collect(client, countries, s.cache_dir / "wikidata" / "events", "--refresh" in sys.argv, only)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    name = "events.json" if not only else "events_sample.json"
    (s.out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    cs = payload["countries"]
    print(f"wrote data_out/{name}: {sum(len(v) for v in cs.values())} events, {sum(bool(v) for v in cs.values())}/{len(cs)} countries")
