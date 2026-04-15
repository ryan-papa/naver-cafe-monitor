"""게시판 URL 생성 유틸리티."""
from __future__ import annotations

_BOARD_URL_TEMPLATE = "https://cafe.naver.com/f-e/cafes/{cafe_id}/menus/{menu_id}"


def build_board_url(cafe_id: int, menu_id: int) -> str:
    """cafe_id와 menu_id로 게시판 URL을 생성한다."""
    return _BOARD_URL_TEMPLATE.format(cafe_id=cafe_id, menu_id=menu_id)
