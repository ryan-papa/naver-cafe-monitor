"""네이버 로그인 세션 관리 모듈.

쿠키 저장 / 복원 및 Playwright 브라우저 컨텍스트 생성을 담당한다.
최초 로그인은 수동(headless=False)으로 진행 → 쿠키 저장 → 이후 쿠키 복원.
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
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_COOKIE_PATH = _REPO_ROOT / "data" / "cookies.json"


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


async def manual_login(playwright: "Playwright", cookie_path: Path = _DEFAULT_COOKIE_PATH) -> None:
    """브라우저를 열어 수동 로그인 후 쿠키를 저장한다.

    headless=False로 브라우저를 띄워 사용자가 직접 로그인(2차 인증 포함).
    로그인 완료 후 쿠키를 저장하고 브라우저를 닫는다.
    """
    context = await build_context(playwright, headless=False)
    page = await context.new_page()

    await page.goto(_NAVER_LOGIN_URL, wait_until="domcontentloaded")
    logger.info("브라우저가 열렸습니다. 네이버 로그인을 완료해주세요.")
    print("\n" + "=" * 50)
    print("브라우저에서 네이버 로그인을 완료해주세요.")
    print("(2차 인증 포함)")
    print("로그인 완료 후 여기로 돌아와 Enter를 누르세요.")
    print("=" * 50)

    # 네이버 메인으로 이동할 때까지 대기 (로그인 성공 시 리다이렉트)
    try:
        await page.wait_for_url("**/www.naver.com/**", timeout=300_000)
        logger.info("로그인 감지됨 (자동)")
    except Exception:
        # 자동 감지 실패 시 수동 대기
        input("\n로그인 완료 후 Enter를 누르세요...")

    await save_cookies(context, cookie_path)
    await context.close()
    print("쿠키 저장 완료. 이후 자동 로그인됩니다.")


async def is_logged_in(page: "Page", cafe_url: str = "https://cafe.naver.com") -> bool:
    """카페 접근 가능 여부로 로그인 상태를 확인한다."""
    await page.goto(cafe_url, wait_until="domcontentloaded")
    # 로그인 안 된 상태면 로그인 페이지로 리다이렉트됨
    return "nidlogin" not in page.url
