"""FastAPI 메인 애플리케이션.

실행: uvicorn api.src.main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

# shared 모듈 import
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from shared.database import get_connection
from shared.post_repository import PostRepository

app = FastAPI(title="Naver Cafe Monitor API", version="0.1.0")


def _get_repo() -> PostRepository:
    conn = get_connection()
    return PostRepository(conn)


@app.get("/api/posts")
def list_posts(
    board_id: Optional[str] = Query(None, description="게시판 필터 (menus/6, menus/13)"),
    status: Optional[str] = Query(None, description="상태 필터 (SUCCESS, FAIL)"),
    sort_by: str = Query("reg_ts", description="정렬 기준 (reg_ts, post_date, post_id)"),
    sort_order: str = Query("DESC", description="정렬 방향 (ASC, DESC)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """게시글 처리 이력 목록 조회."""
    repo = _get_repo()
    try:
        rows, total = repo.find_all(
            board_id=board_id,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=limit,
        )
    finally:
        repo._conn.close()

    # datetime 직렬화
    for row in rows:
        for key in ("reg_ts", "upd_ts", "post_date"):
            if key in row and row[key] is not None:
                row[key] = str(row[key])

    return {"items": rows, "total": total, "offset": offset, "limit": limit}


@app.get("/api/posts/{record_id}")
def get_post(record_id: int):
    """게시글 단건 상세 조회."""
    repo = _get_repo()
    try:
        row = repo.find_by_id(record_id)
    finally:
        repo._conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")

    for key in ("reg_ts", "upd_ts", "post_date"):
        if key in row and row[key] is not None:
            row[key] = str(row[key])

    return row
