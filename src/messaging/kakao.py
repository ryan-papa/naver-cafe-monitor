"""카카오 1:1 메시지 전송 모듈.

PyKakao 라이브러리를 사용하여 카카오 나에게 보내기 API로 메시지를 전송한다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyKakao.api import Message

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

# 카카오 이미지 첨부 최대 개수
_MAX_IMAGE_ATTACHMENTS = 5


class KakaoMessenger:
    """카카오 메시지 전송 클래스."""

    def __init__(self, access_token: str) -> None:
        """초기화.

        Args:
            access_token: 카카오 OAuth 액세스 토큰
        """
        self._client = Message(service_key=None)
        self._client.set_access_token(access_token)

    @classmethod
    def from_config(cls, config: Config) -> KakaoMessenger:
        """Config 인스턴스에서 KakaoMessenger를 생성한다.

        Args:
            config: 애플리케이션 설정

        Returns:
            KakaoMessenger 인스턴스
        """
        return cls(access_token=config.kakao_token)

    def send_text(self, message: str) -> None:
        """텍스트 메시지를 나에게 전송한다.

        Args:
            message: 전송할 텍스트 메시지

        Raises:
            RuntimeError: 메시지 전송 실패 시
        """
        try:
            self._client.send_message_to_me(
                message_type="text",
                text=message,
            )
            logger.info("카카오 텍스트 메시지 전송 완료")
        except Exception as exc:
            logger.error("카카오 텍스트 메시지 전송 실패: %s", exc)
            raise RuntimeError(f"카카오 텍스트 메시지 전송 실패: {exc}") from exc

    def send_images(
        self,
        image_paths: list[Path],
        caption: str = "",
    ) -> None:
        """이미지를 나에게 전송한다.

        최대 첨부 수(_MAX_IMAGE_ATTACHMENTS)를 초과하면 배치로 나누어 전송한다.
        피드 메시지 타입은 링크 필드가 필수이므로 텍스트 메시지로 폴백하고
        이미지 경로 정보를 포함한다.

        Args:
            image_paths: 전송할 이미지 파일 경로 목록
            caption: 이미지에 첨부할 텍스트 (선택)

        Raises:
            RuntimeError: 메시지 전송 실패 시
        """
        if not image_paths:
            logger.warning("전송할 이미지가 없습니다.")
            return

        batches = [
            image_paths[i : i + _MAX_IMAGE_ATTACHMENTS]
            for i in range(0, len(image_paths), _MAX_IMAGE_ATTACHMENTS)
        ]

        for batch_index, batch in enumerate(batches, start=1):
            paths_text = "\n".join(str(p) for p in batch)
            batch_caption = caption or ""
            if len(batches) > 1:
                batch_caption = f"[{batch_index}/{len(batches)}] {batch_caption}".strip()

            text_body = f"{batch_caption}\n{paths_text}".strip() if batch_caption else paths_text

            try:
                self._client.send_message_to_me(
                    message_type="text",
                    text=text_body,
                )
                logger.info(
                    "카카오 이미지 배치 %d/%d 전송 완료 (%d장)",
                    batch_index,
                    len(batches),
                    len(batch),
                )
            except Exception as exc:
                logger.error(
                    "카카오 이미지 배치 %d/%d 전송 실패: %s",
                    batch_index,
                    len(batches),
                    exc,
                )
                raise RuntimeError(
                    f"카카오 이미지 전송 실패 (배치 {batch_index}/{len(batches)}): {exc}"
                ) from exc

    def send_notice_summary(self, title: str, summary: str) -> None:
        """공지 요약을 포맷하여 나에게 전송한다.

        Args:
            title: 공지 제목
            summary: 공지 요약 내용

        Raises:
            RuntimeError: 메시지 전송 실패 시
        """
        message = f"[네이버 카페 공지]\n\n{title}\n\n{summary}"
        self.send_text(message)
        logger.info("카카오 공지 요약 전송 완료: %s", title)
