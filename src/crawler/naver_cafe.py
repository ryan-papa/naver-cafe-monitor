"""네이버 카페 Playwright 기반 헤드리스 크롤러.

로그인 세션 유지(쿠키 저장/복원), 게시판 목록 수집, 게시물 상세 수집을 수행한다.
인증정보는 Config 객체에서만 참조한다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.async_api import async_playwright

from src.crawler.parser import PostDetail, PostSummary, parse_post_detail, parse_post_list
from src.crawler.session import build_context, is_logged_in, login, restore_cookies, save_cookies

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

_DEFAULT_COOKIE_PATH = Path("data/cookies.json")


class NaverCafeCrawler:
    """네이버 카페 크롤러.

    사용 예::

        async with NaverCafeCrawler(config) as crawler:
            posts = await crawler.fetch_post_list(board_url, board_type="자유게시판")
            detail = await crawler.fetch_post_detail(posts[0].url, posts[0].post_id)
    """

    def __init__(
        self,
        config: "Config",
        cookie_path: Path = _DEFAULT_COOKIE_PATH,
        headless: bool = True,
    ) -> None:
        self._config = config
        self._cookie_path = cookie_path
        self._headless = headless
        self._playwright = None
        self._context = None

    # ── 컨텍스트 매니저 ──────────────────────────────────────────────────────

    async def __aenter__(self) -> "NaverCafeCrawler":
        self._playwright = await async_playwright().start()
        self._context = await build_context(self._playwright, headless=self._headless)
        await self._ensure_logged_in()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._context:
            await save_cookies(self._context, self._cookie_path)
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    # ── 로그인 보장 ──────────────────────────────────────────────────────────

    async def _ensure_logged_in(self) -> None:
        """쿠키 복원 → 로그인 상태 확인 → 필요 시 ID/PW 로그인."""
        assert self._context is not None

        cookie_restored = await restore_cookies(self._context, self._cookie_path)
        page = await self._context.new_page()
        try:
            if cookie_restored and await is_logged_in(page):
                logger.info("저장된 세션으로 로그인 상태 확인")
                return
            logger.info("새 로그인 수행")
            await login(page, self._config.naver_id, self._config.naver_pw)
        finally:
            await page.close()

    # ── 게시판 목록 수집 ─────────────────────────────────────────────────────

    async def fetch_post_list(self, board_url: str, board_type: str) -> list[PostSummary]:
        """지정 게시판 URL에서 게시물 목록을 수집하여 반환한다.

        Args:
            board_url:  크롤링할 게시판 URL
            board_type: 게시판 유형 문자열 (예: "자유게시판", "사진게시판")

        Returns:
            PostSummary 리스트
        """
        assert self._context is not None
        page = await self._context.new_page()
        try:
            logger.info("게시판 접근: %s", board_url)
            await page.goto(board_url, wait_until="domcontentloaded")
            posts = await parse_post_list(page, board_type)
            logger.info("게시물 %d건 수집", len(posts))
            return posts
        finally:
            await page.close()

    # ── 게시물 상세 수집 ─────────────────────────────────────────────────────

    async def fetch_post_detail(self, post_url: str, post_id: str) -> PostDetail:
        """게시물 상세 페이지에서 본문 텍스트와 이미지 URL 목록을 반환한다.

        Args:
            post_url: 게시물 상세 URL
            post_id:  게시물 식별자

        Returns:
            PostDetail (body_text, image_urls 포함)
        """
        assert self._context is not None
        page = await self._context.new_page()
        try:
            logger.info("게시물 상세 접근: %s", post_url)
            await page.goto(post_url, wait_until="domcontentloaded")
            detail = await parse_post_detail(page, post_id)
            logger.info(
                "게시물 상세 수집 완료 (이미지 %d개)", len(detail.image_urls)
            )
            return detail
        finally:
            await page.close()

    # ── 편의 메서드: 카페 전체 게시판 일괄 수집 ────────────────────────────

    async def fetch_all_boards(self) -> list[PostSummary]:
        """Config에 설정된 모든 게시판을 순회하며 게시물 목록을 수집한다."""
        cafe_url = self._config.cafe_url.rstrip("/")
        all_posts: list[PostSummary] = []
        for board in self._config.boards:
            board_url = f"{cafe_url}?iframe_url=/ArticleList.nhn%3Fsearch.clubid=0%26search.menuid={board.id}"
            posts = await self.fetch_post_list(board_url, board.name)
            all_posts.extend(posts)
        return all_posts
