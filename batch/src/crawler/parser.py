"""네이버 카페 HTML 파싱 유틸리티.

Playwright Page 객체로부터 게시물 목록 및 상세 데이터를 추출한다.
실제 네트워크 호출과 분리되어 단독으로 테스트 가능하다.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

_CAFE_BASE = "https://cafe.naver.com"


@dataclass
class PostSummary:
    """게시물 목록 항목."""

    post_id: str
    title: str
    url: str
    board_type: str
    written_at: datetime | None


@dataclass
class PostDetail:
    """게시물 상세 내용."""

    post_id: str
    title: str
    url: str
    body_text: str
    image_urls: list[str] = field(default_factory=list)


def _parse_written_at(raw: str) -> datetime | None:
    """날짜 문자열을 datetime으로 변환. 파싱 실패 시 None 반환."""
    raw = raw.strip()
    for fmt in ("%Y.%m.%d. %H:%M", "%Y.%m.%d.", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    logger.debug("날짜 파싱 실패: %r", raw)
    return None


def _build_url(href: str) -> str:
    """상대 경로를 절대 URL로 변환한다."""
    if href.startswith("http"):
        return href
    return _CAFE_BASE + href


async def parse_post_list(page: "Page", board_type: str) -> list[PostSummary]:
    """카페 게시판 목록 페이지에서 게시물 요약 목록을 추출한다.

    네이버 카페 PC 게시판의 article 행(tr.item) 구조를 기준으로 파싱한다.
    """
    posts: list[PostSummary] = []

    # iframe 안에 게시판이 있는 경우 처리
    frame = page.frame("cafe_main") or page.main_frame

    rows = await frame.query_selector_all("tr.item, .article-board tbody tr")
    logger.debug("게시물 행 %d개 발견", len(rows))

    for row in rows:
        try:
            # 제목 / 링크
            title_el = await row.query_selector("a.article, td.td-article a")
            if not title_el:
                continue
            title = (await title_el.inner_text()).strip()
            href = await title_el.get_attribute("href") or ""
            if not href:
                continue

            # 게시물 ID — URL 쿼리스트링 또는 경로에서 추출
            m = re.search(r"articleid=(\d+)", href) or re.search(r"/(\d+)(?:\?|$)", href)
            post_id = m.group(1) if m else href

            # 날짜
            date_el = await row.query_selector("td.td-date, span.date")
            raw_date = (await date_el.inner_text()).strip() if date_el else ""
            written_at = _parse_written_at(raw_date) if raw_date else None

            posts.append(
                PostSummary(
                    post_id=post_id,
                    title=title,
                    url=_build_url(href),
                    board_type=board_type,
                    written_at=written_at,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("행 파싱 오류 (스킵): %s", exc)

    return posts


async def parse_post_detail(page: "Page", post_id: str) -> PostDetail:
    """게시물 상세 페이지에서 본문 텍스트와 이미지 URL 목록을 추출한다."""
    frame = page.frame("cafe_main") or page.main_frame

    # 제목
    title_el = await frame.query_selector(".se-title-text, #subject, .tit-view")
    title = (await title_el.inner_text()).strip() if title_el else ""

    # 본문 텍스트
    body_el = await frame.query_selector(".se-main-container, #postContent, .article-viewer")
    body_text = (await body_el.inner_text()).strip() if body_el else ""

    # 이미지 URL — 본문 영역 내 <img> 태그
    image_urls: list[str] = []
    if body_el:
        img_els = await body_el.query_selector_all("img")
        for img in img_els:
            src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
            src = src.strip()
            if src and not src.startswith("data:"):
                image_urls.append(src)

    return PostDetail(
        post_id=post_id,
        title=title,
        url=page.url,
        body_text=body_text,
        image_urls=image_urls,
    )
