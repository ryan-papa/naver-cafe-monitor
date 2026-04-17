"""Unit tests for api.src.auth.csrf (TA-06)."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.src.auth.csrf import CSRF_COOKIE, CSRF_HEADER, verify_csrf


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/safe")
    async def _safe(_: None = Depends(verify_csrf)):
        return {"ok": True}

    @app.post("/mutate")
    async def _mutate(_: None = Depends(verify_csrf)):
        return {"ok": True}

    return app


def test_get_bypasses_csrf():
    client = TestClient(_make_app())
    r = client.get("/safe")
    assert r.status_code == 200


def test_post_without_cookie_or_header_rejected():
    client = TestClient(_make_app())
    r = client.post("/mutate")
    assert r.status_code == 403
    assert "missing" in r.json()["detail"].lower()


def test_post_without_header_rejected():
    client = TestClient(_make_app())
    r = client.post("/mutate", cookies={CSRF_COOKIE: "abc"})
    assert r.status_code == 403


def test_post_without_cookie_rejected():
    client = TestClient(_make_app())
    r = client.post("/mutate", headers={CSRF_HEADER: "abc"})
    assert r.status_code == 403


def test_mismatch_rejected():
    client = TestClient(_make_app())
    r = client.post(
        "/mutate",
        cookies={CSRF_COOKIE: "abc"},
        headers={CSRF_HEADER: "xyz"},
    )
    assert r.status_code == 403
    assert "mismatch" in r.json()["detail"].lower()


def test_match_allowed():
    client = TestClient(_make_app())
    r = client.post(
        "/mutate",
        cookies={CSRF_COOKIE: "abc-123"},
        headers={CSRF_HEADER: "abc-123"},
    )
    assert r.status_code == 200
