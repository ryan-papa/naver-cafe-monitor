"""CSRF double-submit 검증 (TA-06).

PRD: 모든 state-changing 요청(POST/PATCH/PUT/DELETE)은
  - `csrf_token` 쿠키 (Secure, SameSite=Strict, HttpOnly=false)
  - `X-CSRF-Token` 헤더
두 값이 일치해야 통과.

FastAPI Depends 로 라우터에 주입해서 사용.
"""
from __future__ import annotations

import hmac

from fastapi import Cookie, Header, HTTPException, Request, status

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


async def verify_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER),
) -> None:
    if request.method in _SAFE_METHODS:
        return
    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing"
        )
    if not _constant_time_equals(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch"
        )
