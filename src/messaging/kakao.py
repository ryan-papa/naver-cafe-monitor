"""카카오 메시지 전송 모듈.

카카오 REST API를 직접 호출하여 메시지를 전송한다.
이미지는 카카오 CDN에 업로드 후 list 타입으로 묶어서 전송.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
_IMAGE_UPLOAD_URL = "https://kapi.kakao.com/v2/api/talk/message/image/upload"
_MAX_LIST_ITEMS = 3  # list 타입 최대 항목 수


class KakaoMessenger:
    """카카오 메시지 전송 클래스."""

    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._headers = {"Authorization": f"Bearer {access_token}"}

    @classmethod
    def from_config(cls, config: "Config") -> "KakaoMessenger":
        return cls(access_token=config.kakao_token)

    def _send_template(self, template: dict) -> None:
        data = {"template_object": json.dumps(template, ensure_ascii=False)}
        r = requests.post(_MEMO_URL, headers=self._headers, data=data)
        if r.status_code != 200:
            logger.error("카카오 전송 실패: %s %s", r.status_code, r.text)
            raise RuntimeError(f"카카오 전송 실패: {r.status_code} {r.text}")

    def _upload_image(self, image_path: Path) -> str:
        """이미지를 카카오 CDN에 업로드하고 URL을 반환한다."""
        with open(image_path, "rb") as f:
            r = requests.post(
                _IMAGE_UPLOAD_URL,
                headers=self._headers,
                files={"file": (image_path.name, f, "image/jpeg")},
            )
        if r.status_code != 200:
            raise RuntimeError(f"이미지 업로드 실패: {r.status_code} {r.text}")
        return r.json()["infos"]["original"]["url"]

    def send_text(self, message: str, link_url: str = "https://cafe.naver.com/sewhakinder", button_label: str = "") -> None:
        """텍스트 메시지를 전송한다."""
        template: dict = {
            "object_type": "text",
            "text": message[:2000],
            "link": {"web_url": link_url, "mobile_web_url": link_url},
        }
        if button_label:
            template["buttons"] = [
                {"title": button_label, "link": {"web_url": link_url, "mobile_web_url": link_url}}
            ]
        self._send_template(template)

    def send_notice_summary(self, title: str, summary: str) -> None:
        """공지 요약을 전송한다."""
        self.send_text(f"[세화유치원 공지]\n\n📋 {title}\n\n{summary}")

    def send_matched_images(
        self, title: str, image_paths: list[Path], post_url: str
    ) -> None:
        """매칭된 이미지를 업로드 후 list 타입으로 묶어서 전송한다."""
        # 이미지 업로드
        uploaded = []
        for path in image_paths:
            try:
                url = self._upload_image(path)
                uploaded.append(url)
                logger.info("이미지 업로드: %s", path.name)
            except Exception as e:
                logger.warning("업로드 실패 스킵: %s — %s", path.name, e)

        if not uploaded:
            logger.warning("업로드된 이미지 없음")
            return

        # 텍스트 알림
        self.send_text(
            f"[세화유치원 사진]\n\n📷 {title}\n자녀 사진 {len(uploaded)}장 발견"
        )

        # list 타입으로 묶어서 전송 (최대 3장씩)
        for batch_start in range(0, len(uploaded), _MAX_LIST_ITEMS):
            batch = uploaded[batch_start : batch_start + _MAX_LIST_ITEMS]
            batch_num = batch_start // _MAX_LIST_ITEMS + 1
            total = (len(uploaded) + _MAX_LIST_ITEMS - 1) // _MAX_LIST_ITEMS

            header = f"📷 {title}"
            if total > 1:
                header += f" ({batch_num}/{total})"

            self._send_template({
                "object_type": "list",
                "header_title": header,
                "header_link": {"web_url": post_url, "mobile_web_url": post_url},
                "contents": [
                    {
                        "title": f"사진 {batch_start + i + 1}/{len(uploaded)}",
                        "description": "",
                        "image_url": url,
                        "link": {"web_url": post_url, "mobile_web_url": post_url},
                    }
                    for i, url in enumerate(batch)
                ],
            })
            logger.info("이미지 배치 %d/%d 전송 (%d장)", batch_num, total, len(batch))
