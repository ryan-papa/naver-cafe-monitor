"""재시도 유틸리티 모듈.

실패한 함수 호출을 지수 백오프와 함께 재시도하는 유틸리티를 제공한다.
OI-06 기본값: 3회 재시도, 5초 대기.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_DELAY = 5.0

F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    func: Callable[..., Any],
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    delay: float = _DEFAULT_DELAY,
    exponential_backoff: bool = False,
) -> Any:
    """함수를 실패 시 재시도하며 실행한다.

    Args:
        func: 실행할 함수 (인자 없는 callable)
        max_retries: 최대 재시도 횟수 (기본: 3)
        delay: 재시도 간 대기 시간(초) (기본: 5)
        exponential_backoff: 지수 백오프 사용 여부

    Returns:
        func()의 반환값

    Raises:
        Exception: max_retries 초과 후 마지막 예외
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = delay * (2**attempt) if exponential_backoff else delay
                logger.warning(
                    "재시도 %d/%d 실패: %s — %.1f초 후 재시도",
                    attempt + 1,
                    max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "최종 실패 (총 %d회 시도): %s",
                    max_retries + 1,
                    exc,
                )

    raise last_exc  # type: ignore[misc]


def make_retry_decorator(
    max_retries: int = _DEFAULT_MAX_RETRIES,
    delay: float = _DEFAULT_DELAY,
    exponential_backoff: bool = False,
) -> Callable[[F], F]:
    """재시도 데코레이터 팩토리.

    Args:
        max_retries: 최대 재시도 횟수
        delay: 재시도 간 대기 시간(초)
        exponential_backoff: 지수 백오프 사용 여부

    Returns:
        데코레이터 함수
    """
    import functools

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return with_retry(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                delay=delay,
                exponential_backoff=exponential_backoff,
            )

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_from_config(config: "Config") -> Callable[[F], F]:
    """Config 기반 재시도 데코레이터를 반환한다.

    Args:
        config: 애플리케이션 설정

    Returns:
        설정값이 적용된 데코레이터
    """
    max_retries = getattr(config, "retry_max", _DEFAULT_MAX_RETRIES)
    delay = getattr(config, "retry_delay", _DEFAULT_DELAY)
    exponential_backoff = getattr(
        config, "retry_exponential_backoff", False
    )
    return make_retry_decorator(
        max_retries=max_retries,
        delay=delay,
        exponential_backoff=exponential_backoff,
    )
