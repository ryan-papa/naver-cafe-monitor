"""네이버 로그인 세션 관리 모듈.

쿠키 저장 / 복원 및 Playwright 브라우저 컨텍스트 생성을 담당한다.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)

_NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
_NAVER_BASE_URL = "https://www.naver.com"
_DEFAULT_COOKIE_PATH = Path("data/cookies.json")


async def build_context(playwright: "Playwright", headless: bool = True) -> "BrowserContext":
    """Chromium 브라우저 컨텍스트를 생성한다."""
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="ko-KR",
        timezone_id="Asia/Seoul",
    )
    return context


async def save_cookies(context: "BrowserContext", path: Path = _DEFAULT_COOKIE_PATH) -> None:
    """현재 컨텍스트의 쿠키를 JSON 파일로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cookies = await context.cookies()
    path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("쿠키 저장 완료: %s (%d개)", path, len(cookies))


async def restore_cookies(context: "BrowserContext", path: Path = _DEFAULT_COOKIE_PATH) -> bool:
    """저장된 쿠키를 컨텍스트에 복원한다. 성공 시 True, 파일 없으면 False."""
    if not path.exists():
        logger.debug("쿠키 파일 없음: %s", path)
        return False
    cookies = json.loads(path.read_text(encoding="utf-8"))
    await context.add_cookies(cookies)
    logger.info("쿠키 복원 완료: %s (%d개)", path, len(cookies))
    return True


async def login(page: "Page", naver_id: str, naver_pw: str) -> None:
    """네이버 ID/PW로 로그인한다. OTP 없는 기본 로그인을 가정한다."""
    logger.info("네이버 로그인 시도: %s", naver_id)
    await page.goto(_NAVER_LOGIN_URL, wait_until="domcontentloaded")

    # JavaScript로 입력 필드에 값을 주입 (봇 탐지 우회)
    await page.evaluate(
        """([id, pw]) => {
            document.querySelector('#id').value = id;
            document.querySelector('#pw').value = pw;
        }""",
        [naver_id, naver_pw],
    )
    await page.click("input[type=submit]")
    await page.wait_for_load_state("domcontentloaded")
    logger.info("네이버 로그인 완료")


async def is_logged_in(page: "Page") -> bool:
    """현재 페이지 기준으로 로그인 여부를 확인한다."""
    await page.goto(_NAVER_BASE_URL, wait_until="domcontentloaded")
    # 로그인 상태면 네이버 메인에 로그아웃 링크가 존재한다
    return await page.locator("a[href*='nidlogin.logout']").count() > 0
