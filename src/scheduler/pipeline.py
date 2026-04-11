"""플러그인 파이프라인 모듈."""
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
    """공지 게시판 핸들러: 텍스트 요약 + 이미지 전송 (얼굴 필터 없음)."""

    def __init__(
        self,
        summarizer: Any | None = None,
        messenger: Any | None = None,
        image_downloader: Any | None = None,
    ) -> None:
        self._summarizer = summarizer
        self._messenger = messenger
        self._downloader = image_downloader

    def _resolve_images(self, post_detail: dict[str, Any]) -> tuple[list[str], str, str]:
        """이미지 URL, post_id, title을 추출한다."""
        return (
            post_detail.get("image_urls", []),
            post_detail.get("post_id", "unknown"),
            post_detail.get("title", ""),
        )

    def _send_images(self, post_detail: dict[str, Any]) -> None:
        image_urls, post_id, title = self._resolve_images(post_detail)
        if not image_urls or self._messenger is None:
            return
        if self._downloader is not None:
            paths = asyncio.get_event_loop().run_until_complete(
                self._downloader.download_all(post_id=post_id, image_urls=image_urls)
            )
        else:
            paths = image_urls
        self._messenger.send_images(paths, caption=f"[공지] {title}")

    async def _send_images_async(self, post_detail: dict[str, Any]) -> None:
        image_urls, post_id, title = self._resolve_images(post_detail)
        if not image_urls or self._messenger is None:
            return
        if self._downloader is not None:
            paths = await self._downloader.download_all(
                post_id=post_id, image_urls=image_urls
            )
        else:
            paths = image_urls
        self._messenger.send_images(paths, caption=f"[공지] {title}")

    def handle(self, post_detail: dict[str, Any]) -> None:
        """공지 게시글을 처리한다."""
        title, content = post_detail.get("title", ""), post_detail.get("content", "")
        logger.info("공지 게시판 처리 시작: %s", title)
        summary = self._summarizer.summarize(content) if self._summarizer else content
        if self._messenger is not None:
            self._messenger.send_notice_summary(title=title, summary=summary)
        self._send_images(post_detail)
        logger.info("공지 게시판 처리 완료: %s", title)

    async def handle_async(self, post_detail: dict[str, Any]) -> None:
        """공지 게시글을 비동기 처리한다."""
        title, content = post_detail.get("title", ""), post_detail.get("content", "")
        logger.info("공지 게시판 처리 시작(async): %s", title)
        summary = self._summarizer.summarize(content) if self._summarizer else content
        if self._messenger is not None:
            self._messenger.send_notice_summary(title=title, summary=summary)
        await self._send_images_async(post_detail)
        logger.info("공지 게시판 처리 완료(async): %s", title)


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
        """게시글을 적절한 핸들러로 처리한다."""
        handler = self._handlers.get(board_type) or self._default_handler
        if handler is None:
            raise ValueError(f"핸들러 없음: {board_type!r}")
        logger.info("파이프라인 실행: board_type=%s", board_type)
        handler.handle(post_detail)

    async def process_async(self, board_type: str, post_detail: dict[str, Any]) -> None:
        """게시글을 async 핸들러로 처리한다."""
        handler = self._handlers.get(board_type) or self._default_handler
        if handler is None:
            raise ValueError(f"핸들러 없음: {board_type!r}")
        logger.info("파이프라인 실행(async): board_type=%s", board_type)
        if hasattr(handler, "handle_async"):
            await handler.handle_async(post_detail)
        else:
            handler.handle(post_detail)


def create_pipeline(config: "Config") -> Pipeline:
    """Config로부터 실제 모듈을 주입하여 Pipeline을 구성한다."""
    from src.crawler.image_downloader import ImageDownloader
    from src.face.filter import FaceFilter
    from src.messaging.kakao import KakaoMessenger
    from src.notice.summarizer import Summarizer

    messenger = KakaoMessenger.from_config(config)
    dl = ImageDownloader()
    pipeline = Pipeline()
    pipeline.register("image", ImageBoardHandler(
        image_downloader=dl, face_filter=FaceFilter.from_config(config), messenger=messenger,
    ))
    pipeline.register("notice", NoticeBoardHandler(
        summarizer=Summarizer.from_config(config), messenger=messenger, image_downloader=dl,
    ))
    return pipeline
