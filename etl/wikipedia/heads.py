"""Head of each subdivision (spec 024 phase 2: governor, chief minister...) -> data_out/heads.json, keyed by subdivision Q-id.

Tested 2026-11-16 against pt.wikipedia's list of current Brazilian governors (edited 2026-11-08): Wikidata is stale.
  P6 on the state item: 13/27 right (RJ = Witzel, removed 2021). P39 of the office (P1313) on the person, latest start: 16/27
  (it misses the wave of April 2026 resignations: AC, AM, DF, ES, GO, MG, PA, PB, RJ, RR).
So, per country, the Wikipedia list of current holders wins when we have one (LISTS: BR, US, IN), read from the rendered HTML
of the exact revision (MediaWiki API action=parse, cited by permalink). Wikipedia text is CC BY-SA 4.0 (Terms of Use §7:
attribution = title + link); we keep only facts (name, start date) from it. Rows are joined to our subdivisions through the
Wikidata id of the linked article (pageprops.wikibase_item, redirects followed), never by name; the person gets the Wikidata id
of the linked biography.
Elsewhere, Wikidata (CC0) only when WIKIDATA_ELSEWHERE is True: see the spec for the decision and numbers.
  candidates: P6 statements on the subdivision + P39 statements whose value is its P1313 office; non-deprecated, WITH a start
  date (P580). The latest start wins; it counts only when it has no end date (or one in the future) and the holder is alive.
"""

import json
import re
import sys
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached, _get_json
from etl.wikidata.pipeline import LABEL, _qid, _v

# iso2 -> wiki, page, [(unit header, holder header, start header, office in pt-BR)]; a table is used when its header row
# starts with these three headers (prefix match). Office is the name of the post, not gendered.
LISTS: dict[str, dict[str, Any]] = {
    "BR": {"wiki": "pt.wikipedia.org", "page": "Lista de governadores das unidades federativas do Brasil",
           "tables": [("Unidade federativa", "Governador", "No cargo desde", "Governador")]},
    "US": {"wiki": "en.wikipedia.org", "page": "List of current United States governors",
           "tables": [("State", "Governor", "Term start", "Governador"), ("Territory", "Governor", "Term start", "Governador"),
                      ("Federal district", "Mayor", "Term start", "Prefeito")],
           # the state cell links only "Governor of X"; plain "Washington"/"New York"/"Georgia" are other articles.
           # Safe to try: a title counts only if its Wikidata id is one of this country's subdivisions.
           "suffixes": [" (state)", " (U.S. state)"]},
    "IN": {"wiki": "en.wikipedia.org", "page": "List of current Indian chief ministers",
           "tables": [("State/UT", "Officeholder", "Took office", "Ministro-chefe")]},
}
WIKIDATA_ELSEWHERE = False
FILE = re.compile(r"(File|Ficheiro|Arquivo|Image|Imagem):")  # portrait links are not the holder
HEADS_QUERY = """SELECT ?s ?h ?hLabel ?start ?end ?dead ?office ?officeLabel WHERE {{ VALUES ?s {{ {ids} }}
 {{ ?s p:P6 ?st. ?st ps:P6 ?h }} UNION {{ ?s wdt:P1313 ?office. ?h p:P39 ?st. ?st ps:P39 ?office }}
 ?st wikibase:rank ?rank. FILTER(?rank != wikibase:DeprecatedRank)
 ?st pq:P580 ?start. OPTIONAL {{ ?st pq:P582 ?end }} OPTIONAL {{ ?h wdt:P570 ?dead }}
 {label} }}"""
MONTHS = {m: i + 1 for i, m in enumerate(
    ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"])}
MONTHS |= {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}


class _Tables(HTMLParser):
    """Every <table> as rows of cells {t: text, l: [linked article titles], rs, cs}; footnotes (<sup>) and <style> skipped."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[dict[str, Any]]]] = []
        self.stack: list[list[list[dict[str, Any]]]] = []
        self.cell: dict[str, Any] | None = None
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "table":
            self.stack.append([])
        elif tag == "tr" and self.stack:
            self.stack[-1].append([])
        elif tag in ("td", "th") and self.stack and self.stack[-1]:
            self.cell = {"t": "", "l": [], "rs": int(re.sub(r"\D", "", a.get("rowspan", "")) or 1),
                         "cs": int(re.sub(r"\D", "", a.get("colspan", "")) or 1)}
            self.stack[-1][-1].append(self.cell)
        elif tag == "a" and self.cell is not None and a.get("href", "").startswith("/wiki/") and not FILE.match(a["href"][6:]):
            self.cell["l"].append(unquote(a["href"][6:].split("#")[0]).replace("_", " "))
        elif tag in ("sup", "style"):
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.stack:
            self.tables.append(self.stack.pop())
        elif tag in ("td", "th"):
            self.cell = None
        elif tag in ("sup", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data: str) -> None:
        if self.cell is not None and not self.skip:
            self.cell["t"] += data


def grid(rows: list[list[dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    """Expand rowspan/colspan so column i of every row is the cell drawn there."""
    out, carry = [], {}  # type: ignore[var-annotated]
    for r in rows:
        line: list[dict[str, Any]] = []
        k = 0
        while k < len(r) or len(line) in carry:
            ci = len(line)
            if ci in carry:
                c, n = carry.pop(ci)
                line.append(c)
                if n > 1:
                    carry[ci] = (c, n - 1)
                continue
            c = r[k]
            k += 1
            for _ in range(c["cs"]):
                if c["rs"] > 1:
                    carry[len(line)] = (c, c["rs"] - 1)
                line.append(c)
        out.append(line)
    return out


def text(c: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", c["t"]).strip()


def parse_date(s: str) -> str | None:
    """'1.º de janeiro de 2023' / '2 de abril de 2026' / 'April 10, 2017' / '12 June 2024(2 years...' -> ISO date."""
    s = s.lower().replace("1.º", "1").replace("º", "")
    m = (re.search(r"(\d{1,2}) de ([a-zç]+) de (\d{4})", s) or re.search(r"(\d{1,2}) ([a-z]+),? (\d{4})", s))
    if m and m.group(2) in MONTHS:
        d, mo, y = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
    elif (m := re.search(r"([a-z]+) (\d{1,2}), (\d{4})", s)) and m.group(1) in MONTHS:
        d, mo, y = int(m.group(2)), MONTHS[m.group(1)], int(m.group(3))
    else:
        return None
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def list_rows(html: str, tables: list[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    """Rows of the matching tables: {unit_titles, unit_text, name, person_title, since, office}."""
    p = _Tables()
    p.feed(html)
    out = []
    for t in p.tables:
        g = grid(t)
        if not g:
            continue
        head = [text(c) for c in g[0]]
        for unit_h, holder_h, start_h, office in tables:
            st = next((i for i, x in enumerate(head) if x.startswith(start_h)), None)
            if st is None or not head[0].startswith(unit_h):
                continue
            u = 0
            hs = [i for i, x in enumerate(head) if x.startswith(holder_h)]  # "Governador" may span the portrait column too
            for row in g[1:]:
                h = next((i for i in hs if i < len(row) and row[i]["l"]), None)
                if h is None or len(row) <= max(u, st):
                    continue
                unit_text = re.sub(r"\s*\((list|lista)\)\s*$", "", text(row[u]))
                out.append({"unit_titles": [*row[u]["l"], unit_text], "name": text(row[h]), "person_title": row[h]["l"][0],
                            "since": parse_date(text(row[st])), "office": office})
            break
    return out


def wikibase_items(client: httpx.Client, wiki: str, titles: set[str]) -> dict[str, str]:
    """Article title (as linked, redirects followed) -> Wikidata Q-id."""
    out: dict[str, str] = {}
    ts = sorted(t for t in titles if t)
    for i in range(0, len(ts), 50):
        q = _get_json(client, f"https://{wiki}/w/api.php", {"action": "query", "titles": "|".join(ts[i:i + 50]),
                      "redirects": "1", "prop": "pageprops", "ppprop": "wikibase_item", "format": "json",
                      "formatversion": "2"})["query"]
        alias = {x["from"]: x["to"] for k in ("normalized", "redirects") for x in q.get(k, [])}
        qid = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in q.get("pages", [])}
        for t in ts[i:i + 50]:
            final = t
            while final in alias:
                final = alias[final]
            if q_ := qid.get(final):
                out[t] = q_
    return out


def from_list(client: httpx.Client, iso2: str, cfg: dict[str, Any], subs: set[str], cache: Path,
              refresh: bool) -> tuple[dict[str, dict[str, Any]], dict[str, Any], int]:
    f = cache / f"list_{iso2}.json"
    if f.exists() and not refresh:
        parsed = json.loads(f.read_text(encoding="utf-8"))
    else:
        parsed = _get_json(client, f"https://{cfg['wiki']}/w/api.php", {"action": "parse", "page": cfg["page"],
                           "prop": "text|revid", "redirects": "1", "format": "json", "formatversion": "2"})["parse"]
        parsed["retrieved_at"] = datetime.now(UTC).isoformat()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
    rows = list_rows(parsed["text"], cfg["tables"])
    for r in rows:
        r["unit_titles"] += [r["unit_titles"][-1] + x for x in cfg.get("suffixes", [])]
    ids = wikibase_items(client, cfg["wiki"], {t for r in rows for t in [*r["unit_titles"], r["person_title"]]})
    sid = f"wikipedia-heads-{iso2.lower()}"
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        unit = next((ids[t] for t in r["unit_titles"] if ids.get(t) in subs), None)
        if unit and unit not in out:
            out[unit] = {"name": r["name"], "office": r["office"], "since": r["since"],
                         "wikidata_id": ids.get(r["person_title"]), "source_id": sid}
    src = {"id": sid, "title": f"Wikipedia: {parsed['title']} (revisão {parsed['revid']})",
           "url": f"https://{cfg['wiki']}/w/index.php?oldid={parsed['revid']}", "license": "CC BY-SA 4.0",
           "retrieved_at": parsed["retrieved_at"]}
    return out, src, len(rows)


def pick(rows: list[dict[str, Any]], today: str) -> dict[str, Any] | None:
    """One subdivision's Wikidata candidates -> the current holder, or None (latest start ended, holder dead, no start)."""
    if not rows:
        return None
    best = max(rows, key=lambda r: _v(r, "start") or "")
    end, start = (_v(best, "end") or "")[:10], (_v(best, "start") or "")[:10]
    if (end and end <= today) or _v(best, "dead") or not start:
        return None
    hid = _qid(_v(best, "h"))
    name = _v(best, "hLabel")
    if not name or name == hid:
        return None
    office = next((o for r in rows if (o := _v(r, "officeLabel")) and o != _qid(_v(r, "office"))), None)
    return {"name": name, "office": office, "since": start, "wikidata_id": hid, "source_id": "wikidata"}


def from_wikidata(client: httpx.Client, qids: list[str], cache: Path, refresh: bool) -> dict[str, dict[str, Any]]:
    by: dict[str, list[dict[str, Any]]] = {}
    for i in range(0, len(qids), 100):
        q = HEADS_QUERY.format(ids=" ".join("wd:" + x for x in qids[i:i + 100]), label=LABEL)
        for r in _cached(client, cache / f"wikidata_{i // 100:03d}.json", q, refresh):
            by.setdefault(_qid(_v(r, "s")) or "", []).append(r)
    today = date.today().isoformat()
    return {q: h for q in qids if (h := pick(by.get(q, []), today))}


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    subs_file = s.out_dir / "subdivisions.json"
    if not subs_file.exists():
        sys.exit("Run `python -m etl wikidata-subdivisions` first.")
    countries = json.loads(subs_file.read_text(encoding="utf-8"))["countries"]
    cache, refresh = s.cache_dir / "wikipedia" / "heads", "--refresh" in sys.argv
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    items: dict[str, dict[str, Any]] = {}
    sources, stats = [], {}
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        wd = from_wikidata(client, sorted({x["wikidata_id"] for xs in countries.values() for x in xs}), cache, refresh)
        for iso2, cfg in LISTS.items():
            subs = {x["wikidata_id"] for x in countries.get(iso2, [])}
            got, src, n = from_list(client, iso2, cfg, subs, cache, refresh)
            items.update(got)
            sources.append(src)
            agree = sum(1 for q, h in got.items() if wd.get(q, {}).get("wikidata_id") == h["wikidata_id"])
            stats[iso2] = {"subdivisions": len(subs), "list_rows": n, "matched": len(got),
                           "wikidata_has_current": sum(q in wd for q in subs), "wikidata_agrees_with_list": agree}
    rest = {x["wikidata_id"] for iso2, xs in countries.items() if iso2 not in LISTS for x in xs}
    elsewhere = {q: h for q, h in wd.items() if q in rest}
    stats["wikidata_elsewhere"] = {"subdivisions": len(rest), "with_current_holder": len(elsewhere),
                                   "served": WIKIDATA_ELSEWHERE}
    if WIKIDATA_ELSEWHERE:
        items.update(elsewhere)
    payload = {"sources": sources, "retrieved_at": datetime.now(UTC).isoformat(), "items": items, "stats": stats}
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "heads.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/heads.json: {len(items)} heads")
    print(json.dumps(stats, indent=1))
