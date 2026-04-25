"""F-15 호환성: 과거 발급 토큰의 `totp_setup_required` 클레임이 무시됨을 보장."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import jwt
import pytest

from shared.auth_tokens import ACCESS_TYPE, ALGO, TokenPayload, verify_token


SECRET = "test-secret-32-bytes-xxxxxxxxxxx"


def _legacy_token(jti: str = "legacy-jti", *, claim_value: bool = True) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "42",
        "type": ACCESS_TYPE,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + 3600,
        "totp_setup_required": claim_value,
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


@pytest.mark.parametrize("claim_value", [True, False])
def test_legacy_totp_setup_required_claim_is_ignored(claim_value):
    token = _legacy_token(claim_value=claim_value)
    decoded = verify_token(token, SECRET, ACCESS_TYPE)

    assert isinstance(decoded, TokenPayload)
    assert decoded.user_id == 42
    assert decoded.type == ACCESS_TYPE
    assert not hasattr(decoded, "totp_setup_required"), (
        "TokenPayload 는 더 이상 totp_setup_required 필드를 가지지 않아야 함"
    )
