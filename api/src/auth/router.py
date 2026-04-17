"""Auth 라우터.

- GET  /api/auth/public-key   (TA-08): RSA 공개키 배포 (E2E 필드 암호화용)
- GET  /api/auth/me           (TA-12): 현재 사용자
- POST /api/auth/logout       (TA-12): 쿠키 제거 + refresh DB 삭제
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.src.auth.cookies import clear_auth_cookies
from api.src.auth.csrf import verify_csrf
from api.src.auth.dependencies import (
    current_user,
    decrypted_email_and_name,
    get_user_repository,
)
from shared.auth_events import log_auth_event
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
async def me(user: UserRow = Depends(current_user)) -> dict:
    email, name = decrypted_email_and_name(user)
    return {
        "id": user.id,
        "email": email,
        "name": name,
        "is_admin": user.is_admin,
        "totp_enabled": user.totp_enabled,
    }


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
