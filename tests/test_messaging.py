"""T-10 카카오 메시지 전송 테스트."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from src.messaging.kakao import KakaoMessenger


# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_post():
    """requests.post를 mock으로 교체하는 픽스처."""
    with patch("src.messaging.kakao.requests.post") as mock:
        mock.return_value = MagicMock(status_code=200, text="OK")
        yield mock


@pytest.fixture()
def messenger() -> KakaoMessenger:
    """테스트용 KakaoMessenger 인스턴스."""
    return KakaoMessenger(access_token="test-token")


# ── 초기화 테스트 ──────────────────────────────────────────────────────────────

class TestKakaoMessengerInit:
    """KakaoMessenger 초기화 테스트."""

    def test_from_config(self) -> None:
        """from_config() 팩토리가 올바르게 인스턴스를 생성하는지 확인."""
        mock_config = MagicMock()
        mock_config.kakao_token = "my-token"
        messenger = KakaoMessenger.from_config(mock_config)
        assert isinstance(messenger, KakaoMessenger)

    def test_headers_set(self) -> None:
        """초기화 시 Authorization 헤더가 설정되는지 확인."""
        m = KakaoMessenger(access_token="my-access-token")
        assert m._headers["Authorization"] == "Bearer my-access-token"


# ── 텍스트 전송 테스트 ─────────────────────────────────────────────────────────

class TestSendText:
    """send_text() 메서드 테스트."""

    def test_send_text_calls_api(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """send_text()가 requests.post를 올바르게 호출하는지 확인."""
        messenger.send_text("안녕하세요!")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        data = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs[0][1]
        template = json.loads(data["template_object"])
        assert template["object_type"] == "text"
        assert template["text"] == "안녕하세요!"

    def test_send_text_raises_on_failure(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """API 호출 실패 시 RuntimeError가 발생하는지 확인."""
        mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
        with pytest.raises(RuntimeError, match="카카오 전송 실패"):
            messenger.send_text("테스트 메시지")

    def test_send_text_long_message_truncated(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """2000자 초과 메시지가 잘리는지 확인."""
        long_msg = "가" * 3000
        messenger.send_text(long_msg)
        call_kwargs = mock_post.call_args
        template = json.loads(call_kwargs[1]["data"]["template_object"])
        assert len(template["text"]) == 2000

    def test_send_text_includes_link(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """템플릿에 link가 포함되는지 확인."""
        messenger.send_text("테스트")
        template = json.loads(
            mock_post.call_args[1]["data"]["template_object"]
        )
        assert "link" in template


# ── 공지 요약 전송 테스트 ─────────────────────────────────────────────────────

class TestSendNoticeSummary:
    """send_notice_summary() 메서드 테스트."""

    def test_send_notice_includes_title(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """메시지에 공지 제목이 포함되는지 확인."""
        messenger.send_notice_summary(title="봄 축제 안내", summary="행사 내용입니다.")
        template = json.loads(
            mock_post.call_args[1]["data"]["template_object"]
        )
        assert "봄 축제 안내" in template["text"]

    def test_send_notice_includes_summary(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """메시지에 공지 요약이 포함되는지 확인."""
        messenger.send_notice_summary(title="공지", summary="중요한 내용입니다.")
        template = json.loads(
            mock_post.call_args[1]["data"]["template_object"]
        )
        assert "중요한 내용입니다." in template["text"]

    def test_send_notice_format_has_header(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """메시지에 [세화유치원 공지] 헤더가 포함되는지 확인."""
        messenger.send_notice_summary(title="제목", summary="요약")
        template = json.loads(
            mock_post.call_args[1]["data"]["template_object"]
        )
        assert "[세화유치원 공지]" in template["text"]

    def test_send_notice_format_structure(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """메시지 포맷 구조(헤더 → 제목 → 요약)가 올바른지 확인."""
        messenger.send_notice_summary(title="행사 일정", summary="5월 1일 오후 2시")
        template = json.loads(
            mock_post.call_args[1]["data"]["template_object"]
        )
        text = template["text"]
        header_pos = text.find("[세화유치원 공지]")
        title_pos = text.find("행사 일정")
        summary_pos = text.find("5월 1일 오후 2시")
        assert header_pos < title_pos < summary_pos


# ── 이미지 전송 테스트 ─────────────────────────────────────────────────────────

class TestSendMatchedImages:
    """send_matched_images() 메서드 테스트."""

    def _setup_upload(self, mock_post: MagicMock, n: int = 1) -> None:
        """업로드 성공 + 전송 성공 응답을 설정한다."""
        upload_resp = MagicMock(
            status_code=200,
            json=lambda: {"infos": {"original": {"url": "https://cdn/img.jpg"}}},
        )
        send_resp = MagicMock(status_code=200, text="OK")
        # 업로드 n회 + send_text 1회 + list 전송
        mock_post.side_effect = [upload_resp] * n + [send_resp] * 10

    def test_uploads_and_sends(
        self, messenger: KakaoMessenger, mock_post: MagicMock, tmp_path: Path
    ) -> None:
        """이미지 업로드 후 메시지가 전송되는지 확인."""
        self._setup_upload(mock_post, n=1)
        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8test")
        messenger.send_matched_images("공지", [img], "https://cafe.naver.com/1")
        # 업로드 1회 + 텍스트 1회 + list 1회 = 3회
        assert mock_post.call_count == 3

    def test_empty_list_no_call(
        self, messenger: KakaoMessenger, mock_post: MagicMock
    ) -> None:
        """빈 리스트 전달 시 업로드도 전송도 하지 않는지 확인."""
        messenger.send_matched_images("공지", [], "https://cafe.naver.com/1")
        mock_post.assert_not_called()

    def test_upload_failure_skips_image(
        self, messenger: KakaoMessenger, mock_post: MagicMock, tmp_path: Path
    ) -> None:
        """업로드 실패한 이미지는 스킵되는지 확인."""
        mock_post.return_value = MagicMock(status_code=500, text="Server Error")
        img = tmp_path / "bad.jpg"
        img.write_bytes(b"\xff\xd8test")
        # 모든 업로드 실패 → 전송 없음
        messenger.send_matched_images("공지", [img], "https://cafe.naver.com/1")
        # 업로드 시도 1회만 (실패하므로 전송 없음)
        assert mock_post.call_count == 1

    def test_multiple_images_batch(
        self, messenger: KakaoMessenger, mock_post: MagicMock, tmp_path: Path
    ) -> None:
        """4장 업로드 시 배치로 나뉘어 전송되는지 확인 (최대 3장씩)."""
        self._setup_upload(mock_post, n=4)
        imgs = []
        for i in range(4):
            img = tmp_path / f"img{i}.jpg"
            img.write_bytes(b"\xff\xd8test")
            imgs.append(img)
        messenger.send_matched_images("사진", imgs, "https://cafe.naver.com/1")
        # 업로드 4회 + 텍스트 1회 + list 2배치 = 7회
        assert mock_post.call_count == 7
