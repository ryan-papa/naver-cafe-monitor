"""새 게시물 감지 모듈.

마지막으로 확인한 게시물 ID를 파일에 저장·복원하여
다음 실행 시 새로 올라온 게시물만 필터링한다.

최초 실행 시에는 현재 최신 ID만 저장하고 알림을 스킵하여 스팸을 방지한다.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.crawler.parser import PostSummary

logger = logging.getLogger(__name__)

_DEFAULT_LAST_SEEN_PATH = Path("data/last_seen.json")


# ---------------------------------------------------------------------------
# 파일 I/O 추상화 — 테스트에서 mock 교체 가능
# ---------------------------------------------------------------------------

@runtime_checkable
class LastSeenStore(Protocol):
    """last_seen 데이터의 읽기/쓰기 인터페이스."""

    def load(self) -> dict[str, str]:
        """저장된 board_id → last_post_id 매핑을 반환한다."""
        ...

    def save(self, data: dict[str, str]) -> None:
        """board_id → last_post_id 매핑을 영구 저장한다."""
        ...


class JsonFileStore:
    """JSON 파일 기반 LastSeenStore 구현체."""

    def __init__(self, path: Path = _DEFAULT_LAST_SEEN_PATH) -> None:
        self._path = path

    def load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                logger.warning("last_seen.json 형식 오류, 초기화합니다.")
                return {}
            return {str(k): str(v) for k, v in data.items()}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("last_seen.json 읽기 실패: %s", exc)
            return {}

    def save(self, data: dict[str, str]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("last_seen.json 저장 실패: %s", exc)


class DbStore:
    """DB 기반 LastSeenStore 구현체.

    posts 테이블의 board_id별 MAX(post_id)를 last_seen으로 사용한다.
    save()는 no-op (batch.py에서 PostRepository.save()로 개별 기록).
    """

    def __init__(self, conn) -> None:
        self._conn = conn

    def load(self) -> dict[str, str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT board_id, MAX(post_id) AS max_id "
                "FROM posts GROUP BY board_id"
            )
            rows = cur.fetchall()
        result = {}
        for row in rows:
            bid = row["board_id"] if isinstance(row, dict) else row[0]
            mid = row["max_id"] if isinstance(row, dict) else row[1]
            if mid is not None:
                result[str(bid)] = str(mid)
        return result

    def save(self, data: dict[str, str]) -> None:
        """DB 모드에서는 개별 INSERT로 기록하므로 no-op."""
        pass


# ---------------------------------------------------------------------------
# PostTracker
# ---------------------------------------------------------------------------

class PostTracker:
    """게시판별 마지막 게시물 ID를 추적하여 새 게시물만 반환한다.

    Args:
        store: LastSeenStore 구현체. 기본값은 JsonFileStore.
    """

    def __init__(self, store: LastSeenStore | None = None) -> None:
        self._store: LastSeenStore = store or JsonFileStore()
        self._data: dict[str, str] = self._store.load()

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def get_new_posts(
        self,
        board_id: str,
        posts: list[PostSummary],
    ) -> list[PostSummary]:
        """새 게시물만 필터링하여 반환한다.

        최초 실행(board_id 미등록)이면 빈 리스트를 반환하고
        현재 최신 ID를 저장하여 다음 실행부터 정상 감지한다.

        Args:
            board_id: 게시판 식별자 (URL 또는 게시판 고유 ID)
            posts:    크롤러가 수집한 PostSummary 목록 (최신순 정렬 권장)

        Returns:
            last_seen 이후에 등록된 PostSummary 리스트.
            최초 실행이거나 posts가 비어 있으면 빈 리스트.
        """
        if not posts:
            return []

        is_first_run = board_id not in self._data

        if is_first_run:
            # 최초 실행: 현재 최신 ID만 등록하고 알림 스킵
            latest_id = self._max_post_id(posts)
            logger.info(
                "board=%s 최초 실행 — last_seen=%s 저장 (알림 스킵)",
                board_id,
                latest_id,
            )
            self.update_last_seen(board_id, latest_id)
            return []

        last_seen_id = self._data[board_id]
        new_posts = [p for p in posts if self._is_newer(p.post_id, last_seen_id)]

        if new_posts:
            latest_id = self._max_post_id(new_posts)
            logger.info(
                "board=%s 새 게시물 %d건 감지 — last_seen 갱신: %s → %s",
                board_id,
                len(new_posts),
                last_seen_id,
                latest_id,
            )
            self.update_last_seen(board_id, latest_id)

        return new_posts

    def update_last_seen(self, board_id: str, post_id: str) -> None:
        """지정 게시판의 마지막 확인 게시물 ID를 저장한다.

        Args:
            board_id: 게시판 식별자
            post_id:  저장할 게시물 ID
        """
        self._data[board_id] = post_id
        self._store.save(self._data)

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    @staticmethod
    def _is_newer(post_id: str, last_seen_id: str) -> bool:
        """post_id 가 last_seen_id 보다 최신인지 판별한다.

        숫자형 ID면 정수 비교, 아니면 문자열 비교를 사용한다.
        """
        try:
            return int(post_id) > int(last_seen_id)
        except ValueError:
            return post_id > last_seen_id

    @staticmethod
    def _max_post_id(posts: list[PostSummary]) -> str:
        """게시물 목록에서 가장 큰(최신) post_id를 반환한다."""
        def key(p: PostSummary) -> int | str:
            try:
                return int(p.post_id)
            except ValueError:
                return p.post_id

        return max(posts, key=key).post_id
