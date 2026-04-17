"""JWT 발급·검증 유틸 (TA-04).

- access_token: 1h, type='access'
- refresh_token: 24h, type='refresh'
- HS256 서명, 시크릿은 외부에서 주입 (AUTH_JWT_SECRET 환경변수 또는 DI)
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(hours=24)
ALGO = "HS256"

ACCESS_TYPE = "access"
REFRESH_TYPE = "refresh"


class TokenError(Exception):
    """유효하지 않은 토큰(만료·서명 실패·타입 불일치 등)."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    type: str
    jti: str
    issued_at: datetime
    expires_at: datetime
    totp_setup_required: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue(
    user_id: int,
    token_type: str,
    ttl: timedelta,
    secret: str,
    extra_claims: dict | None = None,
) -> tuple[str, TokenPayload]:
    now = _now()
    exp = now + ttl
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, secret, algorithm=ALGO)
    return token, TokenPayload(
        user_id=user_id, type=token_type, jti=jti, issued_at=now, expires_at=exp
    )


def issue_access_token(
    user_id: int, secret: str, extra_claims: dict | None = None
) -> tuple[str, TokenPayload]:
    return _issue(user_id, ACCESS_TYPE, ACCESS_TTL, secret, extra_claims)


def issue_refresh_token(
    user_id: int, secret: str, extra_claims: dict | None = None
) -> tuple[str, TokenPayload]:
    return _issue(user_id, REFRESH_TYPE, REFRESH_TTL, secret, extra_claims)


def verify_token(token: str, secret: str, expected_type: str) -> TokenPayload:
    try:
        decoded = jwt.decode(token, secret, algorithms=[ALGO])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError("invalid") from e

    if decoded.get("type") != expected_type:
        raise TokenError(f"type mismatch: expected {expected_type}, got {decoded.get('type')}")

    try:
        user_id = int(decoded["sub"])
    except (KeyError, ValueError, TypeError) as e:
        raise TokenError("sub missing/invalid") from e

    return TokenPayload(
        user_id=user_id,
        type=decoded["type"],
        jti=decoded.get("jti", ""),
        issued_at=datetime.fromtimestamp(decoded["iat"], tz=timezone.utc),
        expires_at=datetime.fromtimestamp(decoded["exp"], tz=timezone.utc),
        totp_setup_required=bool(decoded.get("totp_setup_required", False)),
    )


def hash_token(token: str) -> str:
    """refresh_tokens.token_hash 저장용 SHA-256 hex."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
