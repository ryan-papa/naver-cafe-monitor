"""Unit tests for shared.rate_limit (TA-05)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from shared import rate_limit as rl


class _FakeCursor:
    def __init__(self, rows_by_sql_prefix: dict[str, dict | None]):
        self._rows = rows_by_sql_prefix
        self.executed: list[tuple[str, tuple]] = []
        self._last_row = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        self.executed.append((sql.strip(), params))
        for prefix, row in self._rows.items():
            if sql.strip().startswith(prefix):
                self._last_row = row
                return
        self._last_row = None

    def fetchone(self):
        return self._last_row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, rows=None):
        self.cursor_obj = _FakeCursor(rows or {})
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def _factory_for(conn: _FakeConn):
    @contextmanager
    def _cm():
        yield conn

    return lambda: _cm()


NOW = datetime(2026, 4, 17, 20, 0, 0)


def test_new_bucket_inserts_count_one():
    conn = _FakeConn(rows={"SELECT count": None})
    r = rl.check_and_increment(
        "ip:1.2.3.4",
        limit=10,
        window=timedelta(minutes=5),
        now=NOW,
        connection_factory=_factory_for(conn),
    )
    assert r.allowed and r.retry_after_seconds == 0
    # INSERT 호출 확인
    assert any("INSERT INTO rate_limit_buckets" in s for s, _ in conn.cursor_obj.executed)
    assert conn.commits == 1


def test_expired_window_is_reset():
    conn = _FakeConn(
        rows={
            "SELECT count": {"count": 9, "window_end": NOW - timedelta(seconds=1)},
        }
    )
    r = rl.check_and_increment(
        "ip:1.2.3.4",
        limit=10,
        window=timedelta(minutes=5),
        now=NOW,
        connection_factory=_factory_for(conn),
    )
    assert r.allowed
    # 리셋 → INSERT ON DUPLICATE
    assert any("INSERT INTO rate_limit_buckets" in s for s, _ in conn.cursor_obj.executed)


def test_under_limit_increments():
    conn = _FakeConn(
        rows={"SELECT count": {"count": 3, "window_end": NOW + timedelta(minutes=4)}}
    )
    r = rl.check_and_increment(
        "ip:1.2.3.4",
        limit=10,
        window=timedelta(minutes=5),
        now=NOW,
        connection_factory=_factory_for(conn),
    )
    assert r.allowed
    update_sqls = [s for s, _ in conn.cursor_obj.executed if s.startswith("UPDATE")]
    assert any("count = count + 1" in s for s in update_sqls)


def test_last_allowed_call_extends_lock():
    """count 가 (limit-1) 이고 이번 호출로 limit 에 도달하는 경우: 허용하되 lock_until 까지 연장."""
    conn = _FakeConn(
        rows={"SELECT count": {"count": 9, "window_end": NOW + timedelta(minutes=4)}}
    )
    r = rl.check_and_increment(
        "ip:1.2.3.4",
        limit=10,
        window=timedelta(minutes=5),
        lock_duration=timedelta(minutes=15),
        now=NOW,
        connection_factory=_factory_for(conn),
    )
    assert r.allowed  # 마지막 허용
    # UPDATE 에 window_end 재설정 파라미터 포함
    updates = [
        (s, p) for s, p in conn.cursor_obj.executed if s.startswith("UPDATE rate_limit_buckets SET count = %s")
    ]
    assert updates, "lock-extending UPDATE expected"
    _, params = updates[0]
    assert params[0] == 10  # new_count
    lock_until: datetime = params[1]
    assert lock_until == NOW + timedelta(minutes=15)


def test_over_limit_rejects_with_retry_after():
    window_end = NOW + timedelta(minutes=10)
    conn = _FakeConn(rows={"SELECT count": {"count": 10, "window_end": window_end}})
    r = rl.check_and_increment(
        "ip:1.2.3.4",
        limit=10,
        window=timedelta(minutes=5),
        now=NOW,
        connection_factory=_factory_for(conn),
    )
    assert not r.allowed
    assert r.retry_after_seconds == int((window_end - NOW).total_seconds())


def test_key_helpers():
    assert rl.ip_key("1.2.3.4") == "ip:1.2.3.4"
    assert rl.account_key(42) == "user:42"


def test_purge_expired_buckets_runs_delete():
    conn = _FakeConn()
    conn.cursor_obj.rowcount = 3
    deleted = rl.purge_expired_buckets(
        now=NOW,
        connection_factory=_factory_for(conn),
    )
    assert deleted == 3
    assert any("DELETE FROM rate_limit_buckets" in s for s, _ in conn.cursor_obj.executed)
    assert conn.commits == 1
