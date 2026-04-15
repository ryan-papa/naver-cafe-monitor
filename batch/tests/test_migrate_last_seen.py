"""db/migrate_last_seen.py 테스트."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

pymysql = pytest.importorskip("pymysql", reason="pymysql 미설치 — skip")

from db.migrate_last_seen import migrate, _LAST_SEEN_PATH


class TestMigrate:
    def test_skips_when_file_missing(self, tmp_path):
        """last_seen.json 없으면 스킵."""
        with patch("db.migrate_last_seen._LAST_SEEN_PATH", tmp_path / "nonexistent.json"):
            migrate()  # 에러 없이 종료

    def test_skips_when_file_empty(self, tmp_path):
        """빈 JSON이면 스킵."""
        f = tmp_path / "last_seen.json"
        f.write_text("{}", encoding="utf-8")

        with patch("db.migrate_last_seen._LAST_SEEN_PATH", f):
            migrate()

        assert f.exists()  # 빈 파일은 삭제하지 않음

    @patch("db.migrate_last_seen.connect")
    def test_inserts_and_deletes_file(self, mock_connect, tmp_path):
        """데이터 삽입 후 파일 삭제."""
        f = tmp_path / "last_seen.json"
        f.write_text(json.dumps({"menus/6": "100", "menus/13": "200"}), encoding="utf-8")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("db.migrate_last_seen._LAST_SEEN_PATH", f):
            migrate()

        assert mock_cursor.execute.call_count == 2
        assert not f.exists()

    @patch("db.migrate_last_seen.connect")
    def test_insert_params(self, mock_connect, tmp_path):
        """INSERT 파라미터가 올바른지 검증."""
        f = tmp_path / "last_seen.json"
        f.write_text(json.dumps({"menus/6": "42"}), encoding="utf-8")

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("db.migrate_last_seen._LAST_SEEN_PATH", f):
            migrate()

        args = mock_cursor.execute.call_args[0]
        assert args[1] == ("menus/6", 42)
