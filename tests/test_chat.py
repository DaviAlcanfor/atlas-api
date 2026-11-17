"""spec 025: POST /v1/chat against a FAKE AI Gateway (httpx.MockTransport, no network) and a real throwaway DB."""
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import _fresh_database

from atlas_api import chat
from atlas_api.config import Settings
from atlas_api.importer import import_content
from atlas_api.main import create_app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    eng = _fresh_database("atlas_chat_test")  # its own DB: other suites drop theirs while running
    with Session(eng) as s, s.begin():
        import_content(s, Path("content"))
    with TestClient(create_app(eng.url.render_as_string(hide_password=False))) as c:
        yield c
    eng.dispose()


def _sse(*chunks: dict[str, Any]) -> bytes:
    lines = [": heartbeat"] + [f"data: {json.dumps(c)}" for c in chunks] + ["data: [DONE]"]
    return ("\n\n".join(lines) + "\n\n").encode()


def _text(t: str) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": {"content": t}, "finish_reason": None}]}


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replies queued per call in `replies`; every request body sent to the gateway lands in `seen`."""
    state: dict[str, Any] = {"replies": [], "seen": []}

    def handler(req: httpx.Request) -> httpx.Response:
        state["seen"].append(json.loads(req.content))
        assert req.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, content=state["replies"].pop(0), headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(chat, "make_http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(chat, "limiter", chat.Limiter())
    monkeypatch.setattr("atlas_api.routers.chat.get_settings", lambda: Settings(ai_gateway_api_key="test-key"))
    return state  # type: ignore[return-value]


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for block in body.strip().split("\n\n"):
        ev, data = block.split("\n")
        out.append((ev.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


Q = {"messages": [{"role": "user", "content": "Qual a capital do Brasil?"}]}


def test_streams_text(client: TestClient, gateway: Any) -> None:
    gateway["replies"].append(_sse(_text("Olá, "), _text("mundo.")))
    r = client.post("/v1/chat", json=Q)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert _events(r.text) == [("text", {"delta": "Olá, "}), ("text", {"delta": "mundo."}), ("done", {"sources": []})]
    sent = gateway["seen"][0]
    assert sent["model"] == "openai/gpt-6-luna" and sent["stream"] is True and sent["max_completion_tokens"] == 1200
    assert sent["messages"][0]["role"] == "system" and sent["messages"][1] == Q["messages"][0]


def test_tool_round(client: TestClient, gateway: Any) -> None:
    call = [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "get_country", "arguments": '{"iso'}},
            {"index": 0, "function": {"arguments": '2": "br"}'}}]
    gateway["replies"] += [
        _sse(*({"choices": [{"index": 0, "delta": {"tool_calls": [c]}}]} for c in call)),
        _sse(_text("A capital do [Brasil](/pais/br) é Brasília (Wikidata).")),
    ]
    ev = _events(client.post("/v1/chat", json=Q).text)
    assert ev[0] == ("tool", {"name": "get_country", "args": {"iso2": "br"}})
    assert ("countries", {"iso2": ["BR"]}) in ev
    assert ev[-1][0] == "done" and all("id" in s and "title" in s for s in ev[-1][1]["sources"])
    second = gateway["seen"][1]["messages"]
    assert second[-2]["tool_calls"][0]["function"] == {"name": "get_country", "arguments": '{"iso2": "br"}'}
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "call_1"
    assert json.loads(second[-1]["content"])["iso2"] == "BR"  # the real query ran in-process


def test_unknown_country_and_last_round_has_no_tools(client: TestClient, gateway: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr("atlas_api.routers.chat.get_settings",
                        lambda: Settings(ai_gateway_api_key="test-key", chat_max_tool_rounds=1))
    tc = {"index": 0, "id": "c", "function": {"name": "get_economy", "arguments": '{"iso2": "ZZ"}'}}
    gateway["replies"] += [_sse({"choices": [{"delta": {"tool_calls": [tc]}}]}), _sse(_text("o Atlas não tem esse dado"))]
    client.post("/v1/chat", json=Q)
    assert "tools" in gateway["seen"][0] and "tools" not in gateway["seen"][1]
    assert "erro" in json.loads(gateway["seen"][1]["messages"][-1]["content"])


def test_rate_limit_429(client: TestClient, gateway: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr("atlas_api.routers.chat.get_settings",
                        lambda: Settings(ai_gateway_api_key="test-key", chat_per_ip_hour=1))
    gateway["replies"].append(_sse(_text("ok")))
    assert client.post("/v1/chat", json=Q).status_code == 200
    r = client.post("/v1/chat", json=Q)
    assert r.status_code == 429 and r.headers["content-type"] == "application/problem+json"
    assert "última hora" in r.json()["detail"]
    gateway["replies"].append(_sse(_text("ok")))
    assert client.post("/v1/chat", json=Q, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 200  # other IP


def test_daily_limit(gateway: Any) -> None:
    lim = chat.Limiter()
    assert lim.hit("a", 20, 2) is None and lim.hit("b", 20, 2) is None
    assert lim.hit("c", 20, 2) == "O chat atingiu o limite de hoje. Tente de novo amanhã."


@pytest.mark.parametrize("body", [
    {}, {"messages": []}, {"messages": [{"role": "system", "content": "x"}]},
    {"messages": [{"role": "user", "content": ""}]}, {"messages": [{"role": "user", "content": "x" * 4001}]},
    {"messages": [{"role": "user", "content": "x"}] * 21}, {"messages": [{"role": "assistant", "content": "x"}]},
])
def test_bad_body_422(client: TestClient, gateway: Any, body: Any) -> None:
    r = client.post("/v1/chat", json=body)
    assert r.status_code == 422 and r.headers["content-type"] == "application/problem+json"


def test_missing_key_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("atlas_api.routers.chat.get_settings", lambda: Settings(ai_gateway_api_key=None))
    r = client.post("/v1/chat", json=Q)
    assert r.status_code == 503 and r.headers["content-type"] == "application/problem+json"


def test_gateway_error_is_an_sse_error(client: TestClient, gateway: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(chat, "make_http",
                        lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="boom"))))
    ev = _events(client.post("/v1/chat", json=Q).text)
    assert ev == [("error", {"message": "O chat está indisponível agora. Tente de novo em instantes."})]


def test_cors_preflight_allows_post(monkeypatch: pytest.MonkeyPatch) -> None:
    from atlas_api.config import get_settings
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    get_settings.cache_clear()
    try:
        c = TestClient(create_app("postgresql+psycopg://x:x@localhost:1/x"))  # no lifespan: CORS answers first
        r = c.options("/v1/chat", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "content-type"})
    finally:
        get_settings.cache_clear()
    assert r.status_code == 200 and "POST" in r.headers["access-control-allow-methods"]
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
