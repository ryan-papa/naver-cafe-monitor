"""TA-27: login domain-based 2FA branch."""
from __future__ import annotations

import base64
import os
from contextlib import contextmanager
from unittest.mock import MagicMock

import pyotp
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.src.auth import login_service as ls
from shared import auth_events
from shared.auth_tokens import REFRESH_TYPE, verify_token
from shared.crypto import aes_gcm_encrypt, argon2_hash, hmac_sha256, rsa_oaep_encrypt
from shared.user_repository import UserRow

AES = os.urandom(32)
HMAC = os.urandom(32)


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
    monkeypatch.setenv("AUTH_AES_KEY", base64.b64encode(AES).decode())
    monkeypatch.setenv("AUTH_HMAC_KEY", base64.b64encode(HMAC).decode())
    monkeypatch.setenv("AUTH_RSA_PRIVATE_KEY", priv.replace("\n", "\\n"))
    monkeypatch.setenv("AUTH_JWT_SECRET", "test-secret-32-bytes-xxxxxxxxxxx")
    monkeypatch.setattr(auth_events, "log_auth_event", lambda *a, **kw: None)
    from api.src.auth import token_service as ts

    monkeypatch.setattr(ts, "log_auth_event", lambda *a, **kw: None)
    monkeypatch.setattr(ls, "log_auth_event", lambda *a, **kw: None)


def _enc(pub, v):
    return base64.b64encode(rsa_oaep_encrypt(pub, v.encode())).decode()


def _user(totp_secret=None, pw="correct123"):
    email = "admin@example.com"
    return UserRow(
        id=7,
        email_enc=aes_gcm_encrypt(email.encode(), AES),
        email_hmac=hmac_sha256(email.encode(), HMAC),
        name_enc=aes_gcm_encrypt(b"Admin", AES),
        password_hash=argon2_hash(pw),
        totp_secret_enc=aes_gcm_encrypt(totp_secret.encode(), AES) if totp_secret else None,
        totp_enabled=bool(totp_secret),
        backup_codes_hash=None,
        is_admin=True,
        failed_login_count=0,
        locked_until=None,
    )


def _repos(user):
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


def test_internal_login_skips_totp_even_when_enabled(pems):
    _, pub = pems
    secret = pyotp.random_base32()
    user = _user(totp_secret=secret)  # totp_enabled=True
    ur, rr, rl = _repos(user)

    # 내부 로그인: TOTP 코드 없이도 통과
    pair = ls.login(
        email_enc_b64=_enc(pub, "admin@example.com"),
        password_enc_b64=_enc(pub, "correct123"),
        totp_code=None,
        user_repo=ur,
        refresh_repo=rr,
        ctx=ls.LoginContext(internal=True),
        rate_limit_factory=rl,
    )
    secret_env = os.environ["AUTH_JWT_SECRET"]
    payload = verify_token(pair.refresh_token, secret_env, REFRESH_TYPE)
    assert payload.totp_setup_required is False


def test_external_login_without_totp_setup_required(pems):
    _, pub = pems
    user = _user(totp_secret=None)  # totp_enabled=False
    ur, rr, rl = _repos(user)

    pair = ls.login(
        email_enc_b64=_enc(pub, "admin@example.com"),
        password_enc_b64=_enc(pub, "correct123"),
        totp_code=None,
        user_repo=ur,
        refresh_repo=rr,
        ctx=ls.LoginContext(internal=False),
        rate_limit_factory=rl,
    )
    secret_env = os.environ["AUTH_JWT_SECRET"]
    payload = verify_token(pair.access_token, secret_env, "access")
    assert payload.totp_setup_required is True


def test_external_login_with_totp_enabled_still_requires_code(pems):
    _, pub = pems
    secret = pyotp.random_base32()
    user = _user(totp_secret=secret)
    ur, rr, rl = _repos(user)

    with pytest.raises(ls.LoginError, match="totp_required"):
        ls.login(
            email_enc_b64=_enc(pub, "admin@example.com"),
            password_enc_b64=_enc(pub, "correct123"),
            totp_code=None,
            user_repo=ur,
            refresh_repo=rr,
            ctx=ls.LoginContext(internal=False),
            rate_limit_factory=rl,
        )


def test_internal_login_without_totp_has_no_setup_required(pems):
    _, pub = pems
    user = _user(totp_secret=None)
    ur, rr, rl = _repos(user)
    pair = ls.login(
        email_enc_b64=_enc(pub, "admin@example.com"),
        password_enc_b64=_enc(pub, "correct123"),
        totp_code=None,
        user_repo=ur,
        refresh_repo=rr,
        ctx=ls.LoginContext(internal=True),
        rate_limit_factory=rl,
    )
    secret_env = os.environ["AUTH_JWT_SECRET"]
    payload = verify_token(pair.access_token, secret_env, "access")
    assert payload.totp_setup_required is False
