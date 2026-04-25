"""회원가입 플로우.

POST /api/auth/signup: 이메일·이름·비번 검증 → users insert → 자동 로그인 (issue_pair)

비번 정책: 최소 10자 + 영문 + 숫자 + 특수문자.
"""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass

from api.src.auth.login_service import decrypt_client_field
from api.src.auth.token_service import IssuedPair, issue_pair
from shared.auth_events import log_auth_event
from shared.crypto import aes_gcm_encrypt, argon2_hash, hmac_sha256
from shared.refresh_token_repository import RefreshTokenRepository
from shared.user_repository import UserRepository


class SignupError(Exception):
    def __init__(self, status_code: int, code: str):
        self.status_code = status_code
        self.code = code
        super().__init__(code)


@dataclass
class SignupResult:
    user_id: int
    pair: IssuedPair


_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password(pw: str) -> None:
    if len(pw) < 10:
        raise SignupError(400, "password_too_short")
    if not re.search(r"[A-Za-z]", pw):
        raise SignupError(400, "password_needs_letter")
    if not re.search(r"[0-9]", pw):
        raise SignupError(400, "password_needs_digit")
    if not _SPECIAL.search(pw):
        raise SignupError(400, "password_needs_symbol")


def _aes_key() -> bytes:
    return base64.b64decode(os.environ["AUTH_AES_KEY"])


def _hmac_key() -> bytes:
    return base64.b64decode(os.environ["AUTH_HMAC_KEY"])


def signup(
    *,
    email_enc_b64: str,
    name_enc_b64: str,
    password_enc_b64: str,
    user_repo: UserRepository,
    refresh_repo: RefreshTokenRepository,
    ip: str | None = None,
    user_agent: str | None = None,
) -> SignupResult:
    email_raw = decrypt_client_field(email_enc_b64).decode().strip()
    name_raw = decrypt_client_field(name_enc_b64).decode().strip()
    password = decrypt_client_field(password_enc_b64).decode()

    if not email_raw or "@" not in email_raw:
        raise SignupError(400, "email_invalid")
    if not name_raw or len(name_raw) > 100:
        raise SignupError(400, "name_invalid")
    validate_password(password)

    email_hmac_val = hmac_sha256(email_raw.lower().encode(), _hmac_key())
    if user_repo.find_by_email_hmac(email_hmac_val) is not None:
        raise SignupError(409, "email_exists")

    aes = _aes_key()
    email_enc = aes_gcm_encrypt(email_raw.encode(), aes)
    name_enc = aes_gcm_encrypt(name_raw.encode(), aes)
    pw_hash = argon2_hash(password)

    user_id = user_repo.create(
        email_enc=email_enc,
        email_hmac=email_hmac_val,
        name_enc=name_enc,
        password_hash=pw_hash,
    )

    log_auth_event("signup", user_id=user_id, ip=ip, user_agent=user_agent)

    pair = issue_pair(user_id, repo=refresh_repo)
    log_auth_event("login_ok", user_id=user_id, ip=ip, user_agent=user_agent)

    return SignupResult(user_id=user_id, pair=pair)
