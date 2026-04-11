"""플러그인 파이프라인 모듈.

BoardHandler 프로토콜을 구현하면 새 게시판 유형을 손쉽게 추가할 수 있다.
Pipeline은 게시판 유형에 따라 적절한 핸들러를 선택하여 실행한다.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)


@runtime_checkable
class BoardHandler(Protocol):
    """게시판 핸들러 프로토콜."""

    def handle(self, post_detail: dict[str, Any]) -> None:
        """게시글을 처리한다."""
        ...


class ImageBoardHandler:
    """이미지 게시판 핸들러: 다운로드 → 얼굴 필터 → 카카오 전송."""

    def __init__(
        self,
        image_downloader: Any | None = None,
        face_filter: Any | None = None,
        messenger: Any | None = None,
    ) -> None:
        self._downloader = image_downloader
        self._face_filter = face_filter
        self._messenger = messenger

    def _filter_and_send(self, paths: list[Any]) -> None:
        """얼굴 필터링 후 메신저로 전송하는 공통 로직."""
        if self._face_filter is not None:
            paths = [p for p in paths if self._face_filter.is_match(p)]
        if self._messenger is not None:
            self._messenger.send_images(paths)

    def handle(self, post_detail: dict[str, Any]) -> None:
        """이미지 게시글을 처리한다 (sync wrapper)."""
        image_urls: list[str] = post_detail.get("image_urls", [])
        post_id: str = post_detail.get("post_id", "unknown")
        logger.info("이미지 게시판 처리 시작: %d장", len(image_urls))

        if self._downloader is not None:
            paths = asyncio.get_event_loop().run_until_complete(
                self._downloader.download_all(post_id=post_id, image_urls=image_urls)
            )
        else:
            paths = image_urls

        self._filter_and_send(paths)
        logger.info("이미지 게시판 처리 완료")

    async def handle_async(self, post_detail: dict[str, Any]) -> None:
        """이미지 게시글을 처리한다 (async)."""
        image_urls: list[str] = post_detail.get("image_urls", [])
        post_id: str = post_detail.get("post_id", "unknown")
        logger.info("이미지 게시판 처리 시작: %d장", len(image_urls))

        if self._downloader is not None:
            paths = await self._downloader.download_all(
                post_id=post_id, image_urls=image_urls
            )
        else:
            paths = image_urls

        self._filter_and_send(paths)
        logger.info("이미지 게시판 처리 완료")


class NoticeBoardHandler:
    """공지 게시판 핸들러: 텍스트 추출 → AI 요약 → 카카오 전송."""

    def __init__(
        self,
        summarizer: Any | None = None,
        messenger: Any | None = None,
    ) -> None:
        self._summarizer = summarizer
        self._messenger = messenger

    def handle(self, post_detail: dict[str, Any]) -> None:
        """공지 게시글을 처리한다."""
        title: str = post_detail.get("title", "")
        content: str = post_detail.get("content", "")
        logger.info("공지 게시판 처리 시작: %s", title)

        if self._summarizer is not None:
            summary = self._summarizer.summarize(content)
        else:
            summary = content

        if self._messenger is not None:
            self._messenger.send_notice_summary(title=title, summary=summary)

        logger.info("공지 게시판 처리 완료: %s", title)


class Pipeline:
    """게시판 유형에 따라 핸들러를 선택·실행하는 파이프라인."""

    def __init__(self) -> None:
        self._handlers: dict[str, BoardHandler] = {}
        self._default_handler: BoardHandler | None = None

    def register(self, board_type: str, handler: BoardHandler) -> None:
        """게시판 유형에 핸들러를 등록한다."""
        self._handlers[board_type] = handler
        logger.debug("핸들러 등록: %s → %s", board_type, type(handler).__name__)

    def set_default(self, handler: BoardHandler) -> None:
        """등록되지 않은 유형에 사용할 기본 핸들러를 설정한다."""
        self._default_handler = handler

    def process(self, board_type: str, post_detail: dict[str, Any]) -> None:
        """게시글을 적절한 핸들러로 처리한다.

        Raises:
            ValueError: 등록된 핸들러가 없고 기본 핸들러도 없을 때
        """
        handler = self._handlers.get(board_type) or self._default_handler
        if handler is None:
            raise ValueError(f"핸들러 없음: {board_type!r}")
        logger.info("파이프라인 실행: board_type=%s", board_type)
        handler.handle(post_detail)

    async def process_async(self, board_type: str, post_detail: dict[str, Any]) -> None:
        """게시글을 async 핸들러로 처리한다.

        핸들러에 handle_async가 있으면 사용하고, 없으면 handle()을 호출한다.
        """
        handler = self._handlers.get(board_type) or self._default_handler
        if handler is None:
            raise ValueError(f"핸들러 없음: {board_type!r}")
        logger.info("파이프라인 실행(async): board_type=%s", board_type)
        if hasattr(handler, "handle_async"):
            await handler.handle_async(post_detail)
        else:
            handler.handle(post_detail)


def create_pipeline(config: "Config") -> Pipeline:
    """Config로부터 실제 모듈을 주입하여 Pipeline을 구성하는 팩토리 함수."""
    from src.crawler.image_downloader import ImageDownloader
    from src.face.filter import FaceFilter
    from src.messaging.kakao import KakaoMessenger
    from src.notice.summarizer import Summarizer

    messenger = KakaoMessenger.from_config(config)
    downloader = ImageDownloader()
    face_filter = FaceFilter.from_config(config)
    summarizer = Summarizer.from_config(config)

    pipeline = Pipeline()
    pipeline.register(
        "image",
        ImageBoardHandler(
            image_downloader=downloader,
            face_filter=face_filter,
            messenger=messenger,
        ),
    )
    pipeline.register(
        "notice",
        NoticeBoardHandler(summarizer=summarizer, messenger=messenger),
    )
    return pipeline
