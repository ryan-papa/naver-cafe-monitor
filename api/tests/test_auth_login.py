"""Unit tests for login_service + /api/auth/login."""
from __future__ import annotations

import base64
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.src.auth import login_service as ls
from shared import auth_events
from shared.crypto import (
    aes_gcm_encrypt,
    argon2_hash,
    hmac_sha256,
    rsa_oaep_encrypt,
)
from shared.user_repository import UserRow


AES_KEY = os.urandom(32)
HMAC_KEY = os.urandom(32)


@pytest.fixture(scope="module")
def rsa_pems():
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
def _env(monkeypatch, rsa_pems):
    priv, _ = rsa_pems
    monkeypatch.setenv("AUTH_AES_KEY", base64.b64encode(AES_KEY).decode())
    monkeypatch.setenv("AUTH_HMAC_KEY", base64.b64encode(HMAC_KEY).decode())
    monkeypatch.setenv("AUTH_RSA_PRIVATE_KEY", priv.replace("\n", "\\n"))
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-32-bytes-xxxxxxxxxxx")
    monkeypatch.setattr(auth_events, "log_auth_event", lambda *a, **kw: None)
    from api.src.auth import token_service as ts

    monkeypatch.setattr(ts, "log_auth_event", lambda *a, **kw: None)
    monkeypatch.setattr(ls, "log_auth_event", lambda *a, **kw: None)


def _encrypt(pub: str, value: str) -> str:
    return base64.b64encode(rsa_oaep_encrypt(pub, value.encode())).decode()


def _user(pw: str = "pw!1234567", *, locked=None, failed=0) -> UserRow:
    email = "admin@example.com"
    return UserRow(
        id=7,
        email_enc=aes_gcm_encrypt(email.encode(), AES_KEY),
        email_hmac=hmac_sha256(email.encode(), HMAC_KEY),
        name_enc=aes_gcm_encrypt(b"Admin", AES_KEY),
        password_hash=argon2_hash(pw),
        is_admin=True,
        failed_login_count=failed,
        locked_until=locked,
    )


def _repos(user: UserRow | None):
    ur = MagicMock()
    ur.find_by_email_hmac.return_value = user
    rr = MagicMock()

    rl_conn = MagicMock()
    rl_cur = MagicMock()
    rl_cur.__enter__ = MagicMock(return_value=rl_cur)
    rl_cur.__exit__ = MagicMock(return_value=False)
    rl_cur.fetchone.return_value = None
    rl_conn.cursor.return_value = rl_cur

    @contextmanager
    def _cm():
        yield rl_conn

    return ur, rr, lambda: _cm()


def test_login_user_not_found_returns_401(rsa_pems):
    _, pub = rsa_pems
    ur, rr, rl = _repos(user=None)
    with pytest.raises(ls.LoginError) as e:
        ls.login(
            email_enc_b64=_encrypt(pub, "nouser@example.com"),
            password_enc_b64=_encrypt(pub, "whatever"),
            user_repo=ur,
            refresh_repo=rr,
            rate_limit_factory=rl,
        )
    assert e.value.status_code == 401
    assert e.value.code == "invalid_credentials"


def test_login_wrong_password_returns_401_and_increments(rsa_pems):
    _, pub = rsa_pems
    user = _user(pw="correct123")
    ur, rr, rl = _repos(user=user)
    with pytest.raises(ls.LoginError) as e:
        ls.login(
            email_enc_b64=_encrypt(pub, "admin@example.com"),
            password_enc_b64=_encrypt(pub, "wrong"),
            user_repo=ur,
            refresh_repo=rr,
            rate_limit_factory=rl,
        )
    assert e.value.code == "invalid_credentials"
    ur.increment_failed_login.assert_called_once_with(7)


def test_login_locked_account_returns_429(rsa_pems):
    _, pub = rsa_pems
    locked = datetime.now() + timedelta(minutes=10)
    user = _user(pw="correct123", locked=locked)
    ur, rr, rl = _repos(user=user)
    with pytest.raises(ls.LoginError) as e:
        ls.login(
            email_enc_b64=_encrypt(pub, "admin@example.com"),
            password_enc_b64=_encrypt(pub, "correct123"),
            user_repo=ur,
            refresh_repo=rr,
            rate_limit_factory=rl,
        )
    assert e.value.status_code == 429
    assert e.value.code == "account_locked"


def test_login_success(rsa_pems):
    _, pub = rsa_pems
    user = _user(pw="correct123")
    ur, rr, rl = _repos(user=user)
    pair = ls.login(
        email_enc_b64=_encrypt(pub, "admin@example.com"),
        password_enc_b64=_encrypt(pub, "correct123"),
        user_repo=ur,
        refresh_repo=rr,
        rate_limit_factory=rl,
    )
    assert pair.access_token and pair.refresh_token and pair.csrf_token
    ur.reset_failed_login.assert_called_once_with(7)
    rr.upsert.assert_called_once()
