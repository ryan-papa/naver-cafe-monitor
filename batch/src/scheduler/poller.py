"""APScheduler 기반 폴링 스케줄러 모듈.

Poller 클래스는 설정된 주기마다 카페 게시판을 순차 폴링한다.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Union

from apscheduler.schedulers.background import BackgroundScheduler

if TYPE_CHECKING:
    from src.config import BoardConfig, Config

logger = logging.getLogger(__name__)

# 폴링 주기 기본값 (분)
_DEFAULT_POLL_INTERVAL_MINUTES = 5

# poll_func이 받을 수 있는 게시판 타입 (BoardConfig 또는 dict)
BoardItem = Union["BoardConfig", dict[str, Any]]


class Poller:
    """카페 게시판 폴링 스케줄러.

    APScheduler BackgroundScheduler를 래핑하여 주기적 폴링을 관리한다.
    """

    def __init__(
        self,
        boards: list[Any],
        poll_func: Callable[[Any], None],
        interval_minutes: int = _DEFAULT_POLL_INTERVAL_MINUTES,
        timezone: str = "Asia/Seoul",
        scheduler: BackgroundScheduler | None = None,
    ) -> None:
        """초기화.

        Args:
            boards: 폴링할 게시판 설정 목록 (BoardConfig 또는 dict)
            poll_func: 게시판 1개를 처리하는 함수
            interval_minutes: 폴링 주기(분)
            timezone: 스케줄러 타임존
            scheduler: 외부 주입용 스케줄러 (테스트용)
        """
        self._boards = boards
        self._poll_func = poll_func
        self._interval_minutes = interval_minutes
        self._running = False
        self._scheduler = scheduler or BackgroundScheduler(timezone=timezone)

    @classmethod
    def from_config(
        cls,
        config: "Config",
        poll_func: Callable[[Any], None],
        scheduler: BackgroundScheduler | None = None,
    ) -> "Poller":
        """Config 인스턴스에서 Poller를 생성한다.

        Args:
            config: 애플리케이션 설정
            poll_func: 게시판 1개를 처리하는 함수 (BoardConfig 수신)
            scheduler: 외부 주입용 스케줄러 (테스트용)

        Returns:
            Poller 인스턴스
        """
        # Config.poll_interval은 초 단위이므로 분으로 변환
        interval_seconds = getattr(config, "poll_interval", None)
        if interval_seconds is not None:
            interval_minutes = max(1, interval_seconds // 60)
        else:
            interval_minutes = _DEFAULT_POLL_INTERVAL_MINUTES

        boards = list(getattr(config, "boards", []))
        timezone = getattr(config, "timezone", "Asia/Seoul")

        return cls(
            boards=boards,
            poll_func=poll_func,
            interval_minutes=interval_minutes,
            timezone=timezone,
            scheduler=scheduler,
        )

    def start(self) -> None:
        """폴링을 시작한다.

        이미 실행 중이면 아무 동작도 하지 않는다.
        """
        if self._running:
            logger.warning("Poller가 이미 실행 중입니다.")
            return

        self._scheduler.add_job(
            self._poll_once,
            trigger="interval",
            minutes=self._interval_minutes,
            id="poll_job",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("Poller 시작: %d분 간격", self._interval_minutes)

    def stop(self) -> None:
        """폴링을 중지한다.

        실행 중이 아니면 아무 동작도 하지 않는다.
        """
        if not self._running:
            logger.warning("Poller가 실행 중이 아닙니다.")
            return

        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Poller 중지")

    def toggle(self) -> bool:
        """폴링을 토글한다.

        Returns:
            토글 후 실행 상태 (True: 실행 중, False: 중지)
        """
        if self._running:
            self.stop()
        else:
            self.start()
        return self._running

    @property
    def is_running(self) -> bool:
        """현재 폴링 실행 여부."""
        return self._running

    def _poll_once(self) -> None:
        """게시판을 순차적으로 폴링한다.

        폴링 실행 시간이 주기를 초과하면 경고 로그를 남긴다.
        """
        started_at = time.monotonic()
        logger.info("폴링 시작: %d개 게시판", len(self._boards))

        for board in self._boards:
            try:
                self._poll_func(board)
            except Exception as exc:
                board_id = getattr(board, "id", None) or (
                    board.get("id", "unknown") if isinstance(board, dict) else "unknown"
                )
                logger.error("게시판 폴링 실패 (id=%s): %s", board_id, exc)

        elapsed = time.monotonic() - started_at
        limit = self._interval_minutes * 60

        if elapsed > limit:
            logger.warning(
                "폴링 실행 시간(%.1f초)이 주기(%d초)를 초과했습니다.",
                elapsed,
                limit,
            )
        else:
            logger.info("폴링 완료: %.1f초 소요", elapsed)
