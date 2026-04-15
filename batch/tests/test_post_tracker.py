"""PostTracker 단위 테스트."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.crawler.parser import PostSummary
from src.crawler.post_tracker import DbStore, PostTracker


# ---------------------------------------------------------------------------
# 픽스처 헬퍼
# ---------------------------------------------------------------------------

def _make_store(initial: dict[str, str] | None = None) -> MagicMock:
    """LastSeenStore 프로토콜을 구현하는 mock 반환."""
    store = MagicMock()
    store.load.return_value = dict(initial) if initial else {}
    store.save = MagicMock()
    return store


def _post(post_id: str, title: str = "제목") -> PostSummary:
    return PostSummary(
        post_id=post_id,
        title=title,
        url=f"https://cafe.naver.com/test/{post_id}",
        board_type="자유게시판",
        written_at=datetime(2026, 1, 1),
    )


# ---------------------------------------------------------------------------
# 최초 실행
# ---------------------------------------------------------------------------

class TestFirstRun:
    def test_returns_empty_on_first_run(self):
        """최초 실행 시 빈 리스트를 반환해야 한다."""
        store = _make_store()
        tracker = PostTracker(store=store)
        posts = [_post("100"), _post("101"), _post("102")]

        result = tracker.get_new_posts("board-A", posts)

        assert result == []

    def test_saves_latest_id_on_first_run(self):
        """최초 실행 시 가장 큰 post_id가 저장되어야 한다."""
        store = _make_store()
        tracker = PostTracker(store=store)
        posts = [_post("100"), _post("102"), _post("101")]

        tracker.get_new_posts("board-A", posts)

        saved: dict = store.save.call_args[0][0]
        assert saved["board-A"] == "102"

    def test_second_run_detects_new_posts(self):
        """두 번째 실행 시 최초 최신 ID 이후 게시물이 감지되어야 한다."""
        store = _make_store({"board-A": "102"})
        tracker = PostTracker(store=store)
        posts = [_post("100"), _post("101"), _post("102"), _post("103"), _post("104")]

        result = tracker.get_new_posts("board-A", posts)

        assert [p.post_id for p in result] == ["103", "104"]


# ---------------------------------------------------------------------------
# 새 게시물 필터링
# ---------------------------------------------------------------------------

class TestGetNewPosts:
    def test_filters_only_newer_posts(self):
        store = _make_store({"board-B": "200"})
        tracker = PostTracker(store=store)
        posts = [_post("199"), _post("200"), _post("201"), _post("202")]

        result = tracker.get_new_posts("board-B", posts)

        ids = [p.post_id for p in result]
        assert "199" not in ids
        assert "200" not in ids
        assert "201" in ids
        assert "202" in ids

    def test_no_new_posts_returns_empty(self):
        store = _make_store({"board-B": "300"})
        tracker = PostTracker(store=store)
        posts = [_post("298"), _post("299"), _post("300")]

        result = tracker.get_new_posts("board-B", posts)

        assert result == []

    def test_no_new_posts_does_not_update_store(self):
        """새 게시물이 없으면 store.save가 호출되지 않아야 한다."""
        store = _make_store({"board-B": "300"})
        tracker = PostTracker(store=store)
        posts = [_post("298"), _post("299"), _post("300")]

        tracker.get_new_posts("board-B", posts)

        store.save.assert_not_called()

    def test_updates_last_seen_to_max_new_post(self):
        """새 게시물 감지 후 last_seen이 가장 큰 ID로 갱신되어야 한다."""
        store = _make_store({"board-C": "50"})
        tracker = PostTracker(store=store)
        posts = [_post("51"), _post("53"), _post("52")]

        tracker.get_new_posts("board-C", posts)

        saved: dict = store.save.call_args[0][0]
        assert saved["board-C"] == "53"

    def test_multiple_boards_are_independent(self):
        """서로 다른 게시판의 last_seen은 독립적으로 관리된다."""
        store = _make_store({"board-X": "10", "board-Y": "20"})
        tracker = PostTracker(store=store)

        new_x = tracker.get_new_posts("board-X", [_post("10"), _post("11")])
        new_y = tracker.get_new_posts("board-Y", [_post("19"), _post("20")])

        assert [p.post_id for p in new_x] == ["11"]
        assert new_y == []


# ---------------------------------------------------------------------------
# 빈 게시물 목록
# ---------------------------------------------------------------------------

class TestEmptyPosts:
    def test_empty_list_returns_empty(self):
        store = _make_store({"board-A": "100"})
        tracker = PostTracker(store=store)

        result = tracker.get_new_posts("board-A", [])

        assert result == []

    def test_empty_list_does_not_save(self):
        store = _make_store({"board-A": "100"})
        tracker = PostTracker(store=store)

        tracker.get_new_posts("board-A", [])

        store.save.assert_not_called()

    def test_empty_list_first_run_does_not_save(self):
        """최초 실행이더라도 빈 목록이면 저장하지 않아야 한다."""
        store = _make_store()
        tracker = PostTracker(store=store)

        tracker.get_new_posts("board-new", [])

        store.save.assert_not_called()


# ---------------------------------------------------------------------------
# update_last_seen
# ---------------------------------------------------------------------------

class TestUpdateLastSeen:
    def test_update_persists_to_store(self):
        store = _make_store()
        tracker = PostTracker(store=store)

        tracker.update_last_seen("board-Z", "999")

        saved: dict = store.save.call_args[0][0]
        assert saved["board-Z"] == "999"

    def test_update_overwrites_existing(self):
        store = _make_store({"board-Z": "100"})
        tracker = PostTracker(store=store)

        tracker.update_last_seen("board-Z", "200")

        saved: dict = store.save.call_args[0][0]
        assert saved["board-Z"] == "200"


# ---------------------------------------------------------------------------
# last_seen 저장·복원
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_load_called_on_init(self):
        store = _make_store({"board-A": "42"})
        tracker = PostTracker(store=store)

        store.load.assert_called_once()
        # 복원된 데이터 확인 — 두 번째 실행처럼 동작해야 함
        result = tracker.get_new_posts("board-A", [_post("42"), _post("43")])
        assert [p.post_id for p in result] == ["43"]

    def test_save_called_after_update(self):
        store = _make_store()
        tracker = PostTracker(store=store)

        tracker.update_last_seen("board-Q", "77")

        store.save.assert_called_once()

    def test_non_numeric_post_ids_use_string_comparison(self):
        """숫자가 아닌 post_id는 문자열 비교로 처리된다."""
        store = _make_store({"board-S": "abc"})
        tracker = PostTracker(store=store)
        posts = [_post("aaa"), _post("abc"), _post("abd")]

        result = tracker.get_new_posts("board-S", posts)

        assert [p.post_id for p in result] == ["abd"]


# ---------------------------------------------------------------------------
# DbStore
# ---------------------------------------------------------------------------

class TestDbStore:
    def _make_db_conn(self, rows):
        """mock DB 연결 반환."""
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        return conn

    def test_load_returns_board_max_ids(self):
        conn = self._make_db_conn([
            {"board_id": "menus/6", "max_id": 100},
            {"board_id": "menus/13", "max_id": 200},
        ])
        store = DbStore(conn)

        result = store.load()

        assert result == {"menus/6": "100", "menus/13": "200"}

    def test_load_empty_table(self):
        conn = self._make_db_conn([])
        store = DbStore(conn)

        result = store.load()

        assert result == {}

    def test_save_is_noop(self):
        conn = MagicMock()
        store = DbStore(conn)

        store.save({"menus/6": "100"})

        conn.cursor.assert_not_called()

    def test_works_with_post_tracker(self):
        """PostTracker와 DbStore 통합 테스트."""
        conn = self._make_db_conn([
            {"board_id": "menus/13", "max_id": 50},
        ])
        store = DbStore(conn)
        tracker = PostTracker(store=store)

        result = tracker.get_new_posts("menus/13", [_post("49"), _post("50"), _post("51")])

        assert [p.post_id for p in result] == ["51"]
