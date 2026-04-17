"""로그인 플로우 (TA-10).

순서:
1. IP rate limit
2. email_enc RSA 복호화 → hmac 룩업 → 사용자 조회 (없으면 401)
3. locked_until > now → 429 (lock)
4. 계정 rate limit
5. password_enc RSA 복호화 → argon2 검증 실패 시 increment + (N 초과 시) lock
6. totp_enabled 면 totp_code 검증
7. 성공 → reset_failed_login + issue_pair + login_ok 이벤트
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import pyotp

from shared.auth_events import log_auth_event
from shared.auth_tokens import hash_token
from shared.crypto import (
    aes_gcm_decrypt,
    argon2_verify,
    hmac_sha256,
    rsa_oaep_decrypt,
)
from shared.rate_limit import (
    ACCOUNT_LIMIT,
    ACCOUNT_WINDOW,
    IP_LIMIT,
    IP_WINDOW,
    LOCK_DURATION,
    account_key,
    check_and_increment,
    ip_key,
)
from shared.refresh_token_repository import RefreshTokenRepository
from shared.user_repository import UserRepository

from api.src.auth.token_service import IssuedPair, issue_pair


class LoginError(Exception):
    def __init__(self, status_code: int, code: str):
        self.status_code = status_code
        self.code = code
        super().__init__(code)


@dataclass
class LoginContext:
    ip: str | None = None
    user_agent: str | None = None


def _aes_key() -> bytes:
    return base64.b64decode(os.environ["AUTH_AES_KEY"])


def _hmac_key() -> bytes:
    return base64.b64decode(os.environ["AUTH_HMAC_KEY"])


def _rsa_private_pem() -> str:
    raw = os.environ.get("AUTH_RSA_PRIVATE_KEY", "")
    if not raw:
        raise RuntimeError("AUTH_RSA_PRIVATE_KEY not set")
    return raw.replace("\\n", "\n")


def decrypt_client_field(b64_ciphertext: str) -> bytes:
    return rsa_oaep_decrypt(_rsa_private_pem(), base64.b64decode(b64_ciphertext))


def verify_totp(secret_enc: bytes, code: str) -> bool:
    secret = aes_gcm_decrypt(secret_enc, _aes_key()).decode()
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def _check_rate(bucket: str, *, limit: int, window: timedelta, now: datetime, rl_factory):
    res = check_and_increment(
        bucket, limit=limit, window=window, now=now, connection_factory=rl_factory
    )
    return res


def login(
    *,
    email_enc_b64: str,
    password_enc_b64: str,
    totp_code: str | None,
    user_repo: UserRepository,
    refresh_repo: RefreshTokenRepository,
    ctx: LoginContext | None = None,
    now: datetime | None = None,
    rate_limit_factory=None,
) -> IssuedPair:
    ctx = ctx or LoginContext()
    current = now or datetime.now()

    if ctx.ip:
        res = _check_rate(
            ip_key(ctx.ip),
            limit=IP_LIMIT,
            window=IP_WINDOW,
            now=current,
            rl_factory=rate_limit_factory,
        )
        if not res.allowed:
            raise LoginError(429, "ip_rate_limited")

    email_bytes = decrypt_client_field(email_enc_b64)
    email = email_bytes.decode().strip().lower()
    email_hmac_val = hmac_sha256(email.encode(), _hmac_key())

    user = user_repo.find_by_email_hmac(email_hmac_val)
    if user is None:
        log_auth_event("login_fail", ip=ctx.ip, user_agent=ctx.user_agent)
        raise LoginError(401, "invalid_credentials")

    if user.locked_until and user.locked_until > current:
        log_auth_event(
            "locked", user_id=user.id, ip=ctx.ip, user_agent=ctx.user_agent
        )
        raise LoginError(429, "account_locked")

    res = _check_rate(
        account_key(user.id),
        limit=ACCOUNT_LIMIT,
        window=ACCOUNT_WINDOW,
        now=current,
        rl_factory=rate_limit_factory,
    )
    if not res.allowed:
        raise LoginError(429, "account_rate_limited")

    password_bytes = decrypt_client_field(password_enc_b64)
    password = password_bytes.decode()

    if not argon2_verify(password, user.password_hash):
        user_repo.increment_failed_login(user.id)
        if user.failed_login_count + 1 >= ACCOUNT_LIMIT:
            user_repo.set_lock(user.id, current + LOCK_DURATION)
            log_auth_event(
                "locked", user_id=user.id, ip=ctx.ip, user_agent=ctx.user_agent
            )
        log_auth_event(
            "login_fail", user_id=user.id, ip=ctx.ip, user_agent=ctx.user_agent
        )
        raise LoginError(401, "invalid_credentials")

    if user.totp_enabled:
        if not totp_code or not user.totp_secret_enc:
            raise LoginError(401, "totp_required")
        if not verify_totp(user.totp_secret_enc, totp_code):
            log_auth_event(
                "totp_fail", user_id=user.id, ip=ctx.ip, user_agent=ctx.user_agent
            )
            raise LoginError(401, "totp_invalid")
        log_auth_event(
            "totp_ok", user_id=user.id, ip=ctx.ip, user_agent=ctx.user_agent
        )

    user_repo.reset_failed_login(user.id)
    pair = issue_pair(user.id, repo=refresh_repo)
    log_auth_event(
        "login_ok", user_id=user.id, ip=ctx.ip, user_agent=ctx.user_agent
    )
    return pair


__all__ = [
    "LoginContext",
    "LoginError",
    "decrypt_client_field",
    "hash_token",
    "login",
    "verify_totp",
]
