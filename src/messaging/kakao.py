"""카카오 메시지 전송 모듈.

PyKakao 라이브러리를 사용하여 본인 및 친구에게 메시지를 전송한다.
recipients 설정으로 본인("self") + 친구("friend") 복수 대상 전송을 지원한다.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyKakao.api import Message

if TYPE_CHECKING:
    from src.config import Config, RecipientConfig

logger = logging.getLogger(__name__)

# 카카오 이미지 첨부 최대 개수
_MAX_IMAGE_ATTACHMENTS = 5


class KakaoMessenger:
    """카카오 메시지 전송 클래스."""

    def __init__(
        self,
        access_token: str,
        recipients: list[RecipientConfig] | None = None,
    ) -> None:
        self._client = Message(service_key=None)
        self._client.set_access_token(access_token)
        self._recipients = recipients or []

    @classmethod
    def from_config(cls, config: Config) -> KakaoMessenger:
        """Config 인스턴스에서 KakaoMessenger를 생성한다."""
        return cls(
            access_token=config.kakao_token,
            recipients=config.notification.kakao.recipients,
        )

    # ── 내부 전송 헬퍼 ───────────────────────────────────────────────────────

    def _send_to_me(self, message_type: str, **kwargs: object) -> None:
        """나에게 보내기 API 호출."""
        self._client.send_message_to_me(message_type=message_type, **kwargs)

    def _send_to_friend(
        self, friend_uuid: str, message_type: str, **kwargs: object
    ) -> None:
        """친구에게 보내기 API 호출."""
        self._client.send_message_to_friend(
            receiver_uuids=[friend_uuid],
            message_type=message_type,
            **kwargs,
        )

    def _send_to_all(self, message_type: str, **kwargs: object) -> None:
        """설정된 모든 수신자에게 메시지를 전송한다.

        recipients가 비어 있으면 본인에게만 전송한다(하위 호환).
        """
        targets = self._recipients or []
        if not targets:
            self._send_to_me(message_type=message_type, **kwargs)
            return

        for recipient in targets:
            if recipient.type == "friend" and recipient.friend_uuid:
                self._send_to_friend(
                    recipient.friend_uuid, message_type=message_type, **kwargs
                )
                logger.info("친구에게 메시지 전송 완료: %s", recipient.friend_uuid[:8])
            else:
                self._send_to_me(message_type=message_type, **kwargs)

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def send_text(self, message: str) -> None:
        """텍스트 메시지를 전송한다."""
        try:
            self._send_to_all(message_type="text", text=message)
            logger.info("카카오 텍스트 메시지 전송 완료")
        except Exception as exc:
            logger.error("카카오 텍스트 메시지 전송 실패: %s", exc)
            raise RuntimeError(f"카카오 텍스트 메시지 전송 실패: {exc}") from exc

    @staticmethod
    def _encode_image_base64(image_path: Path) -> str:
        """이미지 파일을 base64 문자열로 인코딩한다."""
        data = image_path.read_bytes()
        return base64.b64encode(data).decode("utf-8")

    def send_images(
        self,
        image_paths: list[Path],
        caption: str = "",
    ) -> None:
        """이미지를 전송한다.

        최대 첨부 수를 초과하면 배치로 나누어 전송한다.
        """
        if not image_paths:
            logger.warning("전송할 이미지가 없습니다.")
            return

        batches = [
            image_paths[i : i + _MAX_IMAGE_ATTACHMENTS]
            for i in range(0, len(image_paths), _MAX_IMAGE_ATTACHMENTS)
        ]

        for batch_index, batch in enumerate(batches, start=1):
            batch_caption = caption or ""
            if len(batches) > 1:
                batch_caption = f"[{batch_index}/{len(batches)}] {batch_caption}".strip()

            image_data_list: list[str] = []
            for img_path in batch:
                try:
                    encoded = self._encode_image_base64(img_path)
                    image_data_list.append(
                        f"[image:{img_path.name}]\n"
                        f"data:image/{img_path.suffix.lstrip('.')};base64,{encoded}"
                    )
                except FileNotFoundError:
                    logger.warning("이미지 파일을 찾을 수 없습니다: %s", img_path)
                    image_data_list.append(f"[image:{img_path.name}] (파일 없음)")

            images_text = "\n".join(image_data_list)
            text_body = (
                f"{batch_caption}\n{images_text}".strip()
                if batch_caption
                else images_text
            )

            try:
                self._send_to_all(message_type="text", text=text_body)
                logger.info(
                    "카카오 이미지 배치 %d/%d 전송 완료 (%d장)",
                    batch_index, len(batches), len(batch),
                )
            except Exception as exc:
                logger.error(
                    "카카오 이미지 배치 %d/%d 전송 실패: %s",
                    batch_index, len(batches), exc,
                )
                raise RuntimeError(
                    f"카카오 이미지 전송 실패 (배치 {batch_index}/{len(batches)}): {exc}"
                ) from exc

    def send_notice_summary(self, title: str, summary: str) -> None:
        """공지 요약을 포맷하여 전송한다."""
        message = f"[네이버 카페 공지]\n\n{title}\n\n{summary}"
        self.send_text(message)
        logger.info("카카오 공지 요약 전송 완료: %s", title)
