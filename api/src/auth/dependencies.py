"""FastAPI 공통 auth dependencies.

- current_user: access_token 쿠키 검증 → UserRow 반환 (없거나 무효면 401)
- optional_user: 있으면 반환, 없으면 None (공개 페이지용)
"""
from __future__ import annotations

import base64
import os

from fastapi import Cookie, Depends, HTTPException, status
from pymysql.connections import Connection

from shared.auth_tokens import ACCESS_TYPE, TokenError, verify_token
from shared.user_repository import UserRepository, UserRow

from api.src.auth.cookies import ACCESS_COOKIE


def _jwt_secret() -> str:
    secret = os.environ.get("AUTH_JWT_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_JWT_SECRET not configured",
        )
    # base64 로 저장했어도 JWT HS256 은 임의 바이트/문자열 수락
    return secret


def _get_db_conn() -> Connection:
    # 지연 import 로 test 환경 의존 최소화
    from shared.database import get_connection

    return get_connection()


def get_user_repository() -> UserRepository:
    conn = _get_db_conn()
    return UserRepository(conn)


async def current_user(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    repo: UserRepository = Depends(get_user_repository),
) -> UserRow:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = verify_token(access_token, _jwt_secret(), ACCESS_TYPE)
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}"
        ) from e

    user = repo.find_by_id(payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


async def optional_user(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    repo: UserRepository = Depends(get_user_repository),
) -> UserRow | None:
    if not access_token:
        return None
    try:
        payload = verify_token(access_token, _jwt_secret(), ACCESS_TYPE)
    except TokenError:
        return None
    return repo.find_by_id(payload.user_id)


def decrypted_email_and_name(user: UserRow) -> tuple[str, str]:
    from shared.crypto import aes_gcm_decrypt

    aes_key_b64 = os.environ.get("AUTH_AES_KEY", "")
    if not aes_key_b64:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_AES_KEY not configured",
        )
    aes_key = base64.b64decode(aes_key_b64)
    email = aes_gcm_decrypt(user.email_enc, aes_key).decode()
    name = aes_gcm_decrypt(user.name_enc, aes_key).decode()
    return email, name
