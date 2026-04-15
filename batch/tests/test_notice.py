"""T-08 (extractor) + T-09 (summarizer) 테스트."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

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
        detail = _make_detail("<p>공지</p>")
        assert "<p>" not in extract(detail)

    def test_removes_nested_tags(self) -> None:
        detail = _make_detail("<div><p><b>내용</b></p></div>")
        assert "내용" in extract(detail)
        assert "<" not in extract(detail)

    def test_removes_tag_attributes(self) -> None:
        detail = _make_detail('<a href="http://test.com">링크</a>')
        result = extract(detail)
        assert "href" not in result
        assert "링크" in result

    def test_preserves_plain_text(self) -> None:
        detail = _make_detail("일반 텍스트입니다")
        assert extract(detail) == "일반 텍스트입니다"

    def test_handles_self_closing_tags(self) -> None:
        detail = _make_detail("줄1<br/>줄2")
        assert "<br" not in extract(detail)

    def test_handles_empty_body(self) -> None:
        detail = _make_detail("")
        assert extract(detail) == ""

    def test_handles_script_style_tags(self) -> None:
        detail = _make_detail("<script>alert('x')</script>내용")
        result = extract(detail)
        assert "script" not in result.lower() or "내용" in result


class TestExtractWhitespace:
    """공백 정규화 테스트."""

    def test_collapses_multiple_spaces(self) -> None:
        detail = _make_detail("단어1    단어2")
        assert "    " not in extract(detail)

    def test_collapses_multiple_newlines(self) -> None:
        detail = _make_detail("줄1\n\n\n\n줄2")
        result = extract(detail)
        assert "\n\n\n" not in result

    def test_trims_leading_trailing(self) -> None:
        detail = _make_detail("  내용  ")
        assert extract(detail) == "내용"

    def test_decodes_html_entities(self) -> None:
        detail = _make_detail("A &amp; B")
        assert "&amp;" not in extract(detail)

    def test_decodes_nbsp(self) -> None:
        detail = _make_detail("단어1&nbsp;단어2")
        assert "&nbsp;" not in extract(detail)

    def test_mixed_whitespace_types(self) -> None:
        detail = _make_detail("A\t\t B\r\nC")
        result = extract(detail)
        assert "\t\t" not in result

    def test_preserves_single_newline_between_paragraphs(self) -> None:
        detail = _make_detail("문단1\n문단2")
        assert "문단1" in extract(detail) and "문단2" in extract(detail)


class TestDetectDatePatterns:
    """날짜 패턴 감지 테스트."""

    def test_korean_date_format(self) -> None:
        patterns = detect_date_patterns("2024년 5월 1일 행사")
        assert len(patterns) >= 1

    def test_iso_date_format(self) -> None:
        patterns = detect_date_patterns("마감일: 2024-05-01")
        assert len(patterns) >= 1

    def test_slash_date_format(self) -> None:
        patterns = detect_date_patterns("제출일: 5/1")
        assert len(patterns) >= 1

    def test_no_dates_returns_empty(self) -> None:
        patterns = detect_date_patterns("날짜 없는 텍스트")
        assert len(patterns) == 0

    def test_time_pattern(self) -> None:
        patterns = detect_date_patterns("시작: 오후 2시 30분")
        assert len(patterns) >= 1

    def test_period_pattern(self) -> None:
        patterns = detect_date_patterns("기간: 2024년 4월 1일~4월 15일")
        assert len(patterns) >= 1

    def test_mixed_text_with_date(self) -> None:
        text = "다음 주 목요일 2024년 3월 28일에 진행합니다."
        patterns = detect_date_patterns(text)
        assert len(patterns) >= 1

    def test_multiple_dates_all_detected(self) -> None:
        text = "1차: 2024년 3월 5일, 2차: 2024년 4월 10일"
        patterns = detect_date_patterns(text)
        assert len(patterns) >= 2


# ── T-09: 요약 테스트 (Claude CLI 기반) ──────────────────────────────────────

class TestSummarizerInit:
    """Summarizer 초기화 테스트."""

    def test_from_config(self) -> None:
        mock_config = MagicMock()
        mock_config.summary.model = "haiku"
        s = Summarizer.from_config(mock_config)
        assert isinstance(s, Summarizer)
        assert s._model == "haiku"

    def test_default_model(self) -> None:
        s = Summarizer()
        assert s._model == "opus"


class TestSummarizerSummarize:
    """summarize() 메서드 테스트 — subprocess mock."""

    @pytest.fixture()
    def mock_run(self):
        with patch("src.notice.summarizer.subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="**핵심 내용:**\n- 요약 결과",
                stderr="",
            )
            yield mock

    def test_returns_summary_text(self, mock_run: MagicMock) -> None:
        s = Summarizer()
        result = s.summarize("공지 내용")
        assert "핵심 내용" in result

    def test_calls_cli_with_model(self, mock_run: MagicMock) -> None:
        s = Summarizer(model="sonnet")
        s.summarize("공지 내용")
        args = mock_run.call_args[0][0]
        assert "--model" in args
        assert "sonnet" in args

    def test_input_text_included_in_prompt(self, mock_run: MagicMock) -> None:
        s = Summarizer()
        s.summarize("특별한 공지 내용입니다")
        args = mock_run.call_args[0][0]
        prompt = args[2]  # claude -p <prompt>
        assert "특별한 공지 내용입니다" in prompt

    def test_empty_text_returns_empty(self, mock_run: MagicMock) -> None:
        s = Summarizer()
        result = s.summarize("")
        assert result == ""
        mock_run.assert_not_called()

    def test_whitespace_only_returns_empty(self, mock_run: MagicMock) -> None:
        s = Summarizer()
        result = s.summarize("   \n  ")
        assert result == ""
        mock_run.assert_not_called()


class TestSummarizerErrorHandling:
    """CLI 오류 처리 테스트."""

    def test_raises_on_cli_failure(self) -> None:
        with patch("src.notice.summarizer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="error occurred"
            )
            s = Summarizer()
            with pytest.raises(RuntimeError, match="Claude CLI 실패"):
                s.summarize("공지 내용")

    def test_raises_on_timeout(self) -> None:
        with patch("src.notice.summarizer.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)
            s = Summarizer()
            with pytest.raises(RuntimeError, match="타임아웃"):
                s.summarize("공지 내용")
