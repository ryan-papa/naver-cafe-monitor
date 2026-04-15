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

from fastapi.testclient import TestClient
from api.src.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _mock_repo(rows=None, total=0, single=None):
    """PostRepository mock."""
    repo = MagicMock()
    repo.find_all.return_value = (rows or [], total)
    repo.find_by_id.return_value = single
    repo._conn = MagicMock()
    return repo


class TestListPosts:
    @patch("api.src.main._get_repo")
    def test_returns_empty_list(self, mock_get_repo, client):
        mock_get_repo.return_value = _mock_repo()

        resp = client.get("/api/posts")

        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @patch("api.src.main._get_repo")
    def test_returns_items(self, mock_get_repo, client):
        rows = [
            {"id": 1, "board_id": "menus/6", "post_id": 100, "title": "공지",
             "reg_ts": datetime(2026, 4, 15, 10, 0), "upd_ts": datetime(2026, 4, 15, 10, 0),
             "post_date": None, "status": "SUCCESS"},
        ]
        mock_get_repo.return_value = _mock_repo(rows=rows, total=1)

        resp = client.get("/api/posts")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["post_id"] == 100

    @patch("api.src.main._get_repo")
    def test_filter_params(self, mock_get_repo, client):
        mock_get_repo.return_value = _mock_repo()

        client.get("/api/posts?board_id=menus/6&status=FAIL&sort_by=post_date&limit=10")

        repo = mock_get_repo.return_value
        call_kwargs = repo.find_all.call_args[1]
        assert call_kwargs["board_id"] == "menus/6"
        assert call_kwargs["status"] == "FAIL"
        assert call_kwargs["sort_by"] == "post_date"
        assert call_kwargs["limit"] == 10


class TestGetPost:
    @patch("api.src.main._get_repo")
    def test_returns_post(self, mock_get_repo, client):
        row = {"id": 1, "board_id": "menus/6", "post_id": 100, "title": "공지",
               "reg_ts": datetime(2026, 4, 15), "upd_ts": datetime(2026, 4, 15),
               "post_date": None, "status": "SUCCESS"}
        mock_get_repo.return_value = _mock_repo(single=row)

        resp = client.get("/api/posts/1")

        assert resp.status_code == 200
        assert resp.json()["post_id"] == 100

    @patch("api.src.main._get_repo")
    def test_404_when_not_found(self, mock_get_repo, client):
        mock_get_repo.return_value = _mock_repo(single=None)

        resp = client.get("/api/posts/999")

        assert resp.status_code == 404
