"""Ideologies ETL (spec 018): figures and parties of each political current, per country -> data_out/ideologies.json.

Currents: content/ideologies.yaml (`id` + `wikidata` Q-ids). ONLY those Q-ids, matched directly on the person/party: following
P279* (sub-currents) on 2026-11-13 put a sitting US president under fascism and Frederick II under liberalism, i.e. contested
classifications presented as fact, which breaks the neutrality rule. Sub-currents enter only when listed in the YAML by hand.
Wikidata (CC0), same endpoint/politeness/cache as pipeline.py. Q-ids of occupations/party checked with wbgetentities 2026-11-13.
1. per current, worldwide: people with >= MIN_SITELINKS editions who are (a) deceased with the current in a referenced P1142, or
   (b) members of a party of that current (see the comment above HIST_QUERY). Only modern countries of data_out/wikidata.json count.
2. per current: political parties (P31 Q7278) with P1142 = the current and P17 = a country.
3. details of the chosen people in batches: pt label, pt description, birth/death year, image (P18), occupations (P106),
   whether they held a position (P39), notable works (P800, max 3), pt/en Wikipedia.
Role: "leader" when politician or holding a position (P39); else "thinker" when philosopher/economist/political scientist/
sociologist/historian/theologian ("writer" made memoirists thinkers); else "activist" when activist/revolutionary; else "other".
Ranking: declared figures first, then party members, each by sitelinks (Pantheon's HPI covers too few of them); MAX_FIGURES per
current and country. Worldwide "most known" (`founders`) = declared figures only. Each figure records WHY it is there (`via`,
and the party for members) so the UI can say "filiado ao partido X" instead of labelling the person. Photos: Commons, licence per file (same rule as leaders).
Neutrality (spec 018): nothing here is written by us; texts are Wikidata's own labels/descriptions.
"""

import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from etl.settings import get_etl_settings
from etl.wikidata.events import year_of
from etl.wikidata.leaders import _cached, _file, commons_images
from etl.wikidata.pipeline import LABEL, _is_label, _qid, _v

MIN_SITELINKS = 10
MAX_FIGURES = 6
MAX_PARTIES = 50  # stored per country; the country endpoint shows 5, /ideologies/{id} uses all to find where the current governed
CATALOG = Path("content/ideologies.yaml")
THINKER = {"Q4964182", "Q188094", "Q1238570", "Q2306091", "Q201788", "Q1234713"}  # not "writer": memoirists became "thinkers"
POLITICIAN, ACTIVIST = "Q82955", {"Q15253558", "Q3242115"}
# Who counts as a figure of a current (neutrality, spec 018). Tested 2026-11-13: P1142 "political ideology" on LIVING people is
# contested and edited at will (a sitting US president was tagged "fascism", with a reference), so a person enters only by:
#  (a) HIST: deceased, with the current stated on them in a REFERENCED, non-deprecated P1142 statement, country = P27 or birthplace;
#  (b) MEMBER: member (P102) of a party whose P1142 is the current, country = the party's P17. This states party membership, not a
#      label on the person; known limit: it uses the party's CURRENT ideology (Lincoln shows as a conservative Republican).
HIST_QUERY = """SELECT DISTINCT ?p ?c ?sl WHERE {{ VALUES ?i {{ {roots} }}
 ?p p:P1142 ?st. ?st ps:P1142 ?i; wikibase:rank ?r; prov:wasDerivedFrom ?ref. FILTER(?r != wikibase:DeprecatedRank)
 ?p wdt:P570 ?dead; wdt:P31 wd:Q5; wikibase:sitelinks ?sl. FILTER(?sl >= {min_sl})
 {{ ?p wdt:P27 ?c }} UNION {{ ?p wdt:P19/wdt:P17 ?c }} }}"""
MEMBER_QUERY = """SELECT DISTINCT ?p ?party ?c ?sl WHERE {{ VALUES ?i {{ {roots} }}
 ?party wdt:P1142 ?i; wdt:P17 ?c. ?p wdt:P102 ?party; wdt:P31 wd:Q5; wikibase:sitelinks ?sl. FILTER(?sl >= {min_sl}) }}"""
PARTY_QUERY = """SELECT ?party ?partyLabel ?c ?sl WHERE {{ VALUES ?i {{ {roots} }}
 ?party wdt:P1142 ?i; wdt:P31 wd:Q7278; wdt:P17 ?c; wikibase:sitelinks ?sl.
 {label} }}"""
DETAIL_QUERY = """SELECT ?p ?pLabel ?desc ?birth ?death ?image ?occ ?held ?work ?workLabel ?pt ?en WHERE {{ VALUES ?p {{ {ids} }}
 OPTIONAL {{ ?p schema:description ?desc. FILTER(LANG(?desc) = "pt") }}
 OPTIONAL {{ ?p wdt:P569 ?birth }} OPTIONAL {{ ?p wdt:P570 ?death }} OPTIONAL {{ ?p wdt:P18 ?image }}
 OPTIONAL {{ ?p wdt:P106 ?occ }} OPTIONAL {{ ?p wdt:P39 ?held }} OPTIONAL {{ ?p wdt:P800 ?work }}
 OPTIONAL {{ ?pt schema:about ?p; schema:isPartOf <https://pt.wikipedia.org/> }}
 OPTIONAL {{ ?en schema:about ?p; schema:isPartOf <https://en.wikipedia.org/> }}
 {label} }}"""
DETAIL_BATCH = 60
LABELS_QUERY = """SELECT ?x ?xLabel WHERE {{ VALUES ?x {{ {ids} }} {label} }}"""


def role(occupations: set[str], held_position: bool) -> str:
    """Office first: a president who studied economics is shown as a leader, not a thinker."""
    if POLITICIAN in occupations or held_position:
        return "leader"
    if occupations & THINKER:
        return "thinker"
    return "activist" if occupations & ACTIVIST else "other"


def person(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Detail rows of one person (one per occupation/work combination) -> record; None without a usable label."""
    name = next((n for r in rows if (n := _v(r, "pLabel"))), None)
    if not name or not _is_label(name):
        return None
    occ = {q for r in rows if (q := _qid(_v(r, "occ")))}
    works: list[str] = []
    for r in rows:
        w = _v(r, "workLabel")
        if w and _is_label(w) and w not in works:
            works.append(w)
    return {"name": name, "role": role(occ, any(_v(r, "held") for r in rows)),
            "birth_year": next((y for r in rows if (y := year_of(_v(r, "birth")))), None),
            "death_year": next((y for r in rows if (y := year_of(_v(r, "death")))), None),
            "summary": next((d for r in rows if (d := _v(r, "desc"))), None), "works": works[:3],
            "image_file": next((f for r in rows if (f := _file(_v(r, "image")))), None),
            "wikipedia_url": next((u for r in rows if (u := _v(r, "pt"))), None) or next((u for r in rows if (u := _v(r, "en"))), None)}


def rank(declared: dict[str, int], members: dict[str, tuple[int, str]], n: int) -> list[dict[str, str | None]]:
    """Declared figures first (by sitelinks), then party members fill up to n. Entry: {id, via: declared|party, party: Q-id|None}."""
    out: list[dict[str, str | None]] = [{"id": q, "via": "declared", "party": None}
                                        for q, _ in sorted(declared.items(), key=lambda x: (-x[1], x[0]))[:n]]
    taken = {e["id"] for e in out}
    for q, (_, party) in sorted(members.items(), key=lambda x: (-x[1][0], x[0])):
        if len(out) >= n:
            break
        if q not in taken:
            out.append({"id": q, "via": "party", "party": party})
    return out


def collect(client: httpx.Client, iso_of: dict[str, str], cache: Path, refresh: bool) -> dict[str, Any]:
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["terms"]
    out: dict[str, Any] = {}
    for term in catalog:
        roots = " ".join("wd:" + q for q in term["wikidata"])
        hist = _cached(client, cache / f"hist_{term['id']}.json", HIST_QUERY.format(roots=roots, min_sl=MIN_SITELINKS), refresh, retries=2)
        member = _cached(client, cache / f"member_{term['id']}.json", MEMBER_QUERY.format(roots=roots, min_sl=MIN_SITELINKS), refresh, retries=2)
        declared: dict[str, dict[str, int]] = {}
        world: dict[str, int] = {}
        for r in hist:
            p, sl, iso2 = _qid(_v(r, "p")) or "", int(_v(r, "sl") or 0), iso_of.get(_qid(_v(r, "c")) or "")
            world[p] = sl
            if iso2:
                declared.setdefault(iso2, {})[p] = sl
        members: dict[str, dict[str, tuple[int, str]]] = {}
        for r in member:
            iso2 = iso_of.get(_qid(_v(r, "c")) or "")
            if iso2:
                members.setdefault(iso2, {})[_qid(_v(r, "p")) or ""] = (int(_v(r, "sl") or 0), _qid(_v(r, "party")) or "")
        prows = _cached(client, cache / f"parties_{term['id']}.json", PARTY_QUERY.format(roots=roots, label=LABEL), refresh, retries=2)
        parties: dict[str, dict[str, tuple[str, int]]] = {}
        for r in prows:
            iso2, name = iso_of.get(_qid(_v(r, "c")) or ""), _v(r, "partyLabel")
            if iso2 and name and _is_label(name):
                parties.setdefault(iso2, {})[_qid(_v(r, "party")) or ""] = (name, int(_v(r, "sl") or 0))
        countries = {}
        for iso2 in sorted(set(declared) | set(members) | set(parties)):
            pts = sorted(parties.get(iso2, {}).items(), key=lambda x: (-x[1][1], x[0]))[:MAX_PARTIES]
            countries[iso2] = {"figures": rank(declared.get(iso2, {}), members.get(iso2, {}), MAX_FIGURES),
                               "parties": [{"id": q, "name": n} for q, (n, _) in pts]}
        # worldwide "most known": declared figures only (party membership is a country-level fact, not a world reference)
        out[term["id"]] = {"founders": rank(world, {}, MAX_FIGURES), "countries": countries}
    figures = [f for ideo in out.values() for f in [*ideo["founders"], *(x for c in ideo["countries"].values() for x in c["figures"])]]
    every = sorted({f["id"] for f in figures if f["id"]})
    details: dict[str, list[dict[str, Any]]] = {}
    for i in range(0, len(every), DETAIL_BATCH):
        batch = every[i:i + DETAIL_BATCH]
        tag = hashlib.sha256(" ".join(batch).encode()).hexdigest()[:12]
        q = DETAIL_QUERY.format(ids=" ".join("wd:" + x for x in batch), label=LABEL)
        for r in _cached(client, cache / f"detail_{tag}.json", q, refresh, retries=2):
            details.setdefault(_qid(_v(r, "p")) or "", []).append(r)
    party_ids = sorted({f["party"] for f in figures if f["party"]})
    party_names: dict[str, str] = {}
    for i in range(0, len(party_ids), 200):
        batch = party_ids[i:i + 200]
        tag = hashlib.sha256(" ".join(batch).encode()).hexdigest()[:12]
        for r in _cached(client, cache / f"labels_{tag}.json", LABELS_QUERY.format(ids=" ".join("wd:" + x for x in batch), label=LABEL), refresh, retries=2):
            if (n := _v(r, "xLabel")) and _is_label(n):
                party_names[_qid(_v(r, "x")) or ""] = n
    people = {q: rec for q in every if (rec := person(details.get(q, [])))}
    images = commons_images(client, {p["image_file"] for p in people.values() if p["image_file"]}, cache, refresh)
    for rec in people.values():
        rec["image"] = images.get(rec.pop("image_file") or "")

    def keep(fs: list[dict[str, Any]]) -> list[dict[str, Any]]:  # usable people only; party id -> {id, name}
        return [{**f, "party": {"id": f["party"], "name": party_names[f["party"]]} if f["party"] in party_names else None}
                for f in fs if f["id"] in people and (f["via"] == "declared" or f["party"] in party_names)]

    for ideo in out.values():
        ideo["founders"] = keep(ideo["founders"])
        for c in ideo["countries"].values():
            c["figures"] = keep(c["figures"])
    return {"source": {"id": "wikidata", "title": "Wikidata", "url": "https://www.wikidata.org/",
                       "license": "CC0 1.0 (photos: per-file licence from Wikimedia Commons, see image.license)"},
            "retrieved_at": datetime.now(UTC).isoformat(), "ideologies": out, "people": people}


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    countries = json.loads((s.out_dir / "wikidata.json").read_text(encoding="utf-8"))["countries"]
    iso_of = {c["qid"]: iso2 for iso2, c in countries.items() if re.fullmatch(r"[A-Z]{2}", iso2)}
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        payload = collect(client, iso_of, s.cache_dir / "wikidata" / "ideologies", "--refresh" in sys.argv)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "ideologies.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    ideos = payload["ideologies"]
    print(f"wrote data_out/ideologies.json: {len(payload['people'])} people, {len(ideos)} currents")
    for k, v in ideos.items():
        print(f"  {k}: {len(v['countries'])} countries, founders: {[payload['people'][f['id']]['name'] for f in v['founders']][:4]}")
