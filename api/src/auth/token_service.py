"""Access+Refresh 쌍 발급·회전·재사용 감지 로직 (TA-11).

단일 세션 정책 (PRD Q14=2):
- 사용자당 refresh 1개 유지
- 회전 시 이전 token_hash 를 rotated_from 에 기록
- DB 의 current token_hash 와 다른 refresh 가 제시되면 = 재사용 감지
  → 해당 user 의 refresh 삭제 + auth_events.refresh_reuse_detected 기록
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from shared.auth_events import log_auth_event
from shared.auth_tokens import (
    REFRESH_TYPE,
    TokenError,
    generate_csrf_token,
    hash_token,
    issue_access_token,
    issue_refresh_token,
    verify_token,
)
from shared.refresh_token_repository import RefreshTokenRepository


class RefreshReuseDetected(Exception):
    """폐기된 refresh 가 재사용되어 전체 세션 무효화 필요."""


class RefreshInvalid(Exception):
    """만료·서명 실패·유저 불일치 등 일반 실패."""


@dataclass
class IssuedPair:
    access_token: str
    refresh_token: str
    csrf_token: str


def _jwt_secret() -> str:
    s = os.environ.get("AUTH_JWT_SECRET")
    if not s:
        raise RuntimeError("AUTH_JWT_SECRET not configured")
    return s


def issue_pair(
    user_id: int,
    *,
    repo: RefreshTokenRepository,
    previous_hash: str | None = None,
    totp_setup_required: bool = False,
) -> IssuedPair:
    """access + refresh + csrf 발급. refresh 는 DB 에 upsert.

    totp_setup_required=True 면 access/refresh 토큰에 claim 포함 →
    프런트·백엔드가 반쪽 세션으로 인식.
    """
    secret = _jwt_secret()
    extra = {"totp_setup_required": True} if totp_setup_required else None
    access, _ = issue_access_token(user_id, secret, extra)
    refresh, rpayload = issue_refresh_token(user_id, secret, extra)
    repo.upsert(
        user_id=user_id,
        token_hash=hash_token(refresh),
        issued_at=rpayload.issued_at,
        expires_at=rpayload.expires_at,
        rotated_from=previous_hash,
    )
    return IssuedPair(
        access_token=access,
        refresh_token=refresh,
        csrf_token=generate_csrf_token(),
    )


def rotate_refresh(
    presented_refresh: str,
    *,
    repo: RefreshTokenRepository,
    ip: str | None = None,
    user_agent: str | None = None,
) -> IssuedPair:
    """presented refresh → 검증 → 재사용 감지 → 새 쌍 발급."""
    secret = _jwt_secret()
    try:
        payload = verify_token(presented_refresh, secret, REFRESH_TYPE)
    except TokenError as e:
        raise RefreshInvalid(str(e)) from e

    stored = repo.find_by_user(payload.user_id)
    presented_hash = hash_token(presented_refresh)

    if stored is None:
        raise RefreshInvalid("no active session")

    if not secrets.compare_digest(stored.token_hash, presented_hash):
        # 재사용 감지 — 전체 세션 무효화
        repo.delete_by_user(payload.user_id)
        log_auth_event(
            "refresh_reuse_detected",
            user_id=payload.user_id,
            ip=ip,
            user_agent=user_agent,
        )
        raise RefreshReuseDetected("refresh token reuse detected")

    new_pair = issue_pair(
        payload.user_id,
        repo=repo,
        previous_hash=presented_hash,
        totp_setup_required=payload.totp_setup_required,
    )
    log_auth_event(
        "refresh_rotated", user_id=payload.user_id, ip=ip, user_agent=user_agent
    )
    return new_pair
