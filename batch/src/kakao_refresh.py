"""카카오 토큰 주기 선제 갱신 엔트리.

OS 레벨 cron(3시간 주기)에서 호출되어 `KakaoAuth.refresh()` 를 수행한다.
`python -m src.kakao_refresh` 형태로 실행 (batch/ 를 cwd 로 사용).

실패 시 ERROR 로그만 기록하고 종료코드 1. 다음 cron 주기에서 자연 재시도.
배치의 401 자동 갱신 경로는 독립적으로 유지되므로 refresh 실패가 배치 운영에 영향 없음.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import load_config
from src.messaging.kakao_auth import KakaoAuth


_BATCH_ROOT = Path(__file__).resolve().parent.parent
_LOG_PATH = _BATCH_ROOT / "logs" / "kakao_refresh.log"


def _setup_logger() -> logging.Logger:
    """전용 로그 파일에 기록하는 루트 로거를 구성한다."""
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # 이미 구성돼 있으면 중복 핸들러 방지
    for h in list(logger.handlers):
        logger.removeHandler(h)

    handler = RotatingFileHandler(
        _LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )
    logger.addHandler(handler)
    return logger


def main() -> int:
    logger = _setup_logger()
    try:
        config = load_config()
    except Exception as e:
        logger.error("설정 로딩 실패: %s", e)
        return 1

    try:
        auth = KakaoAuth(
            client_id=config.kakao_client_id,
            client_secret=config.kakao_client_secret,
        )
    except Exception as e:
        logger.error("KakaoAuth 초기화 실패: %s", e)
        return 1

    try:
        auth.refresh()
    except Exception as e:
        # KakaoAuth.refresh 내부에서 이미 상세 로그(마스킹) 기록됨
        logger.error("카카오 토큰 갱신 실패 (요약): %s", type(e).__name__)
        return 1

    days_left = auth.check_refresh_token_expiry()
    expires_at = auth._token_data.get("refresh_token_expires_at")
    expires_str = (
        datetime.fromtimestamp(expires_at).isoformat() if expires_at else "unknown"
    )
    logger.info(
        "카카오 토큰 선제 갱신 성공 — refresh_token 만료 %s (%s일 남음)",
        expires_str,
        days_left,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
