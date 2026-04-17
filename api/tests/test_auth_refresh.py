"""Unit tests for /api/auth/refresh + token_service (TA-11)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.src.auth import dependencies as deps
from api.src.auth import router as router_mod
from api.src.auth.cookies import REFRESH_COOKIE
from api.src.auth.router import router
from api.src.auth.token_service import (
    RefreshInvalid,
    RefreshReuseDetected,
    issue_pair,
    rotate_refresh,
)
from shared import auth_events
from shared.auth_tokens import hash_token, issue_refresh_token
from shared.refresh_token_repository import RefreshTokenRow


SECRET = "test-secret-32-bytes-xxxxxxxxxxx"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setattr(auth_events, "log_auth_event", lambda *a, **kw: None)
    monkeypatch.setattr(router_mod, "log_auth_event", lambda *a, **kw: None)
    # token_service 에서도 참조 → 모듈 레벨 import 라 직접 패치
    from api.src.auth import token_service

    monkeypatch.setattr(token_service, "log_auth_event", lambda *a, **kw: None)


def _fake_repo(stored: RefreshTokenRow | None = None):
    repo = MagicMock()
    repo.find_by_user.return_value = stored
    return repo


# ── token_service.rotate_refresh 단위 ──

def test_rotate_invalid_jwt_raises():
    with pytest.raises(RefreshInvalid):
        rotate_refresh("not-a-jwt", repo=_fake_repo(stored=None))


def test_rotate_no_active_session_raises():
    token, _ = issue_refresh_token(1, SECRET)
    with pytest.raises(RefreshInvalid, match="no active session"):
        rotate_refresh(token, repo=_fake_repo(stored=None))


def test_rotate_reuse_detected_wipes_and_raises():
    token, _ = issue_refresh_token(1, SECRET)
    now = datetime.now(timezone.utc)
    # 저장된 hash 는 다른 값 → 재사용
    stored = RefreshTokenRow(
        user_id=1,
        token_hash="stored-different-hash",
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        rotated_from=None,
    )
    repo = _fake_repo(stored=stored)
    with pytest.raises(RefreshReuseDetected):
        rotate_refresh(token, repo=repo)
    repo.delete_by_user.assert_called_once_with(1)


def test_rotate_happy_path_issues_new_pair():
    token, _ = issue_refresh_token(1, SECRET)
    now = datetime.now(timezone.utc)
    stored = RefreshTokenRow(
        user_id=1,
        token_hash=hash_token(token),
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        rotated_from=None,
    )
    repo = _fake_repo(stored=stored)
    pair = rotate_refresh(token, repo=repo)
    assert pair.access_token and pair.refresh_token and pair.csrf_token
    assert pair.refresh_token != token
    # upsert 로 저장 + previous_hash 기록
    call = repo.upsert.call_args
    assert call.kwargs["user_id"] == 1
    assert call.kwargs["rotated_from"] == hash_token(token)


# ── issue_pair 테스트 ──

def test_issue_pair_stores_new_hash():
    repo = MagicMock()
    pair = issue_pair(42, repo=repo)
    assert pair.access_token and pair.refresh_token
    call = repo.upsert.call_args
    assert call.kwargs["user_id"] == 42
    assert call.kwargs["token_hash"] == hash_token(pair.refresh_token)
    assert call.kwargs["rotated_from"] is None


# ── /api/auth/refresh HTTP 통합 ──

def _make_app(refresh_repo: MagicMock):
    app = FastAPI()
    app.include_router(router)

    # user_repo 는 refresh repo 에 conn 전달용 더미
    user_repo = MagicMock()
    user_repo.conn = MagicMock()
    app.dependency_overrides[deps.get_user_repository] = lambda: user_repo
    app.dependency_overrides[router_mod._get_refresh_repository] = lambda: refresh_repo
    return app


def test_refresh_endpoint_no_cookie_returns_401():
    app = _make_app(refresh_repo=MagicMock())
    r = TestClient(app).post("/api/auth/refresh")
    assert r.status_code == 401


def test_refresh_endpoint_happy_path_sets_cookies():
    token, _ = issue_refresh_token(7, SECRET)
    now = datetime.now(timezone.utc)
    stored = RefreshTokenRow(
        user_id=7,
        token_hash=hash_token(token),
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        rotated_from=None,
    )
    repo = MagicMock()
    repo.find_by_user.return_value = stored

    app = _make_app(refresh_repo=repo)
    client = TestClient(app)
    client.cookies.set(REFRESH_COOKIE, token)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    set_cookies = r.headers.get_list("set-cookie")
    assert any(h.startswith("access_token=") for h in set_cookies)
    assert any(h.startswith("refresh_token=") for h in set_cookies)
    assert any(h.startswith("csrf_token=") for h in set_cookies)


def test_refresh_endpoint_reuse_returns_401_and_clears():
    token, _ = issue_refresh_token(7, SECRET)
    now = datetime.now(timezone.utc)
    stored = RefreshTokenRow(
        user_id=7,
        token_hash="stored-different",
        issued_at=now,
        expires_at=now + timedelta(hours=24),
        rotated_from=None,
    )
    repo = MagicMock()
    repo.find_by_user.return_value = stored

    app = _make_app(refresh_repo=repo)
    client = TestClient(app)
    client.cookies.set(REFRESH_COOKIE, token)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401
    repo.delete_by_user.assert_called_once_with(7)
    # 쿠키 clear Set-Cookie 포함
    set_cookies = r.headers.get_list("set-cookie")
    assert any("access_token=" in h for h in set_cookies)
