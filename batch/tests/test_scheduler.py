"""T-11(스케줄러) + T-12(재시도·로그) + T-13(플러그인 구조) 테스트."""
from __future__ import annotations

import logging
import time
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from src.scheduler.pipeline import (
    BoardHandler,
    ImageBoardHandler,
    NoticeBoardHandler,
    Pipeline,
)
from src.scheduler.poller import Poller
from src.scheduler.retry import make_retry_decorator, with_retry


# ── 픽스처 ────────────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_scheduler() -> MagicMock:
    """APScheduler BackgroundScheduler mock."""
    return MagicMock()


@pytest.fixture()
def boards() -> list[dict[str, Any]]:
    return [
        {"id": 1, "name": "자유게시판", "type": "notice"},
        {"id": 2, "name": "사진게시판", "type": "image"},
    ]


@pytest.fixture()
def poll_func() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def poller(boards: list[dict[str, Any]], poll_func: MagicMock, mock_scheduler: MagicMock) -> Poller:
    return Poller(
        boards=boards,
        poll_func=poll_func,
        interval_minutes=5,
        scheduler=mock_scheduler,
    )


# ── Poller: start / stop / toggle 테스트 ─────────────────────────────────────

class TestPollerToggle:
    """폴링 ON/OFF 토글 테스트."""

    def test_start_sets_running(self, poller: Poller) -> None:
        """start() 호출 후 is_running이 True여야 한다."""
        poller.start()
        assert poller.is_running is True

    def test_stop_clears_running(self, poller: Poller) -> None:
        """stop() 호출 후 is_running이 False여야 한다."""
        poller.start()
        poller.stop()
        assert poller.is_running is False

    def test_toggle_starts_when_stopped(self, poller: Poller) -> None:
        """중지 상태에서 toggle()하면 True(실행 중)를 반환해야 한다."""
        result = poller.toggle()
        assert result is True
        assert poller.is_running is True

    def test_toggle_stops_when_running(self, poller: Poller) -> None:
        """실행 중에 toggle()하면 False(중지)를 반환해야 한다."""
        poller.start()
        result = poller.toggle()
        assert result is False
        assert poller.is_running is False

    def test_toggle_twice_returns_to_original_state(self, poller: Poller) -> None:
        """두 번 toggle()하면 원래 상태로 복귀해야 한다."""
        poller.toggle()  # 시작
        poller.toggle()  # 중지
        assert poller.is_running is False

    def test_start_idempotent(self, poller: Poller, mock_scheduler: MagicMock) -> None:
        """이미 실행 중일 때 start()를 다시 호출해도 중복 실행되지 않아야 한다."""
        poller.start()
        poller.start()
        # scheduler.start()는 한 번만 호출되어야 함
        mock_scheduler.start.assert_called_once()

    def test_stop_idempotent(self, poller: Poller, mock_scheduler: MagicMock) -> None:
        """실행 중이 아닐 때 stop()을 호출해도 오류가 없어야 한다."""
        poller.stop()  # 시작 전에 stop 호출
        mock_scheduler.shutdown.assert_not_called()

    def test_scheduler_add_job_on_start(
        self, poller: Poller, mock_scheduler: MagicMock
    ) -> None:
        """start() 시 APScheduler에 job이 추가되어야 한다."""
        poller.start()
        mock_scheduler.add_job.assert_called_once()

    def test_from_config(self, mock_scheduler: MagicMock) -> None:
        """from_config() 팩토리가 Config에서 올바르게 Poller를 생성해야 한다."""
        mock_config = MagicMock(spec=["poll_interval", "boards", "timezone"])
        mock_config.poll_interval = 300
        mock_config.boards = [{"id": 1}]
        mock_config.timezone = "Asia/Seoul"

        def dummy_poll(board: Any) -> None:
            pass

        p = Poller.from_config(mock_config, dummy_poll, scheduler=mock_scheduler)
        assert isinstance(p, Poller)
        assert p._interval_minutes == 5


# ── Poller: _poll_once 테스트 ─────────────────────────────────────────────────

class TestPollOnce:
    """_poll_once() 메서드 테스트."""

    def test_poll_func_called_for_each_board(
        self, poller: Poller, poll_func: MagicMock, boards: list[dict[str, Any]]
    ) -> None:
        """_poll_once() 실행 시 각 게시판마다 poll_func가 호출되어야 한다."""
        poller._poll_once()
        assert poll_func.call_count == len(boards)

    def test_poll_continues_on_board_error(
        self, poller: Poller, poll_func: MagicMock, boards: list[dict[str, Any]]
    ) -> None:
        """한 게시판 폴링 실패 시 나머지 게시판은 계속 처리되어야 한다."""
        poll_func.side_effect = [Exception("크롤링 실패"), None]
        poller._poll_once()
        assert poll_func.call_count == 2

    def test_poll_warns_when_exceeds_interval(
        self,
        boards: list[dict[str, Any]],
        mock_scheduler: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """폴링 시간이 주기를 초과하면 경고 로그가 남아야 한다."""
        def slow_poll(board: dict[str, Any]) -> None:
            pass  # 실제 sleep 대신 monotonic 패치

        poller = Poller(
            boards=boards,
            poll_func=slow_poll,
            interval_minutes=1,
            scheduler=mock_scheduler,
        )

        # time.monotonic을 패치해 경과시간이 주기(60초)보다 크게 만들기
        start_time = 0.0
        call_count = 0

        def fake_monotonic() -> float:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return start_time
            return start_time + 120.0  # 2분 경과 시뮬레이션

        with patch("src.scheduler.poller.time.monotonic", side_effect=fake_monotonic):
            with caplog.at_level(logging.WARNING, logger="src.scheduler.poller"):
                poller._poll_once()

        assert "초과" in caplog.text


# ── 재시도 로직 테스트 ─────────────────────────────────────────────────────────

class TestWithRetry:
    """with_retry() 함수 테스트."""

    def test_succeeds_on_first_try(self) -> None:
        """첫 시도에 성공하면 재시도 없이 반환해야 한다."""
        mock_func = MagicMock(return_value=42)
        result = with_retry(mock_func, max_retries=3, delay=0)
        assert result == 42
        mock_func.assert_called_once()

    def test_retries_until_success(self) -> None:
        """N번 실패 후 성공하면 결과를 반환해야 한다."""
        mock_func = MagicMock(side_effect=[Exception("실패"), Exception("실패"), "성공"])
        result = with_retry(mock_func, max_retries=3, delay=0)
        assert result == "성공"
        assert mock_func.call_count == 3

    def test_raises_after_max_retries(self) -> None:
        """max_retries 초과 시 마지막 예외를 raise해야 한다."""
        exc = RuntimeError("최종 실패")
        mock_func = MagicMock(side_effect=exc)
        with pytest.raises(RuntimeError, match="최종 실패"):
            with_retry(mock_func, max_retries=2, delay=0)
        assert mock_func.call_count == 3  # 1 + 2 재시도

    def test_total_attempts_equals_max_retries_plus_one(self) -> None:
        """총 시도 횟수는 max_retries + 1이어야 한다."""
        mock_func = MagicMock(side_effect=Exception("실패"))
        with pytest.raises(Exception):
            with_retry(mock_func, max_retries=4, delay=0)
        assert mock_func.call_count == 5

    def test_logs_warning_on_retry(self, caplog: pytest.LogCaptureFixture) -> None:
        """재시도 시 경고 로그가 남아야 한다."""
        mock_func = MagicMock(side_effect=[Exception("오류"), "ok"])
        with caplog.at_level(logging.WARNING, logger="src.scheduler.retry"):
            with_retry(mock_func, max_retries=2, delay=0)
        assert "재시도" in caplog.text

    def test_logs_error_on_final_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """최종 실패 시 에러 로그가 남아야 한다."""
        mock_func = MagicMock(side_effect=Exception("최종 오류"))
        with caplog.at_level(logging.ERROR, logger="src.scheduler.retry"):
            with pytest.raises(Exception):
                with_retry(mock_func, max_retries=1, delay=0)
        assert "최종 실패" in caplog.text


# ── 지수 백오프 테스트 ─────────────────────────────────────────────────────────

class TestExponentialBackoff:
    """지수 백오프 테스트."""

    def test_exponential_backoff_increases_wait(self) -> None:
        """지수 백오프 사용 시 대기 시간이 증가해야 한다."""
        sleep_calls: list[float] = []

        def fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)

        mock_func = MagicMock(side_effect=[Exception(), Exception(), Exception(), "ok"])

        with patch("src.scheduler.retry.time.sleep", side_effect=fake_sleep):
            with_retry(mock_func, max_retries=3, delay=1.0, exponential_backoff=True)

        # 대기시간: 1 * 2^0 = 1, 1 * 2^1 = 2, 1 * 2^2 = 4
        assert sleep_calls == [1.0, 2.0, 4.0]

    def test_linear_delay_without_backoff(self) -> None:
        """지수 백오프 미사용 시 대기 시간이 일정해야 한다."""
        sleep_calls: list[float] = []

        def fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)

        mock_func = MagicMock(side_effect=[Exception(), Exception(), "ok"])

        with patch("src.scheduler.retry.time.sleep", side_effect=fake_sleep):
            with_retry(mock_func, max_retries=2, delay=3.0, exponential_backoff=False)

        assert sleep_calls == [3.0, 3.0]

    def test_decorator_with_exponential_backoff(self) -> None:
        """데코레이터 방식에서도 지수 백오프가 적용되어야 한다."""
        sleep_calls: list[float] = []
        call_count = 0

        def fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)

        retry = make_retry_decorator(max_retries=2, delay=2.0, exponential_backoff=True)

        @retry
        def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("실패")
            return "성공"

        with patch("src.scheduler.retry.time.sleep", side_effect=fake_sleep):
            result = flaky()

        assert result == "성공"
        assert sleep_calls == [2.0, 4.0]


# ── 핸들러 라우팅 테스트 ──────────────────────────────────────────────────────

class TestPipelineRouting:
    """Pipeline 핸들러 라우팅 테스트."""

    def test_routes_to_correct_handler(self) -> None:
        """board_type에 맞는 핸들러가 선택되어야 한다."""
        image_handler = MagicMock(spec=BoardHandler)
        notice_handler = MagicMock(spec=BoardHandler)

        pipeline = Pipeline()
        pipeline.register("image", image_handler)
        pipeline.register("notice", notice_handler)

        post = {"title": "공지", "content": "내용"}
        pipeline.process("notice", post)

        notice_handler.handle.assert_called_once_with(post)
        image_handler.handle.assert_not_called()

    def test_image_board_routes_correctly(self) -> None:
        """'image' 유형은 ImageBoardHandler로 라우팅되어야 한다."""
        handler = MagicMock()
        pipeline = Pipeline()
        pipeline.register("image", handler)

        post = {"image_urls": ["http://example.com/img.jpg"]}
        pipeline.process("image", post)

        handler.handle.assert_called_once_with(post)

    def test_notice_board_routes_correctly(self) -> None:
        """'notice' 유형은 NoticeBoardHandler로 라우팅되어야 한다."""
        handler = MagicMock()
        pipeline = Pipeline()
        pipeline.register("notice", handler)

        post = {"title": "공지", "content": "내용"}
        pipeline.process("notice", post)

        handler.handle.assert_called_once_with(post)

    def test_unknown_type_raises_without_default(self) -> None:
        """등록되지 않은 유형이고 기본 핸들러도 없으면 ValueError가 발생해야 한다."""
        pipeline = Pipeline()
        with pytest.raises(ValueError, match="핸들러 없음"):
            pipeline.process("unknown", {})

    def test_default_handler_used_for_unknown_type(self) -> None:
        """등록되지 않은 유형에는 기본 핸들러가 사용되어야 한다."""
        default_handler = MagicMock()
        pipeline = Pipeline()
        pipeline.set_default(default_handler)

        post = {"title": "기타"}
        pipeline.process("whatever", post)
        default_handler.handle.assert_called_once_with(post)

    def test_board_handler_protocol_satisfied(self) -> None:
        """BoardHandler 프로토콜을 구현하면 isinstance 체크를 통과해야 한다."""

        class MyHandler:
            def handle(self, post_detail: dict[str, Any]) -> None:
                pass

        assert isinstance(MyHandler(), BoardHandler)

    def test_image_board_handler_calls_messenger(self) -> None:
        """ImageBoardHandler가 messenger.send_images를 호출해야 한다."""
        mock_messenger = MagicMock()
        handler = ImageBoardHandler(messenger=mock_messenger)

        post = {"image_urls": ["url1", "url2"]}
        handler.handle(post)

        mock_messenger.send_images.assert_called_once()

    def test_notice_board_handler_calls_messenger(self) -> None:
        """NoticeBoardHandler가 messenger.send_notice_summary를 호출해야 한다."""
        mock_messenger = MagicMock()
        handler = NoticeBoardHandler(messenger=mock_messenger)

        post = {"title": "이벤트 안내", "content": "내용입니다"}
        handler.handle(post)

        mock_messenger.send_notice_summary.assert_called_once_with(
            title="이벤트 안내", summary="내용입니다"
        )

    def test_notice_board_handler_with_summarizer(self) -> None:
        """NoticeBoardHandler가 summarizer를 거쳐 요약을 전달해야 한다."""
        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = "AI 요약본"
        mock_messenger = MagicMock()
        handler = NoticeBoardHandler(summarizer=mock_summarizer, messenger=mock_messenger)

        post = {"title": "공지", "content": "긴 원문 내용"}
        handler.handle(post)

        mock_summarizer.summarize.assert_called_once_with("긴 원문 내용")
        mock_messenger.send_notice_summary.assert_called_once_with(
            title="공지", summary="AI 요약본"
        )

    def test_notice_board_handler_sends_images(self) -> None:
        """NoticeBoardHandler가 이미지를 얼굴 필터 없이 전송해야 한다."""
        mock_messenger = MagicMock()
        handler = NoticeBoardHandler(messenger=mock_messenger)

        post = {
            "title": "일정표",
            "content": "4월 일정",
            "image_urls": ["url1.jpg", "url2.jpg"],
            "post_id": "99",
        }
        handler.handle(post)

        mock_messenger.send_notice_summary.assert_called_once()
        mock_messenger.send_images.assert_called_once_with(
            ["url1.jpg", "url2.jpg"], caption="[공지] 일정표"
        )

    def test_notice_board_handler_no_images_no_send(self) -> None:
        """이미지가 없으면 send_images를 호출하지 않아야 한다."""
        mock_messenger = MagicMock()
        handler = NoticeBoardHandler(messenger=mock_messenger)

        post = {"title": "공지", "content": "텍스트만"}
        handler.handle(post)

        mock_messenger.send_notice_summary.assert_called_once()
        mock_messenger.send_images.assert_not_called()
