"""shared/kakao_format.py 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

# shared 모듈 경로 추가 (batch/tests 기준)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.kakao_format import reconstruct_kakao_messages  # noqa: E402


class TestNoticeBoard:
    """공지사항 (menus/6)."""

    def test_notice_without_schedule_returns_single_block(self):
        msgs = reconstruct_kakao_messages(
            board_id="menus/6",
            title="3월 행사 안내",
            summary="3월 15일 봄나들이가 있습니다.",
        )
        assert len(msgs) == 1
        assert msgs[0].startswith("[세화유치원 공지]\n\n📋 3월 행사 안내\n\n")
        assert "3월 15일 봄나들이가 있습니다." in msgs[0]

    def test_notice_with_schedule_returns_two_blocks(self):
        msgs = reconstruct_kakao_messages(
            board_id="menus/6",
            title="4월 공지",
            summary="본문입니다.\n[일정 정리]\n- 4/10 입학식\n- 4/20 소풍",
        )
        assert len(msgs) == 2
        assert msgs[0].startswith("[세화유치원 공지]\n\n📋 4월 공지\n\n본문입니다.")
        assert msgs[1].startswith("[세화유치원 일정]\n\n📅 4월 공지\n\n- 4/10 입학식")
        assert "4/20 소풍" in msgs[1]

    def test_notice_empty_summary_returns_empty_list(self):
        assert reconstruct_kakao_messages("menus/6", "제목", None) == []
        assert reconstruct_kakao_messages("menus/6", "제목", "") == []
        assert reconstruct_kakao_messages("menus/6", "제목", "   ") == []

    def test_notice_only_schedule_suppresses_empty_content_block(self):
        msgs = reconstruct_kakao_messages(
            board_id="menus/6",
            title="일정만",
            summary="[일정 정리]\n- 5/1 휴무",
        )
        assert len(msgs) == 1
        assert msgs[0].startswith("[세화유치원 일정]\n\n📅 일정만\n\n- 5/1 휴무")


class TestOtherBoards:
    """공지 외 게시판 (사진 등)."""

    def test_photo_board_uses_resend_format(self):
        msgs = reconstruct_kakao_messages(
            board_id="menus/13",
            title="사진 게시물",
            summary="본문 텍스트",
        )
        assert msgs == ["[재발송] 사진 게시물\n\n본문 텍스트"]

    def test_empty_summary_returns_empty(self):
        assert reconstruct_kakao_messages("menus/13", "제목", "") == []

    def test_title_none_treated_as_empty_string(self):
        msgs = reconstruct_kakao_messages("menus/13", None, "본문")
        assert msgs == ["[재발송] \n\n본문"]
