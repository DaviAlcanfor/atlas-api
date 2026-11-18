"""spec 042: Wikipedia summary of each historical entity of the map -> data_out/polity_summaries.json.

Terms read 2026-11-18:
- Wikimedia Terms of Use s.7: text is CC BY-SA 4.0; reusers credit "Through hyperlink (where possible) or URL to the page or
  pages that you are reusing" (or a list of authors) and give "a licensing notice stating which license the work is released
  under ... along with either a hyperlink or URL to the text of the license". "Non-text media on the Projects are available under
  a variety of different licenses": each image is licensed on its own file page, so the thumbnail URL is stored but never served.
- mediawiki.org/wiki/Wikimedia_APIs/Rate_limits: unauthenticated bots with a compliant User-Agent get 200 requests/minute
  (10/min without identification). We stay at ~6 requests/second only while cached files last; real runs are one request per entity.
- Wikimedia User-Agent policy asks for "<client name>/<version> (<contact information>)" and blocks generic agents
  (python-requests, curl). Owner's rule: no personal contact in requests, so the agent is the descriptive client name only
  ("atlas-etl/1.0"); if Wikimedia blocks it, add a contact then.

Titles: the pt.wikipedia sitelink of the Q-id (Wikidata, CC0, cached by `etl cliopatria`), else the English title Cliopatria
carries. Text: REST `page/summary/{title}` -> `extract` (plain text, never `extract_html`), `content_urls.desktop.page`,
`revision`, `timestamp`, `thumbnail.source`. Raw answers are cached in etl_cache/wikipedia/polities/<QID>_<lang>.json.
Run: `python -m etl wikipedia-polities [Q-ids...] [--refresh]` (no Q-ids = every entity of the Cliopatria release).
"""
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import httpx

from etl.cliopatria.pipeline import labels, load
from etl.settings import get_etl_settings
from etl.wikidata.leaders import _get_json

UA = "atlas-etl/1.0"
LICENSE = "CC BY-SA 4.0"
PAUSE = 0.15  # seconds between live requests


def titles(rows: list[dict[str, Any]], labs: dict[str, dict[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """Q-id -> [(lang, title)] in order of preference: pt sitelink, then the English title of the Cliopatria row."""
    out: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        q = r["Wikidata"]
        if r["Type"] != "POLITY" or r["Name"].startswith("(") or not q.startswith("Q") or q in out:
            continue
        cand = []
        if pt := labs.get(q, {}).get("wikipedia_pt"):
            cand.append(("pt", unquote(pt.rsplit("/", 1)[-1]).replace("_", " ")))
        if r["Wikipedia"]:
            cand.append(("en", r["Wikipedia"]))
        out[q] = cand
    return out


def parse(lang: str, j: dict[str, Any], now: str) -> dict[str, Any] | None:
    """One REST summary -> a row; None when there is no usable text (disambiguation pages have a short, useless extract)."""
    extract = (j.get("extract") or "").strip()
    page = (j.get("content_urls") or {}).get("desktop", {}).get("page")
    if j.get("type") != "standard" or not extract or not page:
        return None
    return {"lang": lang, "title": j["title"], "extract": extract, "page_url": page, "license": LICENSE,
            "revision": int(j["revision"]) if j.get("revision") else None,
            "fetched_at": now, "thumbnail_url": (j.get("thumbnail") or {}).get("source")}


def fetch(client: httpx.Client, lang: str, title: str, f: Path, refresh: bool) -> dict[str, Any] | None:
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe='')}"
    try:
        j = _get_json(client, url, {})
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            raise
        j = None
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j), encoding="utf-8")
    time.sleep(PAUSE)
    return j  # type: ignore[no-any-return]


def run() -> None:
    s = get_etl_settings()
    only = [a for a in sys.argv[2:] if re.fullmatch(r"Q[0-9]+", a)]
    refresh = "--refresh" in sys.argv
    cache = s.cache_dir / "wikipedia" / "polities"
    lab_rows: list[Any] = []
    for f in sorted((s.cache_dir / "cliopatria").glob("labels_*.json")):
        lab_rows += json.loads(f.read_text(encoding="utf-8"))["rows"]
    cand = titles(load(s.cache_dir / "cliopatria"), labels(lab_rows))
    now = datetime.now(UTC).isoformat()
    items = []
    with httpx.Client(headers={"User-Agent": UA}, timeout=30) as client:
        for q in sorted(only or cand):
            for lang, title in cand.get(q, []):
                j = fetch(client, lang, title, cache / f"{q}_{lang}.json", refresh)
                if j and (row := parse(lang, j, now)):
                    items.append({"wikidata_qid": q, **row})
                    break
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "polity_summaries.json").write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(only or cand)
    print(f"wrote data_out/polity_summaries.json: {len(items)}/{n} entities with a summary "
          f"({sum(i['lang'] == 'pt' for i in items)} pt, {sum(i['lang'] == 'en' for i in items)} en)")
