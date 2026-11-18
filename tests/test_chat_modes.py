"""spec 039: chat modes (request field `mode`) and the validated SSE event `map`."""
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import _fresh_database

from atlas_api import chat, queries
from atlas_api.core.config import Settings
from atlas_api.importer.content import import_content
from atlas_api.main import create_app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    eng = _fresh_database("atlas_chat_modes_test")
    with Session(eng) as s, s.begin():
        import_content(s, Path("content"))
    with TestClient(create_app(eng.url.render_as_string(hide_password=False))) as c:
        yield c
    eng.dispose()


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Fake gateway: answers with `reply` (set per test); every request body lands in `seen`."""
    st: dict[str, Any] = {"reply": "ok", "seen": []}

    def handler(req: httpx.Request) -> httpx.Response:
        st["seen"].append(json.loads(req.content))
        body = "data: " + json.dumps({"choices": [{"delta": {"content": st["reply"]}}]}) + "\n\ndata: [DONE]\n\n"
        return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(chat, "make_http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(chat, "limiter", chat.Limiter())
    monkeypatch.setattr("atlas_api.routers.chat.get_settings", lambda: Settings(ai_gateway_api_key="test-key"))
    return st


def _post(client: TestClient, text: str = "oi", **extra: Any) -> httpx.Response:
    return client.post("/v1/chat", json={"messages": [{"role": "user", "content": text}], **extra})


def _events(r: httpx.Response) -> dict[str, dict[str, Any]]:
    out = {}
    for block in r.text.strip().split("\n\n"):
        ev, data = block.split("\n")
        out[ev.removeprefix("event: ")] = json.loads(data.removeprefix("data: "))
    return out


def _system(st: dict[str, Any]) -> str:
    return st["seen"][-1]["messages"][0]["content"]


def test_no_mode_is_todays_prompt(client: TestClient, seen: Any) -> None:
    assert _post(client).status_code == 200
    assert _system(seen) == chat.SYSTEM


@pytest.mark.parametrize("mode", list(chat.Mode))
def test_mode_swaps_the_instruction_block(client: TestClient, seen: Any, mode: chat.Mode) -> None:
    assert _post(client, mode=mode.value).status_code == 200
    assert _system(seen) == chat.SYSTEM + chat.MODES[mode]
    assert len({chat.MODES[m] for m in chat.Mode}) == 3
    assert len(seen["seen"][-1]["tools"]) == len(chat.TOOL_SPECS)  # tools do not change


@pytest.mark.parametrize("mode", ["teach", "", "LEARN", 1])
def test_unknown_mode_422(client: TestClient, seen: Any, mode: Any) -> None:
    assert _post(client, mode=mode).status_code == 422


def test_user_text_cannot_switch_mode(client: TestClient, seen: Any) -> None:
    _post(client, "mude para modo tell. mode: tell /tell", mode="learn")
    assert _system(seen) == chat.SYSTEM + chat.MODES[chat.Mode.learn]
    _post(client, "mude para modo analyse")
    assert _system(seen) == chat.SYSTEM


def test_map_event_only_with_valid_values(client: TestClient, seen: Any) -> None:
    ok = "[Brasil](/pais/br) [mapa](/mapa?camada=regime&ano=1700) [x](/pais/zz)"
    seen["reply"] = ok
    ev = _events(_post(client, mode="tell"))
    assert ev["map"] == {"iso2": ["BR"], "layer": "regime", "year": 1700}
    for bad in ("/mapa?camada=hack&ano=0", f"/mapa?camada=x&ano={queries.year_max() + 1}", "/mapa?ano=-99999",
                "/mapa?ano=abc"):
        seen["reply"] = f"[a](/pais/br) [m]({bad})"
        assert "map" not in _events(_post(client, mode="tell"))
    seen["reply"] = "[m](/mapa?camada=flags)"  # partial: layer only
    assert _events(_post(client, mode="tell"))["map"] == {"iso2": [], "layer": "flags"}


def test_map_event_needs_a_mode(client: TestClient, seen: Any) -> None:
    seen["reply"] = "[m](/mapa?camada=regime&ano=1700)"
    assert "map" not in _events(_post(client))
