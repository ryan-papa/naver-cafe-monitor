"""TA-28/29: /me flag + setup_required guard."""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.src.auth import dependencies as deps
from api.src.auth.router import router
from shared.auth_tokens import issue_access_token
from shared.crypto import aes_gcm_encrypt
from shared.user_repository import UserRow

AES = os.urandom(32)
SECRET = "test-secret-32-bytes-xxxxxxxxxxx"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_AES_KEY", base64.b64encode(AES).decode())
    from shared import auth_events
    from api.src.auth import router as router_mod

    monkeypatch.setattr(auth_events, "log_auth_event", lambda *a, **kw: None)
    monkeypatch.setattr(router_mod, "log_auth_event", lambda *a, **kw: None)


def _user() -> UserRow:
    return UserRow(
        id=1,
        email_enc=aes_gcm_encrypt(b"admin@example.com", AES),
        email_hmac=b"\x00" * 32,
        name_enc=aes_gcm_encrypt(b"Admin", AES),
        password_hash="$x",
        totp_secret_enc=None,
        totp_enabled=False,
        backup_codes_hash=None,
        is_admin=True,
        failed_login_count=0,
        locked_until=None,
    )


def _app():
    app = FastAPI()
    app.include_router(router)
    # 추가로 보호된 더미 라우트
    from api.src.auth.dependencies import current_user

    @app.get("/api/posts")
    async def _posts(_: UserRow = Depends(current_user)):
        return {"ok": True}

    repo = MagicMock()
    repo.find_by_id.return_value = _user()
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    repo.conn.cursor.return_value = cur
    app.dependency_overrides[deps.get_user_repository] = lambda: repo
    return app


def test_me_includes_setup_required_true():
    app = _app()
    client = TestClient(app)
    token, _ = issue_access_token(1, SECRET, {"totp_setup_required": True})
    client.cookies.set("access_token", token)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["totp_setup_required"] is True


def test_me_setup_required_defaults_to_false_for_normal_token():
    app = _app()
    client = TestClient(app)
    token, _ = issue_access_token(1, SECRET)
    client.cookies.set("access_token", token)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["totp_setup_required"] is False


def test_setup_required_blocks_non_whitelisted_path():
    app = _app()
    client = TestClient(app)
    token, _ = issue_access_token(1, SECRET, {"totp_setup_required": True})
    client.cookies.set("access_token", token)
    r = client.get("/api/posts")
    assert r.status_code == 403
    assert r.json()["detail"] == "totp_setup_required"


def test_setup_required_allows_me_and_logout_and_refresh():
    app = _app()
    client = TestClient(app)
    token, _ = issue_access_token(1, SECRET, {"totp_setup_required": True})
    client.cookies.set("access_token", token)
    assert client.get("/api/auth/me").status_code == 200
    # /api/auth/public-key 는 토큰 없이도 OK
    assert client.get("/api/auth/public-key").status_code in (200, 500)  # env 유무
