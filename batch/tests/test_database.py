"""shared/database.py 연결 테스트."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# shared 모듈 import를 위해 repo root를 path에 추가
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

pymysql = pytest.importorskip("pymysql", reason="pymysql 미설치 — skip")

from shared.database import _build_ssl_context, get_connection, connect


class TestBuildSslContext:
    """SSL 컨텍스트 생성 테스트."""

    @patch("shared.database._CERT_DIR", Path("/fake/certs"))
    def test_raises_on_missing_certs(self):
        with pytest.raises((FileNotFoundError, OSError)):
            _build_ssl_context()


class TestGetConnection:
    """get_connection 테스트."""

    @patch("shared.database.pymysql.connect")
    @patch("shared.database._build_ssl_context")
    @patch("shared.database.load_dotenv")
    def test_uses_env_password(self, mock_dotenv, mock_ssl, mock_connect):
        mock_ssl.return_value = MagicMock()
        mock_connect.return_value = MagicMock()

        with patch.dict("os.environ", {"MYSQL_PASSWORD": "test123"}):
            conn = get_connection()

        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["password"] == "test123"
        assert call_kwargs["host"] == "eepp.shop"
        assert call_kwargs["database"] == "naver_cafe_monitor"
        assert call_kwargs["charset"] == "utf8mb4"

    @patch("shared.database.pymysql.connect")
    @patch("shared.database._build_ssl_context")
    def test_explicit_password(self, mock_ssl, mock_connect):
        mock_ssl.return_value = MagicMock()
        mock_connect.return_value = MagicMock()

        get_connection(password="explicit_pw")

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["password"] == "explicit_pw"


class TestConnect:
    """connect 컨텍스트 매니저 테스트."""

    @patch("shared.database.get_connection")
    def test_commit_on_success(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        with connect():
            pass

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("shared.database.get_connection")
    def test_rollback_on_error(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        with pytest.raises(ValueError):
            with connect() as conn:
                raise ValueError("test error")

        mock_conn.rollback.assert_called_once()
        mock_conn.close.assert_called_once()
