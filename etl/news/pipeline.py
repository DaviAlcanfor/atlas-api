"""Geopolitical news (spec 008): GDELT candidates -> GPT-6 Luna decisions -> data_out/news.json.

GDELT DOC 2.0 API (blog.gdeltproject.org/gdelt-doc-2-0-api-debuts, terms at gdeltproject.org/about.html#termsofuse, read
2026-11-14): "all datasets released by the GDELT Project are available for unlimited and unrestricted use", "You may
redistribute, rehost, republish, and mirror any of the GDELT datasets in any form", and "any use or redistribution of the data
must include a citation to the GDELT Project" + "a link to this website (https://www.gdeltproject.org/)". The API answers
"Please limit requests to one every 5 seconds" (and blocks shared IPs, like this office's), so queries run one at a time,
6 s apart, from GitHub Actions. ArtList returns up to 250 articles; only title, URL, domain, language and date are kept.

Classification: openai/gpt-6-luna-decisions through the Vercel AI Gateway (POST https://ai-gateway.vercel.sh/v1/decisions,
key AI_GATEWAY_API_KEY; owner's choice 2026-11-13, replaces the Jev of the first spec draft). One request per new headline
with every question: `geo` (predicate), `type` (choice), and `about_<ISO2>` (predicate) for at most 5 candidate countries found
in the title by name or demonym (Wikidata labels, CC0). ~512 input tokens each, output free: about US$ 0.00005 per headline.
Policy in code: geo >= 0.5 kept (the API's default feed shows >= 0.7), a country is attached when about >= 0.6. A headline
whose classification fails is left out of this run (never published unclassified). Results are cached per URL.
"""

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import yaml

from etl.settings import get_etl_settings
from etl.wikidata.leaders import _cached

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
DECISIONS = "https://ai-gateway.vercel.sh/v1/decisions"
MODEL = "openai/gpt-6-luna-decisions"
QUERIES = Path("content/news_queries.yaml")
KEEP_P, COUNTRY_P = 0.5, 0.6
MAX_COUNTRIES = 5
RETENTION_DAYS = 30
LANG = {"portuguese": "pt", "english": "en", "spanish": "es", "french": "fr", "german": "de", "italian": "it"}
TYPES = {
    "conflict": "conflito armado, guerra, ataque, bombardeio, operação militar",
    "diplomacy": "negociação, cúpula, visita oficial, relações entre países, cessar-fogo em negociação",
    "election": "eleição, votação, referendo, campanha eleitoral, resultado de eleição",
    "sanctions": "sanções, embargo, tarifas punitivas entre países",
    "agreement": "acordo ou tratado assinado entre países, aliança",
    "protest": "protestos em massa, greves gerais, revoltas contra o governo",
    "coup": "golpe de Estado, tentativa de golpe, junta militar",
    "economy_policy": "política econômica com efeito internacional: comércio exterior, dívida soberana, bancos centrais",
    "other": "outro assunto geopolítico que não se encaixa acima",
}
GEO_Q = ("A manchete trata de relações entre países, conflito armado, segurança internacional, diplomacia, sanções, eleições "
         "ou mudança de governo, com impacto além de um assunto local? Esporte, celebridades, crime comum, acidentes e "
         "economia doméstica não contam.")
NAMES_QUERY = """SELECT ?iso2 ?label ?demonym WHERE { ?c wdt:P31 wd:Q3624078; wdt:P297 ?iso2. FILTER NOT EXISTS { ?c wdt:P576 ?x }
 OPTIONAL { ?c rdfs:label ?label. FILTER(LANG(?label) IN ("pt", "en", "es")) }
 OPTIONAL { ?c wdt:P1549 ?demonym. FILTER(LANG(?demonym) IN ("pt", "en", "es")) } }"""


def norm(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def clean_url(url: str) -> str:
    """Drops tracking parameters and the fragment, so the same article from two queries is one item."""
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urlencode(q), ""))


def item_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def parse_article(a: dict[str, Any]) -> dict[str, Any] | None:
    """GDELT ArtList article -> our item; None without a usable title, URL or date."""
    title, url, seen = (a.get("title") or "").strip(), a.get("url") or "", a.get("seendate") or ""
    m = re.fullmatch(r"(\d{8})T(\d{6})Z", seen)
    if len(title) < 15 or not url.startswith("http") or not m:
        return None
    published = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    u = clean_url(url)
    return {"id": item_id(u), "url": u, "title": re.sub(r"\s+", " ", title), "outlet": (a.get("domain") or urlsplit(u).netloc).lower(),
            "language": LANG.get((a.get("language") or "").lower(), (a.get("language") or "")[:2].lower() or None),
            "published_at": published.isoformat()}


ALIASES = {"eua": "US", "eeuu": "US"}  # abbreviations headlines use all the time


def name_index(rows: list[dict[str, Any]]) -> list[tuple[re.Pattern[str], str]]:
    """(word-bounded pattern, ISO2) for every label and demonym, longest first (so "Coreia do Sul" wins). Matching is on
    accent-free lowercase text, except names under 4 letters, which keep their accents ("irã", not the word "ira")."""
    names: dict[str, str] = dict(ALIASES)
    for r in rows:
        iso2 = r["iso2"]["value"]
        for k in ("label", "demonym"):
            raw = r.get(k, {}).get("value", "").strip().lower()
            v = norm(raw)
            if len(v) >= 4:
                names.setdefault(v, iso2)
            elif len(v) == 3 and raw != v:
                names.setdefault(raw, iso2)
    return [(re.compile(rf"(?<![\w]){re.escape(n)}(?![\w])"), names[n]) for n in sorted(names, key=len, reverse=True)]


def candidates(title: str, index: list[tuple[re.Pattern[str], str]]) -> list[str]:
    plain, accented, out = norm(title), title.lower(), []
    for pat, iso2 in index:
        t = plain if pat.pattern.isascii() else accented
        if iso2 not in out and pat.search(t):
            out.append(iso2)
            plain, accented = pat.sub(" ", plain), pat.sub(" ", accented)  # "Coreia do Sul" is not also "Sul..."
        if len(out) == MAX_COUNTRIES:
            break
    return out


def classify(http: httpx.Client, key: str, item: dict[str, Any], cands: list[str], names: dict[str, str]) -> dict[str, Any] | None:
    questions: list[dict[str, Any]] = [
        {"type": "predicate", "name": "geo", "instructions": GEO_Q},
        {"type": "choice", "name": "type", "instructions": "Qual o tipo do evento da manchete?",
         "choices": [{"value": k, "description": v} for k, v in TYPES.items()]},
    ]
    questions += [{"type": "predicate", "name": f"about_{c}",
          "instructions": f"A manchete é sobre {names.get(c, c)} (como ator ou lugar do evento), e não apenas uma menção de passagem?"}
         for c in cands]
    text = f"Manchete: {item['title']}\nVeículo: {item['outlet']}\nIdioma: {item['language']}"
    try:
        r = http.post(DECISIONS, headers={"Authorization": f"Bearer {key}"}, timeout=60,
                      json={"model": MODEL, "input": text, "questions": questions})
        r.raise_for_status()
        ans = {a["name"]: a for a in r.json()["answers"]}
        return {"geo": float(ans["geo"]["probability"]), "type": ans["type"]["choice"],
                "about": {c: float(ans[f"about_{c}"]["probability"]) for c in cands if f"about_{c}" in ans}}
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


def apply_policy(item: dict[str, Any], c: dict[str, Any]) -> dict[str, Any] | None:
    if c["geo"] < KEEP_P:
        return None
    return {**item, "event_type": c["type"] if c["type"] in TYPES else "other", "geopolitical_p": round(c["geo"], 3),
            "countries": [{"iso2": k, "p": round(v, 3)} for k, v in sorted(c["about"].items(), key=lambda kv: -kv[1]) if v >= COUNTRY_P]}


def fetch_gdelt(http: httpx.Client, queries: list[str], timespan: str) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    titles: set[str] = set()
    for i, q in enumerate(queries):
        if i:
            time.sleep(6)  # GDELT: one request every 5 seconds
        arts = None
        for attempt in range(4):  # GDELT answers a plain-text "Please limit requests..." when the (shared) IP went too fast
            r = http.get(GDELT, params={"query": q, "mode": "ArtList", "format": "json", "maxrecords": "250",
                                        "timespan": timespan, "sort": "DateDesc"})
            try:
                arts = r.json().get("articles", [])
                break
            except ValueError:
                print(f"  GDELT refused query {i + 1} (attempt {attempt + 1}): {r.text[:80]!r}")
                time.sleep(15 * (attempt + 1))
        if arts is None:
            continue
        for a in arts:
            it = parse_article(a)
            if it and it["url"] not in seen and norm(it["title"]) not in titles:
                seen[it["url"]] = it
                titles.add(norm(it["title"]))
        print(f"  query {i + 1}/{len(queries)}: {len(arts)} articles")
    return list(seen.values())


def run() -> None:
    s = get_etl_settings()
    key = os.environ.get("AI_GATEWAY_API_KEY") or _dotenv("AI_GATEWAY_API_KEY")
    if not key:
        sys.exit("Set AI_GATEWAY_API_KEY (env or .env): the Vercel AI Gateway key.")
    conf = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    cache = s.cache_dir / "news"
    cache.mkdir(parents=True, exist_ok=True)
    done_f = cache / "classified.json"
    done: dict[str, Any] = json.loads(done_f.read_text(encoding="utf-8")) if done_f.exists() else {}
    ua = f"atlas-api/0.1 ({s.wikidata_contact or 'https://github.com/DaviAlcanfor/atlas-api'}) python-httpx/{httpx.__version__}"
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as http:
        rows = _cached(http, cache / "country_names.json", NAMES_QUERY, False)
        index = name_index(rows)
        pt = {r["iso2"]["value"]: r["label"]["value"] for r in rows if r.get("label", {}).get("xml:lang") == "pt"}
        items = fetch_gdelt(http, conf["queries"], conf.get("timespan", "6h"))
        new = [it for it in items if it["url"] not in done]
        print(f"GDELT: {len(items)} unique articles, {len(new)} not classified yet")

        def one(it: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
            return it["url"], classify(http, key, it, candidates(it["title"], index), pt)

        with ThreadPoolExecutor(4) as pool:
            for url, c in pool.map(one, new):
                if c is not None:  # a failure is retried next run
                    done[url] = {"c": c, "at": datetime.now(UTC).isoformat()}
    cutoff = (datetime.now(UTC) - timedelta(days=RETENTION_DAYS)).isoformat()
    done = {u: v for u, v in done.items() if v["at"] >= cutoff}
    done_f.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    kept = [x for it in items if it["url"] in done and (x := apply_policy(it, done[it["url"]]["c"]))]
    out = {"source": {"id": "gdelt", "title": "The GDELT Project (DOC 2.0 API)", "url": "https://www.gdeltproject.org/",
                      "license": "Uso livre com citação ao GDELT Project"},
           "classifier": MODEL, "fetched_at": datetime.now(UTC).isoformat(), "items": kept}
    s.out_dir.mkdir(parents=True, exist_ok=True)
    (s.out_dir / "news.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/news.json: {len(kept)} geopolitical of {len(items)} ({sum(x['geopolitical_p'] >= 0.7 for x in kept)} with p >= 0.7)")


def _dotenv(name: str) -> str | None:
    f = Path(".env")
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"') or None
    return None
