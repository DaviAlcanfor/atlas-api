"""Leaders ETL (spec 006, v1.1): heads of state / government per country -> data_out/leaders.json.

Wikidata (CC0), same endpoint, cache and politeness as pipeline.py: one query for the offices,
then ONE query per country, 1 s pause, raw rows cached in etl_cache/wikidata/leaders/<ISO2>.json.
  country -> office: P1906 (head of state), P1313 (head of government)
  holder: humans (P31 Q5, filtered in Python: in SPARQL it times out) with p:P39 = office, qualifiers P580 start / P582 end
  party: P102, the one valid at the term start (qualifiers P580/P582; unqualified = always valid);
         several candidates = null (we never choose)
  link: pt.wikipedia sitelink, else en.
Same office for both roles (presidential systems): emitted ONCE as head_of_state; the web merges.

Photos (P18): Commons licences are PER FILE. Docs read 2026-11-11 (MediaWiki API
prop=imageinfo&iiprop=extmetadata): `LicenseShortName` and `Artist` (HTML) come from the file page
templates. A photo is kept only when BOTH are present; otherwise image = null.

Hotlinking (spec 019): Commons asks re-users to avoid it. When IMAGE_BUCKET_URL and
SUPABASE_SERVICE_KEY are set, mirror_images() copies each 320px thumbnail once to the public
Supabase Storage bucket `atlas-images` and `image.url` points there; unset = Commons URL (fallback).
"""

import hashlib
import html
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

from etl.settings import get_etl_settings
from etl.wikidata.pipeline import ENDPOINT, LABEL, STATE, _qid, _v

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_WIDTH = 320
# Step 1, one query for all countries: their offices. Step 2, per country, the holders of those
# offices passed in VALUES (joining country -> office -> holders in one query times out).
OFFICES_QUERY = (
    f"SELECT ?iso2 ?role ?office ?officeLabel WHERE {{ {STATE} "
    '{ ?c wdt:P1906 ?office. BIND("head_of_state" AS ?role) } UNION '
    '{ ?c wdt:P1313 ?office. BIND("head_of_government" AS ?role) } '
    f"{LABEL} }}"
)
LEADERS_QUERY = """SELECT ?role ?office ?person ?personLabel ?start ?end ?party ?partyLabel
?pstart ?pend ?image ?pt ?en ?human WHERE {{
 VALUES (?office ?role) {{ {offices} }}
 ?person p:P39 ?st. ?st ps:P39 ?office; wikibase:rank ?rank.
 FILTER(?rank != wikibase:DeprecatedRank)
 BIND(EXISTS {{ ?person wdt:P31 wd:Q5 }} AS ?human)
 OPTIONAL {{ ?st pq:P580 ?start }} OPTIONAL {{ ?st pq:P582 ?end }}
 OPTIONAL {{ ?person p:P102 ?pst. ?pst ps:P102 ?party.
            OPTIONAL {{ ?pst pq:P580 ?pstart }} OPTIONAL {{ ?pst pq:P582 ?pend }} }}
 OPTIONAL {{ ?person wdt:P18 ?image }}
 OPTIONAL {{ ?pt schema:about ?person; schema:isPartOf <https://pt.wikipedia.org/> }}
 OPTIONAL {{ ?en schema:about ?person; schema:isPartOf <https://en.wikipedia.org/> }}
 {label} }}"""


def _get_json(client: httpx.Client, url: str, params: dict[str, str], retries: int = 4) -> Any:
    """GET with retries: 429 waits Retry-After; 5xx / dropped connections back off 15 s, 30 s...
    `retries=1`: a 5xx fails at once (WDQS query timeouts are 500s: retrying the same query only burns minutes)."""
    for attempt in range(1, retries + 1):
        try:
            r = client.get(url, params=params)
        except httpx.TransportError:
            time.sleep(15 * attempt)
            continue
        if r.status_code == 429:
            time.sleep(min(int(r.headers.get("Retry-After", "30")), 120))
            continue
        if r.status_code >= 500 and attempt < retries:
            time.sleep(15 * attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up after retries: {url}")


def _cached(client: httpx.Client, f: Path, query: str, refresh: bool, retries: int = 4) -> list[Any]:
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))["rows"]  # type: ignore[no-any-return]
    rows = _get_json(client, ENDPOINT, {"query": query, "format": "json"}, retries)["results"]["bindings"]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"retrieved_at": datetime.now(UTC).isoformat(), "query": query,
                             "rows": rows}, ensure_ascii=False), encoding="utf-8")
    time.sleep(1)  # polite: one query at a time
    return rows  # type: ignore[no-any-return]


def offices(client: httpx.Client, cache: Path, refresh: bool) -> dict[str, list[dict[str, str]]]:
    """ISO2 -> [{role, office (Q-id), label}] from P1906 / P1313."""
    out: dict[str, list[dict[str, str]]] = {}
    for r in _cached(client, cache / "_offices.json", OFFICES_QUERY, refresh):
        out.setdefault(_v(r, "iso2") or "", []).append(
            {"role": _v(r, "role") or "", "office": _qid(_v(r, "office")) or "",
             "label": _v(r, "officeLabel") or ""})
    return out


def fetch_country(client: httpx.Client, iso2: str, offs: list[dict[str, str]], cache: Path,
                  refresh: bool) -> list[Any]:
    values = " ".join(f'(wd:{o["office"]} "{o["role"]}")' for o in offs)
    rows = _cached(client, cache / f"{iso2}.json",
                   LEADERS_QUERY.format(offices=values, label=LABEL), refresh)
    labels = {o["office"]: o["label"] for o in offs}
    for r in rows:  # office label comes from step 1
        r["officeLabel"] = {"value": labels.get(_qid(_v(r, "office")) or "", "")}
    return rows


def _date(v: str | None) -> str | None:
    """Wikidata xsd:dateTime -> 'YYYY-MM-DD' (precision is not exported; keep what is given)."""
    return v[:10] if v and re.match(r"\d{4}-\d{2}-\d{2}", v) else None


def _file(uri: str | None) -> str | None:
    return unquote(uri.rsplit("/", 1)[-1]) if uri else None  # Special:FilePath/<name>


def build_leaders(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows of one country -> Leader records (image = Commons file name, resolved later)."""
    shared = {(_v(r, "office")) for r in rows if _v(r, "role") == "head_of_state"} & {
        _v(r, "office") for r in rows if _v(r, "role") == "head_of_government"}
    terms: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for r in rows:
        office, role = _v(r, "office"), _v(r, "role") or ""
        if _v(r, "human") != "true":  # P39 is also set on non-humans (e.g. election items)
            continue
        if office in shared and role == "head_of_government":
            continue
        pid = _qid(_v(r, "person")) or ""
        key = (pid, role, _qid(office) or "", _date(_v(r, "start")))
        t = terms.setdefault(key, {
            "person_id": pid, "name": _v(r, "personLabel"), "role": role,
            "office": _v(r, "officeLabel"), "office_id": _qid(office),
            "start": _date(_v(r, "start")), "end": _date(_v(r, "end")),
            "parties": {}, "images": set(),
            "wikipedia_url": _v(r, "pt") or _v(r, "en"),
        })
        if t["end"] is None:
            t["end"] = _date(_v(r, "end"))
        if (party := _qid(_v(r, "party"))) and _v(r, "partyLabel"):
            t["parties"][(party, _date(_v(r, "pstart")), _date(_v(r, "pend")))] = _v(r, "partyLabel")
        if f := _file(_v(r, "image")):
            t["images"].add(f)
    out = []
    for t in terms.values():
        start = t["start"]
        valid = {(p, name) for (p, ps, pe), name in t.pop("parties").items()
                 if start is None or ((ps is None or ps <= start) and (pe is None or pe >= start))}
        t["party"] = {"id": next(iter(valid))[0], "name": next(iter(valid))[1]} if len(valid) == 1 else None
        images = sorted(t.pop("images"))
        t["image_file"] = images[0] if len(images) == 1 else None  # several P18 = no pick
        out.append(t)
    # Unlabeled people come back as their Q-id: never serve a Q-id as a name.
    out = [t for t in out if t["name"] and not re.fullmatch(r"Q\d+", t["name"])]
    return sorted(out, key=lambda t: (t["start"] or "", t["person_id"], t["role"]))


def _strip_html(s: str) -> str:
    """Commons HTML -> text; hidden spans (Commons repeats "Unknown author" in one) are dropped."""
    s = re.sub(r'<(\w+)[^>]*display:\s*none[^>]*>.*?</\1>', "", s, flags=re.DOTALL)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", s)).split())


def commons_images(client: httpx.Client, files: set[str], cache: Path, refresh: bool,
                   accept_without_artist: re.Pattern[str] | None = None) -> dict[str, dict[str, str]]:
    """File name -> {url, credit, license}; files without licence AND artist are left out, except when the licence matches
    `accept_without_artist` (flags: public domain, credited to Wikimedia Commons)."""
    f = cache / "commons_imageinfo.json"
    known: dict[str, Any] = {} if refresh or not f.exists() else json.loads(f.read_text(encoding="utf-8"))
    todo = sorted(files - set(known))
    for i in range(0, len(todo), 50):  # API limit: 50 titles per request
        batch = todo[i:i + 50]
        data = _get_json(client, COMMONS_API, {
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": str(THUMB_WIDTH),
            "titles": "|".join("File:" + x for x in batch)})
        norm = {n["to"]: n["from"] for n in data["query"].get("normalized", [])}
        for page in data["query"]["pages"].values():
            name = norm.get(page["title"], page["title"]).removeprefix("File:")
            known[name] = (page.get("imageinfo") or [None])[0]
        for x in batch:
            known.setdefault(x, None)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(known, ensure_ascii=False), encoding="utf-8")
        time.sleep(1)
    out = {}
    for name in files:
        info = known.get(name) or {}
        meta = info.get("extmetadata") or {}
        lic = _strip_html((meta.get("LicenseShortName") or {}).get("value", ""))
        artist = _strip_html((meta.get("Artist") or {}).get("value", ""))
        url = (info.get("thumburl") or info.get("url") or "").split("?", 1)[0]  # drop utm_* tracking
        if lic and url and (artist or (accept_without_artist and accept_without_artist.search(lic))):
            out[name] = {"url": url, "credit": f"{artist} / Wikimedia Commons" if artist else "Wikimedia Commons", "license": lic}
    return mirror_images(client, out, cache)


BUCKET = "atlas-images"


def mirror_images(client: httpx.Client, images: dict[str, dict[str, str]],
                  cache: Path) -> dict[str, dict[str, str]]:
    """Copy thumbnails to Supabase Storage (upsert) and repoint `url`; no-op without credentials.
    Uploaded URLs are remembered in <cache>/mirrored.json, so each file is copied once."""
    s = get_etl_settings()
    if not (s.image_bucket_url and s.supabase_service_key):
        return images
    base, key = s.image_bucket_url.rstrip("/"), s.supabase_service_key.get_secret_value()
    f = cache / "mirrored.json"
    done: dict[str, str] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    out = {}
    for name, img in images.items():
        src = img["url"]
        if src not in done:
            r = client.get(src)
            r.raise_for_status()
            obj = hashlib.sha256(src.encode()).hexdigest()[:24] + Path(urlparse(src).path).suffix.lower()
            up = client.post(f"{base}/object/{BUCKET}/{obj}", content=r.content, headers={
                "Authorization": f"Bearer {key}", "x-upsert": "true",
                "Content-Type": r.headers.get("content-type", "application/octet-stream")})
            up.raise_for_status()
            done[src] = f"{base}/object/public/{BUCKET}/{obj}"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(done), encoding="utf-8")
            time.sleep(0.2)  # polite to upload.wikimedia.org
        out[name] = {**img, "url": done[src]}
    return out


def collect(client: httpx.Client, countries: dict[str, Any], cache: Path, refresh: bool,
            only: list[str] | None = None) -> dict[str, Any]:
    by_country: dict[str, list[dict[str, Any]]] = {}
    retrieved = datetime.now(UTC).isoformat()
    offs = offices(client, cache, refresh)
    for iso2 in sorted(countries):
        if only and iso2 not in only:
            continue
        by_country[iso2] = build_leaders(
            fetch_country(client, iso2, offs[iso2], cache, refresh)) if iso2 in offs else []
    files = {t["image_file"] for ls in by_country.values() for t in ls if t["image_file"]}
    images = commons_images(client, files, cache, refresh)
    for ls in by_country.values():
        for t in ls:
            t["image"] = images.get(t.pop("image_file") or "")
    return {
        "source": {"id": "wikidata", "title": "Wikidata", "url": "https://www.wikidata.org/",
                   "license": "CC0 1.0 (photos: per-file licence from Wikimedia Commons, see image.license)"},
        "retrieved_at": retrieved,
        "countries": by_country,
    }


def run() -> None:
    s = get_etl_settings()
    if not s.wikidata_contact:
        sys.exit("Set WIKIDATA_CONTACT (email or URL) in the env or .env: required by the Wikimedia User-Agent policy.")
    ua = f"atlas-api/0.1 ({s.wikidata_contact}) python-httpx/{httpx.__version__}"
    countries = json.loads((s.out_dir / "wikidata.json").read_text(encoding="utf-8"))["countries"]
    with httpx.Client(headers={"User-Agent": ua}, timeout=70) as client:
        payload = collect(client, countries, s.cache_dir / "wikidata" / "leaders", "--refresh" in sys.argv)
    write(payload, s.out_dir)


def write(payload: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "leaders.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    cs = payload["countries"]
    n = sum(len(v) for v in cs.values())
    print(f"wrote data_out/leaders.json: {n} terms, {sum(bool(v) for v in cs.values())}/{len(cs)} countries")
    print(f"  with image: {sum(t['image'] is not None for v in cs.values() for t in v)}/{n}")
    print(f"  with party: {sum(t['party'] is not None for v in cs.values() for t in v)}/{n}")
