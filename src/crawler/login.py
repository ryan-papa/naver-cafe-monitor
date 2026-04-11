"""수동 로그인 CLI. 브라우저를 열어 네이버 로그인 후 쿠키를 저장한다.

사용법: python -m src.crawler.login
"""
import asyncio

from playwright.async_api import async_playwright

from src.crawler.session import manual_login


async def main() -> None:
    async with async_playwright() as p:
        await manual_login(p)


if __name__ == "__main__":
    asyncio.run(main())
