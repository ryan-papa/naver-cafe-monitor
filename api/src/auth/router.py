"""Auth 라우터.

- GET  /api/auth/public-key   (TA-08): RSA 공개키 배포 (E2E 필드 암호화용)
- GET  /api/auth/me           (TA-12): 현재 사용자
- POST /api/auth/logout       (TA-12): 쿠키 제거 + refresh DB 삭제
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Response, status

from fastapi import Cookie, Request
from fastapi.responses import JSONResponse

from api.src.auth.cookies import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_access_cookie,
    set_csrf_cookie,
    set_refresh_cookie,
)
from api.src.auth.csrf import verify_csrf
from api.src.auth.dependencies import (
    CurrentAuth,
    current_auth,
    current_user,
    decrypted_email_and_name,
    get_user_repository,
)
from api.src.auth.login_service import LoginContext, LoginError, login as do_login
from api.src.auth.signup_service import (
    SignupError,
    confirm_signup,
    signup as do_signup,
)
from api.src.auth.token_service import (
    RefreshInvalid,
    RefreshReuseDetected,
    rotate_refresh,
)
from pydantic import BaseModel, Field
from shared.auth_events import log_auth_event
from shared.host_classifier import is_internal
from shared.refresh_token_repository import RefreshTokenRepository
from shared.user_repository import UserRepository, UserRow

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _load_public_key_pem() -> str:
    raw = os.environ.get("AUTH_RSA_PUBLIC_KEY", "")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_RSA_PUBLIC_KEY not configured",
        )
    return raw.replace("\\n", "\n")


@router.get("/public-key")
async def get_public_key() -> dict:
    return {
        "public_key_pem": _load_public_key_pem(),
        "algorithm": "RSA-OAEP-SHA256",
    }


@router.get("/me")
async def me(auth: CurrentAuth = Depends(current_auth)) -> dict:
    email, name = decrypted_email_and_name(auth.user)
    return {
        "id": auth.user.id,
        "email": email,
        "name": name,
        "is_admin": auth.user.is_admin,
        "totp_enabled": auth.user.totp_enabled,
        "totp_setup_required": auth.token.totp_setup_required,
    }


def _get_refresh_repository(
    user_repo: UserRepository = Depends(get_user_repository),
) -> RefreshTokenRepository:
    # user_repo 와 동일 connection 재사용
    return RefreshTokenRepository(user_repo.conn)


class SignupBody(BaseModel):
    email_enc: str
    name_enc: str
    password_enc: str


class ConfirmSignupBody(BaseModel):
    pending_token: str
    totp_code: str = Field(..., min_length=6, max_length=10)


@router.post("/signup")
async def signup_endpoint(
    body: SignupBody,
    request: Request,
    user_repo: UserRepository = Depends(get_user_repository),
) -> dict:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        result = do_signup(
            email_enc_b64=body.email_enc,
            name_enc_b64=body.name_enc,
            password_enc_b64=body.password_enc,
            user_repo=user_repo,
            ip=ip,
            user_agent=ua,
        )
    except SignupError as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.code})
    return {
        "user_id": result.user_id,
        "pending_token": result.pending_token,
        "otpauth_url": result.otpauth_url,
        "backup_codes": result.backup_codes,
    }


@router.post("/signup/confirm")
async def signup_confirm_endpoint(
    body: ConfirmSignupBody,
    request: Request,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_repo: "RefreshTokenRepository" = Depends(lambda: None),
) -> dict:
    from shared.refresh_token_repository import RefreshTokenRepository

    if refresh_repo is None:
        refresh_repo = RefreshTokenRepository(user_repo.conn)

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        result = confirm_signup(
            pending_token=body.pending_token,
            totp_code=body.totp_code,
            user_repo=user_repo,
            refresh_repo=refresh_repo,
            ip=ip,
            user_agent=ua,
        )
    except SignupError as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.code})

    set_access_cookie(response, result.pair.access_token)
    set_refresh_cookie(response, result.pair.refresh_token)
    set_csrf_cookie(response, result.pair.csrf_token)
    return {"ok": True, "user_id": result.user_id}


class LoginBody(BaseModel):
    email_enc: str = Field(..., description="RSA-OAEP(email) → base64")
    password_enc: str = Field(..., description="RSA-OAEP(password) → base64")
    totp_code: str | None = Field(default=None, max_length=10)


@router.post("/login")
async def login_endpoint(
    body: LoginBody,
    request: Request,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repository),
    refresh_repo: "RefreshTokenRepository" = Depends(lambda: None),  # override below
) -> dict:
    from shared.refresh_token_repository import RefreshTokenRepository

    if refresh_repo is None:
        refresh_repo = RefreshTokenRepository(user_repo.conn)

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    internal = is_internal(request.url.hostname)
    try:
        pair = do_login(
            email_enc_b64=body.email_enc,
            password_enc_b64=body.password_enc,
            totp_code=body.totp_code,
            user_repo=user_repo,
            refresh_repo=refresh_repo,
            ctx=LoginContext(ip=ip, user_agent=ua, internal=internal),
        )
    except LoginError as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.code})

    set_access_cookie(response, pair.access_token)
    set_refresh_cookie(response, pair.refresh_token)
    set_csrf_cookie(response, pair.csrf_token)
    return {"ok": True}


@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    refresh_repo: RefreshTokenRepository = Depends(_get_refresh_repository),
) -> dict:
    if not refresh_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token"
        )
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    try:
        pair = rotate_refresh(
            refresh_cookie, repo=refresh_repo, ip=ip, user_agent=ua
        )
    except (RefreshReuseDetected, RefreshInvalid) as e:
        fail = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(e)}
        )
        clear_auth_cookies(fail)
        return fail

    set_access_cookie(response, pair.access_token)
    set_refresh_cookie(response, pair.refresh_token)
    set_csrf_cookie(response, pair.csrf_token)
    return {"ok": True}


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def logout(
    response: Response,
    user: UserRow = Depends(current_user),
    repo: UserRepository = Depends(get_user_repository),
) -> dict:
    with repo.conn.cursor() as cur:
        cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user.id,))
    repo.conn.commit()
    log_auth_event("logout", user_id=user.id)
    clear_auth_cookies(response)
    return {"ok": True}
