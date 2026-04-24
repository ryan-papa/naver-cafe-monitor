"""`KakaoAuth` 파일 락 + 재로드·머지 프로세스간 테스트.

fcntl.flock 은 스레드로는 재현 불가하므로 multiprocessing.Process 로 독립 프로세스 2개를 실행한다.
시나리오: P1 = refresh (access_token + refresh_token 회전), P2 = mark_alert_sent (last_alert_date 기록).
최종 파일에 두 변경 모두 보존되어야 함.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.messaging.kakao_auth import KakaoAuth


def _worker_refresh(token_path: str, delay_after_post_sec: float) -> None:
    """락 획득 후 인위적 지연을 두고 토큰 회전을 시뮬레이션한다."""
    with patch("src.messaging.kakao_auth.requests.post") as mock_post:
        # 일부러 약간 오래 걸리게: 요청 반환 후 sleep
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "access_token": "new_access",
                "expires_in": 21599,
                "refresh_token": "rotated_refresh",
                "refresh_token_expires_in": 60 * 86400,
            }),
            text='{"access_token":"new_access"}',
        )

        auth = KakaoAuth(
            client_id="cid",
            client_secret="csec",
            token_path=Path(token_path),
        )
        # 시간 지연: 락 유지 시간을 늘려 P2가 대기하도록 유도
        original_post = mock_post.return_value

        def delayed(*args, **kwargs):
            time.sleep(delay_after_post_sec)
            return original_post

        mock_post.side_effect = delayed
        auth.refresh()


def _worker_mark_alert(token_path: str, start_delay_sec: float) -> None:
    """P1이 락을 먼저 잡도록 잠시 대기 후 mark_alert_sent 실행."""
    time.sleep(start_delay_sec)
    auth = KakaoAuth(
        client_id="cid",
        client_secret="csec",
        token_path=Path(token_path),
    )
    # refresh_token_expires_at을 알림 조건과 상관없이 강제로 호출
    auth.mark_alert_sent()


@pytest.fixture
def token_file(tmp_path):
    path = tmp_path / "kakao_token.json"
    path.write_text(json.dumps({
        "access_token": "old_access",
        "refresh_token": "old_refresh",
        "expires_at": int(time.time()) + 3600,
        "refresh_token_expires_at": int(time.time()) + 86400 * 20,
        "last_alert_date": "",
    }))
    return path


def test_cross_process_refresh_and_mark_alert_preserves_both(token_file):
    """두 프로세스 교차 실행 후 refresh_token 회전 + last_alert_date 모두 보존."""
    ctx = mp.get_context("fork")

    p1 = ctx.Process(target=_worker_refresh, args=(str(token_file), 0.5))
    p2 = ctx.Process(target=_worker_mark_alert, args=(str(token_file), 0.1))

    p1.start()
    p2.start()
    p1.join(timeout=10)
    p2.join(timeout=10)

    assert p1.exitcode == 0, "refresh process failed"
    assert p2.exitcode == 0, "mark_alert process failed"

    saved = json.loads(token_file.read_text())
    assert saved["refresh_token"] == "rotated_refresh", "refresh_token 회전 유실"
    assert saved["access_token"] == "new_access"
    assert saved["last_alert_date"] != "", "last_alert_date 유실"


def test_volatile_whitelist_enforced(token_file):
    auth = KakaoAuth(client_id="cid", client_secret="csec", token_path=token_file)
    with pytest.raises(ValueError, match="화이트리스트"):
        auth._commit_changes({"unknown_field": "x"})
