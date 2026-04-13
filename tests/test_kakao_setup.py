"""kakao_setup.py 토큰 교환 로직 테스트."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# scripts 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from kakao_setup import _exchange_token, _TOKEN_PATH


class TestExchangeToken:
    @patch("kakao_setup.requests.post")
    def test_success(self, mock_post):
        """정상 토큰 교환."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 21599,
                "refresh_token_expires_in": 5183999,
            }),
        )
        result = _exchange_token("cid", "csec", "code123")
        assert result["access_token"] == "at"
        assert result["refresh_token"] == "rt"

    @patch("kakao_setup.requests.post")
    def test_failure_exits(self, mock_post):
        """실패 시 SystemExit."""
        mock_post.return_value = MagicMock(
            status_code=401,
            text="bad",
        )
        with pytest.raises(SystemExit):
            _exchange_token("cid", "csec", "badcode")
