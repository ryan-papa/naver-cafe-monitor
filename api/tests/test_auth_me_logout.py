"""Unit tests for /api/auth/me and /api/auth/logout (TA-12)."""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.src.auth import dependencies as deps
from api.src.auth.csrf import CSRF_COOKIE, CSRF_HEADER
from api.src.auth.router import router
from shared.auth_tokens import issue_access_token
from shared.crypto import aes_gcm_encrypt
from shared.user_repository import UserRow

AES_KEY = os.urandom(32)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-32-bytes-xxxxxxxxxxx")
    monkeypatch.setenv("AUTH_AES_KEY", base64.b64encode(AES_KEY).decode())
    # log_auth_event 는 DB 연결을 시도하므로 no-op 으로 패치
    from shared import auth_events
    from api.src.auth import router as router_mod

    monkeypatch.setattr(router_mod, "log_auth_event", lambda *a, **kw: None)
    monkeypatch.setattr(auth_events, "log_auth_event", lambda *a, **kw: None)


def _fake_user(user_id: int = 1) -> UserRow:
    return UserRow(
        id=user_id,
        email_enc=aes_gcm_encrypt(b"admin@example.com", AES_KEY),
        email_hmac=b"\x00" * 32,
        name_enc=aes_gcm_encrypt(b"Admin", AES_KEY),
        password_hash="$argon2id$...",
        is_admin=True,
        failed_login_count=0,
        locked_until=None,
    )


def _make_app(user: UserRow | None = None, repo_mock: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if repo_mock is not None:
        repo = repo_mock
    else:
        repo = MagicMock()
        repo.find_by_id.return_value = user
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        repo.conn.cursor.return_value = cur

    def _override_repo():
        return repo

    app.dependency_overrides[deps.get_user_repository] = _override_repo
    return app


def test_me_without_cookie_returns_401():
    app = _make_app()
    client = TestClient(app)
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_invalid_token_returns_401():
    app = _make_app(user=_fake_user())
    client = TestClient(app)
    client.cookies.set("access_token", "not-a-jwt")
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_decrypted_fields():
    user = _fake_user(user_id=7)
    app = _make_app(user=user)
    client = TestClient(app)
    token, _ = issue_access_token(7, os.environ["AUTH_JWT_SECRET"])
    client.cookies.set("access_token", token)

    r = client.get("/api/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "id": 7,
        "email": "admin@example.com",
        "name": "Admin",
        "is_admin": True,
    }


def test_logout_requires_csrf():
    user = _fake_user()
    app = _make_app(user=user)
    client = TestClient(app)
    token, _ = issue_access_token(1, os.environ["AUTH_JWT_SECRET"])
    client.cookies.set("access_token", token)
    # CSRF 없음 → 403
    r = client.post("/api/auth/logout")
    assert r.status_code == 403


def test_logout_deletes_refresh_and_clears_cookies():
    user = _fake_user()
    repo = MagicMock()
    repo.find_by_id.return_value = user
    cur_cm = MagicMock()
    cur_cm.__enter__ = MagicMock(return_value=cur_cm)
    cur_cm.__exit__ = MagicMock(return_value=False)
    repo.conn.cursor.return_value = cur_cm

    app = _make_app(user=user, repo_mock=repo)
    client = TestClient(app)
    token, _ = issue_access_token(1, os.environ["AUTH_JWT_SECRET"])
    client.cookies.set("access_token", token)
    client.cookies.set(CSRF_COOKIE, "xyz")

    r = client.post("/api/auth/logout", headers={CSRF_HEADER: "xyz"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # DELETE refresh 호출 확인
    executed_sql = [call.args[0] for call in cur_cm.execute.call_args_list]
    assert any("DELETE FROM refresh_tokens" in s for s in executed_sql)
    repo.conn.commit.assert_called()

    # Set-Cookie 헤더에 3개 쿠키 삭제 명령
    cookie_headers = r.headers.get_list("set-cookie")
    assert any("access_token=" in h for h in cookie_headers)
    assert any("refresh_token=" in h for h in cookie_headers)
    assert any("csrf_token=" in h for h in cookie_headers)
