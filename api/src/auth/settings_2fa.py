"""`/api/settings/2fa/*` 라우터 (TA-30).

엔드포인트:
- GET  /status   : totp_enabled / has_pending_secret / setup_required
- POST /init     : secret 없으면 생성·저장, 있으면 재사용. 최초 생성 시 backup_codes 평문 반환
- POST /confirm  : totp_code 검증 → totp_enabled=True + 새 pair (setup_required=False) 쿠키 세팅
- POST /reset    : 비번 + (totp OR backup) 본인확인 → 새 secret + 새 backup_codes 발급
"""
from __future__ import annotations

import base64
import os

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from api.src.auth.cookies import set_access_cookie, set_csrf_cookie, set_refresh_cookie
from api.src.auth.dependencies import (
    CurrentAuth,
    current_auth,
    decrypted_email_and_name,
    get_user_repository,
)
from api.src.auth.login_service import decrypt_client_field, verify_totp
from api.src.auth.signup_service import (
    _gen_backup_codes,
    verify_backup_code,
)
from api.src.auth.token_service import issue_pair
from shared.auth_events import log_auth_event
from shared.crypto import aes_gcm_decrypt, aes_gcm_encrypt, argon2_verify
from shared.refresh_token_repository import RefreshTokenRepository
from shared.user_repository import UserRepository

router = APIRouter(prefix="/api/settings/2fa", tags=["settings-2fa"])
TOTP_ISSUER = "naver-cafe-monitor"


def _aes_key() -> bytes:
    return base64.b64decode(os.environ["AUTH_AES_KEY"])


def _otpauth_url(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)


@router.get("/status")
async def get_status(auth: CurrentAuth = Depends(current_auth)) -> dict:
    u = auth.user
    return {
        "totp_enabled": u.totp_enabled,
        "has_pending_secret": (u.totp_secret_enc is not None and not u.totp_enabled),
        "setup_required": auth.token.totp_setup_required,
    }


@router.post("/init")
async def init_2fa(
    auth: CurrentAuth = Depends(current_auth),
    repo: UserRepository = Depends(get_user_repository),
) -> dict:
    u = auth.user
    if u.totp_enabled:
        raise HTTPException(400, "already_enabled")

    email, _ = decrypted_email_and_name(u)
    aes = _aes_key()

    if u.totp_secret_enc:
        # 이미 진행 중 - secret 재사용, 평문 codes 는 재노출 불가
        secret = aes_gcm_decrypt(u.totp_secret_enc, aes).decode()
        return {
            "otpauth_url": _otpauth_url(secret, email),
            "backup_codes": None,
            "reused": True,
        }

    # 최초 생성
    secret = pyotp.random_base32()
    codes, codes_hash_json = _gen_backup_codes()
    with repo.conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET totp_secret_enc = %s, backup_codes_hash = %s, "
            "totp_enabled = FALSE WHERE id = %s",
            (aes_gcm_encrypt(secret.encode(), aes), codes_hash_json, u.id),
        )
    repo.conn.commit()
    return {
        "otpauth_url": _otpauth_url(secret, email),
        "backup_codes": codes,
        "reused": False,
    }


class ConfirmBody(BaseModel):
    totp_code: str = Field(..., min_length=6, max_length=10)


@router.post("/confirm")
async def confirm_2fa(
    body: ConfirmBody,
    request: Request,
    response: Response,
    auth: CurrentAuth = Depends(current_auth),
    repo: UserRepository = Depends(get_user_repository),
) -> dict:
    u = auth.user
    if u.totp_enabled:
        raise HTTPException(400, "already_enabled")
    if not u.totp_secret_enc:
        raise HTTPException(400, "not_initialized")
    if not verify_totp(u.totp_secret_enc, body.totp_code):
        log_auth_event("totp_fail", user_id=u.id)
        raise HTTPException(401, "totp_invalid")

    with repo.conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET totp_enabled = TRUE WHERE id = %s", (u.id,)
        )
    repo.conn.commit()
    log_auth_event("totp_ok", user_id=u.id)

    # setup_required 제거된 새 쌍 발급
    refresh_repo = RefreshTokenRepository(repo.conn)
    pair = issue_pair(u.id, repo=refresh_repo, totp_setup_required=False)
    set_access_cookie(response, pair.access_token)
    set_refresh_cookie(response, pair.refresh_token)
    set_csrf_cookie(response, pair.csrf_token)
    return {"ok": True}


class ResetBody(BaseModel):
    password_enc: str
    totp_code: str | None = None
    backup_code: str | None = None


@router.post("/reset")
async def reset_2fa(
    body: ResetBody,
    auth: CurrentAuth = Depends(current_auth),
    repo: UserRepository = Depends(get_user_repository),
) -> dict:
    u = auth.user

    password = decrypt_client_field(body.password_enc).decode()
    if not argon2_verify(password, u.password_hash):
        raise HTTPException(401, "invalid_password")

    verified = False
    if body.totp_code and u.totp_secret_enc:
        verified = verify_totp(u.totp_secret_enc, body.totp_code)
    if not verified and body.backup_code and u.backup_codes_hash:
        idx = verify_backup_code(body.backup_code, u.backup_codes_hash)
        verified = idx is not None
    if not verified:
        raise HTTPException(401, "second_factor_invalid")

    # 새 secret + 새 backup codes 로 교체 (totp_enabled 는 true 유지)
    aes = _aes_key()
    new_secret = pyotp.random_base32()
    new_codes, new_codes_hash_json = _gen_backup_codes()
    with repo.conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET totp_secret_enc = %s, backup_codes_hash = %s WHERE id = %s",
            (aes_gcm_encrypt(new_secret.encode(), aes), new_codes_hash_json, u.id),
        )
    repo.conn.commit()
    log_auth_event("totp_ok", user_id=u.id)  # reset 성공은 totp_ok 와 유사 이벤트

    email, _ = decrypted_email_and_name(u)
    return {
        "otpauth_url": _otpauth_url(new_secret, email),
        "backup_codes": new_codes,
    }
