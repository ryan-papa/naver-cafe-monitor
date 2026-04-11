"""네이버 카페 모니터 엔트리포인트.

``python -m src`` 로 실행한다.

Config 로딩 → Crawler 생성 → PostTracker → Pipeline(핸들러 등록)
→ Poller → 폴링 시작 순서로 초기화한다.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from src.config import BoardConfig, load_config
from src.crawler.naver_cafe import NaverCafeCrawler
from src.crawler.post_tracker import PostTracker
from src.scheduler.pipeline import Pipeline, create_pipeline
from src.scheduler.poller import Poller

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def _poll_board(
    board: BoardConfig,
    crawler: NaverCafeCrawler,
    tracker: PostTracker,
    pipeline: Pipeline,
    cafe_url: str,
) -> None:
    """게시판 1개를 폴링하고 새 게시물을 파이프라인으로 처리한다."""
    board_url = (
        f"{cafe_url.rstrip('/')}?iframe_url=/ArticleList.nhn"
        f"%3Fsearch.clubid=0%26search.menuid={board.id}"
    )
    board_type = "image" if board.face_check else "notice"

    posts = await crawler.fetch_post_list(board_url, board.name)
    new_posts = tracker.get_new_posts(str(board.id), posts)

    for post in new_posts:
        detail = await crawler.fetch_post_detail(post.url, post.post_id)
        post_detail: dict[str, Any] = {
            "post_id": detail.post_id,
            "title": detail.title,
            "content": detail.body_text,
            "image_urls": detail.image_urls,
            "url": detail.url,
        }
        await pipeline.process_async(board_type, post_detail)


async def main() -> None:
    """메인 비동기 루프."""
    config = load_config()
    tracker = PostTracker()
    pipeline = create_pipeline(config)

    async with NaverCafeCrawler(config) as crawler:

        def poll_sync(board: Any) -> None:
            """Poller(APScheduler)에서 호출할 sync 콜백."""
            asyncio.get_event_loop().run_until_complete(
                _poll_board(board, crawler, tracker, pipeline, config.cafe_url)
            )

        poller = Poller.from_config(config, poll_func=poll_sync)
        poller.start()

        logger.info("네이버 카페 모니터 시작 (Ctrl+C로 종료)")

        stop_event = asyncio.Event()

        def _signal_handler(*_: object) -> None:
            logger.info("종료 시그널 수신")
            stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        await stop_event.wait()
        poller.stop()
        logger.info("네이버 카페 모니터 종료")


if __name__ == "__main__":
    asyncio.run(main())
