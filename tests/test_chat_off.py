"""The chat router is only mounted when CHAT_ENABLED is true (off in production for now)."""
from fastapi.testclient import TestClient

from atlas_api.core.config import Settings
from atlas_api import main


def test_chat_route_absent_by_default(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(chat_enabled=False))
    paths = set(main.create_app("postgresql+psycopg://x@localhost/none").openapi()["paths"])
    assert "/v1/chat" not in paths and "/v1/health" in paths


def test_chat_route_present_when_enabled(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(chat_enabled=True))
    paths = set(main.create_app("postgresql+psycopg://x@localhost/none").openapi()["paths"])
    assert "/v1/chat" in paths
