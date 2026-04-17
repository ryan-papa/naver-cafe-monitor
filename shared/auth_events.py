"""auth_events 기록 유틸 (TA-07).

PRD 기능: signup/login/TOTP/refresh rotation/재사용 감지/logout/locked 이벤트를
`auth_events` 테이블에 기록한다.

민감 정보(비밀번호·토큰 값·이메일 원문)는 절대 기록하지 않는다.
저장 대상: user_id, event_type, ip, user_agent(앞 255자).
"""
from __future__ import annotations

from typing import Literal, Protocol

AuthEventType = Literal[
    "signup",
    "login_ok",
    "login_fail",
    "totp_ok",
    "totp_fail",
    "refresh_rotated",
    "refresh_reuse_detected",
    "logout",
    "locked",
]

_UA_MAX = 255


class _ConnectionFactory(Protocol):
    def __call__(self):
        """Returns an object usable as `with ... as conn`."""


def _default_cm():
    # Lazy import 로 모듈 로드 시 DB 의존 제거.
    from shared.database import connect

    return connect()


def log_auth_event(
    event_type: AuthEventType,
    *,
    user_id: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    connection_factory: _ConnectionFactory | None = None,
) -> None:
    """auth_events 테이블에 1행 insert 후 커밋.

    Args:
        event_type: PRD 정의 9종 (DB enum 으로 강제).
        user_id: 가입 실패/IP 잠금 등 미식별 케이스는 None.
        ip: IPv4/IPv6, 최대 45자.
        user_agent: 앞 255자로 자름.
        connection_factory: 테스트 주입용. 호출 시 context-manager 를 반환해야 함.
    """
    ua = user_agent[:_UA_MAX] if user_agent else None
    cm = connection_factory() if connection_factory else _default_cm()
    with cm as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth_events (user_id, event_type, ip, user_agent) "
                "VALUES (%s, %s, %s, %s)",
                (user_id, event_type, ip, ua),
            )
        conn.commit()
