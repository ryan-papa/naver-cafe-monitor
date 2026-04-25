"""쿠키 헬퍼 (TA-04).

PRD의 쿠키·CSRF 상세 정책을 구현.

| 쿠키 | HttpOnly | Secure | SameSite | Path | Max-Age |
|------|----------|--------|----------|------|---------|
| access_token   | True  | True | Lax    | /            | 3600  |
| refresh_token  | True  | True | Lax    | /api/auth    | 86400 |
| csrf_token     | False | True | Lax    | /            | 3600  |

OAuth 콜백 후 cross-site 네비게이션에서 Set-Cookie가 후속 요청에 전송되도록 Lax 사용.
"""
from __future__ import annotations

from fastapi import Response

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"

ACCESS_MAX_AGE = 3600
REFRESH_MAX_AGE = 86400
REFRESH_PATH = "/api/auth"


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        max_age=ACCESS_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=REFRESH_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path=REFRESH_PATH,
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=ACCESS_MAX_AGE,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")
