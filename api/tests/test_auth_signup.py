"""Unit tests for signup_service."""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.src.auth import signup_service as ss
from shared import auth_events
from shared.crypto import hmac_sha256, rsa_oaep_encrypt
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
    monkeypatch.setattr(ss, "log_auth_event", lambda *a, **kw: None)
    from api.src.auth import token_service as ts

    monkeypatch.setattr(ts, "log_auth_event", lambda *a, **kw: None)


def _encrypt(pub: str, v: str) -> str:
    return base64.b64encode(rsa_oaep_encrypt(pub, v.encode())).decode()


def _user_repo(existing_email: UserRow | None = None):
    ur = MagicMock()
    ur.find_by_email_hmac.return_value = existing_email
    ur.create.return_value = 123
    return ur


def test_validate_password_policy():
    with pytest.raises(ss.SignupError, match="password_too_short"):
        ss.validate_password("ab1!")
    with pytest.raises(ss.SignupError, match="password_needs_letter"):
        ss.validate_password("1234567890!")
    with pytest.raises(ss.SignupError, match="password_needs_digit"):
        ss.validate_password("abcdefghij!")
    with pytest.raises(ss.SignupError, match="password_needs_symbol"):
        ss.validate_password("abcdefghij1")
    ss.validate_password("abcdefgh1!")


def test_signup_rejects_duplicate_email(rsa_pems):
    _, pub = rsa_pems
    existing = UserRow(
        id=1,
        email_enc=b"x",
        email_hmac=hmac_sha256(b"dup@example.com", HMAC_KEY),
        name_enc=b"x",
        password_hash="$x",
        is_admin=False,
        failed_login_count=0,
        locked_until=None,
    )
    ur = _user_repo(existing_email=existing)
    rr = MagicMock()
    with pytest.raises(ss.SignupError, match="email_exists"):
        ss.signup(
            email_enc_b64=_encrypt(pub, "dup@example.com"),
            name_enc_b64=_encrypt(pub, "X"),
            password_enc_b64=_encrypt(pub, "strong1234!"),
            user_repo=ur,
            refresh_repo=rr,
        )


def test_signup_creates_user_and_returns_pair(rsa_pems):
    _, pub = rsa_pems
    ur = _user_repo()
    rr = MagicMock()
    result = ss.signup(
        email_enc_b64=_encrypt(pub, "new@example.com"),
        name_enc_b64=_encrypt(pub, "Alice"),
        password_enc_b64=_encrypt(pub, "strongPW!123"),
        user_repo=ur,
        refresh_repo=rr,
    )
    assert result.user_id == 123
    assert result.pair.access_token and result.pair.refresh_token and result.pair.csrf_token
    ur.create.assert_called_once()
    rr.upsert.assert_called_once()


def test_signup_rejects_weak_password(rsa_pems):
    _, pub = rsa_pems
    ur = _user_repo()
    rr = MagicMock()
    with pytest.raises(ss.SignupError, match="password_too_short"):
        ss.signup(
            email_enc_b64=_encrypt(pub, "a@b.com"),
            name_enc_b64=_encrypt(pub, "X"),
            password_enc_b64=_encrypt(pub, "short1!"),
            user_repo=ur,
            refresh_repo=rr,
        )
