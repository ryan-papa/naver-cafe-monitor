"""플러그인 파이프라인 모듈.

BoardHandler 프로토콜을 구현하면 새 게시판 유형을 손쉽게 추가할 수 있다.
Pipeline은 게시판 유형에 따라 적절한 핸들러를 선택하여 실행한다.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class BoardHandler(Protocol):
    """게시판 핸들러 프로토콜.

    새 게시판 유형을 추가하려면 이 프로토콜을 구현하는 클래스를 작성하고
    Pipeline에 등록하면 된다.
    """

    def handle(self, post_detail: dict[str, Any]) -> None:
        """게시글을 처리한다.

        Args:
            post_detail: 게시글 상세 정보 딕셔너리
        """
        ...


class ImageBoardHandler:
    """이미지 게시판 핸들러.

    이미지 다운로드 → 얼굴 필터 → 카카오 전송 순으로 처리한다.
    """

    def __init__(
        self,
        image_downloader: Any | None = None,
        face_filter: Any | None = None,
        messenger: Any | None = None,
    ) -> None:
        self._downloader = image_downloader
        self._face_filter = face_filter
        self._messenger = messenger

    def handle(self, post_detail: dict[str, Any]) -> None:
        """이미지 게시글을 처리한다.

        Args:
            post_detail: 게시글 상세 정보 (image_urls 키 포함)
        """
        image_urls: list[str] = post_detail.get("image_urls", [])
        logger.info("이미지 게시판 처리 시작: %d장", len(image_urls))

        if self._downloader is not None:
            paths = self._downloader.download(image_urls)
        else:
            paths = image_urls

        if self._face_filter is not None:
            paths = self._face_filter.filter(paths)

        if self._messenger is not None:
            self._messenger.send_images(paths)

        logger.info("이미지 게시판 처리 완료")


class NoticeBoardHandler:
    """공지 게시판 핸들러.

    텍스트 추출 → AI 요약 → 카카오 전송 순으로 처리한다.
    """

    def __init__(
        self,
        summarizer: Any | None = None,
        messenger: Any | None = None,
    ) -> None:
        self._summarizer = summarizer
        self._messenger = messenger

    def handle(self, post_detail: dict[str, Any]) -> None:
        """공지 게시글을 처리한다.

        Args:
            post_detail: 게시글 상세 정보 (title, content 키 포함)
        """
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
    """게시판 유형에 따라 핸들러를 선택·실행하는 파이프라인.

    새 핸들러는 register()로 등록한다.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, BoardHandler] = {}
        self._default_handler: BoardHandler | None = None

    def register(self, board_type: str, handler: BoardHandler) -> None:
        """게시판 유형에 핸들러를 등록한다.

        Args:
            board_type: 게시판 유형 식별자 (예: "image", "notice")
            handler: BoardHandler 프로토콜 구현체
        """
        self._handlers[board_type] = handler
        logger.debug("핸들러 등록: %s → %s", board_type, type(handler).__name__)

    def set_default(self, handler: BoardHandler) -> None:
        """등록되지 않은 유형에 사용할 기본 핸들러를 설정한다.

        Args:
            handler: 기본 핸들러
        """
        self._default_handler = handler

    def process(self, board_type: str, post_detail: dict[str, Any]) -> None:
        """게시글을 적절한 핸들러로 처리한다.

        Args:
            board_type: 게시판 유형 식별자
            post_detail: 게시글 상세 정보

        Raises:
            ValueError: 등록된 핸들러가 없고 기본 핸들러도 없을 때
        """
        handler = self._handlers.get(board_type) or self._default_handler
        if handler is None:
            raise ValueError(f"핸들러 없음: {board_type!r}")
        logger.info("파이프라인 실행: board_type=%s", board_type)
        handler.handle(post_detail)
