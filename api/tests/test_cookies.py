"""Unit tests for api.src.auth.cookies (TA-04)."""
from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from api.src.auth import cookies


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/set")
    def _set(response: Response):
        cookies.set_access_cookie(response, "access-xyz")
        cookies.set_refresh_cookie(response, "refresh-xyz")
        cookies.set_csrf_cookie(response, "csrf-xyz")
        return {"ok": True}

    @app.get("/clear")
    def _clear(response: Response):
        cookies.clear_auth_cookies(response)
        return {"ok": True}

    return app


def _set_cookie_headers(response):
    # httpx Response: headers.get_list 로 중복 헤더 배열 수집
    return response.headers.get_list("set-cookie")


def test_cookies_have_required_flags():
    client = TestClient(_make_app())
    r = client.get("/set")
    assert r.status_code == 200
    raw = _set_cookie_headers(r)

    access = next(h for h in raw if h.startswith(cookies.ACCESS_COOKIE + "="))
    refresh = next(h for h in raw if h.startswith(cookies.REFRESH_COOKIE + "="))
    csrf = next(h for h in raw if h.startswith(cookies.CSRF_COOKIE + "="))

    # access / refresh / csrf common: Secure + SameSite=strict
    for h in (access, refresh, csrf):
        assert "Secure" in h
        assert "SameSite=strict" in h.lower() or "samesite=strict" in h.lower()

    # HttpOnly
    assert "HttpOnly" in access
    assert "HttpOnly" in refresh
    assert "HttpOnly" not in csrf  # CSRF는 JS가 읽어야 함

    # Path / Max-Age
    assert "Path=/" in access and f"Max-Age={cookies.ACCESS_MAX_AGE}" in access
    assert f"Path={cookies.REFRESH_PATH}" in refresh
    assert f"Max-Age={cookies.REFRESH_MAX_AGE}" in refresh
    assert "Path=/" in csrf


def test_clear_cookies_emits_deletion_headers():
    client = TestClient(_make_app())
    r = client.get("/clear")
    raw = _set_cookie_headers(r)
    # Starlette의 delete_cookie 는 Max-Age 대신 expires=...(과거 날짜)로 처리
    # → 쿠키명과 빈 값(=;)만 확인
    assert any(h.startswith(cookies.ACCESS_COOKIE + "=") for h in raw)
    assert any(h.startswith(cookies.REFRESH_COOKIE + "=") for h in raw)
    assert any(h.startswith(cookies.CSRF_COOKIE + "=") for h in raw)
    # 과거 만료 표기 혹은 Max-Age=0
    for name in (cookies.ACCESS_COOKIE, cookies.REFRESH_COOKIE, cookies.CSRF_COOKIE):
        h = next(x for x in raw if x.startswith(name + "="))
        assert "Max-Age=0" in h or "expires=" in h.lower()
