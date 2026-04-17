"""Unit tests for signup_service (TA-09)."""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock

import pyotp
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from api.src.auth import signup_service as ss
from shared import auth_events
from shared.crypto import aes_gcm_encrypt, argon2_hash, hmac_sha256, rsa_oaep_encrypt
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
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    ur.conn.cursor.return_value = cur
    return ur, cur


# ── password policy ──

def test_validate_password_policy():
    with pytest.raises(ss.SignupError, match="password_too_short"):
        ss.validate_password("ab1!")
    with pytest.raises(ss.SignupError, match="password_needs_letter"):
        ss.validate_password("1234567890!")
    with pytest.raises(ss.SignupError, match="password_needs_digit"):
        ss.validate_password("abcdefghij!")
    with pytest.raises(ss.SignupError, match="password_needs_symbol"):
        ss.validate_password("abcdefghij1")
    ss.validate_password("abcdefgh1!")  # OK


# ── signup ──

def test_signup_rejects_duplicate_email(rsa_pems):
    _, pub = rsa_pems
    existing = UserRow(
        id=1,
        email_enc=b"x",
        email_hmac=hmac_sha256(b"dup@example.com", HMAC_KEY),
        name_enc=b"x",
        password_hash="$x",
        totp_secret_enc=None,
        totp_enabled=False,
        backup_codes_hash=None,
        is_admin=False,
        failed_login_count=0,
        locked_until=None,
    )
    ur, _ = _user_repo(existing_email=existing)
    with pytest.raises(ss.SignupError, match="email_exists"):
        ss.signup(
            email_enc_b64=_encrypt(pub, "dup@example.com"),
            name_enc_b64=_encrypt(pub, "X"),
            password_enc_b64=_encrypt(pub, "strong1234!"),
            user_repo=ur,
        )


def test_signup_creates_user_and_returns_backup_codes_and_url(rsa_pems):
    _, pub = rsa_pems
    ur, cur = _user_repo()
    result = ss.signup(
        email_enc_b64=_encrypt(pub, "new@example.com"),
        name_enc_b64=_encrypt(pub, "Alice"),
        password_enc_b64=_encrypt(pub, "strongPW!123"),
        user_repo=ur,
    )
    assert result.user_id == 123
    assert result.pending_token
    assert result.otpauth_url.startswith("otpauth://totp/")
    assert len(result.backup_codes) == 10
    assert all(len(c) == 10 for c in result.backup_codes)
    ur.create.assert_called_once()
    # UPDATE totp_secret_enc 실행 확인
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any("totp_secret_enc = %s" in s and "totp_enabled = FALSE" in s for s in executed)


def test_signup_rejects_weak_password(rsa_pems):
    _, pub = rsa_pems
    ur, _ = _user_repo()
    with pytest.raises(ss.SignupError, match="password_too_short"):
        ss.signup(
            email_enc_b64=_encrypt(pub, "a@b.com"),
            name_enc_b64=_encrypt(pub, "X"),
            password_enc_b64=_encrypt(pub, "short1!"),
            user_repo=ur,
        )


# ── confirm ──

def _user_with_totp(secret: str, enabled=False) -> UserRow:
    return UserRow(
        id=123,
        email_enc=b"x",
        email_hmac=b"\x00" * 32,
        name_enc=b"x",
        password_hash="$x",
        totp_secret_enc=aes_gcm_encrypt(secret.encode(), AES_KEY),
        totp_enabled=enabled,
        backup_codes_hash=None,
        is_admin=False,
        failed_login_count=0,
        locked_until=None,
    )


def test_confirm_rejects_invalid_pending_token():
    ur, _ = _user_repo()
    ur.find_by_id.return_value = _user_with_totp("JBSWY3DPEHPK3PXP")
    rr = MagicMock()
    with pytest.raises(ss.SignupError, match="pending_invalid"):
        ss.confirm_signup(
            pending_token="not-a-jwt",
            totp_code="000000",
            user_repo=ur,
            refresh_repo=rr,
        )


def test_confirm_rejects_wrong_totp():
    secret = pyotp.random_base32()
    ur, _ = _user_repo()
    ur.find_by_id.return_value = _user_with_totp(secret)
    rr = MagicMock()
    pending = ss._issue_pending(123)
    with pytest.raises(ss.SignupError, match="totp_invalid"):
        ss.confirm_signup(
            pending_token=pending,
            totp_code="000000",
            user_repo=ur,
            refresh_repo=rr,
        )


def test_confirm_success_enables_totp_and_issues_pair():
    secret = pyotp.random_base32()
    ur, cur = _user_repo()
    ur.find_by_id.return_value = _user_with_totp(secret)
    rr = MagicMock()
    pending = ss._issue_pending(123)
    code = pyotp.TOTP(secret).now()

    result = ss.confirm_signup(
        pending_token=pending,
        totp_code=code,
        user_repo=ur,
        refresh_repo=rr,
    )
    assert result.user_id == 123
    assert result.pair.access_token and result.pair.refresh_token
    executed = [c.args[0] for c in cur.execute.call_args_list]
    assert any("totp_enabled = TRUE" in s for s in executed)
    rr.upsert.assert_called_once()


def test_confirm_already_enabled():
    secret = pyotp.random_base32()
    ur, _ = _user_repo()
    ur.find_by_id.return_value = _user_with_totp(secret, enabled=True)
    rr = MagicMock()
    pending = ss._issue_pending(123)
    with pytest.raises(ss.SignupError, match="already_confirmed"):
        ss.confirm_signup(
            pending_token=pending,
            totp_code="000000",
            user_repo=ur,
            refresh_repo=rr,
        )


# ── backup code ──

def test_verify_backup_code_matches_and_rejects():
    codes = ["ABCD123456", "ZZZZ000000"]
    hashes_json = __import__("json").dumps([argon2_hash(c) for c in codes])
    assert ss.verify_backup_code("ABCD123456", hashes_json) == 0
    assert ss.verify_backup_code("ZZZZ000000", hashes_json) == 1
    assert ss.verify_backup_code("unknown", hashes_json) is None
