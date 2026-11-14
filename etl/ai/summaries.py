"""Country summary (spec 022): a short pt-BR text built by a FORMULA from facts the Atlas API already serves, then lightly
reworded by a small model for readability.

Facts: read from the Atlas API itself (ATLAS_API_URL, default production): country, profile, economy, history, leaders.
Text: `template()` fills fixed pt-BR sentences with those facts (free, deterministic, nothing invented). `polish()` asks
openai/gpt-6-luna through the Vercel AI Gateway (OpenAI-compatible endpoint https://ai-gateway.vercel.sh/v1/chat/completions,
key AI_GATEWAY_API_KEY; docs read 2026-11-13) to reword it without adding anything. A check keeps the reworded text only if
every number in it already appears in the formula's text; otherwise the formula's text is used. Owner's choice (2026-11-13):
formula first, GPT-6 Luna for the rewording (~US$ 0.10 / 0.50 per million tokens: cents for every country).
Cached by a hash of model + prompt + formula text in etl_cache/ai/summaries/: a re-run only pays for countries that changed.
"""

import hashlib
import json
import os
import re
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from etl.settings import get_etl_settings

MODEL = "openai/gpt-6-luna"
GATEWAY = "https://ai-gateway.vercel.sh/v1/chat/completions"
PROMPT_VERSION = 2
WORKERS = 2  # requests in flight, to the gateway and to the Atlas API (48 at once once took the API down)

POLISH = """Reescreva o texto abaixo em português do Brasil para ficar mais fácil e agradável de ler.
Regras: mantenha EXATAMENTE os mesmos fatos, números e anos; não acrescente nenhuma informação, opinião ou adjetivo de valor;
não remova fatos; frases curtas; sem listas e sem markdown. Responda só com o JSON {"tldr": "...", "now": "..."}."""
NUM = re.compile(r"\d+(?:[.,]\d+)*")


# --- number formatting (pt-BR) -----------------------------------------------------------------------------------------
def _dec(v: float, nd: int) -> str:
    s = f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s[:-2] if nd and s.endswith(",0") else s


def big(v: float) -> str:
    """214_211_951 -> '214 milhões'; 2.3e12 -> '2,3 trilhões'; below a thousand: the number itself."""
    for div, one, many in ((1e12, "trilhão", "trilhões"), (1e9, "bilhão", "bilhões"), (1e6, "milhão", "milhões"), (1e3, "mil", "mil")):
        if abs(v) >= div:
            txt = _dec(v / div, 0 if v / div >= 100 else 1)
            return f"{txt} {one if txt == '1' else many}"
    return _dec(v, 0)


def pct(v: float) -> str:
    return f"{_dec(v, 1)}%"


# --- facts -------------------------------------------------------------------------------------------------------------
def _get(client: httpx.Client, base: str, path: str) -> Any:
    r = client.get(base + path)
    return r.json() if r.status_code == 200 else None


def facts_for(client: httpx.Client, base: str, iso2: str) -> dict[str, Any] | None:
    """Facts from the Atlas API keyed for the formula; None when the country itself is missing."""
    c = _get(client, base, f"/v1/countries/{iso2}")
    if not c:
        return None
    ind: dict[str, dict[str, Any]] = {}
    sources = {s["id"] for s in c.get("sources") or []}
    prof = _get(client, base, f"/v1/countries/{iso2}/profile") or {}
    for g in prof.get("groups", []):
        for i in g["indicators"]:
            ind[i["id"]] = {"value": i["value"], "year": i["year"], "median": (i.get("world") or {}).get("median")}
    sources |= {s["id"] for s in prof.get("sources") or []}
    eco = _get(client, base, f"/v1/countries/{iso2}/economy") or {}
    for i in eco.get("indicators", []):
        if i.get("value") is not None and i["id"] not in ind:
            ind[i["id"]] = {"value": i["value"], "year": i["year"], "median": None}
    sources |= {s["id"] for s in eco.get("sources") or []}
    hist = _get(client, base, f"/v1/countries/{iso2}/history") or {}
    sources |= {s["id"] for s in hist.get("sources") or []}
    leaders = [x for x in (_get(client, base, f"/v1/countries/{iso2}/leaders") or {}).get("items", []) if not x.get("end")]
    if leaders:
        sources.add("wikidata")
    return {"name": c["name"], "region": c.get("region"), "capital": c.get("capital"), "area": c.get("area_km2"),
            "population": c.get("population"), "history": hist.get("summary"), "leaders": leaders, "ind": ind,
            "sources": sorted(sources)}


# --- the formula -------------------------------------------------------------------------------------------------------
def first_sentence(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s*\([^()]*:[^()]*\)", "", text)  # "(japonês: 日本の歴史 ...)", "(em inglês: ...)": noise in a summary
    m = re.search(r"^(.{40,400}?[.!?])(?:\s|$)", text.strip().replace("\n", " "))
    return m.group(1) if m else None


def _vs(i: dict[str, Any], fmt: Callable[[float], str]) -> str:
    """', acima da mediana mundial (0,762)' when the world median is known."""
    m = i.get("median")
    if m is None or i["value"] == m:
        return ""
    return f", {'acima' if i['value'] > m else 'abaixo'} da mediana mundial ({fmt(m)})"


def _count(v: float, unit: str) -> str:
    return f"{big(v)} de {unit}" if v >= 1e6 else f"{_dec(v, 0)} {unit}"


def template(f: dict[str, Any]) -> dict[str, str]:
    """The formula: fixed sentences, each one only when its facts exist."""
    ind = f["ind"]
    s = [f"{f['name']} fica {'na ' + f['region'] if f.get('region') else 'no mapa'}" + (f", com capital em {f['capital']}." if f.get("capital") else ".")]
    size = []
    if f.get("area"):
        size.append(_count(f["area"], "km²"))
    if pop := f.get("population"):
        size.append(_count(pop["value"], "habitantes") + (f" ({pop['year']})" if pop.get("year") else ""))
    if size:
        s.append("Tem " + " e ".join(size) + ".")
    if hs := first_sentence(f.get("history")):
        s.append(hs)
    eco = []
    if g := ind.get("NY.GDP.PCAP.PP.CD"):
        eco.append(f"o PIB per capita (PPC) é de US$ {big(g['value'])} ({g['year']})")
    if h := ind.get("HDR.HDI"):
        eco.append(f"o IDH é {_dec(h['value'], 3)} ({h['year']}{_vs(h, lambda v: _dec(v, 3))})")
    if le := ind.get("SP.DYN.LE00.IN"):
        eco.append(f"a expectativa de vida é de {_dec(le['value'], 0)} anos ({le['year']})")
    if eco:
        s.append(eco[0][0].upper() + eco[0][1:] + "".join("; " + e for e in eco[1:]) + ".")
    now = []
    if f["leaders"]:
        who = []
        for x in f["leaders"][:2]:
            party = (x.get("party") or {}).get("name")
            who.append(f"{x.get('office') or 'governante'}: {x['name']}" + (f" ({party})" if party and party != "sem partido" else "")
                       + (f", desde {x['start'][:4]}" if x.get("start") else ""))
        now.append("No governo: " + "; ".join(who) + ".")
    last = [(n, ind[k]) for k, n in (("NY.GDP.MKTP.KD.ZG", "crescimento do PIB"), ("FP.CPI.TOTL.ZG", "inflação"),
                                     ("SL.UEM.TOTL.ZS", "desemprego")) if k in ind]
    if last:
        now.append("Dados mais recentes: " + ", ".join(f"{n} de {pct(i['value'])} ({i['year']})" for n, i in last) + ".")
    return {"tldr": " ".join(s), "now": " ".join(now)}


# --- the rewording -----------------------------------------------------------------------------------------------------
def numbers(text: str) -> set[str]:
    return {n.rstrip(".,") for n in NUM.findall(text)}


def keeps_facts(new: dict[str, str], old: dict[str, str]) -> bool:
    """Every number of the reworded text must already be in the formula's text (no new or changed figures)."""
    return bool(new["tldr"]) and numbers(new["tldr"] + " " + new["now"]) <= numbers(old["tldr"] + " " + old["now"])


def polish(http: httpx.Client, key: str, t: dict[str, str]) -> dict[str, str] | None:
    """GPT-6 Luna rewording; None (= keep the formula) on any error or when a number changes."""
    try:
        r = http.post(GATEWAY, headers={"Authorization": f"Bearer {key}"}, timeout=90, json={
            "model": MODEL, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": POLISH}, {"role": "user", "content": json.dumps(t, ensure_ascii=False)}]})
        r.raise_for_status()
        out = json.loads(r.json()["choices"][0]["message"]["content"])
        new = {"tldr": str(out["tldr"]).strip(), "now": str(out.get("now") or "").strip()}
    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError):
        return None
    return new if keeps_facts(new, t) else None


def run() -> None:
    s = get_etl_settings()
    key = os.environ.get("AI_GATEWAY_API_KEY") or _dotenv("AI_GATEWAY_API_KEY")
    base = (os.environ.get("ATLAS_API_URL") or "https://atlas-api.fastapicloud.dev").rstrip("/")
    only = [a for a in sys.argv[2:] if re.fullmatch(r"[A-Z]{2}", a)]
    cache = s.cache_dir / "ai" / "summaries"
    cache.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60) as client:
        isos = only or sorted(x["iso2"] for x in client.get(base + "/v1/countries").json()["items"])

        def one(iso2: str) -> tuple[str, dict[str, Any] | None, str]:
            facts = facts_for(client, base, iso2)
            if not facts:
                return iso2, None, "no facts"
            t = template(facts)
            h = hashlib.sha256(json.dumps([MODEL, PROMPT_VERSION, POLISH, t], ensure_ascii=False).encode()).hexdigest()[:16]
            f = cache / f"{iso2}.json"
            if f.exists() and (old := json.loads(f.read_text(encoding="utf-8"))).get("hash") == h:
                return iso2, old["item"], "cached"
            p = polish(client, key, t) if key else None
            item = {**(p or t), "method": "template+gpt-6-luna" if p else "template",
                    "generated_at": datetime.now(UTC).isoformat(), "source_ids": facts["sources"]}
            f.write_text(json.dumps({"hash": h, "item": item}, ensure_ascii=False), encoding="utf-8")
            return iso2, item, item["method"]

        t0 = time.time()
        with ThreadPoolExecutor(WORKERS) as pool:
            results = list(pool.map(one, isos))
    counts: dict[str, int] = {}
    for _, _, how in results:
        counts[how] = counts.get(how, 0) + 1
    payload: dict[str, Any] = {"source": {"id": "atlas-summary", "title": "Resumo montado pelo Atlas a partir dos próprios dados (redação revisada por IA: GPT-6 Luna)",
                          "url": None, "license": None, "retrieved_at": datetime.now(UTC).isoformat()},
               "model": MODEL, "prompt_version": PROMPT_VERSION,
               "countries": {iso2: item for iso2, item, _ in results if item}}
    s.out_dir.mkdir(parents=True, exist_ok=True)
    name = "summaries.json" if not only else "summaries_sample.json"
    (s.out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote data_out/{name}: {len(payload['countries'])}/{len(isos)} countries in {time.time() - t0:.0f}s {counts}")


def _dotenv(name: str) -> str | None:
    f = Path(".env")
    if not f.exists():
        return None
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"') or None
    return None
