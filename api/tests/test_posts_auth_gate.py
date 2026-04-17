"""TA-13: posts 엔드포인트 인증 게이트."""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.src.auth.dependencies import get_user_repository
from api.src.main import app, get_repo
from shared.post_repository import PostRepository


def _mock_repo():
    repo = MagicMock(spec=PostRepository)
    repo.find_all.return_value = ([], 0)
    return repo


def _mock_user_repo():
    # DB 연결 회피. 실제 호출 전 401 이 먼저 반환되므로 내용은 중요치 않음.
    return MagicMock()


def _override():
    app.dependency_overrides[get_repo] = lambda: _mock_repo()
    app.dependency_overrides[get_user_repository] = lambda: _mock_user_repo()


def test_list_posts_without_auth_returns_401():
    _override()
    try:
        r = TestClient(app).get("/api/posts")
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_get_post_without_auth_returns_401():
    _override()
    try:
        r = TestClient(app).get("/api/posts/1")
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_resend_post_without_auth_returns_401():
    _override()
    try:
        r = TestClient(app).post("/api/posts/1/resend")
        # CSRF 도 걸려있고 auth 도 걸려있음 — 둘 중 어느 쪽이든 미인증/차단이어야 함
        assert r.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()
