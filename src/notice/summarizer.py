"""공지사항 AI 요약 모듈 (T-09).

Anthropic Claude API를 사용하여 정제된 공지 텍스트를
핵심 내용과 일정을 포함한 불릿 리스트로 요약한다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anthropic

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "당신은 네이버 카페 공지사항을 요약하는 어시스턴트입니다. "
    "핵심 내용과 일정을 간결하게 추출하세요."
)

_USER_PROMPT_TEMPLATE = """\
다음 공지사항 텍스트를 읽고 아래 형식으로 요약해 주세요.

**핵심 내용:**
- (주요 내용을 불릿 리스트로)

**일정 및 기한:**
- (날짜·기간·마감일 등을 불릿 리스트로, 없으면 "없음")

---
{text}
"""


class Summarizer:
    """공지사항 텍스트를 Claude API로 요약하는 클래스."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-haiku-20241022",
        max_tokens: int = 300,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    # ── 팩토리 ───────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config: "Config") -> "Summarizer":
        """Config 인스턴스로부터 Summarizer를 생성한다."""
        return cls(
            api_key=config.anthropic_api_key,
            model=config.summary.model,
            max_tokens=config.summary.max_tokens,
        )

    # ── 요약 ─────────────────────────────────────────────────────────────────

    def summarize(self, text: str) -> str:
        """공지 텍스트를 요약하여 반환한다.

        Args:
            text: 정제된 공지사항 텍스트

        Returns:
            핵심 내용과 일정을 포함한 불릿 리스트 요약문

        Raises:
            anthropic.APIError: API 호출 실패 시
        """
        if not text.strip():
            logger.warning("빈 텍스트가 입력되었습니다.")
            return ""

        user_content = _USER_PROMPT_TEMPLATE.format(text=text)

        logger.debug("Claude API 요약 요청: model=%s, max_tokens=%d", self._model, self._max_tokens)

        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )

        result = message.content[0].text
        logger.debug("요약 완료: %d자", len(result))
        return result
