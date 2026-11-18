"""spec 038: chat tool logs hold tool names, argument keys and identifier-like values; never user text; 14-day retention."""
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from tests.conftest import _fresh_database

from atlas_api import chat, chat_logs
from atlas_api.core.config import Settings
from atlas_api.db.models import ChatToolLog
from atlas_api.importer.content import import_content
from atlas_api.main import create_app

SECRET = "meu-segredo-12345"  # appears only in the user's message and in model-chosen free text


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    eng = _fresh_database("atlas_chatlogs_test")
    with Session(eng) as s, s.begin():
        import_content(s, Path("content"))
    with TestClient(create_app(eng.url.render_as_string(hide_password=False))) as c:
        yield c
    eng.dispose()


def _sse(*chunks: dict[str, Any]) -> bytes:
    return ("\n\n".join([f"data: {json.dumps(c)}" for c in chunks] + ["data: [DONE]"]) + "\n\n").encode()


def _call(i: int, name: str, args: dict[str, Any]) -> dict[str, Any]:
    tc = {"index": i % 2, "id": f"c{i}", "function": {"name": name, "arguments": json.dumps(args)}}
    return {"choices": [{"delta": {"tool_calls": [tc]}}]}


def _ask(client: TestClient, monkeypatch: pytest.MonkeyPatch, replies: list[bytes]) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=replies.pop(0), headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(chat, "make_http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(chat, "limiter", chat.Limiter())
    monkeypatch.setattr("atlas_api.routers.chat.get_settings", lambda: Settings(ai_gateway_api_key="k"))
    r = client.post("/v1/chat", json={"messages": [{"role": "user", "content": f"Fale do Brasil {SECRET}"}]})
    assert r.status_code == 200


def _rows(client: TestClient) -> list[ChatToolLog]:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        return list(s.scalars(select(ChatToolLog).order_by(ChatToolLog.id)))


def test_logs_one_row_per_call_without_user_text(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    with client.app.state.session_factory() as s, s.begin():  # type: ignore[attr-defined]
        s.execute(delete(ChatToolLog))
    answer = f"A resposta contém {SECRET} também."
    _ask(client, monkeypatch, [
        _sse(_call(2, "get_country", {"iso2": "br"}), _call(1, "search", {"q": SECRET})),
        _sse(_call(2, "indicator_ranking", {"id": "gdp", "countries": ["BR", f"x {SECRET}"], "limit": 5})),
        _sse({"choices": [{"delta": {"content": answer}}]}),
    ])
    rows = _rows(client)
    assert [r.tool for r in rows] == ["get_country", "search", "indicator_ranking"]
    assert rows[0].args == {"iso2": "br"} and rows[0].ok
    assert rows[1].args == {"q": None} and rows[2].args == {"id": "gdp", "countries": ["BR"], "limit": 5}
    assert SECRET not in json.dumps([r.args for r in rows]) and all(r.ts for r in rows)


def test_free_text_keys_keep_no_value(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _ask(client, monkeypatch, [_sse(_call(1, "search", {"q": SECRET})), _sse({"choices": [{"delta": {"content": "ok"}}]})])
    last = _rows(client)[-1]
    assert last.tool == "search" and last.args == {"q": None}
    assert "ip" not in {c.name for c in ChatToolLog.__table__.columns}  # type: ignore[attr-defined]


def test_failed_tool_is_logged_with_ok_false(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _ask(client, monkeypatch, [_sse(_call(1, "get_economy", {"iso2": "ZZ"})), _sse({"choices": [{"delta": {"content": "x"}}]})])
    assert _rows(client)[-1].ok is False


def test_retention_deletes_old_rows_on_insert(client: TestClient) -> None:
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    chat_logs.record(factory, "get_country", {"iso2": "AR"}, True)
    old = datetime.now(UTC) - timedelta(days=chat_logs.RETENTION_DAYS + 1)
    with factory() as s, s.begin():
        s.execute(update(ChatToolLog).where(ChatToolLog.args["iso2"].astext == "AR").values(ts=old))
    chat_logs.record(factory, "get_country", {"iso2": "CL"}, True)  # this insert purges the 15-day-old row
    assert [r.args.get("iso2") for r in _rows(client)].count("AR") == 0
    assert any(r.args.get("iso2") == "CL" for r in _rows(client))


def test_logging_failure_never_breaks_the_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Session:
        raise RuntimeError("db down")

    chat_logs.record(boom, "search", {}, True)  # must not raise


def test_cli_summary(client: TestClient, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from atlas_api import cli
    with client.app.state.session_factory() as s, s.begin():  # type: ignore[attr-defined]
        s.execute(delete(ChatToolLog))
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    for iso in ("BR", "BR", "AR"):
        chat_logs.record(factory, "get_country", {"iso2": iso}, True)
    chat_logs.record(factory, "indicator_ranking", {"id": "gdp", "countries": ["BR", "US"]}, True)
    url = client.app.state.test_url if hasattr(client.app.state, "test_url") else factory.kw["bind"].url.render_as_string(hide_password=False)
    monkeypatch.setattr("sys.argv", ["cli", "chat-logs", "--since", "1d"])
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(database_url=url))
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "4" in out.splitlines()[0] and "get_country: 3" in out and "indicator_ranking: 1" in out
    assert "BR: 3" in out and "AR: 1" in out and "US: 1" in out


def test_parse_since() -> None:
    assert chat_logs.parse_since("2d") == timedelta(days=2) and chat_logs.parse_since("6h") == timedelta(hours=6)
    with pytest.raises(ValueError):
        chat_logs.parse_since("abc")
