"""Tests unitaires : la base et le LLM sont simulés (aucun conteneur requis)."""
import pytest
from fastapi.testclient import TestClient

from app import db, llm
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(db, "init_pool", lambda: None)
    monkeypatch.setattr(db, "close_pool", lambda: None)
    with TestClient(app) as c:
        yield c


def test_liveness(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_degraded_when_llm_down(client, monkeypatch):
    monkeypatch.setattr(llm, "is_ready", lambda: False)
    monkeypatch.setattr(db, "ping", lambda: True)
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["llm"] is False


def test_chat_ok(client, monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda m: ("Bonjour !", 3))
    monkeypatch.setattr(db, "save_message", lambda *a, **k: 42)
    r = client.post("/api/chat", json={"message": "Salut"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 42 and body["answer"] == "Bonjour !" and body["tokens"] == 3


def test_chat_llm_down_returns_502(client, monkeypatch):
    def boom(_):
        raise llm.LLMError("down")
    monkeypatch.setattr(llm, "chat", boom)
    r = client.post("/api/chat", json={"message": "Salut"})
    assert r.status_code == 502


def test_chat_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_metrics_exposed(client):
    client.get("/health/live")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
