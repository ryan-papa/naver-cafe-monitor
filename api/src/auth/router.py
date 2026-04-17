"""Auth 라우터 (TA-08 ~).

현재 구현:
- GET /api/auth/public-key   (TA-08): RSA 공개키 배포 (E2E 필드 암호화용)
추후 추가: /signup, /signup/confirm, /login, /refresh, /logout, /me
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _load_public_key_pem() -> str:
    raw = os.environ.get("AUTH_RSA_PUBLIC_KEY", "")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AUTH_RSA_PUBLIC_KEY not configured",
        )
    # generate_secrets.py 가 \n 을 \\n 으로 escape 해서 저장 → 원복
    return raw.replace("\\n", "\n")


@router.get("/public-key")
async def get_public_key() -> dict:
    return {
        "public_key_pem": _load_public_key_pem(),
        "algorithm": "RSA-OAEP-SHA256",
    }
