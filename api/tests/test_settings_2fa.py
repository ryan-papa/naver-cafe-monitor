"""TA-30: /api/settings/2fa/*."""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

import pyotp
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.src.auth import dependencies as deps
from api.src.auth.settings_2fa import router
from shared import auth_events
from shared.auth_tokens import issue_access_token
from shared.crypto import aes_gcm_encrypt, argon2_hash, rsa_oaep_encrypt
from shared.user_repository import UserRow

AES = os.urandom(32)
SECRET = "test-secret-32-bytes-xxxxxxxxxxx"


@pytest.fixture(scope="module")
def pems():
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = k.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        k.public_key()
        .public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        .decode()
    )
    return priv, pub


@pytest.fixture(autouse=True)
def _env(monkeypatch, pems):
    priv, _ = pems
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_AES_KEY", base64.b64encode(AES).decode())
    monkeypatch.setenv("AUTH_RSA_PRIVATE_KEY", priv.replace("\n", "\\n"))
    monkeypatch.setenv("AUTH_HMAC_KEY", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setattr(auth_events, "log_auth_event", lambda *a, **kw: None)
    from api.src.auth import settings_2fa as s2fa

    monkeypatch.setattr(s2fa, "log_auth_event", lambda *a, **kw: None)
    from api.src.auth import token_service as ts

    monkeypatch.setattr(ts, "log_auth_event", lambda *a, **kw: None)


def _user(
    *,
    totp_enabled=False,
    secret: str | None = None,
    backup_codes_hash_json: str | None = None,
    password_hash: str | None = None,
) -> UserRow:
    email = "admin@example.com"
    return UserRow(
        id=11,
        email_enc=aes_gcm_encrypt(email.encode(), AES),
        email_hmac=b"\x00" * 32,
        name_enc=aes_gcm_encrypt(b"Admin", AES),
        password_hash=password_hash or argon2_hash("correct123"),
        totp_secret_enc=aes_gcm_encrypt(secret.encode(), AES) if secret else None,
        totp_enabled=totp_enabled,
        backup_codes_hash=backup_codes_hash_json,
        is_admin=True,
        failed_login_count=0,
        locked_until=None,
    )


def _make_app(user: UserRow, setup_required: bool = True):
    app = FastAPI()
    app.include_router(router)

    repo = MagicMock()
    repo.find_by_id.return_value = user
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    repo.conn.cursor.return_value = cur
    app.dependency_overrides[deps.get_user_repository] = lambda: repo

    client = TestClient(app)
    extra = {"totp_setup_required": True} if setup_required else None
    token, _ = issue_access_token(user.id, SECRET, extra)
    client.cookies.set("access_token", token)
    return client, repo, cur


def _enc(pub, v):
    return base64.b64encode(rsa_oaep_encrypt(pub, v.encode())).decode()


# ── status ──

def test_status_returns_flags():
    u = _user()
    client, _, _ = _make_app(u)
    r = client.get("/api/settings/2fa/status")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "totp_enabled": False,
        "has_pending_secret": False,
        "setup_required": True,
    }


# ── init ──

def test_init_creates_secret_and_returns_codes():
    u = _user()
    client, repo, cur = _make_app(u)
    r = client.post("/api/settings/2fa/init")
    assert r.status_code == 200
    body = r.json()
    assert body["otpauth_url"].startswith("otpauth://totp/")
    assert isinstance(body["backup_codes"], list) and len(body["backup_codes"]) == 10
    assert body["reused"] is False
    # UPDATE 호출 확인
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any("totp_secret_enc = %s" in s and "totp_enabled = FALSE" in s for s in executed)


def test_init_reuses_existing_pending_secret():
    secret = pyotp.random_base32()
    u = _user(secret=secret)  # totp_enabled=False, secret exists
    client, _, _ = _make_app(u)
    r = client.post("/api/settings/2fa/init")
    assert r.status_code == 200
    body = r.json()
    assert body["reused"] is True
    assert body["backup_codes"] is None


def test_init_rejects_when_already_enabled():
    secret = pyotp.random_base32()
    u = _user(totp_enabled=True, secret=secret)
    client, _, _ = _make_app(u)
    r = client.post("/api/settings/2fa/init")
    assert r.status_code == 400
    assert r.json()["detail"] == "already_enabled"


# ── confirm ──

def test_confirm_wrong_code_returns_401():
    secret = pyotp.random_base32()
    u = _user(secret=secret)
    client, _, _ = _make_app(u)
    r = client.post("/api/settings/2fa/confirm", json={"totp_code": "000000"})
    assert r.status_code == 401


def test_confirm_success_enables_and_sets_cookies():
    secret = pyotp.random_base32()
    u = _user(secret=secret)
    client, repo, cur = _make_app(u)
    code = pyotp.TOTP(secret).now()
    r = client.post("/api/settings/2fa/confirm", json={"totp_code": code})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any("totp_enabled = TRUE" in s for s in executed)
    # 쿠키 3종 설정
    raw = r.headers.get_list("set-cookie")
    assert any(h.startswith("access_token=") for h in raw)
    assert any(h.startswith("refresh_token=") for h in raw)
    assert any(h.startswith("csrf_token=") for h in raw)


# ── reset ──

def test_reset_wrong_password_returns_401(pems):
    _, pub = pems
    import json

    from shared.crypto import argon2_hash
    secret = pyotp.random_base32()
    codes_hash = json.dumps([argon2_hash("CODE0")])
    u = _user(
        totp_enabled=True,
        secret=secret,
        backup_codes_hash_json=codes_hash,
        password_hash=argon2_hash("correct123"),
    )
    client, _, _ = _make_app(u, setup_required=False)
    r = client.post(
        "/api/settings/2fa/reset",
        json={"password_enc": _enc(pub, "wrong"), "totp_code": "000000"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_password"


def test_reset_with_backup_code_issues_new_secret(pems):
    _, pub = pems
    import json

    secret = pyotp.random_base32()
    backup = "BACKUP1234"
    codes_hash = json.dumps([argon2_hash(backup)])
    u = _user(
        totp_enabled=True,
        secret=secret,
        backup_codes_hash_json=codes_hash,
    )
    client, _, cur = _make_app(u, setup_required=False)
    r = client.post(
        "/api/settings/2fa/reset",
        json={"password_enc": _enc(pub, "correct123"), "backup_code": backup},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["otpauth_url"].startswith("otpauth://totp/")
    assert len(body["backup_codes"]) == 10
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any("totp_secret_enc = %s" in s and "backup_codes_hash = %s" in s for s in executed)


def test_reset_with_totp_code_succeeds(pems):
    _, pub = pems
    import json

    secret = pyotp.random_base32()
    codes_hash = json.dumps([argon2_hash("CODE0")])
    u = _user(
        totp_enabled=True,
        secret=secret,
        backup_codes_hash_json=codes_hash,
    )
    client, _, _ = _make_app(u, setup_required=False)
    code = pyotp.TOTP(secret).now()
    r = client.post(
        "/api/settings/2fa/reset",
        json={"password_enc": _enc(pub, "correct123"), "totp_code": code},
    )
    assert r.status_code == 200


def test_reset_without_any_second_factor_fails(pems):
    _, pub = pems
    u = _user(
        totp_enabled=True,
        secret=pyotp.random_base32(),
        backup_codes_hash_json="[]",
    )
    client, _, _ = _make_app(u, setup_required=False)
    r = client.post(
        "/api/settings/2fa/reset",
        json={"password_enc": _enc(pub, "correct123")},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "second_factor_invalid"
