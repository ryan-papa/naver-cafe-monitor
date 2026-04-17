"""카카오톡 전송 텍스트 재구성.

`api.src.main.resend_post` 및 `batch.src.messaging.kakao.send_notice_summary`와
동일한 포맷으로 사전 미리보기를 생성한다.
"""

from __future__ import annotations


def reconstruct_kakao_messages(
    board_id: str,
    title: str | None,
    summary: str | None,
) -> list[str]:
    """재발송 시 실제 전송될 메시지 블록을 재구성한다.

    - `menus/6` (공지): `send_notice_summary` 포맷. `[일정 정리]` 구분자로 2블록 분할.
    - 그 외: `[재발송] {title}\\n\\n{summary}` 단일 블록.

    Args:
        board_id: 게시판 식별자.
        title: 게시글 제목.
        summary: 요약 본문. 비어 있으면 빈 리스트 반환.

    Returns:
        전송 텍스트 블록 리스트. `summary`가 비어 있으면 `[]`.
    """
    if not summary or not summary.strip():
        return []

    t = title or ""

    if board_id == "menus/6":
        parts = summary.split("[일정 정리]")
        content = parts[0].strip()
        schedule = parts[1].strip() if len(parts) > 1 else ""

        blocks: list[str] = []
        if content:
            blocks.append(f"[세화유치원 공지]\n\n📋 {t}\n\n{content}")
        if schedule:
            blocks.append(f"[세화유치원 일정]\n\n📅 {t}\n\n{schedule}")
        return blocks

    return [f"[재발송] {t}\n\n{summary.strip()}"]
