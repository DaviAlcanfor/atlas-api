"""Languages ETL (spec 017, v1.2): official and other spoken languages -> data_out/languages.json.

Wikidata (CC0), same endpoint/politeness/cache as pipeline.py. Two steps (one big join times out):
1. per country (cache etl_cache/wikidata/languages/<ISO2>.json), the candidate languages:
   P37 of the country (official), P2936 "language used", languages with P2341 "indigenous to" =
   country, and P37 of items whose P17 = country (co-official in a subdivision / municipality).
2. per batch of 150 Q-ids (cache .../languages/_attr_<hash>.json), the attributes: is it a
   language (P31/P279* Q34770), a sign language (Q34228), dead/extinct (P31 Q45762 / Q38058796, or
   P576, or UNESCO "extinct"), ISO codes, UNESCO status (P1999), pt/en Wikipedia, P279+
   ancestors ("variety of" + families), speakers (P1098 with a place qualifier = the country). The step-1 "subdivisions"
   are checked the same way (P31/P279* Q56061 administrative territorial entity, not dissolved,
   not an organisation Q43229), so P37 of Mercosul, a church, ethnic groups or colonial
   captaincies does not count. "Language" = P31/P279* Q34770 language or Q33384 dialect (Talian
   and Hunsrik are typed as dialects).

`family` comes ONLY from content/language_families.yaml (Wikidata Q-id -> our pt-BR label):
the top of the P279 chain in Wikidata is often a contested macro-family (Dené-Caucasian,
Sino-Austronesian...), so we never print it; a language with no listed ancestor has family null.

Status, first match wins: official > co_official > sign > historical > indigenous (P2341 = country,
or an ancestor family listed in content/language_families.yaml for the country's region) >
immigrant. Varieties of an official language (P279+ ancestor is official, e.g. "português
brasileiro") are dropped: they would repeat the official one. Speakers only when the statement
is qualified with the country (else null: a world total is not "speakers in this country").
"""

import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached
from etl.wikidata.pipeline import LABEL, _is_label, _qid, _v

STATUSES = ("official", "co_official", "sign", "historical", "indigenous", "immigrant")  # precedence
ORDER = ("official", "co_official", "indigenous", "immigrant", "sign", "historical")  # contract sort
FAMILIES = Path("content/language_families.yaml")
WHERE_MAX = 3
BATCH = 60  # Q-ids per attribute query (150 timed out often; each timeout used to cost ~5 min of retries)
log = logging.getLogger("etl.languages")

COUNTRY_QUERY = """SELECT ?l ?kind ?sub ?subLabel WHERE {{
 {{ wd:{q} wdt:P37 ?l. BIND("official" AS ?kind) }} UNION
 {{ wd:{q} wdt:P2936 ?l. BIND("used" AS ?kind) }} UNION
 {{ ?l wdt:P2341 wd:{q}. BIND("indigenous_to" AS ?kind) }} UNION
 {{ ?sub wdt:P17 wd:{q}; wdt:P37 ?l. FILTER(?sub != wd:{q}) BIND("sub" AS ?kind) }}
 {label} }}"""
INFO_QUERY = """SELECT ?l ?lLabel ?isLang ?isSign ?isDead ?isAdmin ?c1 ?c3 ?ietf ?st ?stLabel ?pt ?en
WHERE {{ VALUES ?l {{ {ids} }}
 BIND(EXISTS {{ ?l wdt:P31/wdt:P279* ?lt. VALUES ?lt {{ wd:Q34770 wd:Q33384 }} }} AS ?isLang)
 BIND(EXISTS {{ ?l wdt:P31/wdt:P279* wd:Q34228 }} AS ?isSign)
 BIND(EXISTS {{ {{ ?l wdt:P31 wd:Q45762 }} UNION {{ ?l wdt:P31 wd:Q38058796 }} UNION
               {{ ?l wdt:P576 ?gone }} }} AS ?isDead)
 BIND((EXISTS {{ ?l wdt:P31/wdt:P279* wd:Q56061 }} && !EXISTS {{ ?l wdt:P576 ?g2 }}
        && !EXISTS {{ ?l wdt:P31/wdt:P279* wd:Q43229 }}) AS ?isAdmin)
 OPTIONAL {{ ?l wdt:P218 ?c1 }} OPTIONAL {{ ?l wdt:P220 ?c3 }} OPTIONAL {{ ?l wdt:P305 ?ietf }}
 OPTIONAL {{ ?l wdt:P1999 ?st }}
 OPTIONAL {{ ?pt schema:about ?l; schema:isPartOf <https://pt.wikipedia.org/> }}
 OPTIONAL {{ ?en schema:about ?l; schema:isPartOf <https://en.wikipedia.org/> }}
 {label} }}"""
ANCESTORS_QUERY = """SELECT ?l ?a WHERE {{ VALUES ?l {{ {ids} }} ?l wdt:P279+ ?a. }}"""
# UNESCO Atlas status (P1999): fixed 6-step scale, our pt-BR wording (Wikidata labels are mixed).
ENDANGERMENT = {"Q20672086": "segura", "Q20672087": "vulnerável", "Q20672088": "definitivamente em perigo",
                "Q20672089": "severamente em perigo", "Q20672090": "criticamente em perigo",
                "Q20672091": "extinta"}
SPEAKERS_QUERY = """SELECT ?l ?n ?when ?place WHERE {{ VALUES ?l {{ {ids} }}
 ?l p:P1098 ?s. ?s ps:P1098 ?n; wikibase:rank ?rank. FILTER(?rank != wikibase:DeprecatedRank)
 OPTIONAL {{ ?s pq:P585 ?when }}
 {{ ?s pq:P17 ?place }} UNION {{ ?s pq:P276 ?place }} UNION {{ ?s pq:P3005 ?place }} }}"""


def _batched(client: httpx.Client, cache: Path, query: str, qids: list[str],
             refresh: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    todo = [qids[i:i + BATCH] for i in range(0, len(qids), BATCH)]
    while todo:
        batch = todo.pop(0)
        tag = hashlib.sha256((query + " ".join(batch)).encode()).hexdigest()[:12]
        q = query.format(ids=" ".join("wd:" + x for x in batch), label=LABEL)
        try:
            rows += _cached(client, cache / f"_attr_{tag}.json", q, refresh, retries=1)
        except (httpx.HTTPStatusError, RuntimeError):  # 60 s query timeout: split now, never retry the same batch
            if len(batch) == 1:
                log.warning("gave up on %s (query keeps timing out)", batch[0])
                continue
            half = len(batch) // 2
            todo[:0] = [batch[:half], batch[half:]]
    return rows


def attributes(rows: dict[str, list[dict[str, Any]]], anc: list[dict[str, Any]],
               spk: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Q-id -> merged attributes from the three batched queries (multi-valued kept as sets)."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows["info"]:
        q = _qid(_v(r, "l")) or ""
        a = out.setdefault(q, {"name": _v(r, "lLabel"), "lang": _v(r, "isLang") == "true",
                               "sign": _v(r, "isSign") == "true", "dead": _v(r, "isDead") == "true",
                               "admin": _v(r, "isAdmin") == "true", "codes": set(),
                               "status": None, "wikipedia_url": None, "ancestors": set(),
                               "speakers": []})
        for k in ("c1", "ietf", "c3"):
            if v := _v(r, k):
                a["codes"].add((k, v))
        if st := ENDANGERMENT.get(_qid(_v(r, "st")) or ""):
            a["status"] = st
            a["dead"] = a["dead"] or st == "extinta"
        a["wikipedia_url"] = a["wikipedia_url"] or _v(r, "pt") or _v(r, "en")
    for r in anc:
        if (a_ := out.get(_qid(_v(r, "l")) or "")) is not None:
            a_["ancestors"].add(_qid(_v(r, "a")) or "")
    for r in spk:
        a_ = out.get(_qid(_v(r, "l")) or "")
        if a_ is not None and (n := _v(r, "n")):
            a_["speakers"].append((_qid(_v(r, "place")), _v(r, "when"), int(float(n))))
    return out


def _code(codes: set[tuple[str, str]]) -> str | None:
    for k in ("c1", "ietf", "c3"):  # ISO 639-1, else IETF tag, else ISO 639-3
        vals = sorted(v for kk, v in codes if kk == k)
        if vals:
            return vals[0]
    return None


def _speakers(a: dict[str, Any], country: str) -> dict[str, Any] | None:
    mine = [(w or "", n) for place, w, n in a["speakers"] if place == country]
    if not mine:
        return None
    when, n = max(mine)  # latest dated statement
    return {"value": n, "year": int(when[:4]) if when[:4].isdigit() else None}


def classify(country_q: str, region: str | None, cand: list[dict[str, Any]],
             attrs: dict[str, dict[str, Any]], families: dict[str, Any]) -> list[dict[str, Any]]:
    """Step-1 rows of one country + attributes -> sorted LanguageSpoken records."""
    official, used, indig = set(), set(), set()
    where: dict[str, set[str]] = {}
    for r in cand:
        q, kind = _qid(_v(r, "l")) or "", _v(r, "kind")
        if kind == "official":
            official.add(q)
        elif kind == "used":
            used.add(q)
        elif kind == "indigenous_to":
            indig.add(q)
        elif kind == "sub":
            sub = attrs.get(_qid(_v(r, "sub")) or "")
            if sub and sub["admin"] and _is_label(_v(r, "subLabel")):
                where.setdefault(q, set()).add(_v(r, "subLabel") or "")
    regions = set((region or "").split(" / "))
    out = []
    for q in sorted(official | used | indig | set(where)):
        a = attrs.get(q)
        if not a or not a["lang"] or not _is_label(a["name"]):
            continue
        if q not in official and a["ancestors"] & official:
            continue  # a variety of an official language (pt-BR of pt)
        hits = [f for f in families if f in a["ancestors"]]  # yaml order
        native = any(set(families[f].get("regions") or []) & regions for f in hits)
        # a family that arrived by colonisation/migration in this region (e.g. Indo-European in the Americas) is never indigenous
        # there, even when Wikidata's P2341 says so (Hunsrik and Talian took shape in Brazil but are immigrant languages)
        foreign = any(set(families[f].get("foreign_in") or []) & regions for f in hits)
        status = ("official" if q in official else "co_official" if q in where
                  else "sign" if a["sign"] else "historical" if a["dead"]
                  else "indigenous" if (q in indig and not foreign) or native else "immigrant")
        places = sorted(where.get(q, set())) if status == "co_official" else []
        out.append({
            "qid": q, "code": _code(a["codes"]), "name": a["name"], "status": status,
            "where": (", ".join(places[:WHERE_MAX]) + (f" e mais {len(places) - WHERE_MAX}"
                      if len(places) > WHERE_MAX else "")) if places else None,
            "speakers": _speakers(a, country_q),
            "family": next((families[f]["label"] for f in hits if families[f].get("label")), None),
            "endangerment": a["status"], "wikipedia_url": a["wikipedia_url"],
        })
    return sorted(out, key=lambda x: (ORDER.index(x["status"]),
                                      -(x["speakers"] or {}).get("value", -1), x["name"].casefold()))


def collect(client: httpx.Client, countries: dict[str, Any], cache: Path, refresh: bool,
            only: list[str] | None = None) -> dict[str, Any]:
    cand: dict[str, list[dict[str, Any]]] = {}
    for iso2, c in sorted(countries.items()):
        if only and iso2 not in only:
            continue
        cand[iso2] = _cached(client, cache / f"{iso2}.json",
                             COUNTRY_QUERY.format(q=c["qid"], label=LABEL), refresh)
    langs = sorted({_qid(_v(r, "l")) or "" for rs in cand.values() for r in rs})
    subs: set[str] = set()  # only subdivisions that could make a NON-official language co-official
    for rs in cand.values():
        official = {_v(r, "l") for r in rs if _v(r, "kind") == "official"}
        subs |= {_qid(_v(r, "sub")) or "" for r in rs
                 if _v(r, "kind") == "sub" and _v(r, "l") not in official}
    info = _batched(client, cache, INFO_QUERY, sorted(set(langs) | subs), refresh)
    attrs = attributes({"info": info}, _batched(client, cache, ANCESTORS_QUERY, langs, refresh),
                       _batched(client, cache, SPEAKERS_QUERY, langs, refresh))
    fams = yaml.safe_load(FAMILIES.read_text(encoding="utf-8")) if FAMILIES.exists() else {}
    return {
        "source": {"id": "wikidata", "title": "Wikidata", "url": "https://www.wikidata.org/",
                   "license": "CC0 1.0"},
        "retrieved_at": datetime.now(UTC).isoformat(),
        "countries": {iso2: classify(countries[iso2]["qid"], countries[iso2].get("region"), rows,
                                     attrs, fams.get("families", {}))
                      for iso2, rows in cand.items()},
    }


def run() -> None:
    logging.basicConfig(level=logging.WARNING, format="  %(message)s")
    s = get_etl_settings()
    ua = f"atlas-api/0.1 ({s.wikidata_contact or 'generic ETL client'}) python-httpx/{httpx.__version__}"
    countries = json.loads((s.out_dir / "wikidata.json").read_text(encoding="utf-8"))["countries"]
    only = [a for a in sys.argv[2:] if len(a) == 2 and a.isupper()] or None
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        payload = collect(client, countries, s.cache_dir / "wikidata" / "languages",
                          "--refresh" in sys.argv, only)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    name = "languages.json" if not only else "languages_sample.json"
    (s.out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    cs = payload["countries"]
    print(f"wrote data_out/{name}: {sum(len(v) for v in cs.values())} languages, "
          f"{sum(bool(v) for v in cs.values())}/{len(cs)} countries with any")
    for st in STATUSES:
        print(f"  {st}: {sum(x['status'] == st for v in cs.values() for x in v)}"
              f" in {sum(any(x['status'] == st for x in v) for v in cs.values())} countries")
    print(f"  with speakers: {sum(x['speakers'] is not None for v in cs.values() for x in v)}")
    print(f"  with family: {sum(x['family'] is not None for v in cs.values() for x in v)}")
