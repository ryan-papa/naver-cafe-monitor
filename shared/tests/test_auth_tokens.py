"""Unit tests for shared.auth_tokens (TA-04)."""
from __future__ import annotations

import time
from datetime import timedelta

import jwt
import pytest

from shared import auth_tokens as at

SECRET = "test-secret-32-bytes-long-xxxxxx"


def test_issue_access_token_roundtrip():
    token, payload = at.issue_access_token(42, SECRET)
    assert payload.user_id == 42
    assert payload.type == at.ACCESS_TYPE
    assert (payload.expires_at - payload.issued_at) == at.ACCESS_TTL

    verified = at.verify_token(token, SECRET, at.ACCESS_TYPE)
    assert verified.user_id == 42
    assert verified.type == at.ACCESS_TYPE
    assert verified.jti == payload.jti


def test_issue_refresh_token_has_24h_ttl():
    _, payload = at.issue_refresh_token(7, SECRET)
    assert payload.type == at.REFRESH_TYPE
    assert (payload.expires_at - payload.issued_at) == at.REFRESH_TTL


def test_verify_rejects_wrong_secret():
    token, _ = at.issue_access_token(1, SECRET)
    with pytest.raises(at.TokenError):
        at.verify_token(token, "wrong-secret", at.ACCESS_TYPE)


def test_verify_rejects_type_mismatch():
    access_token, _ = at.issue_access_token(1, SECRET)
    with pytest.raises(at.TokenError, match="type mismatch"):
        at.verify_token(access_token, SECRET, at.REFRESH_TYPE)


def test_verify_rejects_expired_token():
    # 직접 expired payload 구성
    past = int(time.time()) - 10
    expired = jwt.encode(
        {"sub": "1", "type": "access", "jti": "x", "iat": past - 60, "exp": past},
        SECRET,
        algorithm=at.ALGO,
    )
    with pytest.raises(at.TokenError, match="expired"):
        at.verify_token(expired, SECRET, at.ACCESS_TYPE)


def test_verify_rejects_malformed_sub():
    bad = jwt.encode(
        {"sub": "not-a-number", "type": "access", "jti": "x", "iat": 0, "exp": 9999999999},
        SECRET,
        algorithm=at.ALGO,
    )
    with pytest.raises(at.TokenError):
        at.verify_token(bad, SECRET, at.ACCESS_TYPE)


def test_jti_is_unique_per_issue():
    _, p1 = at.issue_access_token(1, SECRET)
    _, p2 = at.issue_access_token(1, SECRET)
    assert p1.jti != p2.jti


def test_hash_token_is_deterministic_sha256_hex():
    h = at.hash_token("abc")
    assert len(h) == 64
    assert h == at.hash_token("abc")
    assert h != at.hash_token("abd")


def test_generate_csrf_token_is_random_and_long():
    a = at.generate_csrf_token()
    b = at.generate_csrf_token()
    assert a != b
    assert len(a) >= 32
