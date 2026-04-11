"""crawler 비즈니스 로직 테스트.

실제 네트워크 호출 없이 Playwright를 mock하여 파싱·세션 로직을 검증한다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.crawler.parser import (
    PostDetail,
    PostSummary,
    _build_url,
    _parse_written_at,
    parse_post_detail,
    parse_post_list,
)
from src.crawler.session import restore_cookies, save_cookies
from src.config import Config


# ── 공통 픽스처 ───────────────────────────────────────────────────────────────

_VALID_ENV: dict[str, str] = {
    "NAVER_ID": "test_id",
    "NAVER_PW": "test_pw",
    "KAKAO_TOKEN": "test_kakao",
    "ANTHROPIC_API_KEY": "test_key",
}
_MINIMAL_RAW: dict = {
    "scheduler": {"poll_interval_seconds": 60, "timezone": "Asia/Seoul"},
    "cafe": {
        "url": "https://cafe.naver.com/testcafe",
        "boards": [
            {"id": 1, "name": "자유게시판", "face_check": False},
            {"id": 2, "name": "사진게시판", "face_check": True},
        ],
    },
    "face": {"tolerance": 0.55, "reference_dir": "data/faces/"},
    "notification": {"kakao": {"enabled": True, "target_id": "me"}},
    "summary": {"enabled": True, "model": "claude-3-5-haiku-20241022", "max_tokens": 300},
}


@pytest.fixture()
def cfg() -> Config:
    return Config(_MINIMAL_RAW, _VALID_ENV)


def _make_el(text: str = "", href: str = "", src: str = "") -> AsyncMock:
    """셀렉터가 반환하는 엘리먼트 mock을 생성한다."""
    el = AsyncMock()
    el.inner_text = AsyncMock(return_value=text)
    el.get_attribute = AsyncMock(side_effect=lambda attr: {
        "href": href, "src": src, "data-src": ""
    }.get(attr, ""))
    return el


def _make_row(title: str, href: str, date_str: str) -> AsyncMock:
    """게시물 행 mock을 생성한다."""
    row = AsyncMock()
    title_el = _make_el(text=title, href=href)
    date_el = _make_el(text=date_str)
    row.query_selector = AsyncMock(side_effect=lambda sel: {
        "a.article, td.td-article a": title_el,
        "td.td-date, span.date": date_el,
    }.get(sel))
    return row


def _make_page(rows: list[AsyncMock] | None = None) -> MagicMock:
    """게시판 목록 페이지 mock을 생성한다."""
    frame = AsyncMock()
    frame.query_selector_all = AsyncMock(return_value=rows or [])
    frame.query_selector = AsyncMock(return_value=None)

    page = MagicMock()
    page.frame = MagicMock(return_value=None)   # cafe_main frame 없음 → main_frame 사용
    page.main_frame = frame
    page.url = "https://cafe.naver.com/testcafe/123"
    return page


# ── _parse_written_at 단위 테스트 ─────────────────────────────────────────────

class TestParseWrittenAt:
    def test_full_datetime_format(self) -> None:
        result = _parse_written_at("2024.03.15. 14:30")
        assert result == datetime(2024, 3, 15, 14, 30)

    def test_date_only_format(self) -> None:
        result = _parse_written_at("2024.03.15.")
        assert result == datetime(2024, 3, 15)

    def test_iso_datetime_format(self) -> None:
        result = _parse_written_at("2024-03-15 09:00:00")
        assert result == datetime(2024, 3, 15, 9, 0, 0)

    def test_iso_date_format(self) -> None:
        result = _parse_written_at("2024-03-15")
        assert result == datetime(2024, 3, 15)

    def test_invalid_string_returns_none(self) -> None:
        assert _parse_written_at("잘못된날짜") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_written_at("") is None

    def test_strips_whitespace(self) -> None:
        result = _parse_written_at("  2024.03.15.  ")
        assert result == datetime(2024, 3, 15)


# ── _build_url 단위 테스트 ────────────────────────────────────────────────────

class TestBuildUrl:
    def test_relative_href_prepends_base(self) -> None:
        assert _build_url("/testcafe/123") == "https://cafe.naver.com/testcafe/123"

    def test_absolute_href_unchanged(self) -> None:
        url = "https://cafe.naver.com/testcafe/123"
        assert _build_url(url) == url

    def test_empty_string_prepends_base(self) -> None:
        assert _build_url("") == "https://cafe.naver.com"


# ── parse_post_list 테스트 ────────────────────────────────────────────────────

class TestParsePostList:
    @pytest.mark.asyncio
    async def test_parses_single_row(self) -> None:
        row = _make_row(
            title="테스트 게시물",
            href="/testcafe?articleid=42",
            date_str="2024.03.15. 10:00",
        )
        page = _make_page(rows=[row])

        posts = await parse_post_list(page, "자유게시판")

        assert len(posts) == 1
        assert posts[0].title == "테스트 게시물"
        assert posts[0].post_id == "42"
        assert posts[0].board_type == "자유게시판"
        assert posts[0].url == "https://cafe.naver.com/testcafe?articleid=42"
        assert posts[0].written_at == datetime(2024, 3, 15, 10, 0)

    @pytest.mark.asyncio
    async def test_parses_multiple_rows(self) -> None:
        rows = [
            _make_row("게시물1", "/testcafe?articleid=1", "2024.01.01. 09:00"),
            _make_row("게시물2", "/testcafe?articleid=2", "2024.01.02. 10:00"),
            _make_row("게시물3", "/testcafe?articleid=3", "2024.01.03. 11:00"),
        ]
        page = _make_page(rows=rows)

        posts = await parse_post_list(page, "사진게시판")

        assert len(posts) == 3
        assert [p.post_id for p in posts] == ["1", "2", "3"]
        assert all(p.board_type == "사진게시판" for p in posts)

    @pytest.mark.asyncio
    async def test_skips_row_without_title_element(self) -> None:
        # 제목 엘리먼트가 없는 행은 스킵
        row = AsyncMock()
        row.query_selector = AsyncMock(return_value=None)
        page = _make_page(rows=[row])

        posts = await parse_post_list(page, "자유게시판")

        assert posts == []

    @pytest.mark.asyncio
    async def test_empty_board_returns_empty_list(self) -> None:
        page = _make_page(rows=[])
        posts = await parse_post_list(page, "자유게시판")
        assert posts == []

    @pytest.mark.asyncio
    async def test_returns_post_summary_dataclass(self) -> None:
        row = _make_row("제목", "/testcafe?articleid=99", "2024.06.01.")
        page = _make_page(rows=[row])

        posts = await parse_post_list(page, "자유게시판")

        assert isinstance(posts[0], PostSummary)

    @pytest.mark.asyncio
    async def test_date_none_when_empty(self) -> None:
        row = _make_row("제목", "/testcafe?articleid=5", "")
        # date_el이 없는 경우
        title_el = _make_el(text="제목", href="/testcafe?articleid=5")
        row.query_selector = AsyncMock(side_effect=lambda sel: {
            "a.article, td.td-article a": title_el,
            "td.td-date, span.date": None,
        }.get(sel))
        page = _make_page(rows=[row])

        posts = await parse_post_list(page, "자유게시판")
        assert posts[0].written_at is None


# ── parse_post_detail 테스트 ──────────────────────────────────────────────────

class TestParsePostDetail:
    def _make_detail_page(
        self,
        title: str = "상세 제목",
        body: str = "본문 내용",
        img_srcs: list[str] | None = None,
    ) -> MagicMock:
        title_el = _make_el(text=title)
        img_srcs = img_srcs or []

        img_els = []
        for src in img_srcs:
            img = AsyncMock()
            img.get_attribute = AsyncMock(side_effect=lambda attr, s=src: {
                "src": s, "data-src": ""
            }.get(attr, ""))
            img_els.append(img)

        body_el = AsyncMock()
        body_el.inner_text = AsyncMock(return_value=body)
        body_el.query_selector_all = AsyncMock(return_value=img_els)

        frame = AsyncMock()
        frame.query_selector = AsyncMock(side_effect=lambda sel: {
            ".se-title-text, #subject, .tit-view": title_el,
            ".se-main-container, #postContent, .article-viewer": body_el,
        }.get(sel))

        page = MagicMock()
        page.frame = MagicMock(return_value=None)
        page.main_frame = frame
        page.url = "https://cafe.naver.com/testcafe/42"
        return page

    @pytest.mark.asyncio
    async def test_extracts_title_and_body(self) -> None:
        page = self._make_detail_page(title="테스트 제목", body="본문 텍스트")
        detail = await parse_post_detail(page, "42")
        assert detail.title == "테스트 제목"
        assert detail.body_text == "본문 텍스트"

    @pytest.mark.asyncio
    async def test_extracts_image_urls(self) -> None:
        img_srcs = [
            "https://cafeptthumb-phinf.pstatic.net/img1.jpg",
            "https://cafeptthumb-phinf.pstatic.net/img2.jpg",
        ]
        page = self._make_detail_page(img_srcs=img_srcs)
        detail = await parse_post_detail(page, "42")
        assert detail.image_urls == img_srcs

    @pytest.mark.asyncio
    async def test_excludes_data_uri_images(self) -> None:
        """data: URI 이미지는 image_urls에 포함되지 않아야 한다."""
        img = AsyncMock()
        img.get_attribute = AsyncMock(side_effect=lambda attr: {
            "src": "data:image/png;base64,abc123",
            "data-src": "",
        }.get(attr, ""))

        body_el = AsyncMock()
        body_el.inner_text = AsyncMock(return_value="본문")
        body_el.query_selector_all = AsyncMock(return_value=[img])

        frame = AsyncMock()
        frame.query_selector = AsyncMock(side_effect=lambda sel: (
            body_el if "container" in sel or "postContent" in sel or "viewer" in sel else None
        ))

        page = MagicMock()
        page.frame = MagicMock(return_value=None)
        page.main_frame = frame
        page.url = "https://cafe.naver.com/testcafe/42"

        detail = await parse_post_detail(page, "42")
        assert detail.image_urls == []

    @pytest.mark.asyncio
    async def test_returns_post_detail_dataclass(self) -> None:
        page = self._make_detail_page()
        detail = await parse_post_detail(page, "42")
        assert isinstance(detail, PostDetail)
        assert detail.post_id == "42"

    @pytest.mark.asyncio
    async def test_empty_image_list_when_no_images(self) -> None:
        page = self._make_detail_page(img_srcs=[])
        detail = await parse_post_detail(page, "42")
        assert detail.image_urls == []


# ── 세션 쿠키 저장/복원 테스트 ────────────────────────────────────────────────

class TestSessionCookies:
    @pytest.mark.asyncio
    async def test_save_cookies_writes_json_file(self, tmp_path: Path) -> None:
        cookie_path = tmp_path / "cookies.json"
        sample_cookies = [
            {"name": "NID_AUT", "value": "token123", "domain": ".naver.com"},
            {"name": "NID_SES", "value": "session456", "domain": ".naver.com"},
        ]
        context = AsyncMock()
        context.cookies = AsyncMock(return_value=sample_cookies)

        await save_cookies(context, cookie_path)

        assert cookie_path.exists()
        saved = json.loads(cookie_path.read_text(encoding="utf-8"))
        assert saved == sample_cookies

    @pytest.mark.asyncio
    async def test_restore_cookies_returns_true_when_file_exists(self, tmp_path: Path) -> None:
        cookie_path = tmp_path / "cookies.json"
        cookies = [{"name": "NID_AUT", "value": "tok", "domain": ".naver.com"}]
        cookie_path.write_text(json.dumps(cookies), encoding="utf-8")

        context = AsyncMock()
        context.add_cookies = AsyncMock()

        result = await restore_cookies(context, cookie_path)

        assert result is True
        context.add_cookies.assert_awaited_once_with(cookies)

    @pytest.mark.asyncio
    async def test_restore_cookies_returns_false_when_no_file(self, tmp_path: Path) -> None:
        cookie_path = tmp_path / "nonexistent.json"
        context = AsyncMock()

        result = await restore_cookies(context, cookie_path)

        assert result is False
        context.add_cookies.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_cookies_creates_parent_directories(self, tmp_path: Path) -> None:
        cookie_path = tmp_path / "nested" / "dir" / "cookies.json"
        context = AsyncMock()
        context.cookies = AsyncMock(return_value=[])

        await save_cookies(context, cookie_path)

        assert cookie_path.exists()

    @pytest.mark.asyncio
    async def test_restore_cookies_loads_all_cookies(self, tmp_path: Path) -> None:
        cookie_path = tmp_path / "cookies.json"
        cookies = [
            {"name": f"cookie{i}", "value": f"val{i}", "domain": ".naver.com"}
            for i in range(5)
        ]
        cookie_path.write_text(json.dumps(cookies), encoding="utf-8")

        context = AsyncMock()
        context.add_cookies = AsyncMock()

        await restore_cookies(context, cookie_path)

        args = context.add_cookies.call_args[0][0]
        assert len(args) == 5
