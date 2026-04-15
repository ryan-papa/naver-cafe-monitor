"""KakaoAuth 테스트.

토큰 로드/저장/갱신, 만료 알림 판정을 mock HTTP로 검증한다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.messaging.kakao_auth import KakaoAuth, InvalidTokenFile


# ── 픽스처 ────────────────────────────────────────────────────────────────────

def _make_token_file(tmp_path: Path, data: dict | None = None) -> Path:
    """테스트용 토큰 파일을 생성한다."""
    token_path = tmp_path / "kakao_token.json"
    if data is None:
        data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": int(time.time()) + 21600,
            "refresh_token_expires_at": int(time.time()) + 5184000,
        }
    token_path.write_text(json.dumps(data), encoding="utf-8")
    return token_path


@pytest.fixture
def token_path(tmp_path: Path) -> Path:
    return _make_token_file(tmp_path)


@pytest.fixture
def auth(token_path: Path) -> KakaoAuth:
    return KakaoAuth(
        client_id="test_client_id",
        client_secret="test_client_secret",
        token_path=token_path,
    )


# ── 토큰 로드 테스트 ─────────────────────────────────────────────────────────

class TestLoadToken:
    def test_load_valid_token(self, auth: KakaoAuth):
        assert auth.access_token == "test_access"

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            KakaoAuth("id", "secret", token_path=tmp_path / "missing.json")

    def test_empty_file(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text("")
        with pytest.raises(InvalidTokenFile, match="비어 있습니다"):
            KakaoAuth("id", "secret", token_path=path)

    def test_invalid_json(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("{invalid json")
        with pytest.raises(InvalidTokenFile, match="JSON 파싱 실패"):
            KakaoAuth("id", "secret", token_path=path)

    def test_missing_required_fields(self, tmp_path: Path):
        path = _make_token_file(tmp_path, {"access_token": "a"})
        with pytest.raises(InvalidTokenFile, match="필수 필드 누락"):
            KakaoAuth("id", "secret", token_path=path)


# ── 토큰 저장 테스트 ─────────────────────────────────────────────────────────

class TestSaveToken:
    def test_atomic_write(self, auth: KakaoAuth, token_path: Path):
        """저장 후 파일 내용이 올바른지 확인."""
        auth._token_data["access_token"] = "new_token"
        auth._save_token()

        saved = json.loads(token_path.read_text(encoding="utf-8"))
        assert saved["access_token"] == "new_token"

    def test_save_preserves_all_fields(self, auth: KakaoAuth, token_path: Path):
        """저장 시 기존 필드가 유지되는지 확인."""
        auth._save_token()
        saved = json.loads(token_path.read_text(encoding="utf-8"))
        assert "refresh_token" in saved
        assert "expires_at" in saved


# ── 토큰 갱신 테스트 ─────────────────────────────────────────────────────────

class TestRefresh:
    @patch("src.messaging.kakao_auth.requests.post")
    def test_refresh_success_with_new_refresh_token(self, mock_post, auth: KakaoAuth):
        """갱신 성공 시 access_token + refresh_token 모두 업데이트."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 21599,
                "refresh_token_expires_in": 5183999,
            }),
        )

        result = auth.refresh()

        assert result == "new_access"
        assert auth.access_token == "new_access"
        assert auth._token_data["refresh_token"] == "new_refresh"

    @patch("src.messaging.kakao_auth.requests.post")
    def test_refresh_success_without_new_refresh_token(self, mock_post, auth: KakaoAuth):
        """응답에 refresh_token이 없으면 기존 값 유지."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "new_access",
                "expires_in": 21599,
            }),
        )

        auth.refresh()

        assert auth.access_token == "new_access"
        assert auth._token_data["refresh_token"] == "test_refresh"  # 기존 값

    @patch("src.messaging.kakao_auth.requests.post")
    def test_refresh_failure_raises(self, mock_post, auth: KakaoAuth):
        """갱신 실패(401) 시 RuntimeError 발생."""
        mock_post.return_value = MagicMock(
            status_code=401,
            text='{"error":"invalid_grant"}',
        )

        with pytest.raises(RuntimeError, match="카카오 토큰 갱신 실패"):
            auth.refresh()

    @patch("src.messaging.kakao_auth.requests.post")
    def test_refresh_saves_to_file(self, mock_post, auth: KakaoAuth, token_path: Path):
        """갱신 후 파일에 저장되는지 확인."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "saved_access",
                "expires_in": 21599,
            }),
        )

        auth.refresh()

        saved = json.loads(token_path.read_text(encoding="utf-8"))
        assert saved["access_token"] == "saved_access"


# ── 만료 알림 테스트 ─────────────────────────────────────────────────────────

class TestRefreshTokenExpiry:
    def test_days_remaining(self, auth: KakaoAuth):
        """남은 일수 계산."""
        auth._token_data["refresh_token_expires_at"] = int(time.time()) + 86400 * 10
        assert auth.check_refresh_token_expiry() == 10

    def test_no_expiry_info(self, tmp_path: Path):
        """expires_at 없으면 None 반환."""
        path = _make_token_file(tmp_path, {
            "access_token": "a",
            "refresh_token": "b",
        })
        a = KakaoAuth("id", "secret", token_path=path)
        assert a.check_refresh_token_expiry() is None

    def test_expired_returns_zero(self, auth: KakaoAuth):
        """만료 시 0 반환."""
        auth._token_data["refresh_token_expires_at"] = int(time.time()) - 100
        assert auth.check_refresh_token_expiry() == 0


class TestShouldAlertToday:
    def test_alert_when_within_14_days(self, auth: KakaoAuth):
        """14일 이내면 알림 필요."""
        auth._token_data["refresh_token_expires_at"] = int(time.time()) + 86400 * 7
        assert auth.should_alert_today() is True

    def test_no_alert_when_far_from_expiry(self, auth: KakaoAuth):
        """14일 초과면 알림 불필요."""
        auth._token_data["refresh_token_expires_at"] = int(time.time()) + 86400 * 30
        assert auth.should_alert_today() is False

    def test_no_duplicate_alert_same_day(self, auth: KakaoAuth):
        """같은 날 중복 알림 방지."""
        auth._token_data["refresh_token_expires_at"] = int(time.time()) + 86400 * 7
        auth.mark_alert_sent()
        assert auth.should_alert_today() is False

    def test_alert_next_day(self, auth: KakaoAuth):
        """다음 날에는 다시 알림."""
        auth._token_data["refresh_token_expires_at"] = int(time.time()) + 86400 * 7
        auth._token_data["last_alert_date"] = "2020-01-01"
        assert auth.should_alert_today() is True
