"""Rate limit 버킷 유틸 (TA-05).

PRD 정책:
- IP 5분 10회, 계정 5분 5회 초과 시 → 15분 lock
- `rate_limit_buckets` 테이블 사용: bucket_key PK, count, window_end
- 원자성: SELECT ... FOR UPDATE → INSERT/UPDATE, 트랜잭션으로 묶음
- 버킷 만료 시 해당 윈도우 리셋

호출 측 (login/signup API)이 실패/성공 여부와 무관하게 사전 체크 후 허용.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

IP_WINDOW = timedelta(minutes=5)
IP_LIMIT = 10
ACCOUNT_WINDOW = timedelta(minutes=5)
ACCOUNT_LIMIT = 5
LOCK_DURATION = timedelta(minutes=15)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0


class _ConnectionFactory(Protocol):
    def __call__(self):
        """Returns object usable as `with ... as conn`."""


def _default_cm():
    from shared.database import connect

    return connect()


def ip_key(ip: str) -> str:
    return f"ip:{ip}"


def account_key(user_id: int) -> str:
    return f"user:{user_id}"


def check_and_increment(
    bucket_key: str,
    *,
    limit: int,
    window: timedelta,
    lock_duration: timedelta = LOCK_DURATION,
    now: datetime | None = None,
    connection_factory: _ConnectionFactory | None = None,
) -> RateLimitResult:
    """버킷 count+1 시도. 초과 시 lock_duration 만큼 차단."""
    current = now or datetime.now()
    cm = connection_factory() if connection_factory else _default_cm()
    with cm as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count, window_end FROM rate_limit_buckets "
                "WHERE bucket_key = %s FOR UPDATE",
                (bucket_key,),
            )
            row = cur.fetchone()

            if row is None or row["window_end"] <= current:
                # 신규 또는 윈도우 만료 → 리셋
                new_end = current + window
                cur.execute(
                    "INSERT INTO rate_limit_buckets (bucket_key, count, window_end) "
                    "VALUES (%s, 1, %s) "
                    "ON DUPLICATE KEY UPDATE count = 1, window_end = VALUES(window_end)",
                    (bucket_key, new_end),
                )
                conn.commit()
                return RateLimitResult(allowed=True)

            count = row["count"]
            window_end = row["window_end"]

            if count >= limit:
                # 이미 lock 상태. window_end 가 lock 해제 시점.
                retry = int((window_end - current).total_seconds())
                return RateLimitResult(allowed=False, retry_after_seconds=max(retry, 1))

            new_count = count + 1
            if new_count >= limit:
                # 방금 이 호출로 한도 도달 → lock_duration 으로 window_end 연장
                lock_until = current + lock_duration
                cur.execute(
                    "UPDATE rate_limit_buckets SET count = %s, window_end = %s "
                    "WHERE bucket_key = %s",
                    (new_count, lock_until, bucket_key),
                )
                conn.commit()
                # 이번 요청은 허용하되, 다음 요청부터 차단 (count == limit)
                return RateLimitResult(allowed=True)

            cur.execute(
                "UPDATE rate_limit_buckets SET count = count + 1 WHERE bucket_key = %s",
                (bucket_key,),
            )
        conn.commit()
        return RateLimitResult(allowed=True)


def purge_expired_buckets(
    *,
    now: datetime | None = None,
    connection_factory: _ConnectionFactory | None = None,
) -> int:
    """만료된 버킷 일괄 삭제. cron 에서 주기적으로 호출."""
    current = now or datetime.now()
    cm = connection_factory() if connection_factory else _default_cm()
    with cm as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM rate_limit_buckets WHERE window_end <= %s",
                (current,),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted
