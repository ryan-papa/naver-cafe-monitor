"""T-10 카카오 메시지 전송 테스트."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.messaging.kakao import KakaoMessenger


# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_message_client():
    """PyKakao Message 클라이언트를 mock으로 교체하는 픽스처."""
    with patch("src.messaging.kakao.Message") as MockMessage:
        mock_instance = MockMessage.return_value
        yield mock_instance


@pytest.fixture()
def messenger(mock_message_client: MagicMock) -> KakaoMessenger:
    """테스트용 KakaoMessenger 인스턴스."""
    return KakaoMessenger(access_token="test-token")


# ── 초기화 테스트 ──────────────────────────────────────────────────────────────

class TestKakaoMessengerInit:
    """KakaoMessenger 초기화 테스트."""

    def test_from_config(self) -> None:
        """from_config() 팩토리가 올바르게 인스턴스를 생성하는지 확인."""
        mock_config = MagicMock()
        mock_config.kakao_token = "my-token"

        with patch("src.messaging.kakao.Message"):
            messenger = KakaoMessenger.from_config(mock_config)

        assert isinstance(messenger, KakaoMessenger)

    def test_set_access_token_called(self) -> None:
        """초기화 시 액세스 토큰이 클라이언트에 설정되는지 확인."""
        with patch("src.messaging.kakao.Message") as MockMessage:
            mock_instance = MockMessage.return_value
            KakaoMessenger(access_token="my-access-token")
            mock_instance.set_access_token.assert_called_once_with("my-access-token")


# ── 텍스트 전송 테스트 ─────────────────────────────────────────────────────────

class TestSendText:
    """send_text() 메서드 테스트."""

    def test_send_text_calls_api(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """send_text()가 API를 올바르게 호출하는지 확인."""
        messenger.send_text("안녕하세요!")
        mock_message_client.send_message_to_me.assert_called_once_with(
            message_type="text",
            text="안녕하세요!",
        )

    def test_send_text_raises_on_failure(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """API 호출 실패 시 RuntimeError가 발생하는지 확인."""
        mock_message_client.send_message_to_me.side_effect = Exception("API 오류")

        with pytest.raises(RuntimeError, match="카카오 텍스트 메시지 전송 실패"):
            messenger.send_text("테스트 메시지")

    def test_send_text_logs_on_failure(
        self,
        messenger: KakaoMessenger,
        mock_message_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """전송 실패 시 오류 로그가 기록되는지 확인."""
        import logging

        mock_message_client.send_message_to_me.side_effect = Exception("연결 실패")

        with caplog.at_level(logging.ERROR, logger="src.messaging.kakao"):
            with pytest.raises(RuntimeError):
                messenger.send_text("실패 메시지")

        assert "전송 실패" in caplog.text

    def test_send_text_long_message(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """긴 메시지도 정상 전송되는지 확인."""
        long_msg = "내용 " * 200
        messenger.send_text(long_msg)
        mock_message_client.send_message_to_me.assert_called_once()


# ── 이미지 전송 테스트 ─────────────────────────────────────────────────────────

class TestSendImages:
    """send_images() 메서드 테스트."""

    def test_send_single_image(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """단일 이미지 전송 시 API가 1회 호출되는지 확인."""
        paths = [Path("/tmp/img1.jpg")]
        messenger.send_images(paths)
        mock_message_client.send_message_to_me.assert_called_once()

    def test_send_images_with_caption(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """캡션이 메시지에 포함되는지 확인."""
        paths = [Path("/tmp/img1.jpg")]
        messenger.send_images(paths, caption="오늘의 공지")

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        assert "오늘의 공지" in call_kwargs["text"]

    def test_send_images_path_in_message(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """이미지 경로가 메시지 텍스트에 포함되는지 확인."""
        paths = [Path("/tmp/photo.jpg")]
        messenger.send_images(paths)

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        assert "/tmp/photo.jpg" in call_kwargs["text"]

    def test_send_images_batches_over_limit(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """최대 첨부 수(5장) 초과 시 배치로 나뉘어 전송되는지 확인."""
        paths = [Path(f"/tmp/img{i}.jpg") for i in range(12)]
        messenger.send_images(paths)
        # 12장 → 3배치 (5 + 5 + 2)
        assert mock_message_client.send_message_to_me.call_count == 3

    def test_send_images_batch_label_in_message(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """배치 전송 시 배치 번호가 메시지에 포함되는지 확인."""
        paths = [Path(f"/tmp/img{i}.jpg") for i in range(6)]
        messenger.send_images(paths, caption="사진")

        first_call_kwargs = mock_message_client.send_message_to_me.call_args_list[0][1]
        assert "1/2" in first_call_kwargs["text"]

    def test_send_images_empty_list_no_call(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """빈 리스트 전달 시 API가 호출되지 않는지 확인."""
        messenger.send_images([])
        mock_message_client.send_message_to_me.assert_not_called()

    def test_send_images_raises_on_failure(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """이미지 전송 실패 시 RuntimeError가 발생하는지 확인."""
        mock_message_client.send_message_to_me.side_effect = Exception("이미지 업로드 실패")
        paths = [Path("/tmp/img1.jpg")]

        with pytest.raises(RuntimeError, match="카카오 이미지 전송 실패"):
            messenger.send_images(paths)

    def test_send_exactly_max_images_single_batch(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """최대 첨부 수 이하(5장)는 1배치로 전송되는지 확인."""
        paths = [Path(f"/tmp/img{i}.jpg") for i in range(5)]
        messenger.send_images(paths)
        mock_message_client.send_message_to_me.assert_called_once()


# ── 공지 요약 전송 테스트 ─────────────────────────────────────────────────────

class TestSendNoticeSummary:
    """send_notice_summary() 메서드 테스트."""

    def test_send_notice_includes_title(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """메시지에 공지 제목이 포함되는지 확인."""
        messenger.send_notice_summary(title="봄 축제 안내", summary="행사 내용입니다.")

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        assert "봄 축제 안내" in call_kwargs["text"]

    def test_send_notice_includes_summary(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """메시지에 공지 요약이 포함되는지 확인."""
        messenger.send_notice_summary(title="공지", summary="중요한 내용입니다.")

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        assert "중요한 내용입니다." in call_kwargs["text"]

    def test_send_notice_format_has_header(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """메시지에 [네이버 카페 공지] 헤더가 포함되는지 확인."""
        messenger.send_notice_summary(title="제목", summary="요약")

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        assert "[네이버 카페 공지]" in call_kwargs["text"]

    def test_send_notice_message_type_is_text(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """message_type이 'text'로 설정되는지 확인."""
        messenger.send_notice_summary(title="제목", summary="요약")

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        assert call_kwargs["message_type"] == "text"

    def test_send_notice_raises_on_failure(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """전송 실패 시 RuntimeError가 전파되는지 확인."""
        mock_message_client.send_message_to_me.side_effect = Exception("전송 오류")

        with pytest.raises(RuntimeError):
            messenger.send_notice_summary(title="공지", summary="내용")

    def test_send_notice_format_structure(
        self, messenger: KakaoMessenger, mock_message_client: MagicMock
    ) -> None:
        """메시지 포맷 구조(헤더 → 제목 → 요약)가 올바른지 확인."""
        messenger.send_notice_summary(title="행사 일정", summary="5월 1일 오후 2시")

        call_kwargs = mock_message_client.send_message_to_me.call_args[1]
        text = call_kwargs["text"]

        header_pos = text.find("[네이버 카페 공지]")
        title_pos = text.find("행사 일정")
        summary_pos = text.find("5월 1일 오후 2시")

        assert header_pos < title_pos < summary_pos
