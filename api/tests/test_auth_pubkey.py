"""Unit tests for /api/auth/public-key (TA-08)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.src.auth.router import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_returns_pem_and_algorithm(monkeypatch):
    pem = "-----BEGIN PUBLIC KEY-----\\nABC\\nXYZ\\n-----END PUBLIC KEY-----\\n"
    monkeypatch.setenv("AUTH_RSA_PUBLIC_KEY", pem)

    client = TestClient(_make_app())
    r = client.get("/api/auth/public-key")
    assert r.status_code == 200
    body = r.json()
    # \n escape 복원 확인
    assert "\\n" not in body["public_key_pem"]
    assert body["public_key_pem"].startswith("-----BEGIN PUBLIC KEY-----")
    assert body["algorithm"] == "RSA-OAEP-SHA256"


def test_returns_500_when_env_missing(monkeypatch):
    monkeypatch.delenv("AUTH_RSA_PUBLIC_KEY", raising=False)
    client = TestClient(_make_app())
    r = client.get("/api/auth/public-key")
    assert r.status_code == 500
    assert "not configured" in r.json()["detail"].lower()
