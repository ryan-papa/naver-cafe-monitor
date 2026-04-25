"""FastAPI 메인 애플리케이션.

실행: uvicorn api.src.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Generator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# shared + batch 모듈 import
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "batch"))

from shared.database import get_connection
from shared.post_repository import PostRepository
from shared.user_repository import UserRow

from api.src.auth.csrf import verify_csrf
from api.src.auth.dependencies import current_admin
from api.src.auth.google_oauth import router as google_oauth_router
from api.src.auth.router import router as auth_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Naver Cafe Monitor API", version="0.1.0")
app.include_router(auth_router)
app.include_router(google_oauth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "http://localhost:3000",
        "http://eepp.shop",
        "https://eepp.shop",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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
    _user: UserRow = Depends(current_admin),
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
def get_post(
    record_id: int,
    repo: PostRepository = Depends(get_repo),
    _user: UserRow = Depends(current_admin),
):
    """게시글 단건 상세 조회 — 카카오톡 재구성 메시지 + 원본 URL 포함."""
    from shared.kakao_format import reconstruct_kakao_messages

    row = repo.find_by_id(record_id)

    if not row:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")

    for key in ("reg_ts", "upd_ts", "post_date"):
        if key in row and row[key] is not None:
            row[key] = str(row[key])

    row["kakao_messages"] = reconstruct_kakao_messages(
        board_id=row.get("board_id", ""),
        title=row.get("title"),
        summary=row.get("summary"),
    )
    row["post_url"] = f"https://m.cafe.naver.com/sewhakinder/{row.get('post_id', '')}"

    return row


def _get_kakao_messenger():
    """KakaoMessenger 인스턴스를 생성한다."""
    from src.messaging.kakao_auth import KakaoAuth
    from src.messaging.kakao import KakaoMessenger

    client_id = os.environ.get("KAKAO_CLIENT_ID", "")
    client_secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="카카오 인증 정보가 설정되지 않았습니다")

    auth = KakaoAuth(client_id=client_id, client_secret=client_secret)
    return KakaoMessenger(auth=auth)


@app.post(
    "/api/posts/{record_id}/resend",
    dependencies=[Depends(verify_csrf)],
)
def resend_post(
    record_id: int,
    repo: PostRepository = Depends(get_repo),
    _user: UserRow = Depends(current_admin),
):
    """게시글 카카오톡 알림을 재발송한다."""
    row = repo.find_by_id(record_id)

    if not row:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다")

    if row.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail="SUCCESS 상태의 게시글만 재발송할 수 있습니다")

    summary = row.get("summary")
    if not summary or not summary.strip():
        raise HTTPException(status_code=400, detail="발송할 내용(summary)이 없습니다")

    title = row.get("title", "")
    board_id = row.get("board_id", "")
    post_id = row.get("post_id", 0)
    post_url = f"https://m.cafe.naver.com/sewhakinder/{post_id}"

    messenger = _get_kakao_messenger()

    if board_id == "menus/6":
        messenger.send_notice_summary(title=title, summary=summary, post_url=post_url)
    else:
        messenger._send_chunked(
            f"[재발송] {title}\n\n{summary.strip()}",
            link_url=post_url,
            button_label="카페에서 원문 보기",
        )

    logger.info("재발송 완료: id=%d board=%s post=%d", record_id, board_id, post_id)
    return {"status": "ok", "message": "카카오톡 발송 완료"}
