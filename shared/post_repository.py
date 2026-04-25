"""게시글 처리 이력 DB 저장소.

posts 테이블에 대한 CRUD를 제공한다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pymysql.connections import Connection

logger = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO posts (board_id, post_id, title, summary, image_count, post_date, status)
VALUES (%(board_id)s, %(post_id)s, %(title)s, %(summary)s, %(image_count)s, %(post_date)s, %(status)s)
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    summary = VALUES(summary),
    image_count = VALUES(image_count),
    post_date = VALUES(post_date),
    status = VALUES(status)
"""

_MAX_POST_ID_SQL = """
SELECT MAX(post_id) AS max_id FROM posts WHERE board_id = %s
"""


class PostRepository:
    """posts 테이블 저장소."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def save(
        self,
        board_id: str,
        post_id: int,
        title: str = "",
        summary: str | None = None,
        image_count: int = 0,
        post_date: datetime | None = None,
        status: str = "SUCCESS",
    ) -> None:
        """게시글 처리 결과를 저장한다. 중복 시 업데이트."""
        with self._conn.cursor() as cur:
            cur.execute(_INSERT_SQL, {
                "board_id": board_id,
                "post_id": post_id,
                "title": title,
                "summary": summary,
                "image_count": image_count,
                "post_date": post_date,
                "status": status,
            })
        self._conn.commit()
        logger.info("posts 저장: board=%s post=%d status=%s", board_id, post_id, status)

    def get_last_seen_id(self, board_id: str) -> int:
        """board_id별 최신 처리 post_id를 반환한다. 없으면 0."""
        with self._conn.cursor() as cur:
            cur.execute(_MAX_POST_ID_SQL, (board_id,))
            row = cur.fetchone()
        if row and row.get("max_id") is not None:
            return int(row["max_id"])
        return 0

    def find_all(
        self,
        board_id: str | None = None,
        status: str | None = None,
        sort_by: str = "reg_ts",
        sort_order: str = "DESC",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """게시글 목록을 조회한다. (목록, 전체 건수) 반환."""
        where_clauses = []
        params: list[Any] = []

        if board_id:
            where_clauses.append("board_id = %s")
            params.append(board_id)
        if status:
            where_clauses.append("status = %s")
            params.append(status)

        where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        allowed_sort = {"reg_ts", "post_date", "post_id"}
        if sort_by not in allowed_sort:
            sort_by = "reg_ts"
        if sort_order.upper() not in ("ASC", "DESC"):
            sort_order = "DESC"

        with self._conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM posts {where}", params)
            total = cur.fetchone()["cnt"]

            cur.execute(
                f"SELECT * FROM posts {where} ORDER BY {sort_by} {sort_order} LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()

        return rows, total

    def find_by_id(self, record_id: int) -> dict[str, Any] | None:
        """PK로 단건 조회."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM posts WHERE id = %s", (record_id,))
            return cur.fetchone()
