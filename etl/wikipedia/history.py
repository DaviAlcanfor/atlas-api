"""History summary ETL (spec 016, stage 1): "História de X" on pt.wikipedia, condensed -> data_out/history.json.

Which article: Wikidata P2184 ("history of topic") of the country item, its pt.wikipedia sitelink (no title guessing).
Text: MediaWiki API, TextExtracts (`prop=extracts&explaintext=1&exsectionformat=wiki`, one page per request) + the
revision id, so every summary cites the exact revision it came from. Docs read 2026-11-12: mediawiki.org/wiki/Extension:TextExtracts,
API:Etiquette (descriptive User-Agent with contact, requests in series), Wikipedia text licence CC BY-SA 4.0
(Terms of Use §7: reuse requires attribution (title + link) and a note of changes; the condensed text is shared under the same licence).

Condensing is mechanical, never generative: summary = first paragraphs of the lead (<= SUMMARY_CHARS, cut at a sentence end);
period = each level-2 section that is not reference matter, title as written (years parsed from it when present),
text = its first paragraphs (<= PERIOD_CHARS) and, when it has subsections (spec 026), one more paragraph per subsection:
"<subsection title>: <its first sentences>" (<= SUB_CHARS each, <= PERIOD_WITH_SUBS in all). Raw extracts are cached in etl_cache/wikipedia/history/<ISO2>.json.
"""

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached, _get_json

WIKI_API = "https://pt.wikipedia.org/w/api.php"
SUMMARY_CHARS = 1100
PERIOD_CHARS = 650
SUB_CHARS = 380  # spec 026: per subsection
PERIOD_WITH_SUBS = 2600
NL2 = "\n\n"
_SENTENCE = re.compile(r"(?<=[.!?])(?<!\b[A-ZÀ-Ý]\.)\s+(?=[A-ZÀ-Ý])")  # not after "D." (D. Pedro)
ARTICLES_QUERY = """SELECT ?iso2 ?pt WHERE { ?c wdt:P297 ?iso2; wdt:P2184 ?h.
 ?pt schema:about ?h; schema:isPartOf <https://pt.wikipedia.org/> }"""
SKIP = re.compile(r"^(ver também|notas?|referências|bibliografia|ligações externas|leitura (adicional|complementar)|"
                  r"galeria|fontes|periodização|historiografia|cronologia|ver tamb[eé]m)\b", re.IGNORECASE)
_MAINT = re.compile(r"\s?\[[^\[\]\n]{1,30}\]\??")  # maintenance tags: "[carece de fontes]?", "[nota 1]", "[3]"
_H3PLUS = re.compile(r"^===+ .*? ===+\s*$", re.MULTILINE)
_YEAR = r"(\d{1,4})(\s*a\.?\s?C\.?)?"
_RANGE = re.compile(rf"\((?:c\.\s*)?(?:(até)\s+)?{_YEAR}(?:\s*[–—-]\s*(?:{_YEAR}|(presente|atualidade|hoje|dias atuais)))?\)", re.IGNORECASE)


def _year(n: str | None, bce: str | None) -> int | None:
    return None if n is None else (-int(n) if bce else int(n))


def parse_years(title: str) -> tuple[str, int | None, int | None]:
    """'Império (1822–1889)' -> ('Império', 1822, 1889); '(até 1500)' -> end only; '(1889–presente)' -> open end."""
    m = _RANGE.search(title)
    if not m:
        return title.strip(), None, None
    until, a, abce, b, bbce, now = m.groups()
    clean = (title[: m.start()] + title[m.end():]).strip(" –-")
    if until:
        return clean, None, _year(a, abce)
    if b is None and not now:  # single year: a point in time, not a range
        return clean, _year(a, abce), _year(a, abce)
    return clean, _year(a, abce), None if now else _year(b, bbce)


def condense(text: str, limit: int) -> str:
    """Whole paragraphs while they fit; the first one is cut at the last sentence end before `limit`."""
    text = _MAINT.sub("", _H3PLUS.sub("", text))
    paras = [p.strip() for p in text.split("\n") if len(p.strip()) > 40]
    out = ""
    for p in paras:
        if out and len(out) + len(p) + 2 > limit:
            break
        if not out and len(p) > limit:
            cut = max(p.rfind(". ", 0, limit), p.rfind("? ", 0, limit))
            return p[: cut + 1] if cut > 0 else p[:limit].rsplit(" ", 1)[0] + "…"
        out = f"{out}\n\n{p}" if out else p
    return out


def _sections(text: str, level: int) -> list[tuple[str, str]]:
    eq = "=" * level
    parts = re.split(rf"^{eq} ([^=].*?) {eq}\s*$", text, flags=re.MULTILINE)  # [before, h1, body1, h2, body2, ...]
    return list(zip(parts[1::2], parts[2::2], strict=True))


def first_sentences(text: str, limit: int) -> str:
    """The first paragraph's leading sentences while they fit in `limit` (at least one, cut like condense())."""
    first = condense(text, 10**6).split(NL2, 1)[0]
    out = ""
    for sent in _SENTENCE.split(first):
        if out and len(out) + len(sent) + 1 > limit:
            break
        out = f"{out} {sent}" if out else sent
    return out if len(out) <= limit else condense(out, limit)


def period_text(body: str, level: int) -> str:
    """spec 026: intro paragraphs + one "<title>: <first sentences>" paragraph per subsection (level + 1), by whole paragraphs."""
    subs = [(t.strip(), b) for t, b in _sections(body, level + 1) if not SKIP.match(t.strip())]
    intro = re.split(rf"^{'=' * (level + 1)} ", body, maxsplit=1, flags=re.MULTILINE)[0] if subs else body
    firsts = [(t, first_sentences(b, SUB_CHARS)) for t, b in subs]
    paras = [x for x in [condense(intro, PERIOD_CHARS), *(f"{t}: {f}" for t, f in firsts if f)] if x]
    out = ""
    for x in paras:
        if out and len(out) + len(x) + 2 > PERIOD_WITH_SUBS:
            break
        out = f"{out}{NL2}{x}" if out else x
    return out


def _periods(sections: list[tuple[str, str]], level: int) -> list[dict[str, Any]]:
    out = []
    for title, body in sections:
        text = period_text(body, level)
        if text and not SKIP.match(title.strip()):
            clean, start, end = parse_years(title)
            out.append({"title": clean, "year_start": start, "year_end": end, "text": text})
    return out


def split(extract: str, country_article: bool = False) -> dict[str, Any]:
    """History article: lead = summary, level-2 sections = periods (level 3 when level 2 gives < 3, e.g. Japan).
    Country article (no pt "História de X"): its "História" section = summary, its level-3 subsections = periods."""
    if country_article:
        body = next((b for t, b in _sections(extract, 2) if t.strip().lower() == "história"), None)
        if body is None:
            return {"summary": None, "periods": []}
        intro = re.split(r"^=== ", body, maxsplit=1, flags=re.MULTILINE)[0]
        return {"summary": condense(intro, SUMMARY_CHARS) or None, "periods": _periods(_sections(body, 3), 3)}
    lead = re.split(r"^==", extract, maxsplit=1, flags=re.MULTILINE)[0]
    kept = "".join(f"== {t} ==\n{b}" for t, b in _sections(extract, 2) if not SKIP.match(t.strip()))
    periods = _periods(_sections(kept, 2), 2)
    if len(periods) < 3:
        periods = _periods(_sections(kept, 3), 3) or periods
    summary = re.sub(r"^História d", "A história d", condense(lead, SUMMARY_CHARS))  # spec 026: the lead drops the article
    return {"summary": summary or None, "periods": periods}


def fetch(client: httpx.Client, title: str, f: Path, refresh: bool) -> dict[str, Any]:
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    j = _get_json(client, WIKI_API, {"action": "query", "prop": "extracts|info|revisions", "explaintext": "1",
                                     "exsectionformat": "wiki", "titles": title, "redirects": "1", "inprop": "url",
                                     "rvprop": "ids", "format": "json", "formatversion": "2"})
    page = j["query"]["pages"][0]
    raw = {"retrieved_at": datetime.now(UTC).isoformat(), "title": page.get("title"), "url": page.get("fullurl"),
           "revision": (page.get("revisions") or [{}])[0].get("revid"), "extract": page.get("extract") or ""}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    time.sleep(1)  # API:Etiquette: requests in series
    return raw


def collect(client: httpx.Client, countries: dict[str, Any], cache: Path, refresh: bool,
            only: list[str] | None = None) -> dict[str, Any]:
    titles: dict[str, str] = {}
    for r in _cached(client, cache / "_articles.json", ARTICLES_QUERY, refresh):
        iso2 = r["iso2"]["value"]
        titles.setdefault(iso2, unquote(r["pt"]["value"].rsplit("/", 1)[-1]).replace("_", " "))
    out: dict[str, Any] = {}
    for iso2 in sorted(countries):
        if (only and iso2 not in only) or iso2 not in titles:
            continue
        raw = fetch(client, titles[iso2], cache / f"{iso2}.json", refresh)
        if not raw["extract"]:
            continue
        part = split(raw["extract"], country_article=not raw["title"].startswith("História"))  # redirect to the country page
        if part["summary"] or part["periods"]:
            out[iso2] = {"title": raw["title"], "url": raw["url"], "revision": raw["revision"],
                         "retrieved_at": raw["retrieved_at"], **part}
    return {"source": {"id": "wikipedia-pt", "title": "Wikipédia em português", "url": "https://pt.wikipedia.org/",
                       "license": "CC BY-SA 4.0"}, "countries": out}


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    countries = json.loads((s.out_dir / "wikidata.json").read_text(encoding="utf-8"))["countries"]
    only = [a for a in sys.argv[2:] if re.fullmatch(r"[A-Z]{2}", a)]
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        payload = collect(client, countries, s.cache_dir / "wikipedia" / "history", "--refresh" in sys.argv, only)
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "history.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    cs = payload["countries"]
    print(f"wrote data_out/history.json: {len(cs)}/{len(countries)} countries, "
          f"{sum(len(c['periods']) for c in cs.values())} periods, {sum(c['summary'] is not None for c in cs.values())} summaries")
