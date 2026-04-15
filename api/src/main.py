"""FastAPI 메인 애플리케이션.

실행: uvicorn api.src.main:app --reload --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

# shared 모듈 import
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from shared.database import get_connection
from shared.post_repository import PostRepository

app = FastAPI(title="Naver Cafe Monitor API", version="0.1.0")


def get_repo() -> Generator[PostRepository, None, None]:
    """FastAPI dependency — 요청별 DB 연결 관리."""
    conn = get_connection()
    try:
        yield PostRepository(conn)
    finally:
        conn.close()


@app.get("/api/posts")
def list_posts(
    repo: PostRepository = Depends(get_repo),
    board_id: Optional[str] = Query(None, description="게시판 필터 (menus/6, menus/13)"),
    status: Optional[str] = Query(None, description="상태 필터 (SUCCESS, FAIL)"),
    sort_by: str = Query("reg_ts", description="정렬 기준 (reg_ts, post_date, post_id)"),
    sort_order: str = Query("DESC", description="정렬 방향 (ASC, DESC)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """게시글 처리 이력 목록 조회."""
    rows, total = repo.find_all(
        board_id=board_id,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )

    # datetime 직렬화
    for row in rows:
        for key in ("reg_ts", "upd_ts", "post_date"):
            if key in row and row[key] is not None:
                row[key] = str(row[key])

    return {"items": rows, "total": total, "offset": offset, "limit": limit}


@app.get("/api/posts/{record_id}")
def get_post(record_id: int, repo: PostRepository = Depends(get_repo)):
    """게시글 단건 상세 조회."""
    row = repo.find_by_id(record_id)

    if not row:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")

    for key in ("reg_ts", "upd_ts", "post_date"):
        if key in row and row[key] is not None:
            row[key] = str(row[key])

    return row
