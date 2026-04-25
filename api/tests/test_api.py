"""FastAPI 엔드포인트 테스트."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

pymysql = pytest.importorskip("pymysql", reason="pymysql 미설치 — skip")
fastapi = pytest.importorskip("fastapi", reason="fastapi 미설치 — skip")

from api.src.main import app, get_repo
from api.src.auth.dependencies import current_user
from api.src.auth.csrf import CSRF_COOKIE, CSRF_HEADER, verify_csrf
from fastapi.testclient import TestClient
from shared.post_repository import PostRepository
from shared.user_repository import UserRow


def _mock_repo(rows=None, total=0, single=None):
    """PostRepository mock."""
    repo = MagicMock(spec=PostRepository)
    repo.find_all.return_value = (rows or [], total)
    repo.find_by_id.return_value = single
    repo._conn = MagicMock()
    return repo


def _fake_user() -> UserRow:
    return UserRow(
        id=1, email_enc=b"x", email_hmac=b"\x00" * 32, name_enc=b"x",
        password_hash="$x", is_admin=True, failed_login_count=0, locked_until=None,
    )


@pytest.fixture
def client():
    mock = _mock_repo()
    app.dependency_overrides[get_repo] = lambda: mock
    app.dependency_overrides[current_user] = lambda: _fake_user()
    # 기존 테스트는 CSRF 헤더 없음 → bypass
    app.dependency_overrides[verify_csrf] = lambda: None
    yield TestClient(app), mock
    app.dependency_overrides.clear()


class TestListPosts:
    def test_returns_empty_list(self, client):
        c, mock = client
        resp = c.get("/api/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_returns_items(self, client):
        c, mock = client
        rows = [
            {"id": 1, "board_id": "menus/6", "post_id": 100, "title": "공지",
             "reg_ts": datetime(2026, 4, 15, 10, 0), "upd_ts": datetime(2026, 4, 15, 10, 0),
             "post_date": None, "status": "SUCCESS", "image_count": 2, "summary": None},
        ]
        mock.find_all.return_value = (rows, 1)

        resp = c.get("/api/posts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["post_id"] == 100

    def test_filter_params(self, client):
        c, mock = client
        c.get("/api/posts?board_id=menus/6&status=FAIL&sort_by=post_date&limit=10")

        call_kwargs = mock.find_all.call_args[1]
        assert call_kwargs["board_id"] == "menus/6"
        assert call_kwargs["status"] == "FAIL"
        assert call_kwargs["sort_by"] == "post_date"
        assert call_kwargs["limit"] == 10


class TestGetPost:
    def test_returns_post(self, client):
        c, mock = client
        row = {"id": 1, "board_id": "menus/6", "post_id": 100, "title": "공지",
               "reg_ts": datetime(2026, 4, 15), "upd_ts": datetime(2026, 4, 15),
               "post_date": None, "status": "SUCCESS", "image_count": 0, "summary": None}
        mock.find_by_id.return_value = row

        resp = c.get("/api/posts/1")
        assert resp.status_code == 200
        assert resp.json()["post_id"] == 100

    def test_404_when_not_found(self, client):
        c, mock = client
        mock.find_by_id.return_value = None

        resp = c.get("/api/posts/999")
        assert resp.status_code == 404


class TestResendPost:
    def _row(self, **overrides):
        base = {
            "id": 1, "board_id": "menus/6", "post_id": 100,
            "title": "공지 테스트", "summary": "요약 내용\n\n[일정 정리]\n4/20 행사",
            "reg_ts": datetime(2026, 4, 15), "upd_ts": datetime(2026, 4, 15),
            "post_date": None, "status": "SUCCESS", "image_count": 0,
        }
        base.update(overrides)
        return base

    @patch("api.src.main._get_kakao_messenger")
    def test_resend_notice_success(self, mock_get_messenger, client):
        c, mock_repo = client
        mock_repo.find_by_id.return_value = self._row()
        messenger = MagicMock()
        mock_get_messenger.return_value = messenger

        resp = c.post("/api/posts/1/resend")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        messenger.send_notice_summary.assert_called_once()

    @patch("api.src.main._get_kakao_messenger")
    def test_resend_photo_success(self, mock_get_messenger, client):
        c, mock_repo = client
        mock_repo.find_by_id.return_value = self._row(board_id="menus/13", summary="사진 요약")
        messenger = MagicMock()
        mock_get_messenger.return_value = messenger

        resp = c.post("/api/posts/1/resend")
        assert resp.status_code == 200
        messenger._send_chunked.assert_called_once()

    def test_resend_404_not_found(self, client):
        c, mock_repo = client
        mock_repo.find_by_id.return_value = None

        resp = c.post("/api/posts/999/resend")
        assert resp.status_code == 404

    def test_resend_400_fail_status(self, client):
        c, mock_repo = client
        mock_repo.find_by_id.return_value = self._row(status="FAIL")

        resp = c.post("/api/posts/1/resend")
        assert resp.status_code == 400
        assert "SUCCESS" in resp.json()["detail"]

    def test_resend_400_empty_summary(self, client):
        c, mock_repo = client
        mock_repo.find_by_id.return_value = self._row(summary="")

        resp = c.post("/api/posts/1/resend")
        assert resp.status_code == 400
        assert "summary" in resp.json()["detail"]

    def test_resend_400_null_summary(self, client):
        c, mock_repo = client
        mock_repo.find_by_id.return_value = self._row(summary=None)

        resp = c.post("/api/posts/1/resend")
        assert resp.status_code == 400
