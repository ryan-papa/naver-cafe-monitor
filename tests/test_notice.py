"""T-08 (extractor) + T-09 (summarizer) 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from src.crawler.parser import PostDetail
from src.notice.extractor import detect_date_patterns, extract
from src.notice.summarizer import Summarizer


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _make_detail(body_text: str) -> PostDetail:
    return PostDetail(
        post_id="1",
        title="테스트 공지",
        url="https://cafe.naver.com/test/1",
        body_text=body_text,
    )


# ── T-08: 텍스트 정제 테스트 ──────────────────────────────────────────────────

class TestExtractHtmlRemoval:
    """HTML 태그 제거 관련 테스트."""

    def test_removes_simple_tags(self) -> None:
        detail = _make_detail("<p>안녕하세요.</p>")
        assert extract(detail) == "안녕하세요."

    def test_removes_nested_tags(self) -> None:
        detail = _make_detail("<div><b>중요</b> 공지입니다.</div>")
        assert "중요" in extract(detail)
        assert "<" not in extract(detail)
        assert ">" not in extract(detail)

    def test_removes_anchor_tag(self) -> None:
        detail = _make_detail('<a href="https://example.com">링크</a> 참고하세요.')
        result = extract(detail)
        assert "href" not in result
        assert "링크" in result

    def test_removes_img_tag(self) -> None:
        detail = _make_detail('<img src="photo.jpg" alt="사진"/> 본문')
        result = extract(detail)
        assert "<img" not in result
        assert "본문" in result

    def test_decodes_html_entities(self) -> None:
        detail = _make_detail("가격: 10,000원 &amp; 부가세 포함")
        result = extract(detail)
        assert "&" in result
        assert "&amp;" not in result

    def test_decodes_nbsp(self) -> None:
        detail = _make_detail("단어1&nbsp;단어2")
        result = extract(detail)
        assert "&nbsp;" not in result
        assert "단어1" in result
        assert "단어2" in result

    def test_decodes_lt_gt_entities(self) -> None:
        detail = _make_detail("A &lt; B &gt; C")
        result = extract(detail)
        assert "<" in result
        assert ">" in result
        assert "&lt;" not in result


class TestExtractWhitespace:
    """공백·줄바꿈 정규화 테스트."""

    def test_strips_leading_trailing_whitespace(self) -> None:
        detail = _make_detail("   공지입니다.   ")
        assert extract(detail) == "공지입니다."

    def test_collapses_multiple_spaces(self) -> None:
        detail = _make_detail("단어1   단어2")
        result = extract(detail)
        assert "  " not in result
        assert "단어1" in result
        assert "단어2" in result

    def test_collapses_excessive_newlines(self) -> None:
        detail = _make_detail("첫 줄\n\n\n\n\n두 번째 줄")
        result = extract(detail)
        assert "\n\n\n" not in result
        assert "첫 줄" in result
        assert "두 번째 줄" in result

    def test_preserves_meaningful_newlines(self) -> None:
        detail = _make_detail("첫 줄\n두 번째 줄")
        result = extract(detail)
        assert "첫 줄" in result
        assert "두 번째 줄" in result

    def test_empty_body_returns_empty_string(self) -> None:
        detail = _make_detail("")
        assert extract(detail) == ""

    def test_whitespace_only_body_returns_empty(self) -> None:
        detail = _make_detail("   \n\t  ")
        assert extract(detail) == ""

    def test_html_with_mixed_whitespace(self) -> None:
        detail = _make_detail("<p>  첫 문단  </p>\n\n\n<p>  두 번째 문단  </p>")
        result = extract(detail)
        assert "첫 문단" in result
        assert "두 번째 문단" in result
        assert "  " not in result


# ── T-08: 날짜 패턴 감지 테스트 ──────────────────────────────────────────────

class TestDetectDatePatterns:
    """날짜·일정 패턴 감지 테스트."""

    def test_detects_korean_date(self) -> None:
        text = "행사는 2024년 5월 10일에 진행됩니다."
        patterns = detect_date_patterns(text)
        assert any("2024년" in p for p in patterns)

    def test_detects_iso_date_hyphen(self) -> None:
        text = "마감일: 2024-03-15"
        patterns = detect_date_patterns(text)
        assert any("2024-03-15" in p for p in patterns)

    def test_detects_iso_date_dot(self) -> None:
        text = "기한: 2024.12.31"
        patterns = detect_date_patterns(text)
        assert any("2024.12.31" in p for p in patterns)

    def test_detects_mmdd_slash(self) -> None:
        text = "신청 마감: 3/15"
        patterns = detect_date_patterns(text)
        assert len(patterns) > 0

    def test_detects_time_range(self) -> None:
        text = "오후 14:00 ~ 18:00에 진행됩니다."
        patterns = detect_date_patterns(text)
        assert len(patterns) > 0

    def test_detects_period(self) -> None:
        text = "3박 4일 일정으로 진행됩니다."
        patterns = detect_date_patterns(text)
        assert any("3박" in p or "4일" in p for p in patterns)

    def test_no_pattern_returns_empty_list(self) -> None:
        text = "특별한 일정이 없는 공지입니다."
        patterns = detect_date_patterns(text)
        assert isinstance(patterns, list)

    def test_multiple_dates_all_detected(self) -> None:
        text = "1차: 2024년 3월 5일, 2차: 2024년 4월 10일"
        patterns = detect_date_patterns(text)
        assert len(patterns) >= 2


# ── T-09: 요약 테스트 ─────────────────────────────────────────────────────────

class TestSummarizerInit:
    """Summarizer 초기화 테스트."""

    def test_from_config(self) -> None:
        mock_config = MagicMock()
        mock_config.anthropic_api_key = "test-key"
        mock_config.summary.model = "claude-3-5-haiku-20241022"
        mock_config.summary.max_tokens = 300

        with patch("anthropic.Anthropic"):
            s = Summarizer.from_config(mock_config)
        assert isinstance(s, Summarizer)
        assert s._model == "claude-3-5-haiku-20241022"
        assert s._max_tokens == 300

    def test_default_model(self) -> None:
        with patch("anthropic.Anthropic"):
            s = Summarizer(api_key="key")
        assert s._model == "claude-3-5-haiku-20241022"
        assert s._max_tokens == 300


class TestSummarizerSummarize:
    """summarize() 메서드 테스트 — API mock 사용."""

    @pytest.fixture()
    def mock_client(self):
        """anthropic.Anthropic를 mock으로 교체하는 픽스처."""
        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_instance = MockAnthropicClass.return_value
            yield mock_instance

    def _make_api_response(self, text: str) -> MagicMock:
        """API 응답 형태의 mock 객체를 생성한다."""
        response = MagicMock()
        response.content = [MagicMock(text=text)]
        return response

    def test_returns_summary_text(self, mock_client: MagicMock) -> None:
        expected = "**핵심 내용:**\n- 정기 모임 안내\n\n**일정 및 기한:**\n- 2024년 5월 1일"
        mock_client.messages.create.return_value = self._make_api_response(expected)

        s = Summarizer(api_key="test-key")
        result = s.summarize("정기 모임이 2024년 5월 1일에 있습니다.")

        assert result == expected

    def test_calls_api_with_correct_model(self, mock_client: MagicMock) -> None:
        mock_client.messages.create.return_value = self._make_api_response("요약")

        s = Summarizer(api_key="test-key", model="claude-3-haiku-20240307")
        s.summarize("공지 내용")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-3-haiku-20240307"

    def test_calls_api_with_max_tokens(self, mock_client: MagicMock) -> None:
        mock_client.messages.create.return_value = self._make_api_response("요약")

        s = Summarizer(api_key="test-key", max_tokens=500)
        s.summarize("공지 내용")

        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 500

    def test_input_text_included_in_prompt(self, mock_client: MagicMock) -> None:
        mock_client.messages.create.return_value = self._make_api_response("요약")

        s = Summarizer(api_key="test-key")
        s.summarize("특별한 공지 내용입니다")

        call_kwargs = mock_client.messages.create.call_args[1]
        messages = call_kwargs["messages"]
        user_content = messages[0]["content"]
        assert "특별한 공지 내용입니다" in user_content

    def test_empty_text_returns_empty_without_api_call(self, mock_client: MagicMock) -> None:
        s = Summarizer(api_key="test-key")
        result = s.summarize("")

        assert result == ""
        mock_client.messages.create.assert_not_called()

    def test_whitespace_only_text_returns_empty(self, mock_client: MagicMock) -> None:
        s = Summarizer(api_key="test-key")
        result = s.summarize("   \n  ")

        assert result == ""
        mock_client.messages.create.assert_not_called()


class TestSummarizerErrorHandling:
    """API 오류 처리 테스트."""

    def test_raises_api_error_on_failure(self) -> None:
        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_instance = MockAnthropicClass.return_value
            mock_instance.messages.create.side_effect = anthropic.APIConnectionError(
                request=MagicMock()
            )

            s = Summarizer(api_key="test-key")
            with pytest.raises(anthropic.APIConnectionError):
                s.summarize("공지 내용")

    def test_raises_authentication_error(self) -> None:
        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_instance = MockAnthropicClass.return_value
            mock_instance.messages.create.side_effect = anthropic.AuthenticationError(
                message="invalid api key",
                response=MagicMock(),
                body={},
            )

            s = Summarizer(api_key="invalid-key")
            with pytest.raises(anthropic.AuthenticationError):
                s.summarize("공지 내용")

    def test_raises_rate_limit_error(self) -> None:
        with patch("anthropic.Anthropic") as MockAnthropicClass:
            mock_instance = MockAnthropicClass.return_value
            mock_instance.messages.create.side_effect = anthropic.RateLimitError(
                message="rate limit exceeded",
                response=MagicMock(),
                body={},
            )

            s = Summarizer(api_key="test-key")
            with pytest.raises(anthropic.RateLimitError):
                s.summarize("공지 내용")
