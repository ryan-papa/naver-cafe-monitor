"""회원가입 플로우 (TA-09).

2단계:
  1) POST /api/auth/signup: 이메일·이름·비번 검증 → users insert (totp_enabled=False)
     + TOTP secret 생성 → users.totp_secret_enc 저장 (아직 비활성)
     + 백업코드 10개 생성 → argon2 해시해서 저장, 평문은 응답 1회 반환
     + signup_pending_token (JWT 10분) 반환
  2) POST /api/auth/signup/confirm: pending token + totp_code 검증 → totp_enabled=True
     + 자동 로그인 (issue_pair)

비번 정책: 최소 10자 + 영문 + 숫자 + 특수문자.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
import pyotp

from api.src.auth.login_service import decrypt_client_field, verify_totp
from api.src.auth.token_service import IssuedPair, issue_pair
from shared.auth_events import log_auth_event
from shared.auth_tokens import ALGO
from shared.crypto import aes_gcm_encrypt, argon2_hash, argon2_verify, hmac_sha256
from shared.refresh_token_repository import RefreshTokenRepository
from shared.user_repository import UserRepository

PENDING_TYPE: Literal["signup_pending"] = "signup_pending"
PENDING_TTL = timedelta(minutes=10)
BACKUP_CODE_COUNT = 10
BACKUP_CODE_LEN = 10
TOTP_ISSUER = "naver-cafe-monitor"


class SignupError(Exception):
    def __init__(self, status_code: int, code: str):
        self.status_code = status_code
        self.code = code
        super().__init__(code)


@dataclass
class SignupResult:
    user_id: int
    pending_token: str
    otpauth_url: str
    backup_codes: list[str]  # 평문, 1회만 노출


@dataclass
class ConfirmResult:
    user_id: int
    pair: IssuedPair


# ─── policy ───
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


def _jwt_secret() -> str:
    return os.environ["AUTH_JWT_SECRET"]


# ─── pending token ───
def _issue_pending(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": PENDING_TYPE,
            "iat": int(now.timestamp()),
            "exp": int((now + PENDING_TTL).timestamp()),
        },
        _jwt_secret(),
        algorithm=ALGO,
    )


def _verify_pending(token: str) -> int:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGO])
    except jwt.InvalidTokenError as e:
        raise SignupError(401, "pending_invalid") from e
    if payload.get("type") != PENDING_TYPE:
        raise SignupError(401, "pending_invalid")
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError) as e:
        raise SignupError(401, "pending_invalid") from e


# ─── backup codes ───
def _gen_backup_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(BACKUP_CODE_LEN))


def _gen_backup_codes() -> tuple[list[str], str]:
    codes = [_gen_backup_code() for _ in range(BACKUP_CODE_COUNT)]
    hashes = [argon2_hash(c) for c in codes]
    return codes, json.dumps(hashes)


def verify_backup_code(code: str, hashes_json: str) -> int | None:
    """Returns matched index (0..N-1) or None. 호출 측이 해당 index 를 DB 에서 제거해야 함."""
    try:
        hashes = json.loads(hashes_json or "[]")
    except json.JSONDecodeError:
        return None
    for idx, h in enumerate(hashes):
        if argon2_verify(code, h):
            return idx
    return None


# ─── signup ───
def signup(
    *,
    email_enc_b64: str,
    name_enc_b64: str,
    password_enc_b64: str,
    user_repo: UserRepository,
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

    totp_secret = pyotp.random_base32()
    totp_secret_enc = aes_gcm_encrypt(totp_secret.encode(), aes)
    codes, codes_hash_json = _gen_backup_codes()

    # set_totp 는 totp_enabled=TRUE 로 설정 → 직접 UPDATE 로 enabled=FALSE 유지
    with user_repo.conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET totp_secret_enc = %s, backup_codes_hash = %s, "
            "totp_enabled = FALSE WHERE id = %s",
            (totp_secret_enc, codes_hash_json, user_id),
        )
    user_repo.conn.commit()

    otpauth_url = pyotp.TOTP(totp_secret).provisioning_uri(
        name=email_raw, issuer_name=TOTP_ISSUER
    )

    log_auth_event("signup", user_id=user_id, ip=ip, user_agent=user_agent)

    return SignupResult(
        user_id=user_id,
        pending_token=_issue_pending(user_id),
        otpauth_url=otpauth_url,
        backup_codes=codes,
    )


def confirm_signup(
    *,
    pending_token: str,
    totp_code: str,
    user_repo: UserRepository,
    refresh_repo: RefreshTokenRepository,
    ip: str | None = None,
    user_agent: str | None = None,
) -> ConfirmResult:
    user_id = _verify_pending(pending_token)
    user = user_repo.find_by_id(user_id)
    if user is None:
        raise SignupError(404, "user_not_found")
    if user.totp_enabled:
        raise SignupError(409, "already_confirmed")
    if not user.totp_secret_enc:
        raise SignupError(500, "totp_secret_missing")

    if not verify_totp(user.totp_secret_enc, totp_code):
        log_auth_event(
            "totp_fail", user_id=user_id, ip=ip, user_agent=user_agent
        )
        raise SignupError(401, "totp_invalid")

    with user_repo.conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET totp_enabled = TRUE WHERE id = %s", (user_id,)
        )
    user_repo.conn.commit()

    pair = issue_pair(user_id, repo=refresh_repo)
    log_auth_event("totp_ok", user_id=user_id, ip=ip, user_agent=user_agent)
    log_auth_event("login_ok", user_id=user_id, ip=ip, user_agent=user_agent)
    return ConfirmResult(user_id=user_id, pair=pair)
