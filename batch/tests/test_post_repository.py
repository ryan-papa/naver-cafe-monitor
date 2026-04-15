"""shared/post_repository.py 테스트."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

pymysql = pytest.importorskip("pymysql", reason="pymysql 미설치 — skip")

from shared.post_repository import PostRepository


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


class TestSave:
    def test_save_inserts_record(self, mock_conn):
        conn, cursor = mock_conn
        repo = PostRepository(conn)

        repo.save(board_id="menus/13", post_id=100, title="테스트", image_count=3, status="SUCCESS")

        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "INSERT INTO posts" in sql
        assert params["board_id"] == "menus/13"
        assert params["post_id"] == 100
        assert params["status"] == "SUCCESS"
        conn.commit.assert_called_once()

    def test_save_with_summary(self, mock_conn):
        conn, cursor = mock_conn
        repo = PostRepository(conn)

        repo.save(board_id="menus/6", post_id=200, title="공지", summary="요약 내용", status="SUCCESS")

        params = cursor.execute.call_args[0][1]
        assert params["summary"] == "요약 내용"

    def test_save_fail_status(self, mock_conn):
        conn, cursor = mock_conn
        repo = PostRepository(conn)

        repo.save(board_id="menus/13", post_id=300, status="FAIL")

        params = cursor.execute.call_args[0][1]
        assert params["status"] == "FAIL"


class TestGetLastSeenId:
    def test_returns_max_post_id(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"max_id": 500}
        repo = PostRepository(conn)

        result = repo.get_last_seen_id("menus/13")

        assert result == 500

    def test_returns_zero_when_no_records(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"max_id": None}
        repo = PostRepository(conn)

        result = repo.get_last_seen_id("menus/13")

        assert result == 0


class TestFindAll:
    def test_returns_rows_and_count(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"cnt": 2}
        cursor.fetchall.return_value = [
            {"id": 1, "post_id": 100},
            {"id": 2, "post_id": 200},
        ]
        repo = PostRepository(conn)

        rows, total = repo.find_all()

        assert total == 2
        assert len(rows) == 2

    def test_filters_by_board_id(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"cnt": 1}
        cursor.fetchall.return_value = [{"id": 1}]
        repo = PostRepository(conn)

        repo.find_all(board_id="menus/6")

        count_sql = cursor.execute.call_args_list[0][0][0]
        assert "board_id = %s" in count_sql

    def test_rejects_invalid_sort(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"cnt": 0}
        cursor.fetchall.return_value = []
        repo = PostRepository(conn)

        repo.find_all(sort_by="DROP TABLE posts; --")

        select_sql = cursor.execute.call_args_list[1][0][0]
        assert "reg_ts" in select_sql
        assert "DROP" not in select_sql


class TestFindById:
    def test_returns_record(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = {"id": 1, "post_id": 100}
        repo = PostRepository(conn)

        result = repo.find_by_id(1)

        assert result["id"] == 1

    def test_returns_none_when_not_found(self, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = None
        repo = PostRepository(conn)

        result = repo.find_by_id(999)

        assert result is None
