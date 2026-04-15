#!/usr/bin/env python3
"""last_seen.json → DB 마이그레이션 스크립트.

기존 last_seen.json의 board_id/last_post_id 데이터를 posts 테이블에 시드로 삽입하고,
성공 시 last_seen.json 파일을 삭제한다.

사용법: python db/migrate_last_seen.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# repo root를 path에 추가
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from shared.database import connect

logger = logging.getLogger(__name__)

_LAST_SEEN_PATH = _REPO_ROOT / "batch" / "data" / "last_seen.json"

_INSERT_SQL = """
INSERT IGNORE INTO posts (board_id, post_id, title, status)
VALUES (%s, %s, '[마이그레이션] last_seen 시드', 'SUCCESS')
"""


def migrate() -> None:
    """last_seen.json → DB 마이그레이션."""
    if not _LAST_SEEN_PATH.exists():
        logger.info("last_seen.json 없음 — 마이그레이션 불필요")
        return

    text = _LAST_SEEN_PATH.read_text(encoding="utf-8")
    data = json.loads(text)

    if not data:
        logger.info("last_seen.json 비어있음 — 마이그레이션 불필요")
        return

    logger.info("마이그레이션 대상: %s", data)

    with connect() as conn:
        cur = conn.cursor()
        for board_id, post_id in data.items():
            cur.execute(_INSERT_SQL, (board_id, int(post_id)))
            logger.info("  %s → post_id=%s 삽입", board_id, post_id)

    # 성공 시 파일 삭제
    _LAST_SEEN_PATH.unlink()
    logger.info("last_seen.json 삭제 완료 — 마이그레이션 성공")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        migrate()
    except Exception as e:
        logger.error("마이그레이션 실패: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
