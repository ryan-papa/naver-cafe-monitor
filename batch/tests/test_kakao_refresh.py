"""`src.kakao_refresh` 엔트리 모듈 단위 테스트."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import kakao_refresh
from src.messaging.kakao_auth import _mask_tokens


@pytest.fixture
def _log_to_tmp(tmp_path, monkeypatch):
    """로그 파일 경로를 tmp 로 우회한다."""
    monkeypatch.setattr(kakao_refresh, "_LOG_PATH", tmp_path / "kakao_refresh.log")
    yield tmp_path / "kakao_refresh.log"
    # 핸들러 정리
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)


def _make_token(tmp_path: Path) -> Path:
    path = tmp_path / "kakao_token.json"
    path.write_text(json.dumps({
        "access_token": "a",
        "refresh_token": "r",
        "expires_at": int(time.time()) + 3600,
        "refresh_token_expires_at": int(time.time()) + 86400 * 20,
    }))
    return path


def test_main_success(_log_to_tmp, tmp_path, monkeypatch):
    token_path = _make_token(tmp_path)

    fake_config = MagicMock(
        kakao_client_id="cid", kakao_client_secret="csec"
    )
    monkeypatch.setattr(kakao_refresh, "load_config", lambda: fake_config)

    original_init = kakao_refresh.KakaoAuth.__init__

    def _init(self, client_id, client_secret, **_kwargs):
        original_init(self, client_id, client_secret, token_path=token_path)

    monkeypatch.setattr(kakao_refresh.KakaoAuth, "__init__", _init)

    with patch("src.messaging.kakao_auth.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "new_access",
                "expires_in": 21599,
                "refresh_token": "new_refresh",
                "refresh_token_expires_in": 60 * 86400,
            }),
            text='{"access_token":"new_access"}',
        )
        rc = kakao_refresh.main()

    assert rc == 0
    saved = json.loads(token_path.read_text())
    assert saved["access_token"] == "new_access"
    assert saved["refresh_token"] == "new_refresh"

    log_text = _log_to_tmp.read_text()
    assert "선제 갱신 성공" in log_text
    # 로그에 토큰 원문이 없어야 함 (성공 경로에서는 토큰 값을 기록하지 않음)
    assert "new_access" not in log_text
    assert "new_refresh" not in log_text


def test_main_failure_masks_tokens(_log_to_tmp, tmp_path, monkeypatch):
    token_path = _make_token(tmp_path)

    monkeypatch.setattr(
        kakao_refresh, "load_config",
        lambda: MagicMock(kakao_client_id="cid", kakao_client_secret="csec"),
    )
    original_init = kakao_refresh.KakaoAuth.__init__
    monkeypatch.setattr(
        kakao_refresh.KakaoAuth, "__init__",
        lambda self, client_id, client_secret, **_k: original_init(
            self, client_id, client_secret, token_path=token_path,
        ),
    )

    with patch("src.messaging.kakao_auth.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=401,
            text='{"error":"invalid_grant","access_token":"leaked_a","refresh_token":"leaked_r"}',
        )
        rc = kakao_refresh.main()

    assert rc == 1
    log_text = _log_to_tmp.read_text()
    # 응답 본문에 포함된 토큰 문자열이 원문 그대로 기록되면 안 됨
    assert "leaked_a" not in log_text
    assert "leaked_r" not in log_text


def test_mask_tokens_regex_fallback():
    """JSON 파싱 실패 시 정규식 fallback 으로 치환."""
    body = 'bad\x00json "access_token": "secret_a" "refresh_token": "secret_r"'
    masked = _mask_tokens(body)
    assert "secret_a" not in masked
    assert "secret_r" not in masked
    assert "***" in masked


def test_mask_tokens_json_path():
    body = '{"access_token":"abc","refresh_token":"def","keep":"ok"}'
    masked = _mask_tokens(body)
    data = json.loads(masked)
    assert data["access_token"] == "***"
    assert data["refresh_token"] == "***"
    assert data["keep"] == "ok"
