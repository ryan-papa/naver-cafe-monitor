"""batch.py의 refresh token 만료 알림 테스트."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

# playwright가 설치되지 않은 환경에서도 테스트 가능하도록 mock
if "playwright" not in sys.modules:
    sys.modules["playwright"] = MagicMock()
    sys.modules["playwright.async_api"] = MagicMock()

from src.batch import _check_refresh_token_alert


class TestCheckRefreshTokenAlert:
    def test_sends_alert_when_expiring_soon(self):
        """만료 임박 + 오늘 미알림 → 카카오톡 전송."""
        auth = MagicMock()
        auth.check_refresh_token_expiry.return_value = 7
        auth.should_alert_today.return_value = True

        kakao = MagicMock()

        _check_refresh_token_alert(auth, kakao)

        kakao.send_text.assert_called_once()
        assert "7일" in kakao.send_text.call_args[0][0]
        auth.mark_alert_sent.assert_called_once()

    def test_no_alert_when_far_from_expiry(self):
        """만료까지 충분한 시간 → 알림 없음."""
        auth = MagicMock()
        auth.check_refresh_token_expiry.return_value = 30
        auth.should_alert_today.return_value = False

        kakao = MagicMock()

        _check_refresh_token_alert(auth, kakao)

        kakao.send_text.assert_not_called()

    def test_no_alert_when_already_sent_today(self):
        """오늘 이미 알림 → 중복 전송 없음."""
        auth = MagicMock()
        auth.check_refresh_token_expiry.return_value = 5
        auth.should_alert_today.return_value = False

        kakao = MagicMock()

        _check_refresh_token_alert(auth, kakao)

        kakao.send_text.assert_not_called()

    def test_no_expiry_info_skips(self):
        """만료 정보 없으면 스킵."""
        auth = MagicMock()
        auth.check_refresh_token_expiry.return_value = None

        kakao = MagicMock()

        _check_refresh_token_alert(auth, kakao)

        kakao.send_text.assert_not_called()

    def test_send_failure_does_not_mark(self):
        """전송 실패 시 mark_alert_sent 호출하지 않음."""
        auth = MagicMock()
        auth.check_refresh_token_expiry.return_value = 3
        auth.should_alert_today.return_value = True

        kakao = MagicMock()
        kakao.send_text.side_effect = RuntimeError("전송 실패")

        _check_refresh_token_alert(auth, kakao)

        auth.mark_alert_sent.assert_not_called()
