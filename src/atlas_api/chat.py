"""Atlas chatbot (spec 025): openai/gpt-6-luna through the Vercel AI Gateway, with the API's own queries as tools.

Gateway: OpenAI-compatible POST https://ai-gateway.vercel.sh/v1/chat/completions, `stream: true` (SSE `data: {chunk}` lines,
`: heartbeat` comments, final `data: [DONE]`), tool calling per the OpenAI function-calling spec (docs read 2026-11-17).
The model is fixed by the owner: no other model, no fallback. Nothing is stored: the browser sends the whole history.
"""
import json
import logging
import re
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from atlas_api import chat_logs, queries

log = logging.getLogger("atlas_api.chat")
MODEL = "openai/gpt-6-luna"  # owner's decision (2026-11-17): changing it needs his approval
GATEWAY = "https://ai-gateway.vercel.sh/v1/chat/completions"
MAX_CALLS_PER_ROUND = 8  # tool calls executed per model turn (a model may ask for hundreds at once)
TOOL_RESULT_CAP = 32_000  # chars of JSON per tool result sent to the model (all 196 countries fit; bounds input cost)
ISO2 = re.compile(r"^[A-Z]{2}$")
LINK = re.compile(r"/pais/([a-zA-Z]{2})\b")
MAP_LINK = re.compile(r"/mapa\?([^\s)]*)")  # spec 039: [texto](/mapa?camada=regime&ano=1700), only read when a mode is set
MAP_LAYERS = ("content", "regime", "flags", "ranking")  # the web's LayerId minus the geoguessr game

SYSTEM = """Você é o assistente do Atlas, um globo interativo com dados de países.
Regras:
- Responda em português do Brasil, de forma curta e clara.
- Use as ferramentas para buscar os dados. Só afirme o que as ferramentas retornaram; não use conhecimento próprio para números,
  nomes de governantes, datas ou fatos.
- Cite a fonte de cada número entre parênteses, com o título da fonte que veio junto do dado (ex.: "(Banco Mundial, 2023)").
- Se as ferramentas não trouxerem o dado, diga "o Atlas não tem esse dado". Nunca invente.
- Ao mencionar um país, use um link interno em markdown: [Brasil](/pais/br) (código ISO2 em minúsculas).
- Códigos de país são ISO2 em maiúsculas nas ferramentas (BR, AR, US). Se não souber o código, use a ferramenta `search`.
- Para "quais países são X", use `list_countries` (filtros de região/regime) ou `indicator_ranking`."""


class Mode(StrEnum):
    """spec 039: only ever set from the request's `mode` field, never from user or tool text."""
    learn = "learn"
    analyse = "analyse"
    tell = "tell"


_MAP_RULE = """
- Para o usuário ver algo no mapa, inclua um link interno [texto](/mapa?camada=regime&ano=1700) (camada: content, regime,
  flags ou ranking; ano inteiro, sem ano 0, negativo = a.C.). Use só quando fizer sentido; combine com links /pais/xx."""
MODES: dict[Mode, str] = {
    Mode.learn: """
Modo Aprender:
- Explique em etapas curtas, uma ideia por vez, sempre ligada aos dados que as ferramentas retornaram.
- Termine toda resposta oferecendo 2 ou 3 opções para seguir (por exemplo: "simplifica", "continua", "me testa").""" + _MAP_RULE,
    Mode.analyse: """
Modo Analisar:
- Compare países e indicadores informando, para cada número: valor, ano, fonte e método quando o dado trouxer.
- Aponte as lacunas (países ou anos sem dado) e os limites da comparação (anos diferentes, definições diferentes).""" + _MAP_RULE,
    Mode.tell: """
Modo Narrar:
- Conte uma história em etapas curtas, só com conteúdo que o Atlas tem (períodos e fronteiras da viagem no tempo, fatos com fonte).
- Nunca descreva rotas militares nem batalhas sem dado do Atlas; se o Atlas não tem, diga que não tem.
- Quando algo for incerto ou ambíguo, diga a incerteza explicitamente.""" + _MAP_RULE,
}


# --- tools: the API's own queries, called in-process ------------------------------------------------------------------
def _plain(x: Any) -> Any:
    if isinstance(x, BaseModel):
        return x.model_dump(mode="json")
    if isinstance(x, list):
        return [_plain(i) for i in x]
    return x


def _iso(a: dict[str, Any]) -> str:
    iso2 = str(a.get("iso2", "")).upper()
    if not ISO2.match(iso2):
        raise ValueError("iso2 deve ter 2 letras, ex.: BR")
    return iso2


def _country(fn: Callable[[Session, str, dict[str, Any]], Any]) -> Callable[[Session, dict[str, Any]], Any]:
    """Tool over one country: validates iso2, answers 'unknown' instead of raising, turns None into 'no data'."""
    def run(s: Session, a: dict[str, Any]) -> Any:
        iso2 = _iso(a)
        if not queries.country_exists(s, iso2):
            return {"erro": f"o Atlas não tem o país {iso2}"}
        out = fn(s, iso2, a)
        return {"erro": "o Atlas não tem esse dado"} if out is None else out
    return run


def _q(f: Callable[[Session, str], Any]) -> Callable[[Session, dict[str, Any]], Any]:
    return _country(lambda s, iso2, _: f(s, iso2))


def _list_countries(s: Session, a: dict[str, Any]) -> Any:
    region, regime = (queries._fold(str(a.get(k) or "")) for k in ("region", "regime"))
    return [{"iso2": c.iso2, "name": c.name, "capital": c.capital, "region": c.region, "regime": c.regime,
             "regime_id": c.regime_id}
            for c in queries.list_countries(s)
            if region in queries._fold(c.region or "") and regime in queries._fold(f"{c.regime or ''} {c.regime_id or ''}")]


def _leaders(s: Session, iso2: str, a: dict[str, Any]) -> Any:
    rows = queries.list_leaders(s, iso2, str(a["role"]) if a.get("role") else None)[::-1][: max(1, min(int(a.get("limit") or 20), 100))]
    return {"items": _plain(rows),  # newest first
            "sources": _plain(queries._sources(s, {"wikidata"}))}


def _people(s: Session, iso2: str, a: dict[str, Any]) -> Any:
    return queries.list_people(s, iso2, str(a["domain"]) if a.get("domain") else None, max(1, min(int(a.get("limit") or 10), 50)))


def _card(s: Session, iso2: str) -> Any:
    c = queries.get_country(s, iso2)  # timeline and languages_spoken have their own tools: 50 kB -> 2 kB
    return c and c.model_dump(mode="json", exclude={"timeline", "languages_spoken"})


def _languages(s: Session, iso2: str) -> Any:
    c = queries.get_country(s, iso2)
    return c and c.model_dump(mode="json", include={
        "iso2": True, "name": True, "languages": True, "sources": True,
        "languages_spoken": {"__all__": {"code", "name", "status", "where", "speakers", "endangerment"}}})


def _currency(s: Session, a: dict[str, Any]) -> Any:
    code = str(a.get("code", "")).upper()
    return queries.get_currency(s, code) or {"erro": f"o Atlas não tem a moeda {code}"}


def _glossary(s: Session, a: dict[str, Any]) -> Any:
    if a.get("id"):
        return queries.get_glossary_term(s, str(a["id"])) or {"erro": "termo não encontrado"}
    return [{"id": t.id, "kind": t.kind, "label": t.label, "short": t.short} for t in queries.list_glossary(s)]


def _ranking(s: Session, a: dict[str, Any]) -> Any:
    r = queries.indicator_ranking(s, str(a.get("id", "")))
    if r is None:
        return {"erro": "indicador desconhecido; veja list_indicators"}
    items = r.items if a.get("order") != "asc" else r.items[::-1]
    if a.get("countries"):
        wanted = {str(c).upper() for c in a["countries"]}
        items = [i for i in items if i.iso2 in wanted]
    else:
        items = items[: max(1, min(int(a.get("limit") or 10), 50))]
    return {**r.model_dump(mode="json", exclude={"items"}), "total": len(r.items), "items": _plain(items)}


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or []}


_ISO_P = {"iso2": {"type": "string", "description": "código ISO2 do país, ex.: BR"}}
TOOLS: dict[str, tuple[str, dict[str, Any], Callable[[Session, dict[str, Any]], Any]]] = {
    "search": ("Busca países e entidades históricas pelo nome (aceita nomes em português).",
               _obj({"q": {"type": "string"}}, ["q"]), lambda s, a: queries.search(s, str(a.get("q", "")), 10)),
    "list_countries": (("Lista os países do Atlas (iso2, nome, capital, região, regime). Filtros opcionais por trecho"
                        " do nome da região ou do regime (sem acento/maiúsculas)."),
                       _obj({"region": {"type": "string"}, "regime": {"type": "string"}}), _list_countries),
    "get_country": ("Ficha do país: capital, área, população, moeda, idiomas, regime, fontes.", _obj(_ISO_P, ["iso2"]),
                    _q(_card)),
    "get_leaders": ("Governantes do país (chefe de Estado e de governo), com mandatos e partido.",
                    _obj({**_ISO_P, "role": {"type": "string", "enum": ["head_of_state", "head_of_government"]},
                          "limit": {"type": "integer", "description": "os mais recentes primeiro; padrão 20"}}, ["iso2"]),
                    _country(_leaders)),
    "get_people": ("Pessoas notáveis do país.",
                   _obj({**_ISO_P, "domain": {"type": "string"}, "limit": {"type": "integer"}}, ["iso2"]),
                   _country(_people)),
    "get_profile": ("Perfil do país: indicadores de vida, sociedade, renda, ambiente e economia, com ano e mediana mundial.",
                    _obj(_ISO_P, ["iso2"]), _q(queries.get_profile)),
    "get_economy": ("Economia do país: PIB, inflação, desemprego, dívida etc., com ano e fonte.", _obj(_ISO_P, ["iso2"]),
                    _q(queries.get_economy)),
    "get_trade": ("Comércio exterior do país: exportações, importações, principais produtos e parceiros.",
                  _obj(_ISO_P, ["iso2"]),
                  _q(queries.get_trade)),
    "get_history": ("Resumo histórico e linha do tempo do país.", _obj(_ISO_P, ["iso2"]), _q(queries.get_history)),
    "get_languages": ("Idiomas oficiais e idiomas falados no país.", _obj(_ISO_P, ["iso2"]), _q(_languages)),
    "get_currency": ("Moeda (código ISO 4217, ex.: BRL): câmbio atual contra outras moedas e variação.",
                     _obj({"code": {"type": "string"}}, ["code"]), _currency),
    "glossary": ("Glossário do Atlas (regimes, termos). Sem id: lista os termos; com id: o termo completo.",
                 _obj({"id": {"type": "string"}}), _glossary),
    "list_indicators": ("Lista os indicadores que têm ranking entre países (id, nome, unidade).", _obj({}),
                        lambda s, a: queries.list_ranked_indicators(s)),
    "indicator_ranking": (("Ranking de países num indicador (id de list_indicators). order desc = maiores primeiro;"
                           " countries = só esses países."),
                          _obj({"id": {"type": "string"}, "order": {"type": "string", "enum": ["desc", "asc"]},
                                "limit": {"type": "integer"}, "countries": {"type": "array", "items": {"type": "string"}}},
                               ["id"]), _ranking),
}
TOOL_SPECS = [{"type": "function", "function": {"name": n, "description": d, "parameters": p}} for n, (d, p, _) in TOOLS.items()]


def run_tool(factory: Callable[[], Session], name: str, args: dict[str, Any]) -> Any:
    if name not in TOOLS:
        return {"erro": f"ferramenta desconhecida: {name}"}
    try:
        with factory() as s:  # one short session per tool call: never hold a pooled connection while the model talks
            return _plain(TOOLS[name][2](s, args))
    except (ValueError, TypeError) as e:  # bad args from the model: tell it, let it retry
        return {"erro": str(e)}


def collect_sources(result: Any, into: dict[str, dict[str, Any]]) -> None:
    if isinstance(result, dict):
        for src in result.get("sources") or ([result["source"]] if isinstance(result.get("source"), dict) else []):
            if isinstance(src, dict) and "id" in src:
                into.setdefault(src["id"], src)


# --- limits -----------------------------------------------------------------------------------------------------------
class Limiter:
    """N questions/hour per IP and M/day in total (UTC day).
    ponytail: in-memory, per process. FastAPI Cloud may run more than one replica/worker (spec 019 could not pin it),
    so the real ceiling is N x replicas per IP and M x replicas per day; move to a DB/Redis counter if that matters."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.ips: dict[str, deque[float]] = {}
        self.day, self.today = "", 0

    def hit(self, ip: str, per_hour: int, per_day: int) -> str | None:
        """Counts one question; returns the pt-BR refusal when over a limit (nothing is counted then)."""
        now, day = time.monotonic(), datetime.now(UTC).date().isoformat()
        with self.lock:
            if day != self.day:
                self.day, self.today = day, 0
            q = self.ips.setdefault(ip, deque())
            while q and now - q[0] > 3600:
                q.popleft()
            if self.today >= per_day:
                return "O chat atingiu o limite de hoje. Tente de novo amanhã."
            if len(q) >= per_hour:
                return "Você fez muitas perguntas na última hora. Tente de novo mais tarde."
            q.append(now)
            self.today += 1
            if len(self.ips) > 10_000:  # forget idle IPs so the dict cannot grow forever
                self.ips = {k: v for k, v in self.ips.items() if v and now - v[-1] <= 3600}
            return None


limiter = Limiter()


# --- the loop ---------------------------------------------------------------------------------------------------------
def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def make_http() -> httpx.Client:  # tests swap this for a fake gateway (httpx.MockTransport)
    return httpx.Client(timeout=httpx.Timeout(60, connect=10))


def _chunks(http: httpx.Client, key: str, payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Gateway SSE -> chunk dicts. Ignores comment lines (': heartbeat') and stops at [DONE]."""
    with http.stream("POST", GATEWAY, json=payload, headers={"Authorization": f"Bearer {key}"}) as r:
        if r.status_code != 200:
            r.read()
            log.warning("AI Gateway answered %s: %s", r.status_code, r.text[:300])
            raise RuntimeError("gateway")
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            yield json.loads(data)


def _map_view(text: str) -> tuple[str | None, int | None]:
    """First valid layer and year of the answer's /mapa links; anything else is dropped."""
    layer = year = None
    for q in MAP_LINK.findall(text):
        for k, _, v in (p.partition("=") for p in q.split("&")):
            if k == "camada" and layer is None and v in MAP_LAYERS:
                layer = v
            if k == "ano" and year is None and re.fullmatch(r"-?\d{1,5}", v) \
                    and int(v) != 0 and queries.YEAR_MIN <= int(v) <= queries.year_max():
                year = int(v)
    return layer, year


def answer(messages: list[dict[str, str]], key: str, factory: Callable[[], Session], max_rounds: int,
           max_tokens: int, mode: Mode | None = None) -> Iterator[str]:
    """Streams the SSE events of one answer: text*, tool*, countries?, map?, done | error."""
    msgs: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM + (MODES[mode] if mode else "")}, *messages]
    sources: dict[str, dict[str, Any]] = {}
    text = ""
    try:
        with make_http() as http:
            for rnd in range(max_rounds + 1):
                payload: dict[str, Any] = {"model": MODEL, "messages": msgs, "stream": True,
                                           "max_completion_tokens": max_tokens}  # ponytail: per gateway call, not summed over rounds
                if rnd < max_rounds:  # the last call has no tools: it must answer with what it has
                    payload |= {"tools": TOOL_SPECS, "tool_choice": "auto"}
                calls: dict[int, dict[str, str]] = {}
                for chunk in _chunks(http, key, payload):
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            text += delta["content"]
                            yield sse("text", {"delta": delta["content"]})
                        for tc in delta.get("tool_calls") or []:  # streamed in fragments, grouped by index
                            c = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "arguments": ""})
                            fn = tc.get("function") or {}
                            c["id"] = tc.get("id") or c["id"]
                            c["name"] += fn.get("name") or ""
                            c["arguments"] += fn.get("arguments") or ""
                if not calls or rnd == max_rounds:  # the last call offered no tools: ignore any the model emits anyway
                    break
                ordered = [calls[i] for i in sorted(calls)][:MAX_CALLS_PER_ROUND]
                msgs.append({"role": "assistant", "content": None, "tool_calls": [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in ordered]})
                for c in ordered:
                    try:
                        args = json.loads(c["arguments"] or "{}")
                    except ValueError:
                        args = {}
                    args = args if isinstance(args, dict) else {}
                    yield sse("tool", {"name": c["name"], "args": args})
                    result = run_tool(factory, c["name"], args)
                    chat_logs.record(factory, c["name"], args, not (isinstance(result, dict) and "erro" in result))
                    collect_sources(result, sources)
                    msgs.append({"role": "tool", "tool_call_id": c["id"],
                                 "content": json.dumps(result, ensure_ascii=False)[:TOOL_RESULT_CAP]})
        layer, year = _map_view(text) if mode else (None, None)
        iso2s: list[str] = []  # the countries the answer links to (/pais/xx): the globe flies there
        if linked := list(dict.fromkeys(m.upper() for m in LINK.findall(text))):
            with factory() as s:
                iso2s = [i for i in linked if queries.country_exists(s, i)]
    except Exception:  # network, gateway, DB: the client gets a pt-BR message, the log gets the details (never the key)
        log.exception("chat answer failed")
        yield sse("error", {"message": "O chat está indisponível agora. Tente de novo em instantes."})
        return
    if iso2s:
        yield sse("countries", {"iso2": iso2s})
    if layer or year is not None:  # spec 039: only server-validated values
        yield sse("map", {"iso2": iso2s} | ({"layer": layer} if layer else {}) | ({"year": year} if year is not None else {}))
    yield sse("done", {"sources": list(sources.values())})
